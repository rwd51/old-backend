import logging
from _decimal import Decimal
import zipcodes
from django.core.files.storage import default_storage
from django.core.validators import RegexValidator
from rest_framework import serializers
from rest_framework.exceptions import ValidationError, PermissionDenied
from common.helpers import google_bucket_file_url
from rest_framework.serializers import ModelSerializer
from core.helpers import get_note_item_choices, ContentTypeField
from core.permissions import is_admin, is_client
from core.utility.onboarding_step_handler import OnboardingStepManager
from external_payment.models import ExternalPayment
from external_payment.serializers import ExternalPaymentSerializer
from file_uploader.enums import DocumentType
from file_uploader.validators import FileValidator
from pay_admin.serializers import AdminUserSerializer
from utilities.enums import RequestMethod
from core.enums import ServiceList, AllowedCountries, ProfileApprovalStatus, SyncteraUserStatus, AddressType, \
    BdDivisions, NoteType, ProfileType
from core.utility.state_manager import PersonManager
from core.models import PriyoMoneyUser, UserMobileNumber, UserAddress, Profile, SocureIDV, \
    UserAdditionalInfo, UserMetaData, UserLocation, UserIdentification, UserIdentificationDetails, \
    UserOnboardingStep, UserSourceOfIncome, UserSourceOfHearing, PlaidAuthorizationRequest, Note, UserContactReference, \
    ExternalCustomerIdentification
from invitation.models import InvitationToken
from utilities.serializer_mixin import WritableFieldsMixin
from verifications.serializers import PersonaVerificationSerializer

logger = logging.getLogger(__name__)


class UserCommonSerializer(ModelSerializer):

    def create(self, validated_data):
        try:
            request = self.context['request']
            if is_client(request):
                validated_data['user'] = request.user
            instance = super().create(validated_data)
            instance.save()
            return instance
        except Exception as ex:
            raise serializers.ValidationError(ex)

    class Meta:
        extra_kwargs = {
            'user': {'read_only': True}
        }


def verify_zip(zip_code, state):
    return bool(zipcodes.filter_by(zip_code=zip_code, state=state))


class CommonAddressSerializer(serializers.Serializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)

        if self.should_validate_postal_code(attrs.get('country'), self.instance):
            self.validate_postal_code_with_state(attrs)

        return attrs

    @staticmethod
    def should_validate_postal_code(requested_country, instance: UserAddress):
        user_country = requested_country
        if not user_country and instance and instance.country:
            user_country = instance.country
        return user_country == AllowedCountries.US.value

    @staticmethod
    def validate_postal_code_with_state(attrs):
        has_state = 'state' in attrs
        has_postal_code = 'postal_code' in attrs

        if has_state and has_postal_code:
            zip_code = attrs.get('postal_code')
            state = attrs.get('state')
            match_found = verify_zip(zip_code=zip_code, state=state)
            if not match_found:
                raise ValidationError({"postal_code": "Postal code doesn't match with state"})

        elif has_state or has_postal_code:
            if not has_state:
                raise ValidationError({"state": "this field is required"})
            if not has_postal_code:
                raise ValidationError({"postal_code": "this field is required"})


class AddressMixinSerializer(CommonAddressSerializer):
    # common
    address_line_1 = serializers.CharField(max_length=255)
    address_line_2 = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    postal_code = serializers.CharField(max_length=255)
    country = serializers.ChoiceField(choices=AllowedCountries.choices())

    # US
    city = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    state = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)

    # BD
    district = serializers.CharField(max_length=64, required=False, allow_null=True, allow_blank=True)
    thana = serializers.CharField(max_length=64, required=False, allow_null=True, allow_blank=True)
    division = serializers.ChoiceField(choices=BdDivisions.choices(), required=False, allow_null=True, allow_blank=True)


class UserAddressUpdateSerializer(CommonAddressSerializer, UserCommonSerializer):
    class Meta(UserCommonSerializer.Meta):
        model = UserAddress
        fields = '__all__'
        read_only_fields = ('user', 'address_type')

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = self.context['request'].user
        if self.trying_to_change_country(attrs) and not self.can_update_country(user, self.instance.address_type):
            raise ValidationError({"country": "Country cannot be changed"})

        return attrs

    @staticmethod
    def can_update_country(user: PriyoMoneyUser, address_type):
        if address_type == AddressType.LEGAL.value:
            return user.profile_approval_status == ProfileApprovalStatus.AWAITING_SIGNUP_COMPLETION.value
        else:
            return True

    def trying_to_change_country(self, attrs):
        if 'country' not in attrs:
            return False

        current_country = self.instance.country if self.instance else None
        return attrs.get('country') != current_country


class UserAddressSerializer(CommonAddressSerializer, UserCommonSerializer):
    class Meta(UserCommonSerializer.Meta):
        model = UserAddress
        fields = '__all__'


class UserAddressAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAddress
        fields = '__all__'


class UserAddressCreateSerializer(UserAddressSerializer):

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = self.context['request'].user
        if UserAddress.objects.filter(user=user, address_type=attrs.get('address_type', AddressType.LEGAL.value)).exists():
            raise serializers.ValidationError("Address of this type already exists")
        return attrs

    class Meta(UserAddressSerializer.Meta):
        model = UserAddress
        fields = '__all__'


class UserMobileNumberSerializer(UserCommonSerializer):
    class Meta(UserCommonSerializer.Meta):
        model = UserMobileNumber
        fields = '__all__'


class SocureIdvSerializer(ModelSerializer):

    def to_internal_value(self, data):
        data['user'] = self.context['request'].user.id
        return super().to_internal_value(data)

    class Meta:
        model = SocureIDV
        fields = '__all__'


class PriyoMoneyUserSerializer(ModelSerializer):
    user_address = serializers.SerializerMethodField(source='get_user_address', read_only=True)
    legal_address = serializers.SerializerMethodField(source='get_legal_address', read_only=True)
    shipping_address = serializers.SerializerMethodField(source='get_shipping_address', read_only=True)
    billing_address = serializers.SerializerMethodField(source='get_billing_address', read_only=True)

    mobile_number = serializers.SerializerMethodField(source='get_mobile_number', read_only=True)
    applied_token = serializers.SerializerMethodField(source='get_applied_token', read_only=True)
    # linked_account = serializers.SerializerMethodField(source='get_linked_account', read_only=True)
    # linked_cards = serializers.SerializerMethodField(source='get_linked_cards', read_only=True)
    user_additional_info = serializers.SerializerMethodField(source='get_user_additional_info', read_only=True)
    signup_meta_data = serializers.SerializerMethodField(source='get_signup_meta_data', read_only=True)
    payments = serializers.SerializerMethodField(source='get_payments', read_only=True)
    identifications = serializers.SerializerMethodField(source='get_identifications', read_only=True)
    verifications = serializers.SerializerMethodField(source='get_verifications', read_only=True)
    last_onboarding_step = serializers.SerializerMethodField(read_only=True)
    profile_image_icon = serializers.SerializerMethodField(read_only=True)

    def get_last_onboarding_step(self, instance):
        return OnboardingStepManager(instance).get_last_finished_step()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        approval_status = attrs.get('profile_approval_status', None)
        if approval_status is not None:
            if self.context['request'].service == ServiceList.CLIENT.value:
                if approval_status not in [ProfileApprovalStatus.AWAITING_PROFILE_COMPLETION.value,
                                           ProfileApprovalStatus.AWAITING_ADMIN_APPROVAL.value,
                                           ProfileApprovalStatus.PROFILE_INFO_SAVED.value]:
                    raise ValidationError({f'profile_approval_status": "Invalid status {approval_status}'})
        return attrs

    def update(self, instance, validated_data):
        approval_status = validated_data.pop('profile_approval_status', None)
        instance = super().update(instance, validated_data)

        if approval_status is None:
            return instance

        admin_user = None
        if self.context['request'].user != instance:
            admin_user = self.context['request'].user

        state_manager = PersonManager(instance, admin_user)
        state_manager.change_state(new_state=approval_status)

        return PriyoMoneyUser.objects.filter(id=instance.id).get()

    class Meta:
        model = PriyoMoneyUser
        fields = '__all__'
        read_only_fields = ('profile', 'email_address', 'is_email_verified',
                            'synctera_user_id', 'one_auth_uuid', 'is_verified_internal_user',
                            'ssn_submitted_to_synctera')

    def get_user_address(self, instance):
        if instance.legal_address is None:
            return None
        return UserAddressSerializer(instance.legal_address, context={'exclude_metadata': True}).data

    def get_legal_address(self, instance):
        if instance.legal_address is None:
            return None
        return UserAddressSerializer(instance.legal_address, context={'exclude_metadata': True}).data

    def get_shipping_address(self, instance):
        if instance.shipping_address is None:
            return None
        return UserAddressSerializer(instance.shipping_address, context={'exclude_metadata': True}).data

    def get_billing_address(self, instance):
        if instance.billing_address is None:
            return None
        return UserAddressSerializer(instance.billing_address, context={'exclude_metadata': True}).data

    def get_user_additional_info(self, instance):
        if not instance.has_additional_info():
            return None
        additional_info = instance.bd_user_additional_info
        return UserAdditionalInfoSerializer(additional_info, context={'exclude_metadata': True}).data if additional_info else None

    def get_mobile_number(self, instance):
        if not instance.has_mobile_number():
            return None
        mobile = instance.user_mobile_number
        return UserMobileNumberSerializer(mobile, context={'exclude_metadata': True}).data

    def get_applied_token(self, instance):
        if not instance.has_used_token():
            return None
        token = instance.used_token
        return InvitationTokenUsedSerializer(token, context={'exclude_metadata': True}).data

    # def get_linked_account(self, instance: PriyoMoneyUser):
    #     if not hasattr(instance, 'related_bd_account'):
    #         return None
    #     assigned_account = instance.related_bd_account.assigned_account
    #     from accounts.serializers.account import AccountSerializer
    #     return AccountSerializer(instance=assigned_account).data
    #
    # def get_linked_cards(self, instance: PriyoMoneyUser):
    #     assigned_cards = Card.objects.filter(related_bd_card__person=instance)
    #     from accounts.serializers.card import CardSerializer
    #     return CardSerializer(instance=assigned_cards, many=True).data

    def get_signup_meta_data(self, instance):
        if not instance.has_meta_data():
            return None
        if self.context and not is_admin(self.context.get('request')):
            return None
        meta_data = instance.user_meta_data
        return UserMetaDataSerializer(meta_data, context={'exclude_metadata': True}).data if meta_data else None

    def get_payments(self, instance: PriyoMoneyUser):
        payments = ExternalPayment.objects.filter(user=instance)
        return ExternalPaymentSerializer(instance=payments, many=True).data

    def get_identifications(self, instance: PriyoMoneyUser):
        identifications = UserIdentification.objects.filter(user=instance)
        return UserIdentificationSerializer(instance=identifications, many=True).data

    def get_verifications(self, instance: PriyoMoneyUser):
        if self.context and is_admin(self.context.get('request')):
            verifications = instance.persona_verifications
            return PersonaVerificationSerializer(instance=verifications, many=True).data
        else:
            return None

    def get_profile_image_icon(self, instance: PriyoMoneyUser):
        if not self.context.get('include_profile_image_icon'):
            return None
        from file_uploader.manager import ImageCompressManager
        return ImageCompressManager.get_compressed_image_url(
            document=instance.documents_uploader.filter(doc_type=DocumentType.PROFILE_IMAGE.value).first()
        )


class UserIdentificationSerializer(ModelSerializer):
    class Meta:
        model = UserIdentification
        fields = '__all__'


class ExternalCustomerIdentificationSerializer(ModelSerializer):
    external_customer = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ExternalCustomerIdentification
        fields = '__all__'


class UserBasicInfoSerializer(ModelSerializer):
    name = serializers.SerializerMethodField(method_name='get_name', read_only=True)
    profile_image_icon = serializers.SerializerMethodField(read_only=True)

    def get_name(self, instance):
        return instance.get_fullname()

    def get_profile_image_icon(self, instance: PriyoMoneyUser):
        if not self.context.get('include_profile_image_icon'):
            return None
        from file_uploader.manager import ImageCompressManager
        return ImageCompressManager.get_compressed_image_url(
            document=instance.documents_uploader.filter(doc_type=DocumentType.PROFILE_IMAGE.value).first()
        )

    class Meta:
        model = PriyoMoneyUser
        fields = ['email_address', 'name', 'id', 'first_name', 'middle_name', 'last_name', 'profile_image_icon']


class UserSsnSerializer(serializers.Serializer):
    ssn = serializers.CharField(validators=[RegexValidator(
        regex=r'^\d{3}-\d{2}-\d{4}$', message="doesn't match the format r'^\\d{3}-\\d{2}-\\d{4}$'")])

    def validate(self, attrs):
        if not self.context.get('request').user.synctera_user_id:
            raise ValidationError({"user": "User profile not created on Synctera"})

        return attrs


class ProfileSerializer(ModelSerializer):
    class Meta:
        model = Profile
        fields = '__all__'


class InvitationTokenUsedSerializer(ModelSerializer):
    class Meta:
        model = InvitationToken
        fields = ('token', 'origin', 'issuer', 'invitee_name', 'invitee_email', 'invitee_phone_number')


class PersonVerifySerializer(serializers.Serializer):
    person_id = serializers.IntegerField(required=False)

    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        service = self.context['request'].service

        if service == ServiceList.CLIENT.value:
            data['person_id'] = self.context['request'].user.id

        return data

    def validate(self, attrs):
        person_id = attrs.get('person_id')

        try:
            user = PriyoMoneyUser.objects.get(id=person_id)
        except PriyoMoneyUser.DoesNotExist:
            raise serializers.ValidationError({"user": "User not found"})

        if not user.synctera_user_id:
            raise ValidationError({"user": "User profile not created on Synctera"})

        return attrs


class SyncKYCSerializer(serializers.Serializer):
    person_id = serializers.IntegerField()

    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        person_id = data.get('person_id')
        try:
            data['person'] = PriyoMoneyUser.objects.get(id=person_id)
        except PriyoMoneyUser.DoesNotExist:
            raise serializers.ValidationError({"user": "User not found"})
        return data

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = attrs.get('person')
        if user.synctera_user_id is None:
            raise serializers.ValidationError({"user": "synctera id does not exist"})
        return attrs


class BDManualKYCSerializer(serializers.Serializer):
    allowed_requested_statuses = [
        ProfileApprovalStatus.MANUAL_KYC_REJECTED.value,
        ProfileApprovalStatus.MANUAL_KYC_ACCEPTED.value
    ]

    person_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=allowed_requested_statuses)

    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        person_id = data.get('person_id')
        try:
            data['person'] = PriyoMoneyUser.objects.get(id=person_id)
        except PriyoMoneyUser.DoesNotExist:
            raise serializers.ValidationError({"user": "User not found"})
        return data

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = attrs.get('person')
        if user.get_country() != AllowedCountries.BD.value:
            raise serializers.ValidationError({"user": "Forbidden"})
        return attrs


class UserAdditionalInfoSerializer(ModelSerializer):
    year_of_experience = serializers.IntegerField(min_value=0)

    class Meta:
        model = UserAdditionalInfo
        fields = '__all__'
        read_only_fields = ['person']

    person_id = serializers.IntegerField(write_only=True, required=False)

    def to_internal_value(self, data):
        representation = super().to_internal_value(data)
        request = self.context['request']
        representation['person'] = self.assign_person(request, data)
        return representation

    def assign_person(self, request, data):
        if request.method == RequestMethod.PATCH.value:
            return self.instance.person
        elif request.service == ServiceList.ADMIN.value:
            return self.assign_person_from_data(data)
        elif request.service == ServiceList.CLIENT.value:
            return request.user

        raise serializers.ValidationError({"person": "Forbidden"})

    @staticmethod
    def assign_person_from_data(data):
        if 'person_id' not in data:
            raise serializers.ValidationError({'person_id': ['This field is required.']})

        person_id = data.get('person_id')
        try:
            person = PriyoMoneyUser.objects.get(id=person_id)
        except PriyoMoneyUser.DoesNotExist:
            raise serializers.ValidationError({"person": f"person not found with id {person_id}"})
        return person


class UserMetaDataSerializer(ModelSerializer):
    profile_approved_by = AdminUserSerializer(read_only=True)
    profile_verified_by = AdminUserSerializer(read_only=True)
    full_access_update_by = AdminUserSerializer(read_only=True)

    class Meta:
        model = UserMetaData
        fields = '__all__'


class PriyoMoneyUserStatusUpdateSerializer(ModelSerializer):
    synctera_user_status = serializers.ChoiceField(choices=SyncteraUserStatus.choices())

    class Meta:
        model = PriyoMoneyUser
        fields = ('synctera_user_status',)


class UserLocationSerializer(UserCommonSerializer):
    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        data['longitude'] = data['longitude'].quantize(Decimal("1e-10"))
        data['latitude'] = data['latitude'].quantize(Decimal("1e-10"))
        return data

    class Meta(UserCommonSerializer.Meta):
        model = UserLocation
        fields = '__all__'


class UserSourceOfIncomeSerializer(ModelSerializer):
    url = serializers.CharField(max_length=255)

    def to_internal_value(self, data):
        if is_client(self.context['request']):
            data['user'] = self.context['request'].user.id
        return super().to_internal_value(data)

    class Meta:
        model = UserSourceOfIncome
        fields = '__all__'


class UserContactReferenceSerializer(ModelSerializer):

    def to_internal_value(self, data):
        if is_client(self.context['request']):
            data['user'] = self.context['request'].user.id
        return super().to_internal_value(data)

    class Meta:
        model = UserContactReference
        fields = '__all__'


class UserIdentityNumberSerializer(ModelSerializer):
    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        data['user'] = self.context['request'].user
        return data

    def validate(self, attrs):
        request = self.context['request']
        id_class = attrs.get('identification_class')
        id_number = attrs.get('identification_number')
        identity = UserIdentification.objects.filter(identification_class=id_class, identification_number=id_number)
        err_msg = f"This NID number ({id_number}) has already been registered by another user"

        if identity.exists():
            if request.method == "POST" or request.method == "PATCH":
                if request.user != identity.first().user:
                    raise serializers.ValidationError({"identification_number": err_msg})

        return attrs

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if is_admin(self.context['request']):
            details = instance.get_details()
            representation['details'] = UserIdentificationDetailsSerializer(details, many=True).data
        return representation

    def update(self, instance, validated_data):
        if self.context['request'].user != instance.user:
            raise serializers.ValidationError({"user": 'User does not have permission to access this Identification'})

        return super().update(instance, validated_data)

    class Meta:
        model = UserIdentification
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'verification', 'user')


class UserIdentificationDetailsSerializer(ModelSerializer):
    class Meta:
        model = UserIdentificationDetails
        fields = '__all__'


class UserOnboardingStepClientSerializer(WritableFieldsMixin, ModelSerializer):
    def create(self, validated_data):
        user = self.context['request'].user
        step = validated_data['step']
        onboarding_step, created = UserOnboardingStep.objects.get_or_create(user=user, step=step)
        return onboarding_step

    class Meta:
        model = UserOnboardingStep
        fields = '__all__'
        writable_fields = ['step']


class UserOnboardingStepAdminSerializer(ModelSerializer):
    class Meta:
        model = UserOnboardingStep
        fields = '__all__'


class UserTerminationSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=255, required=True)


class UserSourceOfHearingSerializer(ModelSerializer):
    def to_internal_value(self, data):
        data['user'] = self.context['request'].user.pk
        data = super().to_internal_value(data)
        return data

    class Meta:
        model = UserSourceOfHearing
        fields = '__all__'


class PlaidAuthorizationRequestSerializer(ModelSerializer):
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['profile'] = {
            'type': instance.profile.profile_type,
        }
        if instance.profile.profile_type == ProfileType.PERSON.value:
            rep['profile']['data'] = UserBasicInfoSerializer(
                instance=instance.profile.get_entity(),
                context={'include_profile_image_icon': is_admin(self.context.get('request'))}).data
        else:
            from business.serializers.business import BusinessBasicInfoSerializer
            rep['profile']['data'] = BusinessBasicInfoSerializer(instance=instance.profile.get_entity()).data
        return rep

    class Meta:
        model = PlaidAuthorizationRequest
        fields = ['auth_request_id', 'profile', 'status', 'redirection_url', 'created_at']
        read_only_fields = ['status', 'redirection_url', 'created_at']

    def validate_profile(self, profile: Profile):
        if profile.profile_type not in [ProfileType.PERSON.value, ProfileType.BUSINESS.value]:
            raise ValidationError("Invalid profile type")
        if self.context['request'].user not in profile.get_user_set():
            raise PermissionDenied()
        return profile


class NoteSerializer(ModelSerializer):
    item_type = ContentTypeField(choices=get_note_item_choices)
    upload_file = serializers.FileField(required=False, write_only=True, validators=[
        FileValidator(max_size=5 * 1024 * 1024, allowed_extensions=('pdf', 'jpg', 'png', 'jpeg', 'gif'))])
    doc_type = serializers.CharField(max_length=64, write_only=True, required=False)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if instance.created_by:
            rep['created_by'] = AdminUserSerializer(instance.created_by).data
        if instance.document:
            file_name = instance.document.uploaded_file_name
            if default_storage.exists(file_name):
                rep['gcp_url'] = google_bucket_file_url(file_name)
            else:
                rep['gcp_url'] = ""
        return rep

    def validate(self, attrs):
        attrs = super().validate(attrs)
        item_model_class = attrs['item_type'].model_class()
        if not item_model_class.objects.filter(pk=attrs['item_id']).exists():
            raise serializers.ValidationError(detail={"item_id": "Does not exist"})
        attrs['note_type'] = NoteType.ADMIN.value
        attrs['created_by'] = self.context['request'].user
        return attrs

    class Meta:
        model = Note
        fields = '__all__'
        read_only_fields = ['created_by', 'note_type']


class UserFullAccessSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=PriyoMoneyUser.objects.filter(is_full_access_given=False))
