from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from django.conf import settings

from accounts.serializers.account import ProfileAssignmentSerializer
from beneficiary.models import ExternalCustomer
from business.models import Business
from core.models import PriyoMoneyUser
from file_uploader.enums import RelatedResourceType, BDPersonIdentityDocumentName, USPersonIdentityDocumentName
from file_uploader.validators import FileValidator
from file_uploader.models import Documents, SyncteraDocuments
from django.core.files.storage import default_storage
from common.helpers import google_bucket_file_url
from utilities.enums import RequestMethod
from file_uploader.enums import DocumentType
from core.enums import ServiceList
from utilities.helpers import convert_to_safe_text


class DocumentsSerializer(ModelSerializer, ProfileAssignmentSerializer):
    upload_file = serializers.FileField(required=True, write_only=True, validators=[
        FileValidator(max_size=5 * 1024 * 1024, allowed_extensions=('pdf', 'jpg', 'png', 'jpeg', 'gif'))])
    gcp_url = serializers.CharField(max_length=256, required=False, read_only=True)
    gcp_url_compressed = serializers.CharField(max_length=256, required=False, read_only=True)
    uploader_id = serializers.IntegerField(write_only=True, required=False)
    document_name = serializers.CharField(max_length=64, write_only=True, required=False)

    class Meta:
        model = Documents
        fields = '__all__'
        read_only_fields = (
        'id', 'uploader', 'profile', 'uploaded_file_name', 'gcp_url', 'gcp_url_compressed', 'related_resource_type',
        'created_at', 'updated_at', 'doc_name', 'verification_status')

    def to_internal_value(self, data):
        """This method overwrite only for uploading customer's additional identity documents"""
        data = super().to_internal_value(data)
        doc_type = data.get('doc_type')

        if doc_type == DocumentType.ADDITIONAL_IDENTITY_DOCS.value:
            self.validate_additional_identity_documents(data)

        return data

    def validate_additional_identity_documents(self, internal_data):
        document_name = internal_data.get('document_name')
        internal_data['document_name'] = convert_to_safe_text(document_name) if document_name else None

        if self.context['request'].service == ServiceList.ADMIN.value:
            uploader_id = internal_data.pop('uploader_id', None)
            user = PriyoMoneyUser.objects.filter(id=uploader_id).first() if uploader_id else None
            if user:
                internal_data['admin'] = self.context['request'].user
                internal_data['uploader'] = user
                internal_data['profile_id'] = user.profile.id
            else:
                err_msg = "The provided data is invalid for uploading user's additional identity document"
                raise serializers.ValidationError({"upload_file": err_msg})
        else:
            user = self.context['request'].user
            uploaded_docs = Documents.objects.filter(profile=user.profile,
                                                     doc_type=DocumentType.ADDITIONAL_IDENTITY_DOCS.value,
                                                     related_resource_type=RelatedResourceType.CUSTOMER.value).count()

            total_allowed_docs = int(settings.MAXIMUM_ALLOWED_IDENTITY_DOCS)
            if (uploaded_docs + 1) > total_allowed_docs:
                error_message = f"You can upload a maximum of {total_allowed_docs} additional identity documents. " \
                                f"You have already uploaded {uploaded_docs} additional documents!"
                raise serializers.ValidationError({"upload_file": error_message})

        return internal_data

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        uploaded_file_name = representation['uploaded_file_name']

        if default_storage.exists(uploaded_file_name):
            representation['gcp_url'] = google_bucket_file_url(uploaded_file_name)
        else:
            representation['gcp_url'] = ""

        from file_uploader.manager import ImageCompressManager
        compressed_file_url = ImageCompressManager.get_compressed_image_url(instance)
        if compressed_file_url:
            representation['gcp_url_compressed'] = compressed_file_url
        else:
            representation['gcp_url_compressed'] = ""

        return representation


class DocumentFileField(serializers.FileField):
    def __init__(self, **kwargs):
        validators = kwargs.pop('validators', [])
        validators.append(
            FileValidator(max_size=5 * 1024 * 1024, allowed_extensions=('pdf', 'doc', 'docx', 'jpg', 'png', 'jpeg'))
        )
        kwargs['validators'] = validators
        super().__init__(**kwargs)


class CommonDocumentUploadSerializer(serializers.Serializer):
    business_id = serializers.IntegerField()

    required_fields = []

    def validate(self, attrs):
        business_id = attrs.get("business_id")
        try:
            business = Business.objects.get(id=business_id)
        except Business.DoesNotExist:
            raise serializers.ValidationError({"business": f'Business does not exist with id {business_id}'})

        if self.context['request'].user not in business.get_user_set():
            raise serializers.ValidationError({"business": 'User does not have permission to access this business'})

        for field in self.required_fields:
            if self.context['request'].method == RequestMethod.POST.value and field not in attrs:
                raise serializers.ValidationError({field: f"No file was submitted."})

        return attrs


class USBusinessDocUploadSerializer(CommonDocumentUploadSerializer):
    certificate_incorporation = DocumentFileField(required=False)
    electronic_signature = DocumentFileField(required=False)
    ein_verification_letter = DocumentFileField(required=False)
    certificate_good_standing = DocumentFileField(required=False)
    business_tax_form = DocumentFileField(required=False)
    certificate_of_formation = DocumentFileField(required=False)
    dba_document = DocumentFileField(required=False)

    required_fields = ['certificate_incorporation', 'electronic_signature', 'ein_verification_letter']


class BDBusinessDocUploadSerializer(CommonDocumentUploadSerializer):
    nid_or_passport = DocumentFileField(required=False)
    trade_license = DocumentFileField(required=False)
    tin_certificate = DocumentFileField(required=False)
    certificate_incorporation = DocumentFileField(required=False)

    required_fields = ['nid_or_passport']


class USPersonIdentityDocUploadSerializer(serializers.Serializer):
    tax_document = serializers.ListField(required=False, child=DocumentFileField(required=False))
    pay_stub = serializers.ListField(required=False, child=DocumentFileField(required=False))
    ssn_card = serializers.ListField(required=False, child=DocumentFileField(required=False))
    govt_issued_id = serializers.ListField(required=False, child=DocumentFileField(required=False))
    birth_certificate = serializers.ListField(required=False, child=DocumentFileField(required=False))
    copy_of_passport = serializers.ListField(required=False, child=DocumentFileField(required=False))
    driving_license = serializers.ListField(required=False, child=DocumentFileField(required=False))
    proof_of_address = serializers.ListField(required=False, child=DocumentFileField(required=False))


class BDPersonIdentityDocUploadSerializer(serializers.Serializer):
    national_identity_card = DocumentFileField(required=False)
    proof_of_address = DocumentFileField(required=False)
    bank_document = DocumentFileField(required=False)
    birth_certificate = DocumentFileField(required=False)
    copy_of_passport = DocumentFileField(required=False)
    proof_of_income = DocumentFileField(required=False)

    required_fields = ['bank_document', 'proof_of_address']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = self.context['request'].user
        uploaded_docs = Documents.objects.filter(profile=user.profile,
                                                 doc_type=DocumentType.IDENTITY_DOCUMENTATION.value,
                                                 related_resource_type=RelatedResourceType.CUSTOMER.value).count()
        if uploaded_docs == 0:
            for field in self.required_fields:
                if self.context['request'].method == RequestMethod.POST.value and field not in attrs:
                    raise serializers.ValidationError({field: f"No file was submitted."})

        total_allowed_docs = int(settings.MAXIMUM_ALLOWED_IDENTITY_DOCS)

        if (len(attrs) + uploaded_docs) > total_allowed_docs:
            error_message = f"You can upload a maximum of {total_allowed_docs} identity documents. " \
                            f"You have already uploaded {uploaded_docs} documents. " \
                            f"Now You can upload only {total_allowed_docs - uploaded_docs} documents."
            raise serializers.ValidationError({"bank_document": error_message})

        return attrs


class PersonSourceOfIncomeDocUploadSerializer(serializers.Serializer):
    proof_of_income = DocumentFileField()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = self.context['request'].user
        uploaded_docs = Documents.objects.filter(profile=user.profile,
                                                 doc_type=DocumentType.IDENTITY_DOCUMENTATION.value,
                                                 related_resource_type=RelatedResourceType.CUSTOMER.value).count()

        total_allowed_docs = int(settings.MAXIMUM_ALLOWED_IDENTITY_DOCS)

        if (len(attrs) + uploaded_docs) > total_allowed_docs:
            error_message = f"You can upload a maximum of {total_allowed_docs} identity documents. " \
                            f"You have already uploaded {uploaded_docs} documents. " \
                            f"Now You can upload only {total_allowed_docs - uploaded_docs} documents."
            raise serializers.ValidationError({"bank_document": error_message})

        return attrs


class SyncteraDocumentsSerializer(ModelSerializer):
    class Meta:
        model = SyncteraDocuments
        fields = '__all__'


class ExternalCustomerDocumentSerializer(serializers.Serializer):
    business = serializers.PrimaryKeyRelatedField(queryset=Business.objects.none())
    external_customer = serializers.PrimaryKeyRelatedField(queryset=ExternalCustomer.objects.none())
    upload_file = DocumentFileField()
    doc_name = serializers.ChoiceField(choices=BDPersonIdentityDocumentName.choices() + USPersonIdentityDocumentName.choices())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            self.fields['business'].queryset = Business.objects.filter(creator=request.user)
            self.fields['external_customer'].queryset = ExternalCustomer.objects.filter(creator=request.user)


class StudentDocumentUploadSerializer(serializers.Serializer):
    student_photograph = DocumentFileField(required=False)
    financer_photograph = DocumentFileField(required=False)
    student_signature = DocumentFileField(required=False)
    financer_signature = DocumentFileField(required=False)
    admission_letter = DocumentFileField(required=False)
    educational_certificate = DocumentFileField(required=False)
    educational_transcript = DocumentFileField(required=False)
    university_invoice = DocumentFileField(required=False)
    financial_estimate = DocumentFileField(required=False)
    language_test_result = DocumentFileField(required=False)
    other_documents = DocumentFileField(required=False)

    required_fields = ['student_photograph', 'financer_photograph', 'student_signature', 'financer_signature',
                       'admission_letter', 'educational_certificate', 'educational_transcript', 'financial_estimate']
