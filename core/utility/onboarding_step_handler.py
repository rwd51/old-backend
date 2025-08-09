from core.enums import OnboardingSteps, ProfileApprovalStatus
from core.models import PriyoMoneyUser, UserOnboardingStep
from file_uploader.enums import DocumentType


class OnboardingStepManager:

    def __init__(self, user: PriyoMoneyUser):
        self.user = user

    def verify_step_completed(self, step: OnboardingSteps) -> bool:
        if step == OnboardingSteps.LOG_IN.value:
            return True  # If user exists, then this step is completed
        elif step == OnboardingSteps.REFERRAL.value:
            return self.user.get_used_referral_code() is not None
        elif step == OnboardingSteps.ONBOARDING_TYPE.value:
            return self.user.profile_type is not None
        elif step == OnboardingSteps.COUNTRY.value:
            return self.user.get_country() is not None
        elif step == OnboardingSteps.MOBILE.value:
            return self.user.has_mobile_number()
        elif step == OnboardingSteps.NAME_DOB.value:
            return self.user.first_name and self.user.last_name and self.user.date_of_birth
        elif step == OnboardingSteps.LOCATION.value:
            return self.user.has_browser_location()
        elif step == OnboardingSteps.ADDRESS.value:
            return self.user.legal_address is not None and self.user.legal_address.is_complete()
        elif step == OnboardingSteps.PROFILE_PICTURE.value:
            return self.user.has_document(DocumentType.PROFILE_IMAGE.value)
        elif step == OnboardingSteps.DOCUMENTS.value:
            return self.user.profile.documents.exists() and self.user.has_necessary_documents()
        elif step == OnboardingSteps.ADDITIONAL_INFO.value:
            return self.user.has_additional_info() and self.user.bd_user_additional_info.is_complete()
        elif step == OnboardingSteps.SUBSCRIPTION.value:
            return self.user.get_active_subscriptions().exists()
        elif step == OnboardingSteps.PERSONA_VERIFICATION.value:
            return self.user.is_persona_verified()
        elif step == OnboardingSteps.ADMIN_APPROVAL.value:
            applicable_states = ProfileApprovalStatus.get_states_after_admin_approval()
            applicable_states.remove(ProfileApprovalStatus.PROFILE_COMPLETED.value)
            return self.user.profile_approval_status in applicable_states
        elif step == OnboardingSteps.KYC_ACCEPTANCE_FOR_BDT_ONLY.value:
            return self.user.profile_approval_status == ProfileApprovalStatus.KYC_ACCEPTED_FOR_BDT_ONLY.value
        elif step == OnboardingSteps.SYNCTERA_PROFILE_CREATION.value:
            return self.user.synctera_user_id is not None
        elif step == OnboardingSteps.SSN.value:
            return self.user.ssn_submitted_to_synctera
        elif step == OnboardingSteps.KYC_SUBMISSION.value:
            return self.user.profile_approval_status in ProfileApprovalStatus.get_all_synctera_kyc_status()
        elif step == OnboardingSteps.KYC_ACCEPTANCE.value:
            return self.user.profile_approval_status == ProfileApprovalStatus.KYC_ACCEPTED.value
        else:
            raise ValueError(f"Cannot verify onboarding step: {step}")

    # Returns the step object and a boolean indicating whether the step was created or not
    def add_step(self, step: OnboardingSteps, check_completion=True):
        if check_completion and not self.verify_step_completed(step):
            return None, False
        return UserOnboardingStep.objects.get_or_create(user=self.user, step=step)

    def check_and_add_all_steps(self):
        for step in OnboardingSteps.values():
            self.add_step(step, check_completion=True)

    def get_onboarding_flow(self):
        """
        Returns the onboarding flow for the user. Each step is represented as a dictionary with the following keys
        - step: the step name
        - finished: a boolean indicating whether the step is completed or not
        """
        finished_steps = self.user.onboarding_steps.all().values_list('step', flat=True)
        expected_steps = OnboardingSteps.get_expected_onboarding_flow(self.user)
        return [
            {
                "step": step,
                "finished": step in finished_steps
            }
            for step in expected_steps
        ]

    def get_last_finished_step(self):
        finished_steps = self.user.onboarding_steps.all().values_list('step', flat=True)
        expected_steps = OnboardingSteps.get_expected_onboarding_flow(self.user)
        for step in expected_steps[::-1]:
            if step in finished_steps:
                return step
        return None
