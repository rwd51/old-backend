from django.urls import path, include
from rest_framework.routers import SimpleRouter
from core.views import APILogFilterSearchChoices, UserIdentificationView, SendTestEmailView, \
    APILogUserSearchChoices, UserMaskedMobileEmail, PersonVerifyView, BDManualKYCView, UserOnboardingFlowView, \
    SyncKYCView, PlaidAuthorizationRequestViewSet, BusinessSearchChoices, TariffSearchChoices, UserFullAccessView, \
    IncomingPlaidConnectionViewSet
from core.viewsets import PriyoMoneyUserViewSet, UserMobileNumberViewSet, UserAddressViewSet, TerminateUserView, \
    SocureIdvViewSet, UserAdditionalInfoViewSet, UserBasicInfoViewSet, UserOnboardingStepViewSet, \
    UserSMSLogViewSet, UserStatusUpdateViewSet, UserLocationViewSet, UserIdentityNumberViewSet, \
    UserSourceOfIncomeViewSet, UserSourceOfHearingViewSet, NoteViewSet, UserContactReferenceViewSet, NoteCountView, \
    UpdateAdminReviewStatusView

app_name = 'core'

router = SimpleRouter(trailing_slash=True)
router.register(r'user', PriyoMoneyUserViewSet)
router.register(r'user-basic-info', UserBasicInfoViewSet)
router.register(r'user-mobile', UserMobileNumberViewSet)
router.register(r'socure-idv', SocureIdvViewSet)
router.register(r'user-address', UserAddressViewSet)
router.register(r'sms-log', UserSMSLogViewSet)
router.register(r'additional-info', UserAdditionalInfoViewSet)

# TODO: Remove bd/additional-info endpoint when app uses the new endpoint /additional-info
router.register(r'bd/additional-info', UserAdditionalInfoViewSet)
router.register(r'bd/user-identity-number', UserIdentityNumberViewSet)
router.register(r'location', UserLocationViewSet)
router.register(r'user-source-of-income', UserSourceOfIncomeViewSet)
router.register(r'user-contact-reference', UserContactReferenceViewSet)
router.register(r'onboarding-steps', UserOnboardingStepViewSet)
router.register(r'source-of-hearing', UserSourceOfHearingViewSet)
router.register(r'connect/plaid/authorize', PlaidAuthorizationRequestViewSet)
router.register(r'note', NoteViewSet)
router.register(r'incoming-plaid-connection', IncomingPlaidConnectionViewSet)

urlpatterns = [
    path('', include(router.urls)),

    path('api-log/filter-choices/fetch/', APILogFilterSearchChoices.as_view()),
    path('api-log/user-choices/fetch/', APILogUserSearchChoices.as_view()),
    path('business-choices/fetch/', BusinessSearchChoices.as_view()),
    path('tariff-choices/fetch/', TariffSearchChoices.as_view()),
    path('user-identification/', UserIdentificationView.as_view()),
    path('masked-mobile-email/', UserMaskedMobileEmail.as_view()),

    path('person-verify/', PersonVerifyView.as_view()),
    path('sync-kyc/', SyncKYCView.as_view()),
    path('bd/kyc/', BDManualKYCView.as_view()),
    path('user/<int:pk>/terminate/', TerminateUserView.as_view()),
    path('user/<int:pk>/update-admin-review-status/', UpdateAdminReviewStatusView.as_view()),
    path('user/<int:pk>/<str:synctera_user_status>/', UserStatusUpdateViewSet.as_view()),
    path('user-onboarding-flow/<int:user_id>/', UserOnboardingFlowView.as_view()),
    path('send-test-email/', SendTestEmailView.as_view()),
    path('user-full-access/', UserFullAccessView.as_view()),
    path('note-count/', NoteCountView.as_view()),
]
