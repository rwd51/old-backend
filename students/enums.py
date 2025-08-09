from core.enums import AbstractEnumChoices


class StudentOnboardingSteps(AbstractEnumChoices):
    STUDENT_PRIMARY_INFO = 'STUDENT_PRIMARY_INFO'
    STUDENT_EDUCATION = 'STUDENT_EDUCATION'
    STUDENT_EXPERIENCE = 'STUDENT_EXPERIENCE'
    STUDENT_FOREIGN_UNIVERSITY = 'STUDENT_FOREIGN_UNIVERSITY'
    STUDENT_FINANCIAL_INFO = 'STUDENT_FINANCIAL_INFO'
    STUDENT_FINANCER_INFO = 'STUDENT_FINANCER_INFO'
    STUDENT_DOCUMENTS_UPLOAD = 'STUDENT_DOCUMENTS_UPLOAD'
    STUDENT_APPLICATION_REVIEW = 'STUDENT_APPLICATION_REVIEW'
    STUDENT_ADMIN_APPROVAL = 'STUDENT_ADMIN_APPROVAL'

    @staticmethod
    def get_expected_student_onboarding_flow():
        return [
            StudentOnboardingSteps.STUDENT_PRIMARY_INFO.value,
            StudentOnboardingSteps.STUDENT_EDUCATION.value,
            StudentOnboardingSteps.STUDENT_EXPERIENCE.value,
            StudentOnboardingSteps.STUDENT_FOREIGN_UNIVERSITY.value,
            StudentOnboardingSteps.STUDENT_FINANCIAL_INFO.value,
            StudentOnboardingSteps.STUDENT_FINANCER_INFO.value,
            StudentOnboardingSteps.STUDENT_DOCUMENTS_UPLOAD.value,
            StudentOnboardingSteps.STUDENT_APPLICATION_REVIEW.value,
            StudentOnboardingSteps.STUDENT_ADMIN_APPROVAL.value,
        ]

    @staticmethod
    def get_possible_steps_before(step):
        return StudentOnboardingSteps.values()[:StudentOnboardingSteps.values().index(step)]

    @staticmethod
    def get_possible_steps_after(step):
        return StudentOnboardingSteps.values()[StudentOnboardingSteps.values().index(step) + 1:]