from unittest import mock
from rest_framework import status
from business.tests.helpers import create_sample_business
from utilities.testutils import USClientAPITestCase, skip_if_sqlite
from core.enums import ProfileType
from core.models import PriyoMoneyUser
from file_uploader.enums import DocumentType, RelatedResourceType
from file_uploader.models import Documents


def create_business_document(user, business, name='XYZ'):
    document = Documents.objects.create(
        uploader=user,
        profile=business.profile,
        doc_type=DocumentType.IDENTITY_DOCUMENTATION.value,
        doc_name=name,
        related_resource_type=RelatedResourceType.BUSINESS.value,
        uploaded_file_name='xxx'
    )
    document.full_clean()
    return document


# Create your tests here.
class FileUploadTest(USClientAPITestCase):
    def create_base_user(self):
        return PriyoMoneyUser.objects.create(
            one_auth_uuid='xxx',
            profile_type=ProfileType.BUSINESS.value,
            synctera_user_id='xxx',
            is_verified_internal_user=True,
        )

    @skip_if_sqlite
    @mock.patch('django.core.files.storage.default_storage.exists', mock.MagicMock(return_value=False))
    def test_multiple_business_document_filter_by_business(self):
        business1 = create_sample_business(user=self.user, fake_ein="12-3556789")
        business2 = create_sample_business(user=self.user, fake_ein="12-3456798")
        business1_document1 = create_business_document(user=self.user, business=business1, name="A")
        business2_document1 = create_business_document(user=self.user, business=business2, name="B")
        business2_document2 = create_business_document(user=self.user, business=business2, name="C")
        business2_document3 = create_business_document(user=self.user, business=business2, name="C")

        response = self.api_client.get(f'/business-documents/?business={business2.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json().get('count'), 2)

        response = self.api_client.get(f'/business-documents/?business={business1.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json().get('count'), 1)
