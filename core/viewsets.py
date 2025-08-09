import logging

from django.db import transaction
from django.db.models import Q, Count
from rest_framework import status, serializers
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, is_success, HTTP_400_BAD_REQUEST, HTTP_201_CREATED
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.exceptions import PermissionDenied
from common.helpers import google_bucket_file_upload, SyncteraAddressDefaultMappings

from accounts.enums import EntityType, SyncteraAccountStatus
from accounts.handlers.account_balance_handler import AccountBalanceHandler
from accounts.helpers import get_accounts_of_user
from api_clients.synctera_client import SyncteraClient
from common.email import EmailSender
from file_uploader.enums import RelatedResourceType
from file_uploader.models import Documents
from file_uploader.viewsets import FileUploaderViewSet
from utilities.enums import RequestMethod
from common.models import UserSMSLog
from common.serializers import UserSMSLogSerializer
from common.views import CommonTaskManager
from core.enums import ProfileApprovalStatus, AddressType, ProfileType, AdminReviewStatus, AllowedCountries
from core.permissions import IsOwner, ReadOnlyAdmin, IsBDPay, is_bdpay, is_client
from core.models import PriyoMoneyUser, UserMobileNumber, UserAddress, SocureIDV, UserAdditionalInfo, \
    UserLocation, UserIdentification, UserOnboardingStep, UserSourceOfIncome, UserSourceOfHearing, Note, \
    UserContactReference
from core.permissions import is_admin, IsAdmin
from core.serializers import PriyoMoneyUserSerializer, UserMobileNumberSerializer, \
    UserAddressSerializer, SocureIdvSerializer, UserAdditionalInfoSerializer, \
    UserBasicInfoSerializer, PriyoMoneyUserStatusUpdateSerializer, UserLocationSerializer, UserAddressUpdateSerializer, \
    UserAddressAdminSerializer, UserIdentityNumberSerializer, UserOnboardingStepClientSerializer, \
    UserOnboardingStepAdminSerializer, UserSourceOfIncomeSerializer, UserTerminationSerializer, \
    UserSourceOfHearingSerializer, NoteSerializer, UserContactReferenceSerializer, UserAddressCreateSerializer
from core.filters import UserFilter, UserAdditionalInfoFilter, UserSMSLogFilter, \
    UserLocationFilter, UserAddressFilter, UserIdentityNumberFilterSet, UserOnboardingStepFilter, \
    UserSourceOfIncomeFilter, UserSourceOfHearingFilterSet, NoteFilterSet, UserContactReferenceFilter
from core.utility.state_manager import PersonManager
from error_handling.custom_exception import CustomValidationError, CustomErrorWithCode
from error_handling.utils import get_json_validation_error_response, get_json_response_with_error
from common.helpers import SyncteraAddressMappings, create_synctera_address_payload

logger = logging.getLogger(__name__)


class PriyoMoneyUserViewSet(ModelViewSet, CommonTaskManager):
    http_method_names = ['get', 'patch']
    permission_classes = [IsAdmin | IsOwner]

    queryset = PriyoMoneyUser.objects.all()
    serializer_class = PriyoMoneyUserSerializer
    filterset_class = UserFilter

    entity_type = EntityType.USER.value
    view_class_name = __qualname__

    def get_serializer_context(self):
        return (super().get_serializer_context()
                | {'include_profile_image_icon': is_admin(self.request)})

    @classmethod
    def perform_third_party_api_call(cls, validated_data, idempotent_key, **kwargs):
        user_id = kwargs.get('id')
        user = PriyoMoneyUser.objects.get(id=user_id)

        synctera_client = SyncteraClient()
        return synctera_client.update_person(user.synctera_user_id, idempotent_key,
                                             **validated_data)

    @staticmethod
    def generate_validated_data_from_response(synctera_response):
        synctera_validated_data = {
            'first_name': synctera_response.get('first_name'),
            'middle_name': synctera_response.get('middle_name'),
            'last_name': synctera_response.get('last_name') if synctera_response.get('last_name') != "LNU" else None,
            'date_of_birth': synctera_response.get('dob'),
        }
        if 'metadata' in synctera_response:
            synctera_validated_data['citizenship_status'] = synctera_response['metadata'].get('citizenship_status')
        return synctera_validated_data

    @classmethod
    def perform_db_update(cls, synctera_response, validated_data, **kwargs):
        user_id = kwargs.get('id')
        user = PriyoMoneyUser.objects.get(id=user_id)
        serializer = cls.serializer_class(instance=user)
        synctera_validated_data = cls.generate_validated_data_from_response(synctera_response)
        serializer.update(user, synctera_validated_data)
        return serializer.data

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        user = PriyoMoneyUser.objects.get(id=instance.id)
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        if not instance.synctera_user_id or 'profile_approval_status' in request.data:
            self.perform_update(serializer)
            self.send_email_based_on_condition(self.request, user)
            return Response(serializer.data)

        response = self.get_celery_http_response(request, serializer.validated_data,
                                                 id=instance.id,
                                                 method=RequestMethod.PATCH.value)

        self.send_email_based_on_condition(self.request, user)

        if status.is_success(response.status_code) and 'profile_approval_status' not in request.data and \
                user.profile_approval_status in ProfileApprovalStatus.get_all_synctera_kyc_status() \
                and 'synctera_user_status' not in request.data:
            state_manager = PersonManager(user)
            state_manager.submit_kyc_synctera(re_run_kyc=True)

        return response

    @staticmethod
    def send_email_based_on_condition(request, user):
        if is_admin(request):
            EmailSender().send_profile_update_by_admin_email(user, request)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PriyoMoneyUser.objects.none()
        if is_admin(self.request):
            return PriyoMoneyUser.objects.all().order_by('-created_at')
        return PriyoMoneyUser.objects.filter(Q(one_auth_uuid=self.request.user.one_auth_uuid)).order_by('-created_at')


class UserBasicInfoViewSet(ReadOnlyModelViewSet):
    http_method_names = ['get']
    permission_classes = [IsOwner | IsAdmin | IsBDPay]

    queryset = PriyoMoneyUser.objects.all()
    serializer_class = UserBasicInfoSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PriyoMoneyUser.objects.none()
        if is_admin(self.request) or is_bdpay(self.request):
            return PriyoMoneyUser.objects.all().order_by('-created_at')
        return PriyoMoneyUser.objects.filter(Q(one_auth_uuid=self.request.user.one_auth_uuid)).order_by('-created_at')


class UserMobileNumberViewSet(ReadOnlyModelViewSet):
    http_method_names = ['get']
    permission_classes = [IsAdmin | IsOwner]

    queryset = UserMobileNumber.objects.all()
    serializer_class = UserMobileNumberSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserMobileNumber.objects.none()
        if is_admin(self.request):
            return UserMobileNumber.objects.all()
        return UserMobileNumber.objects.filter(Q(user=self.request.user))


class SocureIdvViewSet(ModelViewSet):
    http_method_names = ['get', 'post']
    permission_classes = [IsOwner | ReadOnlyAdmin]

    queryset = SocureIDV.objects.all()
    serializer_class = SocureIdvSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SocureIDV.objects.none()
        if is_admin(self.request):
            return SocureIDV.objects.all()
        return SocureIDV.objects.filter(Q(user=self.request.user))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.delete_previous_and_create_new_idv(user=request.user, serializer=serializer)

        if self.should_resubmit_kyc(user=request.user):
            person_manager = PersonManager(person=request.user)

            try:
                person_manager.submit_kyc_synctera(run_document_verification=True)
            except CustomValidationError as ex:
                return get_json_validation_error_response(ex)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @staticmethod
    def should_resubmit_kyc(user):
        return user.profile_approval_status in ProfileApprovalStatus.get_all_synctera_kyc_status()

    @transaction.atomic
    def delete_previous_and_create_new_idv(self, user, serializer):
        SocureIDV.objects.filter(user=user).delete()
        self.perform_create(serializer)


class UserAddressViewSet(ModelViewSet, CommonTaskManager):
    http_method_names = ['get', 'post', 'patch']
    permission_classes = [IsOwner | IsAdmin]
    serializer_class = UserAddressSerializer

    queryset = UserAddress.objects.all()
    filterset_class = UserAddressFilter

    def get_permissions(self):
        if self.action == 'admin_create':
            return [IsAdmin()]
        if self.request.method == 'POST':
            return [IsOwner()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == 'admin_create':
            return UserAddressAdminSerializer
        if self.action == 'admin_update_country':
            return UserAddressAdminSerializer
        if self.request.method == 'PATCH':
            return UserAddressUpdateSerializer
        if self.request.method == 'POST':
            return  UserAddressCreateSerializer
        return super().get_serializer_class()

    entity_type = EntityType.USER.value
    view_class_name = __qualname__

    @classmethod
    def perform_third_party_api_call(cls, validated_data, idempotent_key, **kwargs):
        synctera_client = SyncteraClient()
        synctera_user_id = kwargs.get('synctera_user_id', None)
        user = PriyoMoneyUser.objects.get(synctera_user_id=synctera_user_id)

        address = UserAddress.objects.get(id=kwargs.get('id'))

        if address.address_type == AddressType.LEGAL.value:
            synctera_payload = create_synctera_address_payload(user.legal_address, validated_data)
            return synctera_client.update_person_legal_address(synctera_user_id, idempotent_key, **synctera_payload)
        elif address.address_type == AddressType.SHIPPING.value:
            synctera_payload = create_synctera_address_payload(user.shipping_address, validated_data)
            return synctera_client.update_person_shipping_address(synctera_user_id, idempotent_key, **synctera_payload)
        elif address.address_type == AddressType.BILLING.value:
            if not synctera_user_id:
                return {"error": "User hasn't onboarded yet"}, HTTP_400_BAD_REQUEST
            return synctera_client.create_or_update_billing_address(synctera_user_id, idempotent_key, address, validated_data)

        return {}, HTTP_200_OK

    @classmethod
    def perform_db_update(cls, synctera_response, validated_data, **kwargs):
        user_address_id = kwargs.get('id')
        user_address = UserAddress.objects.get(id=user_address_id)

        address_response = {}
        if user_address.address_type == AddressType.SHIPPING.value:
            address_response = synctera_response.get('shipping_address') if synctera_response else {}
        elif user_address.address_type == AddressType.LEGAL.value:
            address_response = synctera_response.get('legal_address') if synctera_response else {}
        elif user_address.address_type == AddressType.BILLING.value:
            address_response = synctera_response if synctera_response.get('address_type') == AddressType.BILLING.value else {}

        serializer = cls.serializer_class(instance=user_address)
        country = address_response.get('country_code') or validated_data.get('country') or user_address.country

        if address_response.get("address_type") == AddressType.BILLING.value:
            mapping = SyncteraAddressDefaultMappings
        else:
            mapping = SyncteraAddressMappings[country]

        synctera_validated_data = {}
        for payload_field in address_response:
            if payload_field in mapping:
                synctera_validated_data[mapping[payload_field]] = address_response.get(payload_field)

        for field in validated_data:
            if field not in synctera_validated_data:
                synctera_validated_data[field] = validated_data.get(field)

        serializer.update(user_address, synctera_validated_data)
        return serializer.data

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserAddress.objects.none()
        if is_admin(self.request):
            return UserAddress.objects.all()
        return UserAddress.objects.filter(Q(user=self.request.user))


    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_address = serializer.save()
        user = self.request.user
        if not user.synctera_user_id:
            return Response(data=serializer.data, status=HTTP_201_CREATED)

        validated_data = serializer.validated_data
        validated_data.pop('user', None)

        response = self.get_celery_http_response(request, validated_data, id=user_address.id,
                                                 method=RequestMethod.POST.value,
                                                 synctera_user_id=user_address.user.synctera_user_id,)
        re_run_kyc = request.data.get('re_run_kyc', True)
        if is_admin(self.request):
            EmailSender().send_profile_update_by_admin_email(user_address, request)

        if re_run_kyc and status.is_success(response.status_code) and \
                user_address.user.profile_approval_status in ProfileApprovalStatus.get_all_synctera_kyc_status():
            state_manager = PersonManager(user_address.user)
            state_manager.submit_kyc_synctera(re_run_kyc=re_run_kyc)

        return response

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)

        if not instance.user.synctera_user_id:
            self.perform_update(serializer)
            return Response(serializer.data)

        response = self.get_celery_http_response(request, serializer.validated_data, id=instance.id,
                                                 method=RequestMethod.PATCH.value,
                                                 synctera_user_id=instance.user.synctera_user_id)

        re_run_kyc = request.data.get('re_run_kyc', True)
        if is_admin(self.request):
            EmailSender().send_profile_update_by_admin_email(instance, request)

        if re_run_kyc and status.is_success(response.status_code) and \
                instance.user.profile_approval_status in ProfileApprovalStatus.get_all_synctera_kyc_status():
            state_manager = PersonManager(instance.user)
            state_manager.submit_kyc_synctera(re_run_kyc=re_run_kyc)

        return response

    @action(detail=False, methods=['post'])
    def admin_create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if hasattr(response, 'status_code') and status.is_success(response.status_code):
            EmailSender().send_profile_update_by_admin_email(None, request)
        return response

    @action(detail=True, methods=['patch'], permission_classes=[IsAdmin])
    def admin_update_country(self, request, *args, **kwargs):
        instance = self.get_object()
        user = instance.user
        if user.profile_approval_status != ProfileApprovalStatus.AWAITING_PROFILE_COMPLETION.value:
            return Response({"Error": "User country cannot be changed now"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        if user.get_country() == serializer.validated_data['country']:
            return Response({"Error": "User has already same country"}, status=status.HTTP_400_BAD_REQUEST)

        if user.profile_type == ProfileType.BUSINESS.value:
            return Response({"Error": "Country of business user cant be changed yet"},
                            status=status.HTTP_400_BAD_REQUEST)

        fields_to_keep = ['id', 'user', 'created_at', 'updated_at', 'country', 'address_type']
        for field in instance._meta.fields:
            if field.name not in fields_to_keep:
                setattr(instance, field.name, None)

        serializer.save()
        return Response({"message": "Country updated successfully"}, status=status.HTTP_200_OK)


class UserSMSLogViewSet(ReadOnlyModelViewSet):
    http_method_names = ['get']
    permission_classes = [IsAdmin]

    queryset = UserSMSLog.objects.select_related('user').all()
    serializer_class = UserSMSLogSerializer
    filterset_class = UserSMSLogFilter


class UserAdditionalInfoViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch']
    permission_classes = [IsOwner | IsAdmin]

    filterset_class = UserAdditionalInfoFilter
    queryset = UserAdditionalInfo.objects.all()
    serializer_class = UserAdditionalInfoSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserAdditionalInfo.objects.none()
        if is_admin(self.request):
            return UserAdditionalInfo.objects.all()
        return UserAdditionalInfo.objects.filter(person=self.request.user)

    def get_permissions(self):
        if (self.action == 'partial_update' and is_client(self.request) and
                self.request.user.profile_approval_status == ProfileApprovalStatus.KYC_ACCEPTED.value):
            raise PermissionDenied()
        return super().get_permissions()


class UserStatusUpdateViewSet(GenericAPIView, CommonTaskManager):
    http_method_names = ['patch']
    permission_classes = [IsAdmin]

    serializer_class = PriyoMoneyUserStatusUpdateSerializer
    queryset = PriyoMoneyUser.objects.all()

    entity_type = EntityType.USER.value
    view_class_name = __qualname__

    @classmethod
    def perform_third_party_api_call(cls, validated_data, idempotent_key, **kwargs):
        user_id = kwargs.get('id')
        user = PriyoMoneyUser.objects.get(id=user_id)

        synctera_client = SyncteraClient()
        return synctera_client.update_person_status(user.synctera_user_id, idempotent_key,
                                                    validated_data.get('synctera_user_status'))

    @classmethod
    def perform_db_update(cls, synctera_response, validated_data, **kwargs):
        user_id = kwargs.get('id')
        user = PriyoMoneyUser.objects.get(id=user_id)
        serializer = cls.serializer_class(instance=user)
        synctera_validated_data = {'synctera_user_status': synctera_response.get('status')}
        serializer.update(user, synctera_validated_data)
        return PriyoMoneyUserSerializer(instance=user).data

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=kwargs, partial=True)
        serializer.is_valid(raise_exception=True)

        if kwargs.get('synctera_user_status') == instance.synctera_user_status:
            return Response(PriyoMoneyUserSerializer(instance=instance).data)

        response = self.get_celery_http_response(request, serializer.validated_data, id=instance.id,
                                                 method=RequestMethod.PATCH.value)
        return response


class TerminateUserView(GenericAPIView):
    http_method_names = ['post']
    permission_classes = [IsAdmin]

    serializer_class = UserTerminationSerializer
    queryset = PriyoMoneyUser.objects.all()

    def validate_deactivation_requirements(self, user: PriyoMoneyUser):
        accounts = get_accounts_of_user(user)
        AccountBalanceHandler.sync_balance_with_synctera(accounts)

        for account in accounts:
            user_account = account.user_account
            user_account.refresh_from_db()

            if account.account_status not in SyncteraAccountStatus.get_closed_statuses():
                raise serializers.ValidationError({"user": "User has one or more non-closed accounts"})

    def update_user_synctera_status(self, request, user, note):
        if user.synctera_user_id is not None:
            data = {
                'synctera_user_status': 'INACTIVE',
                'note': note
            }
            response = UserStatusUpdateViewSet().get_celery_http_response(
                request, data, id=user.id, method=RequestMethod.PATCH.value)

            return response, is_success(response.status_code)
        return None, True

    def post(self, request, *args, **kwargs):
        serializers = self.get_serializer(data=request.data)
        serializers.is_valid(raise_exception=True)

        note = serializers.validated_data.get('note')
        user = self.get_object()
        self.validate_deactivation_requirements(user)

        response, success = self.update_user_synctera_status(request, user, note)
        if not success:
            return response

        user.refresh_from_db()
        user.is_terminated = True
        user.save(update_fields=['is_terminated'])
        return Response(PriyoMoneyUserSerializer(instance=user).data, status=status.HTTP_200_OK)


class UserLocationViewSet(ModelViewSet):
    http_method_names = ['get', 'post']
    permission_classes = [ReadOnlyAdmin | IsOwner]

    queryset = UserLocation.objects.all()
    serializer_class = UserLocationSerializer
    filterset_class = UserLocationFilter

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserLocation.objects.none()
        if is_admin(self.request):
            return UserLocation.objects.order_by('-created_at')
        return UserLocation.objects.filter(Q(user=self.request.user)).order_by('-created_at')


class UserSourceOfIncomeViewSet(ModelViewSet):
    http_method_names = ['get', 'post']
    permission_classes = [IsOwner | IsAdmin]
    queryset = UserSourceOfIncome.objects.all()
    serializer_class = UserSourceOfIncomeSerializer
    filterset_class = UserSourceOfIncomeFilter

    def get_permissions(self):
        if self.action == 'update_for_user':
            return [(IsOwner | IsAdmin)()]
        return super().get_permissions()

    def get_queryset(self):
        if is_admin(self.request):
            return UserSourceOfIncome.objects.all()
        return UserSourceOfIncome.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    @transaction.atomic()
    def update_for_user(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, many=True, min_length=1)
        serializer.is_valid(raise_exception=True)
        user = self.request.user if is_client(request) else serializer.validated_data[0]['user']
        UserSourceOfIncome.objects.filter(user=user).delete()
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class UserContactReferenceViewSet(ModelViewSet):
    http_method_names = ['get', 'post']
    permission_classes = [IsOwner | IsAdmin]
    queryset = UserContactReference.objects.all()
    serializer_class = UserContactReferenceSerializer
    filterset_class = UserContactReferenceFilter

    def get_permissions(self):
        if self.action == 'update_for_user':
            return [(IsOwner | IsAdmin)()]
        return super().get_permissions()

    def get_queryset(self):
        if is_admin(self.request):
            return UserContactReference.objects.all()
        return UserContactReference.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    @transaction.atomic()
    def update_for_user(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, many=True, min_length=1)
        serializer.is_valid(raise_exception=True)
        user = self.request.user if is_client(request) else serializer.validated_data[0]['user']
        UserContactReference.objects.filter(user=user).delete()
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class UserIdentityNumberViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch']
    permission_classes = [IsOwner | ReadOnlyAdmin]

    queryset = UserIdentification.objects.all()
    serializer_class = UserIdentityNumberSerializer
    filterset_class = UserIdentityNumberFilterSet

    def get_permissions(self):
        if self.action in ['fetch_details']:
            return [IsAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserIdentification.objects.none()
        if is_admin(self.request):
            return UserIdentification.objects.all()
        return UserIdentification.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def fetch_details(self, request, pk=None):
        identification = UserIdentification.objects.get(pk=pk)
        try:
            identification.fetch_details()
            return Response(data=self.get_serializer(identification).data, status=status.HTTP_200_OK)
        except CustomErrorWithCode as ex:
            return get_json_response_with_error(ex, status.HTTP_400_BAD_REQUEST)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_class = serializer.validated_data.get('identification_class')
        id_number = serializer.validated_data.get('identification_number')
        identity = UserIdentification.objects.filter(identification_class=id_class, identification_number=id_number)

        if identity.exists() and request.user == identity.first().user:
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return super().create(request, *args, **kwargs)


class UserOnboardingStepViewSet(ModelViewSet):
    http_method_names = ['get', 'post']
    permission_classes = [IsAdmin | IsOwner]

    queryset = UserOnboardingStep.objects.all()
    serializer_class = UserOnboardingStepClientSerializer
    filterset_class = UserOnboardingStepFilter

    def get_queryset(self):
        if is_admin(self.request):
            return UserOnboardingStep.objects.all()
        return UserOnboardingStep.objects.filter(Q(user=self.request.user))

    def get_serializer_class(self):
        if is_admin(self.request):
            return UserOnboardingStepAdminSerializer
        return UserOnboardingStepClientSerializer


class UserSourceOfHearingViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch']
    permission_classes = [IsOwner | ReadOnlyAdmin]

    filterset_class = UserSourceOfHearingFilterSet
    queryset = UserSourceOfHearing.objects.all()
    serializer_class = UserSourceOfHearingSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserSourceOfHearing.objects.none()
        if is_admin(self.request):
            return super().get_queryset()
        return super().get_queryset().filter(user=self.request.user)


class NoteViewSet(ModelViewSet):
    http_method_names = ['get', 'post']
    permission_classes = [IsAdmin]
    queryset = Note.objects.order_by('-created_at')
    filterset_class = NoteFilterSet
    serializer_class = NoteSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload_file = serializer.validated_data.pop('upload_file', None)
        doc_type = serializer.validated_data.pop('doc_type', None)
        document = None
        if upload_file and doc_type:
            user_id = serializer.validated_data.get('user')
            folder_prefix = doc_type.lower()
            bucket_folder_name = folder_prefix + "/a" + str(request.user.id) + '_u' + str(user_id)
            file_name = FileUploaderViewSet.build_file_name(upload_file, bucket_folder_name)
            uploaded_file, error_msg = google_bucket_file_upload(the_file=upload_file, file_name=file_name)

            if uploaded_file:
                document = Documents.objects.create(
                    uploader=None,
                    profile=None,
                    doc_type=doc_type,
                    doc_name=doc_type.lower(),
                    related_resource_type=RelatedResourceType.CUSTOMER.value,
                    uploaded_file_name=uploaded_file,
                )
                document.full_clean()
        serializer.validated_data['document'] = document
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class NoteCountView(GenericAPIView):
    http_method_names = ['get']
    permission_classes = [IsAdmin]
    filterset_class = NoteFilterSet

    def get(self, request, *args, **kwargs):
        qs = self.filter_queryset(Note.objects.all())
        result = qs.values('item_id').annotate(count=Count('item_id'))
        return Response({'results': result}, status=status.HTTP_200_OK)


class UpdateAdminReviewStatusView(GenericAPIView):
    http_method_names = ['patch']
    permission_classes = [IsAdmin]
    queryset = PriyoMoneyUser.objects.all()

    def patch(self, request, pk):
        user = self.get_object()
        review_status = request.data.get("admin_review_status")
        response_message = f"Admin Review Status successfully updated to {review_status}"

        if not review_status or review_status not in AdminReviewStatus.values():
            response_message = "Invalid 'admin_review_status' in request body."
            return Response({"detail": response_message}, status=status.HTTP_400_BAD_REQUEST)

        user.admin_review_status = review_status
        user.save(update_fields=['admin_review_status'])

        return Response({"detail": response_message}, status=status.HTTP_200_OK)
