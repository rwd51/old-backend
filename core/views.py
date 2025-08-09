import logging

from django.conf import settings
from django.db import transaction
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from api_clients.synctera_client import SyncteraClient
from business.enums import BusinessVerificationStatus
from business.models import Business
from common.email import EmailSender
from common.enums import EmailType
from common.models import PromoEmailContent, UserEmailContent
from core.decorators import check_prerequisites
from core.enums import ActionStatus, ServiceList, ProfileApprovalStatus, OnboardingSteps, SubServiceList, ProfileType, \
    PlaidAuthorizationRequestStatus
from core.utility.onboarding_step_handler import OnboardingStepManager
from subscription.helpers import is_user_subscribed_for_onboarding
from subscription.models import Tariff
from utilities.enums import RequestMethod
from core.models import PriyoMoneyUser, PlaidAuthorizationRequest, UserMetaData
from core.permissions import IsAdmin, IsOwner, is_client, IsClient, ReadOnlyAdmin, is_admin
from core.serializers import UserSsnSerializer, PersonVerifySerializer, BDManualKYCSerializer, SyncKYCSerializer, \
    PriyoMoneyUserSerializer, PlaidAuthorizationRequestSerializer, UserFullAccessSerializer
from common.serializers import SendTestEmailSerializer
from core.utility.state_manager import PersonManager

logger = logging.getLogger(__name__)


class APILogFilterSearchChoices(GenericAPIView):
    http_method_names = ['get']
    permission_classes = [IsAdmin]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PriyoMoneyUser.objects.none()
        return self.queryset

    def get(self, request, *args, **kwargs):
        request_method_choices = [req_meth.name for req_meth in RequestMethod]
        response_status_choices = [res_status.name for res_status in ActionStatus]
        server_list = [serv_list.name for serv_list in ServiceList]
        sub_service_list = [sub_serv_list.name for sub_serv_list in SubServiceList]
        combined_choices = {
            "request_method_filter_choices": request_method_choices,
            "response_status_filter_choices": response_status_choices,
            "service_list_filter_choices": server_list,
            "sub_service_list_filter_choices": sub_service_list
        }
        return Response(combined_choices, status.HTTP_200_OK)


class APILogUserSearchChoices(GenericAPIView):
    http_method_names = ['get']
    permission_classes = [IsAdmin]
    queryset = PriyoMoneyUser.objects.all()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PriyoMoneyUser.objects.none()
        return self.queryset

    def get(self, request, *args, **kwargs):
        users_list = []
        fields = ['id', 'first_name', 'middle_name', 'last_name', 'email_address', 'profile']

        for user in PriyoMoneyUser.objects.all().order_by('first_name').values(*fields):
            user_name = ' '.join(name for name in [user['first_name'], user['middle_name'], user['last_name']] if name)
            user_name = user['email_address'] if len(user_name.strip()) == 0 else user_name
            user_name = user_name + ' - ' + str(user['id'])
            user_dict = {
                "label": user_name,
                "value": str(user['id']),
                "profile_id": user['profile']
            }
            users_list.append(user_dict)
        return Response(users_list, status.HTTP_200_OK)


class UserIdentificationView(GenericAPIView):
    http_method_names = ['get', 'post']
    permission_classes = [IsOwner]

    serializer_class = UserSsnSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PriyoMoneyUser.objects.none()
        return self.queryset

    def get(self, request, *args, **kwargs):
        if not self.request.user.synctera_user_id:
            return Response({"ssn": ""}, status=status.HTTP_200_OK)

        synctera_client = SyncteraClient()
        person_response, status_code = synctera_client.get_person(self.request.user.synctera_user_id)
        if not status.is_success(status_code):
            return Response(person_response, status=status.HTTP_400_BAD_REQUEST)

        return Response({"ssn": person_response.get('ssn')}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        person = request.user
        ssn = serializer.validated_data.get('ssn')
        synctera_client = SyncteraClient()
        person_response, status_code = synctera_client.update_person_ssn(person.synctera_user_id, ssn)
        if not status.is_success(status_code):
            return Response(person_response, status=status.HTTP_400_BAD_REQUEST)
        else:
            person.ssn_submitted_to_synctera = True
            person.save(update_fields=['ssn_submitted_to_synctera'])

        if self.request.user.profile_approval_status in ProfileApprovalStatus.get_all_synctera_kyc_status():
            state_manager = PersonManager(self.request.user)
            state_manager.submit_kyc_synctera()

        return Response({"ssn": person_response.get('ssn')}, status=status.HTTP_201_CREATED)


class UserMaskedMobileEmail(GenericAPIView):
    http_method_names = ['get']
    permission_classes = [IsOwner]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PriyoMoneyUser.objects.none()
        return self.queryset

    @staticmethod
    def mask_email(email):
        username, domain = email.split('@')
        masked_username = username[:2] + '*' * (len(username) - 2)
        masked_domain = domain[:2] + '*' * (len(domain) - 2)
        masked_email = masked_username + '@' + masked_domain
        return masked_email

    def get(self, request, *args, **kwargs):
        if self.request.service != ServiceList.CLIENT.value:
            return Response({"user": "Service not CLIENT"})
        user = self.request.user
        response_body = {
            'email': self.mask_email(user.email_address)
        }
        if hasattr(user, 'user_mobile_number'):
            mobile_number = user.user_mobile_number.mobile_number
            masked_number = '*' * 7 + mobile_number[-4:]
            response_body['mobile'] = masked_number
        return Response(response_body, status=status.HTTP_200_OK)


class PersonVerifyView(GenericAPIView):
    http_method_names = ['post']
    permission_classes = [IsOwner]
    serializer_class = PersonVerifySerializer

    @check_prerequisites([is_user_subscribed_for_onboarding])
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        person_id = serializer.validated_data.get('person_id')
        user = PriyoMoneyUser.objects.get(id=person_id)

        person_manager = PersonManager(person=user)

        if request.service == ServiceList.CLIENT.value:
            person_manager.submit_disclosure_acknowledge_synctera()

        person_manager.submit_kyc_synctera(run_document_verification=False)

        return Response({"message": "Your request is under process"}, status=status.HTTP_200_OK)


class SyncKYCView(GenericAPIView):
    http_method_names = ['post']
    permission_classes = [IsAdmin]
    serializer_class = SyncKYCSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        person = serializer.validated_data.get('person')

        from verifications.celery_tasks.helpers import get_user_verification_status
        approval_status = get_user_verification_status(person.synctera_user_id)

        if approval_status:
            is_send_email = False
            try:
                with transaction.atomic(using=settings.MASTER_DB_KEY):
                    user = PriyoMoneyUser.objects.select_for_update().get(id=person.id)
                    previous_approval_status = user.profile_approval_status

                    if previous_approval_status != approval_status:
                        user.profile_approval_status = approval_status
                        user.save(update_fields=['profile_approval_status'])
                        is_send_email = True

                    if approval_status == ProfileApprovalStatus.KYC_ACCEPTED.value:
                        OnboardingStepManager(user).add_step(OnboardingSteps.KYC_ACCEPTANCE.value)

            except Exception as ex:
                is_send_email = False
                logger.error(str(ex), exc_info=True)

            if is_send_email:
                EmailSender(user=user).send_kyc_status_change_email(previous_approval_status, approval_status)

        return Response(PriyoMoneyUserSerializer(instance=user).data, status=status.HTTP_200_OK)


class BDManualKYCView(GenericAPIView):
    http_method_names = ['post']
    permission_classes = [IsAdmin]
    serializer_class = BDManualKYCSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        person = serializer.validated_data.get('person')
        requested_status = serializer.validated_data.get('status')

        person_manager = PersonManager(person=person)
        person_manager.change_state(requested_status)

        return Response(serializer.data, status=status.HTTP_200_OK)


class UserOnboardingFlowView(GenericAPIView):
    http_method_names = ['get']
    permission_classes = [IsOwner | IsAdmin]

    def validate_permission(self, request):
        if is_client(request) and self.kwargs.get('user_id') != request.user.id:
            raise PermissionDenied()

        if PriyoMoneyUser.objects.filter(id=self.kwargs.get('user_id')).count() == 0:
            raise Http404()

    def get(self, request, *args, **kwargs):
        self.validate_permission(request)
        user = PriyoMoneyUser.objects.get(id=self.kwargs.get('user_id'))
        finished_steps = user.onboarding_steps.all()

        response = []
        for step in OnboardingSteps.get_expected_onboarding_flow(user):
            matched_items = [item for item in finished_steps if item.step == step]
            has_finished = bool(matched_items)
            time_taken = matched_items[0].time_taken if has_finished else None
            response.append({
                'step': step,
                'finished': has_finished,
                'time_taken': time_taken
            })

        return Response(response, status=status.HTTP_200_OK)


class SendTestEmailView(GenericAPIView):
    http_method_names = ['post']
    permission_classes = [IsAdmin]
    serializer_class = SendTestEmailSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email_address = serializer.validated_data.get('email_address')
        place_holders = serializer.validated_data.get('place_holders')
        email_type = serializer.validated_data.get('email_type')
        email_data = self.get_place_holders_as_dictionary(place_holders)

        status_code = status.HTTP_400_BAD_REQUEST
        context = serializer.validated_data.get('context')
        is_promotional = True
        is_invest_promo = True if email_type == EmailType.PROMO_INVEST.value else False
        recipient_list = []

        try:
            if email_type == EmailType.PROMOTIONAL.value or email_type == EmailType.PROMO_INVEST.value:
                email_content = PromoEmailContent.objects.get(email_context=context)
                subject, message = email_content.email_subject, email_content.email_message

                user = PriyoMoneyUser.objects.filter(email_address=email_address).first()
                user_full_name = user.get_fullname() if user else "PromoEmail Tester"
                recipient_list.append({'user_full_name': user_full_name, 'email_address': email_address})

                recipient = {'user_full_name': 'PriyoSys Developer', 'email_address': settings.BATCH_MAIL_TESTER_EMAIL}
                recipient_list.append(recipient)
            else:
                email_content = UserEmailContent.objects.get(context=context)
                subject, message = email_content.email_subject, email_content.email_body
                is_promotional = False
        except Exception as ex:
            return Response({"message": f"Email content does not exist in the DB. {ex}"}, status=status_code)

        try:
            email_sender = EmailSender(is_promotional=is_promotional, is_inv_promo=is_invest_promo)

            if email_type == EmailType.PROMOTIONAL.value:
                status_code = email_sender.send_batch_email(subject, message, recipient_list, True)
            else:
                email_subject = subject.format(**email_data)
                email_body = message.format(**email_data)
                status_code = email_sender.send_email(email_subject, email_address, email_body, disable_logger=True)

            if status_code in [status.HTTP_200_OK, status.HTTP_202_ACCEPTED]:
                response_msg = f"Email successfully sent to {email_address}"
            else:
                response_msg = f"Failed to send email to {email_address}"
        except KeyError as ex:
            response_msg = f"KeyError in email body with placeholder {ex}"
        except Exception as ex:
            response_msg = f"Failed to send email to {email_address} with error={ex}"

        return Response({"message": response_msg}, status=status_code)

    @staticmethod
    def get_place_holders_as_dictionary(place_holders):
        email_variables = {}

        try:
            for key_value in place_holders.split(","):
                key, value = key_value.strip().split("=")
                email_variables[key.strip()] = value.strip()
        except Exception as ex:
            logger.error("TestEmailSend Placeholders " + str(ex), exc_info=True)

        return email_variables


class PlaidAuthorizationRequestViewSet(ModelViewSet):
    http_method_names = ['post']
    permission_classes = [IsClient]
    queryset = PlaidAuthorizationRequest.objects.none()
    serializer_class = PlaidAuthorizationRequestSerializer

    def decide_grant_status(self, validated_data):
        connecting_profile = validated_data['profile']
        if connecting_profile.profile_type == ProfileType.PERSON.value:
            if connecting_profile.get_entity().profile_approval_status == ProfileApprovalStatus.KYC_ACCEPTED.value:
                return PlaidAuthorizationRequestStatus.GRANTED.value
        if connecting_profile.profile_type == ProfileType.BUSINESS.value:
            if connecting_profile.get_entity().synctera_verification_status == BusinessVerificationStatus.ACCEPTED.value:
                return PlaidAuthorizationRequestStatus.GRANTED.value
        return PlaidAuthorizationRequestStatus.DENIED.value

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        grant_status = self.decide_grant_status(validated_data)

        try:
            synctera_client = SyncteraClient(raise_exception=True)

            if validated_data['profile'].profile_type == ProfileType.PERSON.value:
                synctera_customer_id = validated_data['profile'].get_entity().synctera_user_id
                response, _ = synctera_client.authorize_fdx_request_for_customer(
                    customer_id=synctera_customer_id, status=grant_status,
                    auth_request_id=validated_data['auth_request_id'])
            elif validated_data['profile'].profile_type == ProfileType.BUSINESS.value:
                synctera_business_id = validated_data['profile'].get_entity().synctera_business_id
                response, _ = synctera_client.authorize_fdx_request_for_business(
                    business_id=synctera_business_id, status=grant_status,
                    auth_request_id=validated_data['auth_request_id'])

            instance = PlaidAuthorizationRequest.objects.create(**validated_data, status=grant_status,
                                                                redirection_url=response['redirect_uri'])
        except Exception as ex:
            logger.error(msg="Failed to grant plaid connection request\n" + str(ex), exc_info=True)
            raise

        if grant_status == PlaidAuthorizationRequestStatus.GRANTED.value:
            self.send_email(instance)

        return Response(data=PlaidAuthorizationRequestSerializer(instance).data,
                        status=status.HTTP_201_CREATED if grant_status == PlaidAuthorizationRequestStatus.GRANTED.value
                        else status.HTTP_400_BAD_REQUEST)

    @classmethod
    def send_email(cls, instance: PlaidAuthorizationRequest):
        try:
            context = 'successful_linking_by_plaid'
            email_sender = EmailSender(user=instance.profile.get_user())
            email_sender.send_user_email_bcc_admin(context=context)
        except Exception as ex:
            logger.error("Failed to send mail to notify for successful plaid connection \n" + str(ex))


class BusinessSearchChoices(GenericAPIView):
    http_method_names = ['get']
    permission_classes = [IsAdmin]
    queryset = Business.objects.all()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Business.objects.none()
        return self.queryset

    def get(self, request, *args, **kwargs):
        business_list = []

        for business in Business.objects.all().order_by('name').values('id', 'name', 'profile'):
            user_dict = {
                "label": business['name'] + ' - ' + str(business['id']),
                "value": str(business['id']),
                "profile_id": business['profile']
            }
            business_list.append(user_dict)
        return Response(business_list, status.HTTP_200_OK)


class TariffSearchChoices(GenericAPIView):
    http_method_names = ['get']
    permission_classes = [IsAdmin]
    queryset = Tariff.objects.all()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Tariff.objects.none()
        return self.queryset

    def get(self, request, *args, **kwargs):
        tariff_list = []

        for tariff in Tariff.objects.all().order_by('tariff_name').values('id', 'tariff_name', 'tariff_type'):
            user_dict = {
                "label": tariff['tariff_name'] + ' (' + tariff['tariff_type'] + ')',
                "value": str(tariff['id'])
            }
            tariff_list.append(user_dict)
        return Response(tariff_list, status.HTTP_200_OK)


class UserFullAccessView(GenericAPIView):
    http_method_names = ['post']
    permission_classes = [IsAdmin]
    serializer_class = UserFullAccessSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data.get('user')

        with transaction.atomic():
            user.is_full_access_given = True
            user.save(update_fields=['is_full_access_given'])
            UserMetaData.objects.update_or_create(user=user, defaults={'full_access_updated_by': request.user})

        self.send_mail_to_user(user)

        return Response(status=status.HTTP_200_OK)

    def send_mail_to_user(self, user):
        try:
            context = 'full_access_given'
            email_sender = EmailSender(user=user)
            email_sender.send_user_email(context=context)
        except Exception as ex:
            logger.error("Failed to send mail to notify for full access given \n" + str(ex))


class IncomingPlaidConnectionViewSet(ModelViewSet):
    http_method_names = ['get']
    permission_classes = [IsAdmin]
    queryset = PlaidAuthorizationRequest.objects.select_related('profile').order_by('-created_at')
    serializer_class = PlaidAuthorizationRequestSerializer
