from django.urls import path, include
from rest_framework.routers import SimpleRouter
from students.viewsets import UserEducationViewSet, UserExperienceViewSet, UserForeignUniversityViewSet, \
    UserFinancialInfoViewSet, UserFinancerInfoViewSet, StudentUserViewSet, StudentPrimaryInfoViewSet

app_name = 'students'

router = SimpleRouter(trailing_slash=True)
router.register(r'student-first-step', StudentPrimaryInfoViewSet)
router.register(r'educations', UserEducationViewSet)
router.register(r'experiences', UserExperienceViewSet)
router.register(r'foreign-universities', UserForeignUniversityViewSet)
router.register(r'financial-info', UserFinancialInfoViewSet)
router.register(r'financer-info', UserFinancerInfoViewSet)
router.register(r'student-users', StudentUserViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
