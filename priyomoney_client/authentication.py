import logging
import re

import jwt
import json
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.utils import timezone
from requests import RequestException, HTTPError
from rest_framework import authentication, status
from rest_framework import exceptions
from rest_framework.exceptions import AuthenticationFailed

from auth_client import PriyoClient
from common.email import EmailSender
from core.enums import ServiceList, ProfileApprovalStatus, SubServiceList
from core.models import PriyoMoneyUser, TrustedDevice, UserMetaData
from custom_api_exceptions import UnAuthorized, NonInternalUser, UnrecognizedDevice, SessionExpired
from error_handling.custom_exception import CustomErrorWithCode
from error_handling.error_list import CUSTOM_ERROR_LIST
from common.helpers import get_geo_location
from firebase_admin import app_check

device_safe_urls = [
    '/otp/generate/',
    '/otp/verify/',
    '/masked-mobile-email/'
]

log = logging.getLogger(__name__)


def is_path_device_safe(path):
    return path in device_safe_urls


def is_path_for_invitation_token_use(path):
    return path.startswith('/use-invitation/')


def form_user_creation_data(user):
    if not user.get('email'):
        raise CUSTOM_ERROR_LIST.AUTH_INVALID_USER_DATA_4027("Email is required")

    user_data = {
        'email_address': user['email'],
        'is_email_verified': user.get('is_email_verified', False),
        'first_name': "",
        'middle_name': "",
        'last_name': ""
    }

    if user.get('name') is not None:
        split_names = user.get('name').split(" ")
        name_len = len(split_names)

        if name_len == 0:
            pass
        elif name_len == 1:
            user_data['last_name'] = split_names[0]
        elif name_len == 2:
            user_data['first_name'] = split_names[0]
            user_data['last_name'] = split_names[1]
        elif name_len >= 3:
            user_data['first_name'] = split_names[0]
            user_data['middle_name'] = split_names[1]
            user_data['last_name'] = " ".join(split_names[2:])
    return user_data


def get_or_create_user(user):
    user_data = form_user_creation_data(user)
    priyo_money_user, is_created = PriyoMoneyUser.objects.get_or_create(one_auth_uuid=user['uid'], defaults=user_data)
    return priyo_money_user, is_created


def get_basic_profile_from_profile(profile):
    basic_profile = profile.get('profile', {})
    if not basic_profile:
        basic_profile = {}
    basic_profile.update({
        'id': profile.get('id'),
        'uid': profile.get('uid'),
        'email': profile.get('email'),
        'is_email_verified': profile.get('is_email_verified'),
        'mobile': profile.get('mobile'),
        'is_mobile_verified': profile.get('is_mobile_verified'),

    })
    return basic_profile


class JWTAuth(authentication.BaseAuthentication):

    @staticmethod
    def get_profile_cache_key(token):
        return settings.PROFILE_CACHE_PREFIX + token

    @staticmethod
    def get_user_details_from_one_auth(token):
        api_client = PriyoClient(api_key=settings.AUTH_API_KEY)
        api_client.add_token(token)
        profile = api_client.get_profile(token)
        if not status.is_success(profile.get('status_code', status.HTTP_401_UNAUTHORIZED)):
            raise AuthenticationFailed(detail='Token not valid')
        return get_basic_profile_from_profile(profile)

    def get_user_details_from_cache(self, token):
        is_cache_exists = True
        cache_token = self.get_profile_cache_key(token)
        cached_details = cache.get(cache_token)
        if cached_details:
            return cached_details, is_cache_exists

        is_cache_exists = False
        details = self.get_user_details_from_one_auth(token)
        cache.set(cache_token, details, timeout=settings.PROFILE_CACHE_TTL)
        return details, is_cache_exists

    def logout_user(self, token):
        try:
            api_client = PriyoClient(api_key=settings.AUTH_API_KEY, raise_on_error_status=True)
            api_client.add_token(token)
            api_client.logout(token)
        except HTTPError as e:
            if e.response.status_code != status.HTTP_401_UNAUTHORIZED:
                log.error(f'Error while logging out user from one auth', exc_info=True)
        except RequestException as e:
            log.error('Error while logging out user from one auth', exc_info=True)

        cache_token = self.get_profile_cache_key(token)
        cache.delete(cache_token)

    @staticmethod
    def retrieve_jwt_token_from_request(request):
        is_strict_security = bool(settings.STRICT_SECURITY)

        PREFIX = 'Bearer '
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        device_fingerprint = request.META.get('HTTP_DEVICE_FINGERPRINT')

        if is_strict_security and device_fingerprint is None:
            raise exceptions.AuthenticationFailed('Device fingerprint missing in the header')

        if auth_header is None:
            raise exceptions.AuthenticationFailed('Authorization header missing')

        if not auth_header.startswith(PREFIX):
            raise exceptions.AuthenticationFailed('Bearer prefix missing in authorization header')

        auth_token = auth_header[len(PREFIX):]
        try:
            decoded_token = jwt.decode(auth_token, options={"verify_signature": False})
            return auth_token, decoded_token
        except jwt.exceptions.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Invalid token')

    @staticmethod
    def validate_device_fingerprint(request, priyo_money_user):
        # no validation for non-onboarded customers
        if priyo_money_user.profile_approval_status == ProfileApprovalStatus.AWAITING_SIGNUP_COMPLETION.name:
            return

        is_strict_security = bool(settings.STRICT_SECURITY)
        device_fingerprint = request.META.get('HTTP_DEVICE_FINGERPRINT')

        if is_strict_security and not is_path_device_safe(request.path):
            if not TrustedDevice.objects.filter(user=priyo_money_user, fingerprint=device_fingerprint).exists():
                raise UnrecognizedDevice('Unknown device signature. Please verify with OTP.')

    @staticmethod
    def validate_internal_verified_user(request, priyo_money_user):
        if priyo_money_user.is_verified_internal_user:
            return

        if not is_path_for_invitation_token_use(request.path):
            raise NonInternalUser("Please verify with Invitation Token")

    @staticmethod
    def has_token_expired(token, current_time):
        created_at = int(token.get('created_at'))
        expired_at = int(token.get('expired_at'))
        actual_expired_at = min(expired_at, created_at + settings.SESSION_EXPIRED_AFTER_LOGIN_SECONDS)
        return not created_at <= current_time < actual_expired_at

    # @staticmethod
    # def is_user_active(token, priyo_money_user, current_time):
    #     created_at = int(token.get('created_at'))
    #     last_active_at = priyo_money_user.last_active_at
    #     last_active_at = last_active_at.timestamp() if last_active_at else created_at
    #     last_active_at = max(last_active_at, created_at)
    #     return created_at <= current_time < last_active_at + settings.SESSION_EXPIRED_AFTER_INACTIVE_SECONDS

    def validate_session_not_expired(self, token, user: PriyoMoneyUser):
        try:
            current_time = timezone.now().timestamp()
            # if self.has_token_expired(token, current_time) or not self.is_user_active(token, user, current_time):
            #     raise CUSTOM_ERROR_LIST.SESSION_EXPIRED_4025
            if self.has_token_expired(token, current_time):
                raise CUSTOM_ERROR_LIST.SESSION_EXPIRED_4025
        except (TypeError, KeyError):
            raise CUSTOM_ERROR_LIST.SESSION_EXPIRED_4025

    def authenticate(self, request, username=None):
        if request.service != ServiceList.CLIENT.value:
            return None
        return self.handle_client_service(request)

    def handle_client_service(self, request):
        token, decoded_token = self.retrieve_jwt_token_from_request(request)

        try:
            user, is_cached_data = self.get_user_details_from_cache(token=token)
            priyo_money_user, is_created = get_or_create_user(user)

            if priyo_money_user.is_terminated:
                raise AuthenticationFailed

            if is_created:
                signup_meta_data = get_geo_location(request)
                email_data = {
                    'ip_address': signup_meta_data.get('ip_addr'),
                    'region_country': signup_meta_data.get('region') + " " + signup_meta_data.get('country'),
                    'http_user_agent': str(request.META.get('HTTP_USER_AGENT'))
                }
                UserMetaData.objects.get_or_create(user=priyo_money_user,
                                                   signup_meta_data=json.dumps(signup_meta_data),
                                                   http_user_agent=str(request.META.get('HTTP_USER_AGENT')))
                email_sender = EmailSender(user=priyo_money_user, kwargs=email_data)
                email_sender.send_user_email(context='welcome_email')
                email_sender.send_admin_email(context='new_user_signup_admin_email', is_official=True)
        except AuthenticationFailed:
            raise CUSTOM_ERROR_LIST.SESSION_EXPIRED_4025
        except CustomErrorWithCode as ex:
            raise UnAuthorized(f'User cannot be mapped due to exception: {ex.message} (Code: {ex.code})')
        except Exception as ex:
            raise UnAuthorized(f'User cannot be mapped due to exception: {ex}')

        try:
            self.validate_session_not_expired(decoded_token, priyo_money_user)
        except SessionExpired:
            self.logout_user(token)
            raise

        if not is_cached_data:
            priyo_money_user.last_active_at = timezone.now()
            priyo_money_user.save(update_fields=['last_active_at'])

        self.validate_device_fingerprint(request, priyo_money_user)
        # self.validate_internal_verified_user(request, priyo_money_user)

        return priyo_money_user, None


class NoAuth(authentication.BaseAuthentication):
    def authenticate(self, request):
        if request.service == ServiceList.CLIENT.value:
            return AnonymousUser(), None
        return None


class PriyoBusinessAuth(authentication.BaseAuthentication):
    def authenticate(self, request):
        if request.service == ServiceList.PRIYO_BUSINESS.value:
            return AnonymousUser, None
        return None


class BDPayAuth(authentication.BaseAuthentication):
    def authenticate(self, request):
        if request.service == ServiceList.BDPAY.value:
            return AnonymousUser, None
        return None
