import logging

from django.core.cache import cache

from accounts.enums import EntityType
from api_clients.synctera_client import SyncteraClient
from core.enums import ProfileApprovalStatus
from core.models import PriyoMoneyUser, UserIdentification
from error_handling.error_list import CUSTOM_ERROR_LIST
from verifications.enums import IDType

log = logging.getLogger(__name__)


class PersonCreationManager:
    entity_type = EntityType.USER.value
    view_class_name = __qualname__

    @classmethod
    def perform_third_party_api_call(cls, validated_data, idempotent_key):
        person_id = validated_data.get('user_id')
        person = PriyoMoneyUser.objects.get(id=person_id)

        identification = UserIdentification.objects.filter(user=person, identification_class=IDType.id.value).first()
        if not identification:
            identification = (
                UserIdentification.objects
                .filter(user=person, identification_class__in=[IDType.pp.value, IDType.dl.value])
                .order_by('-identification_class')
                .first()
            )

        synctera_client = SyncteraClient()
        return synctera_client.create_person(user=person,
                                             address=person.legal_address,
                                             mobile=person.user_mobile_number,
                                             idempotent_key=idempotent_key,
                                             identification=identification)

    @classmethod
    def perform_db_update(cls, person_response, validated_data):
        from core.serializers import PriyoMoneyUserSerializer

        person_id = validated_data.get('user_id')
        person = PriyoMoneyUser.objects.get(id=person_id)

        try:
            person.profile_approval_status = ProfileApprovalStatus.PROFILE_CREATED_SYNCTERA.value
            person.synctera_user_id = person_response.get('id')
            person.synctera_user_status = person_response.get('status')
            person.save()
        except Exception as ex:
            raise CUSTOM_ERROR_LIST.DB_GENERAL_ERROR_4004(str(ex))

        cls.remove_ssn_from_cache(person)

        return PriyoMoneyUserSerializer(instance=person).data

    @classmethod
    def remove_ssn_from_cache(cls, person):
        cache.delete(person.one_auth_uuid)
