import logging

from django.utils import timezone
from rest_framework.exceptions import ValidationError
from common.email import EmailSender
from common.views import CommonProfileManager
from core.enums import ProfileApprovalStatus, AllowedCountries, ProfileType, OnboardingSteps, AdminReviewStatus
from core.helpers import upload_persona_documents_to_synctera
from core.models import PriyoMoneyUser, UserMetaData
from dues.tasks import DueCreationTask
from pay_admin.models import PayAdmin
from core.utility.disclosure import PersonDisclosureManager
from core.utility.kyc import KycCreationManager
from core.utility.onboarding_step_handler import OnboardingStepManager
from core.utility.person import PersonCreationManager
from error_handling.error_list import CUSTOM_ERROR_LIST
from subscription.helpers import is_user_subscribed_for_onboarding
from subscription.models import Subscription
from verifications.celery_tasks.persona_kyc import PersonaKycManager
from django.db import transaction
from django.conf import settings

logger = logging.getLogger(__name__)


class PersonManager(CommonProfileManager):

    def __init__(self, person: PriyoMoneyUser, admin: PayAdmin = None):
        self.person = person
        self.admin = admin
        self._handler_dict = {
            ProfileApprovalStatus.AWAITING_PROFILE_COMPLETION.value: self.handle_awaiting_profile_completion,
            ProfileApprovalStatus.PROFILE_INFO_SAVED.value: self.handle_profile_info_saved,
            ProfileApprovalStatus.AWAITING_ADMIN_APPROVAL.value: self.handle_awaiting_admin_approval,
            ProfileApprovalStatus.PROFILE_COMPLETED.value: self.handle_profile_completed,
            ProfileApprovalStatus.MANUAL_KYC_ACCEPTED.value: self.handle_manual_kyc_accepted,
            ProfileApprovalStatus.MANUAL_KYC_REJECTED.value: self.handle_manual_kyc_rejected,
        }

    def should_run_kyc_with_persona(self):
        return self.person.get_country() == AllowedCountries.BD.value

    def create_person_synctera(self):
        self.call_celery(entity_type=PersonCreationManager.entity_type,
                         view_class_name=PersonCreationManager.view_class_name,
                         wait_for_pub=True)

    def submit_kyc_synctera(self, run_document_verification=False, re_run_kyc=False):
        self.person.refresh_from_db()
        if re_run_kyc or self.person.profile_approval_status != ProfileApprovalStatus.KYC_ACCEPTED.value:
            with transaction.atomic():
                user = PriyoMoneyUser.objects.select_for_update().get(id=self.person.id)
                user.profile_approval_status = ProfileApprovalStatus.VERIFICATION_IN_PROGRESS.value
                user.save(update_fields=['profile_approval_status'])

            if self.should_run_kyc_with_persona():
                self.call_celery(entity_type=PersonaKycManager.entity_type,
                                 view_class_name=PersonaKycManager.view_class_name,
                                 run_document_verification=run_document_verification)
            else:
                self.call_celery(entity_type=KycCreationManager.entity_type,
                                 view_class_name=KycCreationManager.view_class_name,
                                 run_document_verification=run_document_verification)

            upload_persona_documents_to_synctera(self.person, async_upload=True)

    def submit_disclosure_acknowledge_synctera(self):
        self.call_celery(entity_type=PersonDisclosureManager.entity_type,
                         view_class_name=PersonDisclosureManager.view_class_name)

    def handle_awaiting_profile_completion(self):
        if self.person.profile_approval_status != ProfileApprovalStatus.AWAITING_SIGNUP_COMPLETION.value:
            raise ValidationError(detail={'profile_approval_status': [
                f'Person status is not {ProfileApprovalStatus.AWAITING_SIGNUP_COMPLETION.value}'
            ]})

        try:
            self.person.profile_approval_status = ProfileApprovalStatus.AWAITING_PROFILE_COMPLETION.value
            self.person.save(update_fields=['profile_approval_status'])
        except Exception as ex:
            raise ValidationError(detail={'profile_approval_status': [str(ex)]})

    def handle_awaiting_admin_approval(self):
        self.person.sync_shipping_address(force_overwrite=True)
        if self.person.profile_approval_status != ProfileApprovalStatus.AWAITING_PROFILE_COMPLETION.value:
            raise ValidationError(detail={'profile_approval_status': [
                f'Person status is not {ProfileApprovalStatus.AWAITING_PROFILE_COMPLETION.value}'
            ]})

        if not self.person.has_complete_onboarding_data():
            missing_fields = self.person.get_missing_onboarding_data()
            raise ValidationError(detail={'profile_approval_status': [
                f'Onboarding criteria not fulfilled: Missing {missing_fields}'
            ]})

        try:
            previous_approval_status = self.person.profile_approval_status
            if self.person.requires_admin_approval():
                approval_status = ProfileApprovalStatus.AWAITING_ADMIN_APPROVAL.value
                admin_review_status = AdminReviewStatus.IN_REVIEW.value
            else:
                approval_status = ProfileApprovalStatus.PROFILE_COMPLETED.value
                admin_review_status = AdminReviewStatus.AUTO_APPROVED.value

            self.person.admin_review_status = admin_review_status
            self.person.profile_approval_status = approval_status
            self.person.save(update_fields=['profile_approval_status', 'admin_review_status'])
            EmailSender(user=self.person).send_kyc_status_change_email(previous_approval_status, approval_status)
        except Exception as ex:
            raise ValidationError(detail={'profile_approval_status': [str(ex)]})

    def handle_profile_completed(self):
        if self.person.profile_approval_status != ProfileApprovalStatus.AWAITING_ADMIN_APPROVAL.value:
            raise ValidationError(detail={'profile_approval_status': [
                f'Person status is not {ProfileApprovalStatus.AWAITING_ADMIN_APPROVAL.value}'
            ]})

        try:
            if self.profile_approve_by_admin():
                previous_approval_status = self.person.profile_approval_status
                approval_status = ProfileApprovalStatus.PROFILE_COMPLETED.value
                self.person.profile_approval_status = approval_status
                self.person.save(update_fields=['profile_approval_status'])
                EmailSender(user=self.person).send_kyc_status_change_email(previous_approval_status, approval_status)

                if previous_approval_status == ProfileApprovalStatus.AWAITING_ADMIN_APPROVAL.value:
                    EmailSender(user=self.person).send_user_email(context='kyc_status_admin_approved_email')

                subscription: Subscription = self.person.get_active_onboarding_subscription()
                DueCreationTask.extend_paid_upto_date_using_kyc_acceptance_or_approval_date(subscription, admin_approved=True)

        except Exception as ex:
            raise ValidationError(detail={'profile_approval_status': [str(ex)]})

    def profile_approve_by_admin(self):
        if self.person.has_meta_data():
            meta_data: UserMetaData = self.person.user_meta_data
            if meta_data.profile_approved_by:
                if meta_data.profile_approved_by == self.admin:
                    raise ValidationError({"admin": "Same Admin User can't verify the User Profile"})

                is_profile_completed = True
                meta_data.profile_verified_by = self.admin
                meta_data.profile_verified_at = timezone.now()
                meta_data.save()
            else:
                meta_data.profile_approved_by = self.admin
                meta_data.profile_approved_at = timezone.now()
                meta_data.save()
                is_profile_completed = True if settings.PROFILE_APPROVAL_ADMIN_STEP == 1 else False
        else:
            UserMetaData.objects.get_or_create(user=self.person, profile_approved_by=self.admin)
            is_profile_completed = True if settings.PROFILE_APPROVAL_ADMIN_STEP == 1 else False

        return is_profile_completed

    def check_persona_requirements(self):
        persona_verification = self.person.persona_verifications.filter(is_active=True).first()
        if not persona_verification or not persona_verification.is_complete():
            raise CUSTOM_ERROR_LIST.PERSONA_VERIFICATION_NOT_COMPLETE

    def handle_profile_info_saved(self):
        if self.person.profile_approval_status != ProfileApprovalStatus.PROFILE_COMPLETED.value:
            raise ValidationError(detail={'profile_approval_status': [
                f'Person status is not {ProfileApprovalStatus.PROFILE_COMPLETED.value}'
            ]})

        if not self.person.has_complete_onboarding_data():
            missing_fields = self.person.get_missing_onboarding_data()
            raise ValidationError(detail={'profile_approval_status': [
                f'Onboarding criteria not fulfilled: Missing {missing_fields}'
            ]})

        if not is_user_subscribed_for_onboarding(self.person):
            raise ValidationError(detail={'subscription': 'Not done'})

        # TODO :: Temporarily skipped Persona for business on-boarding flow.
        # We had a plan to remove profile_type from PriyoMoneyUser
        if self.person.profile_type != ProfileType.BUSINESS.value:
            self.check_persona_requirements()

        if self.person.is_user_only_subscribed_for_bdt_account():
            self.person.profile_approval_status = ProfileApprovalStatus.KYC_ACCEPTED_FOR_BDT_ONLY.value
            self.person.save(update_fields=['profile_approval_status'])
            OnboardingStepManager(self.person).add_step(OnboardingSteps.KYC_ACCEPTANCE_FOR_BDT_ONLY.value)
        else:
            self.create_person_synctera()

    def check_bd_user_kyc_update_requirements(self):
        if self.person.get_country() != AllowedCountries.BD.value:
            raise ValidationError(detail={'country': f'Country must be bd'})

        allowed_current_statuses = [
            ProfileApprovalStatus.MANUAL_KYC_IN_REVIEW.value,
            ProfileApprovalStatus.MANUAL_KYC_REJECTED.value
        ]

        if self.person.profile_approval_status not in allowed_current_statuses:
            raise ValidationError({"user": "User status must be in review or rejected"})

    def handle_manual_kyc_accepted(self):
        self.check_bd_user_kyc_update_requirements()
        self.person.profile_approval_status = ProfileApprovalStatus.MANUAL_KYC_ACCEPTED.value
        self.person.save(update_fields=['profile_approval_status'])

    def handle_manual_kyc_rejected(self):
        self.check_bd_user_kyc_update_requirements()
        self.person.profile_approval_status = ProfileApprovalStatus.MANUAL_KYC_REJECTED.value
        self.person.save(update_fields=['profile_approval_status'])

    def change_state(self, new_state):
        if self.person.profile_approval_status == new_state:
            return

        self._handler_dict[new_state]()
