



from students.enums import StudentOnboardingSteps
from students.models import StudentOnboardingStep, StudentPrimaryInfo
from core.models import PriyoMoneyUser, UserEducation, UserExperience, UserForeignUniversity, UserFinancialInfo, UserFinancerInfo
from file_uploader.enums import DocumentType


class StudentOnboardingStepManager:
    def __init__(self, user: PriyoMoneyUser):
        self.user = user

    def verify_step_completed(self, step: StudentOnboardingSteps) -> bool:
        if step == StudentOnboardingSteps.STUDENT_PRIMARY_INFO.value:
            return StudentPrimaryInfo.objects.filter(user=self.user).exists()
        elif step == StudentOnboardingSteps.STUDENT_EDUCATION.value:
            return UserEducation.objects.filter(user=self.user).exists()
        elif step == StudentOnboardingSteps.STUDENT_EXPERIENCE.value:
            return UserExperience.objects.filter(user=self.user).exists()
        elif step == StudentOnboardingSteps.STUDENT_FOREIGN_UNIVERSITY.value:
            return UserForeignUniversity.objects.filter(user=self.user).exists()
        elif step == StudentOnboardingSteps.STUDENT_FINANCIAL_INFO.value:
            return UserFinancialInfo.objects.filter(user=self.user).exists()
        elif step == StudentOnboardingSteps.STUDENT_FINANCER_INFO.value:
            return UserFinancerInfo.objects.filter(user=self.user).exists()
        elif step == StudentOnboardingSteps.STUDENT_DOCUMENTS_UPLOAD.value:
            return self.user.profile.documents.filter(doc_type=DocumentType.STUDENT_DOCUMENTS.value).exists()
        elif step == StudentOnboardingSteps.STUDENT_APPLICATION_REVIEW.value:
            # Custom logic for application review
            return False
        elif step == StudentOnboardingSteps.STUDENT_ADMIN_APPROVAL.value:
            # Check if student application is approved
            return False
        else:
            raise ValueError(f"Cannot verify student onboarding step: {step}")

    def add_step(self, step: StudentOnboardingSteps, check_completion=True):
        if check_completion and not self.verify_step_completed(step):
            return None, False
        return StudentOnboardingStep.objects.get_or_create(user=self.user, step=step)

    def check_and_add_all_steps(self):
        for step in StudentOnboardingSteps.values():
            self.add_step(step, check_completion=True)

    def get_student_onboarding_flow(self):
        finished_steps = self.user.student_onboarding_steps.all().values_list('step', flat=True)
        expected_steps = StudentOnboardingSteps.get_expected_student_onboarding_flow()
        return [
            {
                "step": step,
                "finished": step in finished_steps
            }
            for step in expected_steps
        ]

    def get_last_finished_step(self):
        finished_steps = self.user.student_onboarding_steps.all().values_list('step', flat=True)
        expected_steps = StudentOnboardingSteps.get_expected_student_onboarding_flow()
        for step in expected_steps[::-1]:
            if step in finished_steps:
                return step
        return None