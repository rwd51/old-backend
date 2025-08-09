from utilities.enums import AbstractEnumChoices


class DocumentType(AbstractEnumChoices):
    APPLICATION_DOCUMENTATION = "APPLICATION_DOCUMENTATION"
    IDENTITY_DOCUMENTATION = "IDENTITY_DOCUMENTATION"
    STATEMENT_DISCLOSURE = "STATEMENT_DISCLOSURE"
    TERMS_OF_SERVICE = "TERMS_OF_SERVICE"
    COMPLIANCE_REPORT = "COMPLIANCE_REPORT"
    STATEMENT = "STATEMENT"
    COMPANY_PROFILE_DOCUMENT = "COMPANY_PROFILE_DOCUMENT"
    CHECK_IMAGE = "CHECK_IMAGE"
    FINANCIAL_FILE = "FINANCIAL_FILE"
    BUSINESS_LOGO = "BUSINESS_LOGO"
    PROFILE_IMAGE = "PROFILE_IMAGE"
    SELFIE = "SELFIE"
    NID_OR_PASSPORT = "NID_OR_PASSPORT"
    ELECTRONIC_SIGNATURE = "ELECTRONIC_SIGNATURE"
    BD_BUSINESS_IDENTITY_DOCS = "BD_BUSINESS_IDENTITY_DOCS"
    PERSONA_DOCUMENT = "PERSONA_DOCUMENT"
    PORICHOY_IMAGE = "PORICHOY_IMAGE"
    PRODUCT_IMAGE = "PRODUCT_IMAGE"
    ADDITIONAL_IDENTITY_DOCS = "ADDITIONAL_IDENTITY_DOCS"
    ADMIN_DOCS = "ADMIN_DOCS"
    LINKED_BUSINESS_IDENTITY_DOCS = "LINKED_BUSINESS_IDENTITY_DOCS"
    REMITTANCE_CERTIFICATE = "REMITTANCE_CERTIFICATE"
    EXTERNAL_CUSTOMER_DOCS = "EXTERNAL_CUSTOMER_DOCS"
    STUDENT_DOCUMENTS = "STUDENT_DOCUMENTS"


class RelatedResourceType(AbstractEnumChoices):
    CUSTOMER = "CUSTOMER"
    BUSINESS = "BUSINESS"
    ACCOUNT = "ACCOUNT"
    PRODUCT = "PRODUCT"
    LINKED_BUSINESS = "LINKED_BUSINESS"


class BusinessDocumentName(AbstractEnumChoices):
    CERTIFICATE_INCORPORATION = "certificate_incorporation"
    CERTIFICATE_GOOD_STANDING = "certificate_good_standing"
    BUSINESS_TAX_FORM = "business_tax_form"
    ELECTRONIC_SIGNATURE = "electronic_signature"
    EIN_VERIFICATION_LETTER = "ein_verification_letter"
    CERTIFICATE_OF_FORMATION = "certificate_of_formation"
    DBA_DOCUMENT = "dba_document"


class BDBusinessDocumentName(AbstractEnumChoices):
    NID_OR_PASSPORT = "nid_or_passport"
    TRADE_LICENSE = "trade_license"
    TIN_CERTIFICATE = "tin_certificate"
    CERTIFICATE_INCORPORATION = "certificate_incorporation"


class DocumentVerificationStatus(AbstractEnumChoices):
    UNVERIFIED = "UNVERIFIED"
    IN_REVIEW = "IN_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class USPersonIdentityDocumentName(AbstractEnumChoices):
    TAX_DOCUMENT = "tax_document"
    PAY_STUB = "pay_stub"
    SSN_CARD = "ssn_card"
    GOVT_ISSUED_ID = "govt_issued_id"
    BIRTH_CERTIFICATE = "birth_certificate"
    COPY_OF_PASSPORT = "copy_of_passport"
    PROOF_OF_ADDRESS = "proof_of_address"
    DRIVING_LICENSE = "driving_license"


class PersonaDocumentType(AbstractEnumChoices):
    SELFIE_CENTER = "SELFIE_CENTER"
    SELFIE_LEFT = "SELFIE_LEFT"
    SELFIE_RIGHT = "SELFIE_RIGHT"
    PASSPORT_FRONT = "PASSPORT_FRONT"
    DRIVER_LICENSE_FRONT = "DRIVER_LICENSE_FRONT"
    DRIVER_LICENSE_BACK = "DRIVER_LICENSE_BACK"
    NID_FRONT = "NID_FRONT"
    NID_BACK = "NID_BACK"


class BDPersonIdentityDocumentName(AbstractEnumChoices):
    NATIONAL_IDENTITY_CARD = "national_identity_card"
    PROOF_OF_ADDRESS = "proof_of_address"
    BANK_DOCUMENT = "bank_document"
    BIRTH_CERTIFICATE = "birth_certificate"
    COPY_OF_PASSPORT = "copy_of_passport"
    PROOF_OF_INCOME = 'proof_of_income'


class LinkedBusinessDocumentName(AbstractEnumChoices):
    TRADE_LICENSE = "TRADE_LICENSE"
    TIN_CERTIFICATE = "TIN_CERTIFICATE"
    BANK_DOCUMENT = "BANK_DOCUMENT"


class StudentDocumentName(AbstractEnumChoices):
    STUDENT_PHOTOGRAPH = "student_photograph"
    FINANCER_PHOTOGRAPH = "financer_photograph"
    STUDENT_SIGNATURE = "student_signature"
    FINANCER_SIGNATURE = "financer_signature"
    ADMISSION_LETTER = "admission_letter"
    EDUCATIONAL_CERTIFICATE = "educational_certificate"
    EDUCATIONAL_TRANSCRIPT = "educational_transcript"
    UNIVERSITY_INVOICE = "university_invoice"
    FINANCIAL_ESTIMATE = "financial_estimate"
    LANGUAGE_TEST_RESULT = "language_test_result"
    OTHER_DOCUMENTS = "other_documents"
