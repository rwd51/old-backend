from django.urls import path, include
from rest_framework.routers import SimpleRouter
from file_uploader.viewsets import FileUploaderViewSet, BDUserDocumentsUploaderViewSet, \
    ExternalCustomerDocumentUploaderViewSet
from file_uploader.viewsets import BusinessDocumentsUploaderViewSet, KYCDocumentsUploaderViewSet, \
    UserSourceOfIncomeDocumentUploaderViewSet, StudentDocumentsUploaderViewSet

app_name = 'file_uploader'

router = SimpleRouter(trailing_slash=True)
router.register(r'business-documents', BusinessDocumentsUploaderViewSet)
router.register(r'kyc-identity-documents', KYCDocumentsUploaderViewSet)
router.register(r'user-source-of-income-document', UserSourceOfIncomeDocumentUploaderViewSet)
router.register(r'bd/user-identity-documents', BDUserDocumentsUploaderViewSet)
router.register(r'file-upload', FileUploaderViewSet)
router.register(r'business-owner-documents', ExternalCustomerDocumentUploaderViewSet)
router.register(r'student-documents', StudentDocumentsUploaderViewSet)


urlpatterns = [
    path('', include(router.urls)),
]
