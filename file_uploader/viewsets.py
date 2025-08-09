import os
import re
import uuid

from django.db.models import Q
from django.conf import settings
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status

from api_clients.synctera_client import SyncteraClient
from business.enums import BusinessAddressType
from common.helpers import google_bucket_file_upload, google_bucket_file_delete
from core.enums import AllowedCountries, ProfileType
from file_uploader.enums import BDBusinessDocumentName, DocumentVerificationStatus, \
    RelatedResourceType, USPersonIdentityDocumentName, BDPersonIdentityDocumentName, StudentDocumentName
from business.models import Business
from business.views.manager import BusinessManager
from core.permissions import IsAdmin, IsOwner, IsClient
from core.models import Profile
from error_handling.error_list import CUSTOM_ERROR_LIST
from file_uploader.filters import UserDocumentsFilter
from file_uploader.models import Documents, SyncteraDocuments, DocumentsUploadedByAdmin, ExternalCustomerDocument
from file_uploader.serializers import USBusinessDocUploadSerializer, DocumentsSerializer, BDBusinessDocUploadSerializer, \
    USPersonIdentityDocUploadSerializer, BDPersonIdentityDocUploadSerializer, PersonSourceOfIncomeDocUploadSerializer, \
    ExternalCustomerDocumentSerializer, StudentDocumentUploadSerializer
from file_uploader.enums import DocumentType, BusinessDocumentName
from core.permissions import is_admin


class FileUploaderViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch']
    permission_classes = [IsOwner | IsAdmin]

    serializer_class = DocumentsSerializer
    queryset = Documents.objects.all()
    filterset_class = UserDocumentsFilter

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Documents.objects.none()
        if is_admin(self.request):
            return self.queryset

        related_businesses = self.request.user.get_involved_businesses_queryset()
        user_profile = self.request.user.profile
        linked_businesses = self.request.user.get_involved_linked_business_queryset()
        documents = self.queryset.filter(Q(profile=user_profile) |
                                         Q(profile__business__in=related_businesses) |
                                         Q(profile__linked_business__in=linked_businesses))

        return documents.distinct("doc_name").order_by("doc_name", "-updated_at")

    def create(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        upload_file = serializer.validated_data.get("upload_file")
        profile_id = serializer.validated_data.get("profile_id")
        doc_type = serializer.validated_data.get("doc_type")
        admin = serializer.validated_data.get("admin")
        profile = Profile.objects.get(id=profile_id)
        user, doc_name = self.get_user_and_doc_name(request, serializer.validated_data)

        try:
            file_name, error_msg = self.upload_file_to_bucket(profile=profile,
                                                              upload_file=upload_file,
                                                              doc_name=doc_name,
                                                              doc_type=doc_type)
            if not file_name:
                error_msg = error_msg if error_msg else "Failed to upload file!"
                raise CUSTOM_ERROR_LIST.FAILED_TO_CREATE_ERROR_4009(error_msg)

            document = self.perform_db_update(user, profile, doc_type, doc_name, file_name, admin)
            return Response(data=self.serializer_class(document).data, status=status.HTTP_200_OK)
        except Exception as ex:
            return Response({'Error': str(ex)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    @classmethod
    def get_user_and_doc_name(cls, request, validated_data):
        uploader = validated_data.get("uploader")
        user = request.user
        if uploader and validated_data.get("admin"):
            user = uploader

        doc_type = validated_data.get("doc_type")
        document_name = validated_data.get("document_name")
        doc_name = doc_type.lower()
        if document_name and doc_type in DocumentType.ADDITIONAL_IDENTITY_DOCS.value:
            doc_name = document_name

        return user, doc_name

    @classmethod
    def build_file_name(cls, upload_file, bucket_folder_name, version_required=True):
        name, extension = os.path.splitext(upload_file.name)
        bucket_file_name = re.sub('[^a-zA-Z0-9]', '_', name)
        if len(bucket_file_name) > settings.GS_BUCKET_FILE_NAME_MAX_CHAR:
            bucket_file_name = bucket_file_name[:settings.GS_BUCKET_FILE_NAME_MAX_CHAR]
        file_version = f"_v{str(uuid.uuid4())[:8]}" if version_required else ""
        file_name = bucket_folder_name + "/" + bucket_file_name + file_version + extension
        return file_name

    @classmethod
    def upload_file_to_bucket_basic(cls, upload_file, bucket_folder_name):
        try:
            file_name = cls.build_file_name(upload_file, bucket_folder_name)
            uploaded_file_url, error_msg = google_bucket_file_upload(the_file=upload_file, file_name=file_name)
            return uploaded_file_url, error_msg
        except Exception as ex:
            raise CUSTOM_ERROR_LIST.DB_GENERAL_ERROR_4004(str(ex))

    @classmethod
    def upload_file_to_bucket(cls, profile, upload_file, doc_name, doc_type, version_required=True, external_customer=None):
        try:
            profile_type = profile.profile_type
            if not external_customer:
                bucket_folder_name = profile_type + "/p" + str(profile.id) + "/" + doc_name
            else:
                bucket_folder_name = f"{profile_type}/p{str(profile.id)}/external_customer/e{str(external_customer.id)}/{doc_name}"

            file_name = cls.build_file_name(upload_file, bucket_folder_name, version_required)

            document = Documents.objects.filter(profile=profile, doc_type=doc_type, doc_name=doc_name).order_by(
                '-updated_at').first()

            uploaded_file, error_msg = google_bucket_file_upload(the_file=upload_file, file_name=file_name)

            if (uploaded_file and doc_type == DocumentType.IDENTITY_DOCUMENTATION.value and
                    profile_type == ProfileType.BUSINESS.value and document and
                    not document.has_synctera_document() and document.uploaded_file_name != file_name):
                google_bucket_file_delete(document.uploaded_file_name)

            return uploaded_file, error_msg
        except Exception as ex:
            raise CUSTOM_ERROR_LIST.DB_GENERAL_ERROR_4004(str(ex))

    @classmethod
    def perform_db_update(cls, user, profile, doc_type, doc_name, file_name, admin=None, external_customer=None):
        resource_type = RelatedResourceType.CUSTOMER.value
        if (profile.profile_type in [RelatedResourceType.BUSINESS.value, RelatedResourceType.LINKED_BUSINESS.value]
                and not external_customer):
            resource_type = profile.profile_type

        doc_data = {
            'uploader': user,
            'profile': profile,
            'doc_type': doc_type,
            'doc_name': doc_name,
            'uploaded_file_name': file_name,
            'related_resource_type': resource_type
        }

        if doc_type in [DocumentType.IDENTITY_DOCUMENTATION.value, DocumentType.BD_BUSINESS_IDENTITY_DOCS.value]:
            document = Documents.objects.filter(profile=profile, doc_type=doc_type, doc_name=doc_name,
                                                synctera_document__isnull=True).order_by('-updated_at').first()
            if document and document.verification_status == DocumentVerificationStatus.UNVERIFIED.value:
                document.uploaded_file_name = file_name
                document.save()
            else:
                document = Documents.objects.create(**doc_data)
        elif doc_type in [DocumentType.STATEMENT.value, DocumentType.REMITTANCE_CERTIFICATE.value]:
            document = Documents.objects.filter(profile=profile, doc_type=doc_type, doc_name=doc_name,
                                                uploaded_file_name=file_name).first()
            if not document:
                document = Documents.objects.create(**doc_data)
        elif doc_type == DocumentType.EXTERNAL_CUSTOMER_DOCS.value:
            document = Documents.objects.filter(profile=profile, doc_type=doc_type, doc_name=doc_name,
                                                uploaded_file_name=file_name).first()
            if not document:
                document = Documents.objects.create(**doc_data)
                ExternalCustomerDocument.objects.create(
                    document=document,
                    external_customer=external_customer
                )

        else:
            document, created = Documents.objects.update_or_create(profile=profile, doc_type=doc_type,
                                                                   doc_name=doc_name, defaults=doc_data)

            if not created and doc_type == DocumentType.PROFILE_IMAGE.value:
                document.uploaded_compressed_file_name = None
                document.save()

            if admin and created:
                DocumentsUploadedByAdmin.objects.create(admin=admin, document=document)

        return document


class BusinessDocumentsUploaderViewSet(FileUploaderViewSet):
    http_method_names = ['get', 'post', 'patch']
    permission_classes = [IsOwner | IsAdmin]

    serializer_class = USBusinessDocUploadSerializer
    serializer_country_classes = {
        AllowedCountries.US.value: USBusinessDocUploadSerializer,
        AllowedCountries.BD.value: BDBusinessDocUploadSerializer
    }

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Documents.objects.none()
        if is_admin(self.request):
            return self.queryset

        related_businesses = self.request.user.get_involved_businesses_queryset()
        documents = self.queryset.filter(profile__business__in=related_businesses,
                                         doc_type=DocumentType.IDENTITY_DOCUMENTATION.value,
                                         related_resource_type=RelatedResourceType.BUSINESS.value)

        return documents.distinct("doc_name").order_by("doc_name", "-updated_at")

    def get_serializer_class(self):
        if self.action in ["get", "list", "retrieve"]:
            self.serializer_class = DocumentsSerializer
        else:
            try:
                business_id = self.request.data.get('business_id') or self.kwargs.get('pk')
                business = Business.objects.get(id=business_id)
                address = business.address.filter(address_type=BusinessAddressType.LEGAL.value).first()
                if address:
                    self.serializer_class = self.serializer_country_classes[address.country]
            except Business.DoesNotExist:
                pass
        return self.serializer_class

    def create(self, request, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        business_id = serializer.validated_data.get("business_id")
        business = Business.objects.get(id=business_id)

        response_data, error_msg = self.upload_business_identity_docs(serializer.validated_data, business, request.user)
        if error_msg:
            return Response({'Error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data=DocumentsSerializer(response_data, many=True).data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data, context={'request': request, 'id': kwargs.get('pk')})
        serializer.is_valid(raise_exception=True)
        business_id = kwargs.get('pk')
        business = Business.objects.get(id=business_id)
        response_data, error_msg = self.upload_business_identity_docs(serializer.validated_data, business, request.user)
        if error_msg:
            return Response({'Error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

        address = business.address.filter(address_type=BusinessAddressType.LEGAL.value).first()
        if business.is_kyb_submitted() and address and address.country == AllowedCountries.US.value:
            business_manager = BusinessManager(business=business)
            business_manager.submit_kyb_with_documents_synctera()

        return Response(data=DocumentsSerializer(response_data, many=True).data, status=status.HTTP_200_OK)

    @classmethod
    def upload_business_identity_docs(cls, validated_data, business, user):
        profile = business.profile
        documents, document_type = cls.get_business_document_names(business)
        response_data = []
        error_message = ""

        try:
            for doc_name in documents:
                uploaded_document = validated_data.get(doc_name)
                if uploaded_document:
                    file_name, error_msg = cls.upload_file_to_bucket(profile=profile,
                                                                     upload_file=uploaded_document,
                                                                     doc_name=doc_name,
                                                                     doc_type=document_type)

                    if file_name:
                        user_document = cls.perform_db_update(user, profile, document_type, doc_name, file_name)
                        response_data.append(user_document)
            if len(response_data) == 0:
                error_message = "Failed to upload files!"
        except Exception as ex:
            error_message = str(ex)

        return response_data, error_message

    @classmethod
    def get_business_document_names(cls, business):
        document_type = DocumentType.IDENTITY_DOCUMENTATION.value
        document_names = BusinessDocumentName.values()
        address = business.address.filter(address_type=BusinessAddressType.LEGAL.value).first()
        if address and address.country != AllowedCountries.US.value:
            document_type = DocumentType.BD_BUSINESS_IDENTITY_DOCS.value
            document_names = BDBusinessDocumentName.values()

        return document_names, document_type


class KYCDocumentsUploaderViewSet(FileUploaderViewSet):
    http_method_names = ['get', 'post']
    permission_classes = [IsOwner | IsAdmin]

    serializer_class = USPersonIdentityDocUploadSerializer

    def get_serializer_class(self):
        if self.action in ["get", "list", "retrieve"]:
            self.serializer_class = DocumentsSerializer

        return self.serializer_class

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Documents.objects.none()
        if is_admin(self.request):
            return self.queryset

        user_profile = self.request.user.profile
        documents = self.queryset.filter(profile=user_profile,
                                         doc_type=DocumentType.IDENTITY_DOCUMENTATION.value,
                                         related_resource_type=RelatedResourceType.CUSTOMER.value)

        order_by = self.get_order_by(self.request)
        if order_by:
            return documents.order_by(order_by)
        else:
            return documents.order_by("doc_name", "-updated_at")

    @classmethod
    def get_order_by(cls, request):
        """We will remove this part after implementing OrderingFilter like filter_backends"""
        order_by_as_str = ''
        order_by = request.query_params.get('order_by', '')
        # example: /kyc-identity-documents/?order_by=updated_at-DESC
        if order_by:
            order_by_name = order_by.split('-')[0]
            order_by_sign = order_by.split('-')[1]
            order_by_sign = '' if order_by_sign.lower() == 'asc' else '-'
            order_by_as_str = order_by_sign + order_by_name
        return order_by_as_str

    def create(self, request, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        response_data, error_msg = self.upload_person_identity_docs(serializer.validated_data, request.user)
        if error_msg:
            return Response({'Error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data=DocumentsSerializer(response_data, many=True).data, status=status.HTTP_200_OK)

    @classmethod
    def upload_person_identity_docs(cls, validated_data, user):
        profile = user.profile
        document_type = DocumentType.IDENTITY_DOCUMENTATION.value
        document_names = USPersonIdentityDocumentName.values()
        response_data = []
        error_message = ""
        total_allowed_docs = int(settings.MAXIMUM_ALLOWED_IDENTITY_DOCS)
        total_submitted_docs = cls.get_submitted_identity_docs_number(validated_data, document_names)
        already_uploaded_docs = Documents.objects.filter(profile=user.profile,
                                                         doc_type=DocumentType.IDENTITY_DOCUMENTATION.value,
                                                         related_resource_type=RelatedResourceType.CUSTOMER.value).count()

        if (total_submitted_docs + already_uploaded_docs) > total_allowed_docs:
            error_message = f"You can upload a maximum of {total_allowed_docs} identity documents. " \
                            f"You have already uploaded {already_uploaded_docs} documents. " \
                            f"Now You can upload only {total_allowed_docs - already_uploaded_docs} documents."
            return response_data, error_message

        try:
            for doc_name in document_names:
                uploaded_doc_list = validated_data.get(doc_name)
                if uploaded_doc_list:
                    for uploaded_document in uploaded_doc_list:
                        file_name, error_msg = cls.upload_file_to_bucket(profile=profile,
                                                                         upload_file=uploaded_document,
                                                                         doc_name=doc_name,
                                                                         doc_type=document_type)

                        if file_name:
                            user_document = cls.perform_db_update(user, profile, document_type, doc_name, file_name)
                            response_data.append(user_document)

                            if user.synctera_user_id:
                                cls.upload_document_to_synctera(user_document, uploaded_document, document_type, user)

            if len(response_data) == 0:
                error_message = "Failed to upload files!"
        except Exception as ex:
            error_message = str(ex)

        return response_data, error_message

    @classmethod
    def get_submitted_identity_docs_number(cls, validated_data, documents):
        identity_docs_number = 0
        for doc_name in documents:
            uploaded_doc_list = validated_data.get(doc_name)
            uploaded_doc_number = len(uploaded_doc_list) if uploaded_doc_list else 0
            identity_docs_number += uploaded_doc_number

        return identity_docs_number

    @classmethod
    def upload_document_to_synctera(cls, user_document, uploaded_doc_file, document_type, user):
        try:
            idempotent_key = f'{document_type}_KYC_ID_DOC{user_document.id}'
            synctera_client = SyncteraClient()
            doc_response, status_code = synctera_client.create_document(resource_id=user.synctera_user_id,
                                                                        resource_type=RelatedResourceType.CUSTOMER.value,
                                                                        doc_name=user_document.doc_name,
                                                                        doc_file=uploaded_doc_file,
                                                                        doc_type=user_document.doc_type,
                                                                        idempotent_key=idempotent_key)

            if not status.is_success(status_code):
                raise CUSTOM_ERROR_LIST.SYNCTERA_REMOTE_API_ERROR_4002(doc_response.get('detail'))

            return SyncteraDocuments.objects.create(document=user_document,
                                                    synctera_document_id=doc_response.get('id'),
                                                    synctera_document_version=doc_response.get('available_versions')[0],
                                                    synctera_upload_response=doc_response)
        except Exception as ex:
            raise CUSTOM_ERROR_LIST.DB_GENERAL_ERROR_4004(str(ex))


class BDUserDocumentsUploaderViewSet(KYCDocumentsUploaderViewSet):
    http_method_names = ['get', 'post']
    permission_classes = [IsOwner | IsAdmin]
    serializer_class = BDPersonIdentityDocUploadSerializer

    @classmethod
    def upload_person_identity_docs(cls, validated_data, user):
        profile = user.profile
        document_type = DocumentType.IDENTITY_DOCUMENTATION.value
        document_names = BDPersonIdentityDocumentName.values()
        response_data = []
        error_message = ""

        try:
            for doc_name in document_names:
                uploaded_document = validated_data.get(doc_name)
                if uploaded_document:
                    file_name, error_msg = cls.upload_file_to_bucket(profile=profile,
                                                                     upload_file=uploaded_document,
                                                                     doc_name=doc_name,
                                                                     doc_type=document_type)

                    if file_name:
                        user_document = cls.perform_db_update(user, profile, document_type, doc_name, file_name)
                        response_data.append(user_document)
        except Exception as ex:
            error_message = str(ex)

        return response_data, error_message


class UserSourceOfIncomeDocumentUploaderViewSet(BDUserDocumentsUploaderViewSet):
    http_method_names = ['get', 'post']
    permission_classes = [IsOwner | IsAdmin]
    serializer_class = PersonSourceOfIncomeDocUploadSerializer


class ExternalCustomerDocumentUploaderViewSet(FileUploaderViewSet):
    http_method_names = ['get', 'post']
    permission_classes = [IsClient | IsAdmin]
    serializer_class = ExternalCustomerDocumentSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Documents.objects.none()
        if is_admin(self.request):
            return self.queryset
        return Documents.objects.filter(user=self.request.user,
                                 doc_type=DocumentType.EXTERNAL_CUSTOMER_DOCS.value,
                                 )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        business = validated_data['business']
        doc_name = validated_data['doc_name']
        external_customer = validated_data['external_customer']
        try:
            file_name, error_msg = self.upload_file_to_bucket(
                profile=business.profile,
                upload_file=validated_data['upload_file'],
                doc_name=doc_name,
                doc_type=DocumentType.EXTERNAL_CUSTOMER_DOCS.value,
                external_customer=external_customer,
            )

            if not file_name:
                error_msg = error_msg if error_msg else "Failed to upload file!"
                raise CUSTOM_ERROR_LIST.FAILED_TO_CREATE_ERROR_4009(error_msg)
            self.perform_db_update(
                user=self.request.user,
                profile=business.profile,
                doc_type=DocumentType.EXTERNAL_CUSTOMER_DOCS.value,
                doc_name=doc_name,
                file_name=file_name,
                external_customer=external_customer,
            )
        except Exception as ex:
            return Response({'Error': str(ex)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_201_CREATED)


class StudentDocumentsUploaderViewSet(FileUploaderViewSet):
    http_method_names = ['get', 'post', 'patch']
    permission_classes = []  # Remove authentication temporarily
    serializer_class = StudentDocumentUploadSerializer

    def get_serializer_class(self):
        if self.action in ["get", "list", "retrieve"]:
            return DocumentsSerializer
        return self.serializer_class

    def list(self, request, *args, **kwargs):
        # Hardcode user_id 1255
        from django.contrib.auth.models import User
        hardcoded_user = User.objects.get(id=1255)
        request.user = hardcoded_user
        
        queryset = self.filter_queryset(self.get_queryset())
        
        # Use the serializer to get proper gcp_url values
        serializer = DocumentsSerializer(queryset, many=True, context={'request': request})
        serialized_data = serializer.data
        
        # Group documents by doc_name
        grouped_documents = {}
        for document_data in serialized_data:
            doc_name = document_data.get('doc_name')
            gcp_url = document_data.get('gcp_url', '')
            if doc_name:
                grouped_documents[doc_name] = gcp_url
        
        # Use the parent's pagination if available
        page = self.paginate_queryset(queryset)
        if page is not None:
            # Re-group only the paginated documents
            page_serializer = DocumentsSerializer(page, many=True, context={'request': request})
            page_data = page_serializer.data
            
            grouped_documents = {}
            for document_data in page_data:
                doc_name = document_data.get('doc_name')
                gcp_url = document_data.get('gcp_url', '')
                if doc_name:
                    grouped_documents[doc_name] = gcp_url
            
            return self.paginator.get_paginated_response([grouped_documents])
        
        # If no pagination, return custom format
        response_data = {
            'count': queryset.count(),
            'next': None,
            'previous': None,
            'start_index': 0,
            'end_index': queryset.count() - 1,
            'results': [grouped_documents]
        }
        return Response(response_data)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Documents.objects.none()
        
        # Hardcode user_id 1255
        from django.contrib.auth.models import User
        hardcoded_user = User.objects.get(id=1255)
        
        documents = self.queryset.filter(profile=hardcoded_user.profile,
                                         doc_type=DocumentType.STUDENT_DOCUMENTS.value,
                                         related_resource_type=RelatedResourceType.CUSTOMER.value)
        return documents.distinct("doc_name").order_by("doc_name", "-updated_at")

    def create(self, request, *args, **kwargs):
        # Hardcode user_id 1255
        from django.contrib.auth.models import User
        hardcoded_user = User.objects.get(id=1255)
        request.user = hardcoded_user
        
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        response_data, error_msg = self.upload_student_onboarding_docs(serializer.validated_data, hardcoded_user)
        if error_msg:
            return Response({'Error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data=DocumentsSerializer(response_data, many=True).data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        # Hardcode user_id 1255
        from django.contrib.auth.models import User
        hardcoded_user = User.objects.get(id=1255)
        request.user = hardcoded_user
        
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data, context={'request': request, 'id': kwargs.get('pk')})
        serializer.is_valid(raise_exception=True)

        response_data, error_msg = self.upload_student_onboarding_docs(serializer.validated_data, hardcoded_user)
        if error_msg:
            return Response({'Error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data=DocumentsSerializer(response_data, many=True).data, status=status.HTTP_200_OK)



    @classmethod
    def upload_student_onboarding_docs(cls, validated_data, user):
        document_type = DocumentType.STUDENT_DOCUMENTS.value
        documents = StudentDocumentName.values()
        response_data = []
        error_message = ""

        try:
            for doc_name in documents:
                uploaded_document = validated_data.get(doc_name)
                if uploaded_document:
                    file_name, error_msg = cls.upload_file_to_bucket(profile=user.profile,
                                                                     upload_file=uploaded_document,
                                                                     doc_name=doc_name,
                                                                     doc_type=document_type)

                    if file_name:
                        user_document = cls.perform_db_update(user, user.profile, document_type, doc_name, file_name)
                        response_data.append(user_document)
            if len(response_data) == 0:
                error_message = "Failed to upload files!"
        except Exception as ex:
            error_message = str(ex)

        return response_data, error_message
