from utilities.enums import AbstractEnumChoices
from error_handling.error_list import CUSTOM_ERROR_LIST


class ProfileApprovalStatus(AbstractEnumChoices):
    AWAITING_SIGNUP_COMPLETION = 'AWAITING_SIGNUP_COMPLETION'
    AWAITING_PROFILE_COMPLETION = 'AWAITING_PROFILE_COMPLETION'

    AWAITING_ADMIN_APPROVAL = 'AWAITING_ADMIN_APPROVAL'
    PROFILE_COMPLETED = 'PROFILE_COMPLETED'

    PROFILE_INFO_SAVED = 'PROFILE_INFO_SAVED'  # pseudo state

    PROFILE_CREATED_SYNCTERA = 'PROFILE_CREATED_SYNCTERA'
    VERIFICATION_IN_PROGRESS = 'VERIFICATION_IN_PROGRESS'  # temporary state

    KYC_UNVERIFIED = 'KYC_UNVERIFIED'
    KYC_PENDING = 'KYC_PENDING'
    KYC_PROVISIONAL = 'KYC_PROVISIONAL'
    KYC_ACCEPTED = 'KYC_ACCEPTED'
    KYC_REVIEW = 'KYC_REVIEW'
    KYC_REJECTED = 'KYC_REJECTED'

    MANUAL_KYC_IN_REVIEW = 'MANUAL_KYC_IN_REVIEW'
    MANUAL_KYC_ACCEPTED = 'MANUAL_KYC_ACCEPTED'
    MANUAL_KYC_REJECTED = 'MANUAL_KYC_REJECTED'

    KYC_ACCEPTED_FOR_BDT_ONLY = 'KYC_ACCEPTED_FOR_BDT_ONLY'
    KYC_REJECTED_FOR_BDT_ONLY = 'KYC_REJECTED_FOR_BDT_ONLY'

    @classmethod
    def get_states_after_admin_approval(cls):
        return [
            cls.PROFILE_COMPLETED.value,
            cls.PROFILE_CREATED_SYNCTERA.value,
            cls.VERIFICATION_IN_PROGRESS.value,
        ] + cls.get_all_synctera_kyc_status() + cls.get_all_bdt_only_kyc_status()

    @classmethod
    def get_kyc_status_from_response(cls, synctera_kyc_status):
        kyc_status = f'KYC_{synctera_kyc_status}'
        if kyc_status not in cls.__members__:
            raise CUSTOM_ERROR_LIST.SYNCTERA_REMOTE_API_ERROR_4002(f'unknown kyc status {kyc_status}')
        return cls.__getitem__(kyc_status).value

    @classmethod
    def get_all_synctera_kyc_status(cls):
        return [cls.KYC_UNVERIFIED.value,
                cls.KYC_PENDING.value,
                cls.KYC_PROVISIONAL.value,
                cls.KYC_ACCEPTED.value,
                cls.KYC_REVIEW.value,
                cls.KYC_REJECTED.value]

    @classmethod
    def get_all_bdt_only_kyc_status(cls):
        return [cls.KYC_ACCEPTED_FOR_BDT_ONLY.value, cls.KYC_REJECTED_FOR_BDT_ONLY.value]

    @classmethod
    def get_acceptable_statuses(cls):
        return [cls.KYC_ACCEPTED.value, cls.KYC_ACCEPTED_FOR_BDT_ONLY.value]

    @classmethod
    def get_kyc_status_in_readable(cls, kyc_status):
        available_statuses = {
            cls.AWAITING_SIGNUP_COMPLETION.value: 'Signup not Completed',
            cls.AWAITING_PROFILE_COMPLETION.value: 'Profile Incomplete',
            cls.PROFILE_INFO_SAVED.value: 'Profile Created',
            cls.PROFILE_CREATED_SYNCTERA.value: 'Profile Created to Synctera',
            cls.VERIFICATION_IN_PROGRESS.value: 'Verification in Progress',
            cls.AWAITING_ADMIN_APPROVAL.value: 'Admin Approval Pending',
            cls.PROFILE_COMPLETED.value: 'IDV Verification Pending',
            cls.KYC_UNVERIFIED.value: 'KYC Unverified',
            cls.KYC_PENDING.value: 'KYC Pending',
            cls.KYC_PROVISIONAL.value: 'KYC Provisional',
            cls.KYC_ACCEPTED.value: 'KYC Accepted',
            cls.KYC_REVIEW.value: 'KYC in Review',
            cls.KYC_REJECTED.value: 'KYC Rejected',
            cls.MANUAL_KYC_IN_REVIEW.value: 'KYC in Review',
            cls.MANUAL_KYC_ACCEPTED.value: 'KYC Accepted',
            cls.MANUAL_KYC_REJECTED.value: 'KYC Rejected',
            cls.KYC_ACCEPTED_FOR_BDT_ONLY.value: 'KYC Accepted for BDT Only',
            cls.KYC_REJECTED_FOR_BDT_ONLY.value: 'KYC Rejected for BDT Only',
        }
        return available_statuses.get(kyc_status, kyc_status)


class SyncteraUserStatus(AbstractEnumChoices):
    ACTIVE = 'ACTIVE'
    DECEASED = 'DECEASED'
    DENIED = 'DENIED'
    DORMANT = 'DORMANT'
    ESCHEAT = 'ESCHEAT'
    FROZEN = 'FROZEN'
    INACTIVE = 'INACTIVE'
    PROSPECT = 'PROSPECT'


class AddressType(AbstractEnumChoices):
    MAILING = 'MAILING'
    BILLING = 'BILLING'
    SHIPPING = 'SHIPPING'
    LEGAL = 'LEGAL'
    CARD_SHIPPING = 'CARD_SHIPPING'
    PRODUCT_SHIPPING = 'PRODUCT_SHIPPING'

    @classmethod
    def unique_types(cls):
        return [AddressType.LEGAL.value, AddressType.SHIPPING.value, AddressType.BILLING.value]


class ServiceList(AbstractEnumChoices):
    ADMIN = "ADMIN"
    CLIENT = "CLIENT"
    SYNCTERA = "SYNCTERA"
    PERSONA = "PERSONA"
    PRIYO_BUSINESS = "PRIYO_BUSINESS"
    BDPAY = "BDPAY"

    API_BACKEND = 'API_BACKEND'

    @classmethod
    def get_priyo_service_list(cls):
        return [
            ServiceList.ADMIN.value,
            ServiceList.CLIENT.value,
            ServiceList.PRIYO_BUSINESS.value,
            ServiceList.BDPAY.value
        ]


class SubServiceList(AbstractEnumChoices):
    WEB_BROWSER = "WEB_BROWSER"
    ANDROID_APP = "ANDROID_APP"


class DeviceType(AbstractEnumChoices):
    ANDROID = "android"
    IOS = "ios"
    WEB_BROWSER = "web_browser"


class ActionStatus(AbstractEnumChoices):
    SUCCESS = 'SUCCESS'
    IN_PROGRESS = 'IN_PROGRESS'
    FAILED = 'FAILED'

    UNKNOWN = 'UNKNOWN'
    SKIPPED = 'SKIPPED'  # for webhooks only


class SMSPurpose(AbstractEnumChoices):
    ACCOUNT_CREATION = 'ACCOUNT_CREATION'
    ADD_BENEFICIARY = 'ADD_BENEFICIARY'
    BD_TRANSFER = 'BD_TRANSFER'
    BUSINESS_UPDATE = 'BUSINESS_UPDATE'
    CARD_CREATION = 'CARD_CREATION'
    INVITATION = 'INVITATION'
    ISSUE_TICKET = 'ISSUE_TICKET'
    TRANSFER = 'TRANSFER'
    PROFILE_UPDATE = 'PROFILE_UPDATE'
    PROFILE_STATUS_UPDATE = 'PROFILE_STATUS_UPDATE'
    OTP = 'OTP'
    OTHER = 'OTHER'


class ProfileType(AbstractEnumChoices):
    PERSON = 'PERSON'
    BUSINESS = 'BUSINESS'
    LINKED_BUSINESS = 'LINKED_BUSINESS'

    @classmethod
    def choices(cls):
        return [
            (cls.PERSON.name, cls.PERSON.value),
            (cls.BUSINESS.name, cls.BUSINESS.value),
        ]

    @classmethod
    def extended_choices(cls):
        return [
            (cls.LINKED_BUSINESS.name, cls.LINKED_BUSINESS.value),
        ] + cls.choices()


class SocureProgressStatus(AbstractEnumChoices):
    WAITING_FOR_REDIRECT_METHOD = 'WAITING_FOR_REDIRECT_METHOD'
    WAITING_FOR_USER_TO_REDIRECT = 'WAITING_FOR_USER_TO_REDIRECT'
    WAITING_FOR_UPLOAD = 'WAITING_FOR_UPLOAD'
    DOCUMENTS_UPLOADED = 'DOCUMENTS_UPLOADED'
    VERIFYING = 'VERIFYING'
    VERIFICATION_COMPLETE = 'VERIFICATION_COMPLETE'
    VERIFICATION_ERROR = 'VERIFICATION_ERROR'


class AllowedCountries(AbstractEnumChoices):
    US = "US"
    BD = "BD"


class BdDivisions(AbstractEnumChoices):
    A = 'A'  # Barishal
    B = 'B'  # Chattogram
    C = 'C'  # Dhaka
    D = 'D'  # Khulna
    E = 'E'  # Mymensingh
    F = 'F'  # Rajshahi
    G = 'G'  # Rangpur
    H = 'H'  # Sylhet


class LocationTypes(AbstractEnumChoices):
    BROWSER = 'BROWSER'
    IP = 'IP'
    IOS = 'IOS'
    ANDROID = 'ANDROID'


class OnboardingSteps(AbstractEnumChoices):
    LOG_IN = 'LOG_IN'
    REFERRAL = 'REFERRAL'
    ONBOARDING_TYPE = 'ONBOARDING_TYPE'
    COUNTRY = 'COUNTRY'
    MOBILE = 'MOBILE'

    NAME_DOB = 'NAME_DOB'
    LOCATION = 'LOCATION'
    ADDRESS = 'ADDRESS'
    PROFILE_PICTURE = 'PROFILE_PICTURE'
    DOCUMENTS = 'DOCUMENTS'
    ADDITIONAL_INFO = 'ADDITIONAL_INFO'

    SUBSCRIPTION = 'SUBSCRIPTION'
    PERSONA_VERIFICATION = 'PERSONA_VERIFICATION'
    ADMIN_APPROVAL = 'ADMIN_APPROVAL'

    KYC_ACCEPTANCE_FOR_BDT_ONLY = 'KYC_ACCEPTANCE_FOR_BDT_ONLY'

    SYNCTERA_PROFILE_CREATION = 'SYNCTERA_PROFILE_CREATION'
    SSN = 'SSN'
    KYC_SUBMISSION = 'KYC_SUBMISSION'
    KYC_ACCEPTANCE = 'KYC_ACCEPTANCE'

    @staticmethod
    def get_possible_steps_before(step):
        return OnboardingSteps.values()[:OnboardingSteps.values().index(step)]

    @staticmethod
    def get_possible_steps_after(step):
        return OnboardingSteps.values()[OnboardingSteps.values().index(step) + 1:]

    @staticmethod
    def get_expected_onboarding_flow(user):
        country = user.get_country()
        steps = [
            OnboardingSteps.LOG_IN.value,
            OnboardingSteps.REFERRAL.value,
            OnboardingSteps.ONBOARDING_TYPE.value,
            OnboardingSteps.COUNTRY.value,
            OnboardingSteps.MOBILE.value,
        ]
        if country == AllowedCountries.BD.value:
            steps.extend([
                OnboardingSteps.NAME_DOB.value,
                OnboardingSteps.LOCATION.value,
                OnboardingSteps.ADDRESS.value,
                OnboardingSteps.PROFILE_PICTURE.value,
                OnboardingSteps.DOCUMENTS.value,
                OnboardingSteps.ADDITIONAL_INFO.value,
                OnboardingSteps.SUBSCRIPTION.value,
                OnboardingSteps.PERSONA_VERIFICATION.value,
                OnboardingSteps.ADMIN_APPROVAL.value,
            ])
            if user.is_user_only_subscribed_for_bdt_account():
                steps.extend([
                    OnboardingSteps.KYC_ACCEPTANCE_FOR_BDT_ONLY.value,
                ])
                if user.is_synctera_kyc_accepted():
                    steps.extend([
                        OnboardingSteps.SYNCTERA_PROFILE_CREATION.value,
                        OnboardingSteps.KYC_SUBMISSION.value,
                        OnboardingSteps.KYC_ACCEPTANCE.value,
                    ])
            else:
                steps.extend([
                    OnboardingSteps.SYNCTERA_PROFILE_CREATION.value,
                    OnboardingSteps.KYC_SUBMISSION.value,
                    OnboardingSteps.KYC_ACCEPTANCE.value,
                ])
        elif country == AllowedCountries.US.value:
            steps.extend([
                OnboardingSteps.NAME_DOB.value,
                OnboardingSteps.LOCATION.value,
                OnboardingSteps.ADDRESS.value,
                OnboardingSteps.DOCUMENTS.value,
                OnboardingSteps.SUBSCRIPTION.value,
                OnboardingSteps.PERSONA_VERIFICATION.value,
                OnboardingSteps.ADMIN_APPROVAL.value,
                OnboardingSteps.SYNCTERA_PROFILE_CREATION.value,
                OnboardingSteps.SSN.value,
                OnboardingSteps.KYC_SUBMISSION.value,
                OnboardingSteps.KYC_ACCEPTANCE.value
            ])
        return steps


class NoteType(AbstractEnumChoices):
    ADMIN = "ADMIN"
    SYNCTERA = "SYNCTERA"
    SYSTEM = "SYSTEM"


class UserSourceOfHearingOptions(AbstractEnumChoices):
    facebook = 'facebook'
    linkedin = 'linkedin'
    youtube = 'youtube'
    twitter = 'twitter'
    newspaper = 'newspaper'
    referral_from_a_friend = 'referral_from_a_friend'
    search_engine = 'search_engine'
    event_or_conference = 'event_or_conference'
    word_of_mouth = 'word_of_mouth'
    blog_or_article = 'blog_or_article'
    other = 'other'


class PlaidAuthorizationRequestStatus(AbstractEnumChoices):
    GRANTED = "GRANTED"
    ERROR = "ERROR"
    DENIED = "DENIED"


class AdminReviewStatus(AbstractEnumChoices):
    AUTO_APPROVED = 'AUTO_APPROVED'
    BLOCKED = 'BLOCKED'
    INITIATED = 'INITIATED'
    IN_REVIEW = 'IN_REVIEW'
    VERIFIED = 'VERIFIED'


class UserGender(AbstractEnumChoices):
    MALE = 'MALE'
    FEMALE = 'FEMALE'
    OTHER = 'OTHER'


class MaritalStatus(AbstractEnumChoices):
    SINGLE = 'SINGLE'
    MARRIED = 'MARRIED'
    DIVORCED = 'DIVORCED'
    WIDOWED = 'WIDOWED'
    SEPARATED = 'SEPARATED'
    OTHER = 'OTHER'


class EmploymentStatus(AbstractEnumChoices):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    SELF_EMPLOYED = "SELF_EMPLOYED"
    FREELANCE = "FREELANCE"
    CONTRACTUAL = "CONTRACTUAL"
    INTERNSHIP = "INTERNSHIP"
    OTHER = "OTHER"
