from _decimal import Decimal
import phonenumbers
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q, UniqueConstraint
from django.utils import timezone
from phonenumbers import NumberParseException
from requests import RequestException

from core.enums import ProfileApprovalStatus, SyncteraUserStatus, AddressType, ServiceList, DeviceType, ProfileType, \
    SocureProgressStatus, AllowedCountries, LocationTypes, OnboardingSteps, NoteType, EmploymentStatus, UserGender,\
    UserSourceOfHearingOptions, SubServiceList, PlaidAuthorizationRequestStatus, AdminReviewStatus, MaritalStatus, BdDivisions
from core.helpers import get_dial_code_list
from dynamic_settings.helpers import global_dynamic_settings
from core.dynamic_settings import AdminApprovalRequiredForBDUser, AdminApprovalRequiredForUSUser
from file_uploader.enums import DocumentType, RelatedResourceType
from pay_admin.models import PayAdmin
from subscription.enums import PackageType
from utilities.helpers import make_dummy_request, get_priyo_business
from utilities.model_mixins import TimeStampMixin, SoftDeleteMixin, SoftDeleteManager, AddressMixin, OnboardingMixin, \
    PersonMixin, ProfileMixin
from error_handling.error_list import CUSTOM_ERROR_LIST
from verifications.enums import IDType, IdentificationInfoSource


class Profile(ProfileMixin, TimeStampMixin, SoftDeleteMixin):
    profile_type = models.CharField(max_length=32, choices=ProfileType.extended_choices())

    def get_entity(self):
        if self.profile_type == ProfileType.PERSON.value:
            return self.user
        elif self.profile_type == ProfileType.BUSINESS.value:
            return self.business
        elif self.profile_type == ProfileType.LINKED_BUSINESS.value:
            return self.linked_business
        else:
            raise Exception("Invalid profile type")

    def get_user(self):
        return self.get_entity().get_user()

    def get_user_set(self):
        return self.get_entity().get_user_set()

    def get_profile_name(self):
        return self.get_entity().get_name()


class PriyoMoneyUser(PersonMixin, OnboardingMixin, TimeStampMixin, SoftDeleteMixin):
    profile = models.OneToOneField(Profile, on_delete=models.PROTECT, related_name='user')

    first_name = models.CharField(max_length=255, null=True, blank=True)
    middle_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)

    email_address = models.CharField(max_length=255, null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)
    date_of_birth = models.DateField(null=True, blank=True)
    citizenship_status = models.CharField(max_length=32, null=True, blank=True)

    synctera_user_status = models.CharField(max_length=255, null=True, blank=True, choices=SyncteraUserStatus.choices())
    synctera_user_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    one_auth_uuid = models.CharField(max_length=255, unique=True, null=False)

    profile_type = models.CharField(max_length=64, choices=ProfileType.choices(), null=True, blank=True)
    profile_approval_status = models.CharField(max_length=255,
                                               choices=ProfileApprovalStatus.choices(),
                                               default=ProfileApprovalStatus.AWAITING_SIGNUP_COMPLETION.value)
    admin_review_status = models.CharField(max_length=16, choices=AdminReviewStatus.choices(),
                                           default=AdminReviewStatus.INITIATED.value)

    is_verified_internal_user = models.BooleanField(default=False)
    ssn_submitted_to_synctera = models.BooleanField(default=False)
    last_active_at = models.DateTimeField(null=True, blank=True)

    is_terminated = models.BooleanField(default=False)

    is_full_access_given = models.BooleanField(default=False)  # Sending money and creating card feature

    gender = models.CharField(max_length=16, choices=UserGender.choices(), null=True, blank=True)
    nationality = models.CharField(max_length=64, null=True, blank=True)
    marital_status = models.CharField(max_length=32, choices=MaritalStatus.choices(), null=True, blank=True)

    objects = SoftDeleteManager()
    SYNCTERA_ID_FIELD = 'synctera_user_id'

    _required_fields_for_onboarding = ('first_name', 'email_address', 'date_of_birth', 'one_auth_uuid')
    _country_specific_required_docs_for_onboarding = {
        AllowedCountries.BD.value: [DocumentType.PROFILE_IMAGE.value]
    }

    def is_synctera_user(self):
        return self.synctera_user_id is not None

    def get_country(self):
        return self.legal_address.country if self.has_legal_address() else None

    def get_fullname(self):
        return ' '.join(str(name) for name in [self.first_name, self.middle_name, self.last_name] if name)

    def get_name(self):
        return self.get_fullname()

    def has_complete_onboarding_data(self):
        return self.is_complete() and self.is_mobile_data_complete() and self.is_address_complete() \
            and self.is_additional_info_complete() and self.has_necessary_documents()

    def get_missing_onboarding_data(self):
        missing_fields = []
        if not self.is_complete():
            missing_fields.append('profile info')
        if not self.is_mobile_data_complete():
            missing_fields.append('mobile')
        if not self.is_address_complete():
            missing_fields.append('address')
        if not self.is_additional_info_complete():
            missing_fields.append('additional_info')
        if not self.has_necessary_documents():
            missing_fields.append('documents/profile image')
        return missing_fields

    def sync_shipping_address(self, force_overwrite=False):
        if force_overwrite or self.shipping_address is None:
            if self.shipping_address is not None:
                self.shipping_address.delete()
            address = self.legal_address
            address.pk = None
            address.address_type = AddressType.SHIPPING.value
            address.save()

    def has_mobile_number(self):
        return hasattr(self, 'user_mobile_number') and self.user_mobile_number is not None

    def is_mobile_data_complete(self):
        return self.has_mobile_number() and self.user_mobile_number.is_complete()

    @property
    def legal_address(self):
        return self.user_addresses.filter(address_type=AddressType.LEGAL.value).first()

    @property
    def shipping_address(self):
        return self.user_addresses.filter(address_type=AddressType.SHIPPING.value).first()

    @property
    def billing_address(self):
        return self.user_addresses.filter(address_type=AddressType.BILLING.value).first()

    def has_legal_address(self):
        return self.user_addresses.filter(address_type=AddressType.LEGAL.value).exists()

    def is_address_complete(self):
        return (self.legal_address and self.legal_address.is_complete() and
                self.shipping_address and self.shipping_address.is_complete())

    def has_additional_info(self):
        return hasattr(self, 'bd_user_additional_info') and self.bd_user_additional_info is not None

    def is_additional_info_complete(self):
        if self.get_country() != AllowedCountries.BD.value:
            return True
        return self.has_additional_info() and self.bd_user_additional_info.is_complete()

    def get_additional_info(self):
        return self.bd_user_additional_info if self.has_additional_info() else None

    def has_document(self, doc_type: DocumentType):
        from file_uploader.models import Documents
        return Documents.objects.filter(profile=self.profile, doc_type=doc_type).exists()

    def has_necessary_documents(self):
        required_docs = self._country_specific_required_docs_for_onboarding.get(self.get_country(), ())
        return all(self.has_document(doc) for doc in required_docs)

    def has_used_token(self):
        return hasattr(self, 'used_token') and self.used_token is not None

    def has_meta_data(self):
        return hasattr(self, 'user_meta_data') and self.user_meta_data is not None

    def has_browser_location(self):
        saved_locations = UserLocation.objects.filter(Q(user=self) & Q(type=LocationTypes.BROWSER.value))
        return saved_locations.count() != 0

    def get_active_subscriptions(self):
        return self.subscriptions.select_related('package').filter(is_active=True)

    def get_active_onboarding_subscription(self):
        return self.subscriptions.select_related('package').filter(is_active=True,
                                                                   package__type=PackageType.ONBOARDING.value).first()

    def get_used_referral_code(self):
        return self.referral_code_usage.referral_code if hasattr(self, 'referral_code_usage') else None

    def get_active_persona_verification(self):
        return self.persona_verifications.filter(is_active=True).first()

    def is_persona_verified(self):
        verification = self.get_active_persona_verification()
        return verification is not None and verification.is_complete()

    def get_user(self):
        return self

    def get_involved_businesses_queryset(self):
        business_model = self.created_businesses.model
        related_business_ids = self.business_relations.all().values_list('business', flat=True)

        related_business_queryset = business_model.objects.filter(id__in=related_business_ids)
        created_business_queryset = self.created_businesses.all()
        return related_business_queryset | created_business_queryset

    def get_involved_linked_business_queryset(self):
        return self.linked_businesses.all()

    def is_synctera_kyc_accepted(self):
        return self.profile_approval_status == ProfileApprovalStatus.KYC_ACCEPTED.value

    def requires_admin_approval(self):
        if self.get_country() == AllowedCountries.BD.value:
            return global_dynamic_settings.get(AdminApprovalRequiredForBDUser)
        elif self.get_country() == AllowedCountries.US.value:
            return global_dynamic_settings.get(AdminApprovalRequiredForUSUser)
        else:
            return True

    def is_user_only_subscribed_for_bdt_account(self):
        subscription = self.get_active_onboarding_subscription()
        return subscription and subscription.package.account_limit == 0 and subscription.package.bdt_account_limit > 0

    def is_access_limited(self):
        return not self.is_full_access_given


class UserMetaData(SoftDeleteMixin):
    user = models.OneToOneField(PriyoMoneyUser, on_delete=models.CASCADE, related_name='user_meta_data')
    signup_meta_data = models.JSONField(null=True, blank=True)
    http_user_agent = models.TextField(blank=True, null=True)
    is_sent_welcome_email = models.BooleanField(default=False)
    profile_approved_by = models.ForeignKey(PayAdmin, on_delete=models.PROTECT, null=True, blank=True,
                                            related_name='approved_by')
    profile_approved_at = models.DateTimeField(null=True, blank=True)
    profile_verified_by = models.ForeignKey(PayAdmin, on_delete=models.PROTECT, null=True, blank=True,
                                            related_name='verified_by')
    profile_verified_at = models.DateTimeField(null=True, blank=True)
    full_access_updated_by = models.ForeignKey(PayAdmin, on_delete=models.PROTECT, null=True, blank=True,
                                               related_name='full_access_updated_by')


class UserMobileNumber(PersonMixin, OnboardingMixin, TimeStampMixin, SoftDeleteMixin):
    user = models.OneToOneField(PriyoMoneyUser, on_delete=models.CASCADE, related_name='user_mobile_number')
    mobile_number = models.CharField(max_length=255, null=True, unique=True)
    mobile_number_country_prefix = models.CharField(max_length=255, null=True, choices=get_dial_code_list())
    objects = SoftDeleteManager()

    def get_user(self):
        return self.user

    _required_fields_for_onboarding = ('mobile_number',)

    @classmethod
    def register_mobile(cls, mobile_number, user):

        try:
            parsed_number = phonenumbers.parse(mobile_number)
        except NumberParseException:
            raise CUSTOM_ERROR_LIST.INVALID_PHONE_NUMBER_4024

        country_prefix = f'+{parsed_number.country_code}'
        user_mobile = UserMobileNumber.objects.create(user=user,
                                                      mobile_number=mobile_number,
                                                      mobile_number_country_prefix=country_prefix)
        user_mobile.full_clean()


class UserAddress(PersonMixin, AddressMixin, TimeStampMixin, OnboardingMixin):
    user = models.ForeignKey(PriyoMoneyUser, on_delete=models.CASCADE, related_name='user_addresses', null=True,
                             blank=True)
    address_type = models.CharField(max_length=255, default=AddressType.LEGAL.value, choices=AddressType.choices())
    synctera_address_id = models.UUIDField(null=True, blank=True)

    _required_fields_for_onboarding = ('address_line_1', 'postal_code', 'country')
    _country_specific_required_fields_for_onboarding = {
        AllowedCountries.US.value: ('state', 'city'),
        AllowedCountries.BD.value: ('district', 'thana', 'division')
    }

    class Meta:
        constraints = [
            UniqueConstraint(fields=['user', 'address_type'],
                             condition=Q(address_type__in=AddressType.unique_types()),
                             name='unique_user_address'),
        ]

    def get_country(self):
        return self.country

    def get_user(self):
        return self.user


class UserAdditionalAddress(PersonMixin, AddressMixin, TimeStampMixin):
    # common
    address_nick_name = models.CharField(max_length=128, null=True, blank=True)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, null=True, blank=True)
    postal_code = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=2)

    # US
    city = models.CharField(max_length=255, null=True, blank=True)
    state = models.CharField(max_length=2, null=True, blank=True)

    # BD
    district = models.CharField(max_length=64, null=True, blank=True)
    thana = models.CharField(max_length=64, null=True, blank=True)
    division = models.CharField(max_length=1, choices=BdDivisions.choices(), null=True, blank=True)

    user = models.ForeignKey(PriyoMoneyUser, on_delete=models.CASCADE, related_name='user_additional_addresses')
    address_type = models.CharField(max_length=255, default=AddressType.LEGAL.value, choices=AddressType.choices())
    synctera_address_id = models.UUIDField(null=True, blank=True)

    def get_address_single_line(self):
        ordered_parts = [
            self.address_line_1,
            self.address_line_2,
            self.city,
            self.state,
            self.thana,
            self.district,
        ]
        if self.country == AllowedCountries.US.value:
            ordered_parts.append(self.postal_code)
        ordered_parts.append(self.country)
        return ", ".join([str(part) for part in ordered_parts if part])

    class Meta:
        constraints = [
            UniqueConstraint(fields=['user', 'address_type'],
                             condition=Q(address_type__in=AddressType.unique_types()),
                             name='unique_user_additional_address'),
        ]

    def get_country(self):
        return self.country

    def get_user(self):
        return self.user


class SocureIDV(PersonMixin, SoftDeleteMixin):
    user = models.ForeignKey(PriyoMoneyUser, on_delete=models.CASCADE, related_name='socure_idv')
    socure_status = models.CharField(max_length=64, choices=SocureProgressStatus.choices())
    document_id = models.UUIDField()
    socure_response = models.JSONField()
    objects = SoftDeleteManager()

    def get_user(self):
        return self.user


class TrustedDevice(PersonMixin, TimeStampMixin, SoftDeleteMixin):
    user = models.ForeignKey(PriyoMoneyUser, on_delete=models.CASCADE, related_name='user_trusted_device')
    fingerprint = models.CharField(max_length=255, null=False)
    device_info = models.JSONField(null=True)
    device_type = models.CharField(max_length=255, null=False, choices=DeviceType.choices())
    objects = SoftDeleteManager()

    def get_user(self):
        return self.user

    class Meta:
        unique_together = ('user', 'fingerprint', 'is_deleted',)

    @staticmethod
    def register_device(request):
        device_fingerprint = request.META.get('HTTP_DEVICE_FINGERPRINT', None)
        device_type = request.META.get('HTTP_DEVICE_TYPE', None)
        if not device_fingerprint or not device_type:
            raise CUSTOM_ERROR_LIST.MISSING_INFO_FROM_HEADER_4023

        TrustedDevice.objects.get_or_create(
            user=request.user,
            fingerprint=device_fingerprint,
            device_type=device_type
        )


class ServiceKey(models.Model):
    secret_key = models.CharField(max_length=255, null=False, blank=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    service = models.CharField(max_length=15, choices=ServiceList.choices())
    sub_service = models.CharField(max_length=15, choices=SubServiceList.choices(), null=True, blank=True)

    class Meta:
        db_table = 'service_key'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['secret_key']),
            models.Index(fields=['service']),
        ]

    def __str__(self):
        return str(self.id)

    @classmethod
    def get_service_and_subservice_from_api_key(cls, api_key):
        if not cls.objects.filter(secret_key=api_key).exists():
            return None, None
        service_key = cls.objects.filter(secret_key=api_key).first()
        return service_key.service, service_key.sub_service

    @classmethod
    def get_key_from_service(cls, service):
        if not cls.objects.filter(service=service).exists():
            return None
        return cls.objects.filter(service=service).first().secret_key


class UserAdditionalInfo(PersonMixin, TimeStampMixin, OnboardingMixin):
    person = models.OneToOneField(PriyoMoneyUser, on_delete=models.CASCADE, related_name='bd_user_additional_info')
    purpose = models.TextField()
    estimated_tx_usd = models.DecimalField(decimal_places=2, max_digits=10,
                                           validators=[MinValueValidator(Decimal('0.01')),
                                                       MaxValueValidator(Decimal('1000000.00'))])

    profession = models.CharField(max_length=255, null=True, blank=True)
    organization = models.CharField(max_length=255, null=True, blank=True)
    social_media_profile = models.CharField(max_length=255, null=True, blank=True)
    linkedin_profile = models.CharField(max_length=255, null=True, blank=True)
    reference_contacts = models.TextField(null=True, blank=True)
    year_of_experience = models.PositiveIntegerField(null=True, blank=True)

    _country_specific_required_fields_for_onboarding = {
        AllowedCountries.BD.value: ('purpose', 'estimated_tx_usd', 'profession')
    }

    def get_country(self):
        return self.person.get_country()

    def get_user(self):
        return self.person


class UserLocation(PersonMixin, SoftDeleteMixin, TimeStampMixin):
    user = models.ForeignKey(PriyoMoneyUser, on_delete=models.CASCADE)
    latitude = models.DecimalField(max_digits=16, decimal_places=11)
    longitude = models.DecimalField(max_digits=16, decimal_places=11)
    type = models.CharField(max_length=64, choices=LocationTypes.choices())

    objects = SoftDeleteManager()

    def get_user(self):
        return self.user


class UserSourceOfIncome(PersonMixin, TimeStampMixin):
    user = models.ForeignKey(PriyoMoneyUser, on_delete=models.CASCADE, related_name="user_source_of_income")
    name = models.CharField(max_length=64)
    url = models.CharField(max_length=255, null=True, blank=True)
    details = models.TextField()

    def get_user(self):
        return self.user


class UserContactReference(PersonMixin, TimeStampMixin):
    user = models.ForeignKey(PriyoMoneyUser, on_delete=models.CASCADE, related_name="user_contact_reference")
    name = models.CharField(max_length=64, null=True, blank=True)
    relation = models.CharField(max_length=255, null=True, blank=True)
    mobile_number = models.CharField(max_length=255, null=True, blank=True)
    email_address = models.CharField(max_length=255, null=True, blank=True)
    address = models.TextField()

    def get_user(self):
        return self.user


class ExternalCustomerIdentification(TimeStampMixin):
    external_customer = models.ForeignKey('beneficiary.ExternalCustomer', on_delete=models.CASCADE,
                                          related_name='related_identifications')
    identification_class = models.CharField(max_length=16, choices=IDType.choices())
    identification_number = models.CharField(max_length=64)


class UserIdentification(TimeStampMixin):
    user = models.ForeignKey(PriyoMoneyUser, on_delete=models.CASCADE, related_name="related_identifications")
    identification_class = models.CharField(max_length=16, choices=IDType.choices())
    identification_number = models.CharField(max_length=64)
    verification = models.ForeignKey('verifications.PersonaVerification', null=True, blank=True,
                                     on_delete=models.SET_NULL)

    class Meta:
        unique_together = ('user', 'identification_class', 'identification_number')

    def get_user(self):
        return self.user

    def get_user_set(self):
        return [self.user]

    def fetch_details(self):
        if self.user.get_country() == AllowedCountries.BD.value and self.identification_class == IDType.id.value:
            self.fetch_porichoy_details()

    def get_details(self):
        return UserIdentificationDetails.objects.filter(identification_number=self.identification_number,
                                                        identification_class=self.identification_class).order_by(
            '-created_at')

    def fetch_porichoy_details(self):
        identification_details = UserIdentificationDetails.objects.create(
            source=IdentificationInfoSource.PORICHOY.value,
            identification_number=self.identification_number,
            identification_class=self.identification_class,
            date_of_birth=self.user.date_of_birth)

        identification_details.fetch_from_porichoy()


class UserIdentificationDetails(TimeStampMixin):
    identification_class = models.CharField(max_length=16, choices=IDType.choices())
    identification_number = models.CharField(max_length=64)

    source = models.CharField(max_length=32, choices=IdentificationInfoSource.choices(), null=True, blank=True)

    full_name_en = models.CharField(max_length=128, null=True, blank=True)
    full_name_bn = models.CharField(max_length=128, null=True, blank=True)

    father_name_en = models.CharField(max_length=128, null=True, blank=True)
    father_name_bn = models.CharField(max_length=128, null=True, blank=True)

    mother_name_en = models.CharField(max_length=128, null=True, blank=True)
    mother_name_bn = models.CharField(max_length=128, null=True, blank=True)

    spouse_name_en = models.CharField(max_length=128, null=True, blank=True)
    spouse_name_bn = models.CharField(max_length=128, null=True, blank=True)

    present_address_en = models.CharField(max_length=256, null=True, blank=True)
    present_address_bn = models.CharField(max_length=256, null=True, blank=True)

    permanent_address_en = models.CharField(max_length=256, null=True, blank=True)
    permanent_address_bn = models.CharField(max_length=256, null=True, blank=True)

    gender = models.CharField(max_length=16, null=True, blank=True)
    profession = models.CharField(max_length=64, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    image = models.ForeignKey('file_uploader.Documents', on_delete=models.PROTECT, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    api_response = models.JSONField(null=True, blank=True)

    def fetch_from_porichoy(self):
        from api_clients.porichoy_client import PorichoyClient
        porichoy_client = PorichoyClient()

        try:
            response = porichoy_client.nid_info_fetch(nid_number=self.identification_number,
                                                      date_of_birth=self.date_of_birth)
        except RequestException as e:
            raise CUSTOM_ERROR_LIST.PORICHOY_API_ERROR(message="API Client error")

        self.api_response = response

        if len(response.get('errors')) != 0:
            errors = response.get('errors')
            error_message = ", ".join(f"{error.get('message')}" for error in errors)
            self.error_message = error_message
            self.save()
        else:
            if 'data' in response and 'nid' in response['data']:
                data = response['data']['nid']
                self.parse_data_from_porichoy_response(data)
                self.save()
                self.get_porichoy_image(data)

        self.full_clean()

    def parse_data_from_porichoy_response(self, data):
        self.full_name_en = data.get('fullNameEN')
        self.full_name_bn = data.get('fullNameBN')
        self.father_name_en = data.get('fathersNameEN')
        self.father_name_bn = data.get('fathersNameBN')
        self.mother_name_en = data.get('mothersNameEN')
        self.mother_name_bn = data.get('mothersNameBN')
        self.spouse_name_en = data.get('spouseNameEN')
        self.spouse_name_bn = data.get('spouseNameBN')
        self.present_address_en = data.get('presentAddressEN')
        self.present_address_bn = data.get('presentAddressBN')
        self.permanent_address_en = data.get('permenantAddressEN')
        self.permanent_address_bn = data.get('permanentAddressBN')
        self.gender = data.get('gender')
        self.profession = data.get('profession')

    def get_porichoy_image(self, data):
        image_download_url = data.get('photoUrl')
        if not image_download_url:
            return

        file_name = "NID_" + self.identification_number + ".jpg"

        from file_uploader.manager import DocumentsManager

        assign_to = {
            'app_label': self._meta.app_label,
            'model_name': self._meta.model_name,
            'id': self.id,
            'assign_to_field': 'image'
        }

        DocumentsManager().upload_documents_with_celery(request=make_dummy_request(service=ServiceList.ADMIN.value),
                                                        download_url=image_download_url,
                                                        file_name=file_name,
                                                        bucket_folder_name="PORICHOY",
                                                        doc_type=DocumentType.PORICHOY_IMAGE.value,
                                                        doc_name=file_name,
                                                        assign_to=assign_to,
                                                        related_resource_type=RelatedResourceType.CUSTOMER.value)


class UserOnboardingStep(PersonMixin, TimeStampMixin):
    user = models.ForeignKey(PriyoMoneyUser, on_delete=models.CASCADE, related_name='onboarding_steps')
    step = models.CharField(max_length=32, choices=OnboardingSteps.choices())
    time_taken = models.DurationField(null=True, serialize=False, editable=False)

    def save(self, *args, **kwargs):
        if not self.pk:
            done_steps = self.user.onboarding_steps.all()
            if len(done_steps) > 0:
                last_step_time = max(done_steps, key=lambda step: step.created_at).created_at
                self.time_taken = timezone.now() - last_step_time

        super().save(*args, **kwargs)

    class Meta:
        unique_together = ('user', 'step')

    def get_user(self):
        return self.user


class UserSourceOfHearing(PersonMixin, TimeStampMixin):
    user = models.OneToOneField(PriyoMoneyUser, on_delete=models.CASCADE, related_name="user_source_of_hearing")
    source_of_hearing = models.CharField(max_length=32, choices=UserSourceOfHearingOptions.choices())

    def get_user(self):
        return self.user


class PlaidAuthorizationRequest(TimeStampMixin):
    auth_request_id = models.CharField(unique=True, max_length=64)
    profile = models.ForeignKey(Profile, on_delete=models.PROTECT, related_name="plaid_connection_requests")
    status = models.CharField(choices=PlaidAuthorizationRequestStatus.choices(), max_length=16)
    redirection_url = models.URLField()


class Note(TimeStampMixin):
    item_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    item_id = models.PositiveIntegerField()
    item_object = GenericForeignKey('item_type', 'item_id')

    note = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    note_type = models.CharField(max_length=16, choices=NoteType.choices())

    document = models.ForeignKey('file_uploader.Documents', on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['item_type', 'item_id']),
        ]


class UserEducation(TimeStampMixin):
    user = models.ForeignKey(PriyoMoneyUser, on_delete=models.CASCADE, related_name="educations")
    institution_name = models.CharField(max_length=255)
    degree_title = models.CharField(max_length=128)
    field_of_study = models.CharField(max_length=128)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "degree_title", "institution_name"],
                name="unique_education_per_user"
            )
        ]

    def get_user(self):
        return self.user

    def get_user_set(self):
        return [self.user]


class UserExperience(TimeStampMixin):
    user = models.ForeignKey(PriyoMoneyUser, on_delete=models.CASCADE, related_name="experiences")
    job_position = models.CharField(max_length=128)
    organization = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    employment_type = models.CharField(max_length=32, choices=EmploymentStatus.choices())
    responsibilities = models.TextField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    def get_user(self):
        return self.user

    def get_user_set(self):
        return [self.user]


class UserForeignUniversity(TimeStampMixin):
    user = models.OneToOneField(PriyoMoneyUser, on_delete=models.CASCADE, related_name="foreign_universities")
    university_name = models.CharField(max_length=255)
    student_id = models.CharField(max_length=64, blank=True, null=True)
    course_name = models.CharField(max_length=128)
    duration_of_course = models.CharField(max_length=32, blank=True, null=True)
    course_start_date = models.DateField()
    annual_exp_tuition_fee_in_cent = models.IntegerField(default=0)
    annual_exp_other_fees_in_cent = models.IntegerField(default=0)
    advance_remittance_amount_in_cent = models.IntegerField(default=0)
    deadline_date_of_advance_remittance = models.DateField(blank=True, null=True)
    is_advance_remittance_amount_refundable = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "university_name", "course_name"],
                name="unique_foreign_university_per_user"
            )
        ]

    def get_user(self):
        return self.user

    def get_user_set(self):
        return [self.user]


class UserFinancialInfo(TimeStampMixin):
    user = models.OneToOneField(PriyoMoneyUser, on_delete=models.CASCADE, related_name="financial_info")
    foreign_currency_purchase_date = models.DateField(blank=True, null=True)
    purchased_currency_amount_in_cent = models.IntegerField(default=0)
    scholarship_title = models.CharField(max_length=255, blank=True, null=True)
    scholarship_amount_in_cent = models.IntegerField(default=0)
    scholarship_period = models.CharField(max_length=255, blank=True, null=True)
    estimated_income_in_cent_from_part_time_per_month = models.IntegerField(default=0)
    remittance_by_other_channels = models.TextField(blank=True, null=True)
    willing_to_return_to_bd = models.BooleanField(default=False)

    def get_user(self):
        return self.user

    def get_user_set(self):
        return [self.user]


class UserFinancerInfo(TimeStampMixin):
    user = models.OneToOneField(PriyoMoneyUser, on_delete=models.CASCADE, related_name="financer_info")
    name = models.CharField(max_length=255)
    address = models.TextField()
    profession = models.CharField(max_length=128)
    nationality = models.CharField(max_length=64)
    mobile_number = models.CharField(max_length=32, null=True)
    relationship_with_student = models.CharField(max_length=128)
    are_parents_alive = models.BooleanField(default=True)
    reason_parents_not_financing = models.TextField(blank=True, null=True)

    def get_user(self):
        return self.user

    def get_user_set(self):
        return [self.user]