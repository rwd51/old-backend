import io
import requests
from rest_framework import status
from django.apps import apps
from accounts.enums import EntityType
from common.helpers import google_bucket_file_url
from common.views import CommonTaskManager
from file_uploader.enums import DocumentType
from file_uploader.models import Documents
from file_uploader.viewsets import FileUploaderViewSet
import logging
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


class DocumentsManager(CommonTaskManager):
    entity_type = EntityType.DOCUMENT.value
    view_class_name = __qualname__

    def upload_documents_with_celery(self, request, download_url, file_name, bucket_folder_name, doc_type, doc_name,
                                     assign_to, related_resource_type):
        self.request = request
        self.call_celery(self.request, validated_data={
            'download_url': download_url,
            'file_name': file_name,
            'bucket_folder_name': bucket_folder_name,
            'doc_type': doc_type,
            'doc_name': doc_name,
            'assign_to': assign_to,
            'related_resource_type': related_resource_type
        }, wait_for_pub=True)

    @classmethod
    def get_file(cls, download_url):
        response = requests.request('GET', download_url)
        return response.content, response.status_code

    @classmethod
    def perform_third_party_api_call(cls, validated_data, idempotent_key, **kwargs):
        download_url = validated_data['download_url']
        file_name = validated_data['file_name']
        bucket_folder_name = validated_data['bucket_folder_name']

        file_bytes, status_code = cls.get_file(download_url)

        file = io.BytesIO(file_bytes)
        file.name = file_name

        uploaded_file_name, error_msg = FileUploaderViewSet.upload_file_to_bucket_basic(upload_file=file,
                                                                                        bucket_folder_name=bucket_folder_name)

        return uploaded_file_name, status.HTTP_201_CREATED

    @classmethod
    def perform_db_update(cls, response, validated_data, **kwargs):
        if response is None:
            return

        document = Documents.objects.create(doc_type=validated_data['doc_type'],
                                            doc_name=validated_data['doc_name'],
                                            related_resource_type=validated_data['related_resource_type'],
                                            uploaded_file_name=response)

        assign_to = validated_data['assign_to']
        if assign_to:
            model_class = apps.get_model(app_label=assign_to['app_label'], model_name=assign_to['model_name'])
            object = model_class.objects.get(pk=assign_to['id'])
            setattr(object, assign_to['assign_to_field'], document)
            object.save()


class ImageCompressManager:
    COMPRESS_WIDTH = 75
    COMPRESS_HEIGHT = 75

    @staticmethod
    def get_compressed_image_url(document: Documents):
        if not document or not document.uploaded_file_name or document.doc_type != DocumentType.PROFILE_IMAGE.value:
            return None

        if document.uploaded_compressed_file_name:
            return google_bucket_file_url(document.uploaded_compressed_file_name)
        try:
            ImageCompressManager.generate_compressed_image(document)
            return google_bucket_file_url(document.uploaded_compressed_file_name)
        except Exception as ex:
            logger.error(f"Failed to compress image, document id {document.pk} \n" + str(ex), exc_info=True)

    @staticmethod
    def generate_compressed_image(document: Documents):
        response = requests.request('GET', google_bucket_file_url(document.uploaded_file_name))
        if not status.is_success(response.status_code):
            logger.error("Failed to retrieve image from gcp bucket to compress")
            return None

        image = Image.open(io.BytesIO(response.content))
        ImageOps.exif_transpose(image, in_place=True)
        image.thumbnail((ImageCompressManager.COMPRESS_WIDTH, ImageCompressManager.COMPRESS_HEIGHT), Image.NEAREST)

        bucket_folder_name, file_name = ImageCompressManager._get_folder_name_and_file_name_for_compressed_file(document)
        image_file_obj = io.BytesIO()
        image_file_obj.name = file_name
        image.save(image_file_obj, format=image.format)

        uploaded_file_name, _ = FileUploaderViewSet.upload_file_to_bucket_basic(upload_file=image_file_obj,
                                                                                bucket_folder_name=bucket_folder_name)

        document.uploaded_compressed_file_name = uploaded_file_name
        document.save()

    @staticmethod
    def _get_folder_name_and_file_name_for_compressed_file(document: Documents):
        splitted_file_name = document.uploaded_file_name.rsplit('/', 1)
        folder_name = '/'.join(splitted_file_name[:-1])
        file_name = splitted_file_name[-1]
        bucket_folder_name = "compressed/" + folder_name
        return bucket_folder_name, file_name
