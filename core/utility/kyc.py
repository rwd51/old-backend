from rest_framework import status

from accounts.enums import EntityType
from api_clients.synctera_client import SyncteraClient
from common.email import EmailSender
from common.views import CommonTaskManager
from core.enums import ProfileApprovalStatus
from core.models import PriyoMoneyUser
from django.db import transaction


class KycCreationManager(CommonTaskManager):
    entity_type = EntityType.KYC.value
    view_class_name = __qualname__

    @classmethod
    def perform_third_party_api_call(cls, validated_data, idempotent_key, **kwargs):
        person_id = validated_data.get('user_id')
        person = PriyoMoneyUser.objects.get(id=person_id)
        synctera_client = SyncteraClient()

        return synctera_client.create_kyc_without_document(person, idempotent_key)

    @staticmethod
    def get_verification_status(synctera_response, synctera_user_id):
        verification_status = synctera_response.get('verification_status')
        if not verification_status:
            synctera_client = SyncteraClient()
            synctera_response, status_code = synctera_client.get_person(synctera_user_id)
            if status.is_success(status_code):
                verification_status = synctera_response.get('verification_status')
        return ProfileApprovalStatus.get_kyc_status_from_response(verification_status)

    @classmethod
    def perform_db_update(cls, synctera_response, validated_data, **kwargs):
        from core.serializers import PriyoMoneyUserSerializer

        person_id = validated_data.get('user_id')
        person = PriyoMoneyUser.objects.get(id=person_id)
        approval_status = cls.get_verification_status(synctera_response, person.synctera_user_id)

        with transaction.atomic():
            user = PriyoMoneyUser.objects.select_for_update().get(id=person.id)
            previous_approval_status = user.profile_approval_status

            if previous_approval_status != approval_status:
                user.profile_approval_status = approval_status
                user.save(update_fields=['profile_approval_status'])

        EmailSender(user=person).send_kyc_status_change_email(previous_approval_status, approval_status)

        return PriyoMoneyUserSerializer(instance=person).data
