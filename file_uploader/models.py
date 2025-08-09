from django.db import models

from accounts.models.account import Account
from bdpay.models import BDTAccount
from core.models import Profile, PriyoMoneyUser
from pay_admin.models import PayAdmin
from utilities.model_mixins import TimeStampMixin, PersonMixin
from file_uploader.enums import DocumentType, RelatedResourceType, DocumentVerificationStatus, PersonaDocumentType
from verifications.models import PersonaVerification


class Documents(TimeStampMixin):
    uploader = models.ForeignKey(PriyoMoneyUser, on_delete=models.PROTECT, related_name='documents_uploader', null=True, blank=True)
    profile = models.ForeignKey(Profile, on_delete=models.PROTECT, related_name='documents', null=True, blank=True)
    doc_type = models.CharField(max_length=32, choices=DocumentType.choices())
    doc_name = models.CharField(max_length=64, null=True)  # A user-friendly name for the document
    related_resource_type = models.CharField(max_length=16, choices=RelatedResourceType.choices())
    uploaded_file_name = models.CharField(max_length=256)
    uploaded_compressed_file_name = models.CharField(max_length=256, null=True, blank=True)
    verification_status = models.CharField(max_length=16, choices=DocumentVerificationStatus.choices(),
                                           default=DocumentVerificationStatus.UNVERIFIED.value)

    class Meta:
        ordering = ('-updated_at',)

    def get_user(self):
        return self.uploader

    def get_owner(self):
        return self.profile.get_entity()

    def get_user_set(self):
        return self.profile.get_entity().get_user_set()

    def has_synctera_document(self):
        return hasattr(self, 'synctera_document') and self.synctera_document is not None


class SyncteraDocuments(TimeStampMixin):
    document = models.OneToOneField(Documents, on_delete=models.PROTECT, related_name='synctera_document')
    synctera_document_id = models.UUIDField()
    synctera_document_version = models.CharField(max_length=8)
    submitted_to_verify = models.BooleanField(default=False)
    synctera_upload_response = models.JSONField(null=True, blank=True)
    synctera_verify_response = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ('-updated_at',)


class PersonaDocuments(TimeStampMixin):
    document = models.OneToOneField(Documents, on_delete=models.PROTECT, related_name='persona_document')
    verification_id = models.CharField(max_length=64)
    persona_verification = models.ForeignKey(PersonaVerification, on_delete=models.PROTECT,
                                             related_name='persona_documents')
    persona_document_type = models.CharField(max_length=32, choices=PersonaDocumentType.choices())


class AccountStatements(TimeStampMixin):
    document = models.OneToOneField(Documents, on_delete=models.PROTECT, related_name='account_statement')
    synctera_statement_id = models.UUIDField(unique=True)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    statement_from_date = models.DateField()
    statement_to_date = models.DateField()

    class Meta:
        ordering = ('-statement_from_date',)


class BDTAccountStatements(TimeStampMixin):
    document = models.OneToOneField(Documents, on_delete=models.PROTECT, related_name='bdt_account_statement')
    bdt_account = models.ForeignKey(BDTAccount, on_delete=models.PROTECT)

    statement_from_date = models.DateField()
    statement_to_date = models.DateField()

    class Meta:
        ordering = ('-statement_from_date',)


class DocumentsUploadedByAdmin(models.Model):
    document = models.OneToOneField(Documents, on_delete=models.PROTECT, related_name='admin_uploaded_documents')
    admin = models.ForeignKey(PayAdmin, on_delete=models.SET_NULL, null=True, related_name='uploaded_by_admin')


class RemittanceCertificates(TimeStampMixin):
    document = models.OneToOneField(Documents, on_delete=models.PROTECT, related_name='remittance_certificates')
    bdt_account = models.ForeignKey(BDTAccount, on_delete=models.PROTECT, null=True, blank=True)
    certificate_from_date = models.DateField()
    certificate_to_date = models.DateField()

    class Meta:
        ordering = ('-certificate_from_date',)


class ExternalCustomerDocument(TimeStampMixin):
    document = models.OneToOneField(Documents, on_delete=models.PROTECT, related_name='external_customer_document')
    external_customer = models.ForeignKey("beneficiary.ExternalCustomer", on_delete=models.PROTECT, related_name='documents')


class StudentOnboardingDocument(TimeStampMixin):
    document = models.OneToOneField(Documents, on_delete=models.PROTECT, related_name='onboarding_document')
    user = models.ForeignKey(PriyoMoneyUser, on_delete=models.PROTECT, related_name='documents')
