import pytz
import uuid
from datetime import datetime
from django.conf import settings
from django.db.models import Q
from rest_framework import status

from accounts.enums import EntityType
from api_clients.synctera_client import SyncteraClient
from common.views import CommonTaskManager
from core.models import PriyoMoneyUser
from disclosure.enums import DisclosureProfile
from disclosure.models import Disclosure, PersonAcknowledgement
from error_handling.error_list import CUSTOM_ERROR_LIST


class PersonDisclosureManager(CommonTaskManager):
    entity_type = EntityType.DISCLOSURE.value
    view_class_name = __qualname__

    @classmethod
    def acknowledge_disclosure(cls, disclosure, person):
        if PersonAcknowledgement.objects.filter(disclosure=disclosure, person=person).exists():
            return

        disclosure_type = disclosure.type
        disclosure_version = disclosure.version
        disclosure_date = datetime.now(pytz.timezone(settings.TIME_ZONE)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        idempotent_key = f'IDM{disclosure.id}_{uuid.uuid4()}'

        synctera_client = SyncteraClient()
        acknowledge_response, status_code = synctera_client.disclosure_acknowledge(
            business_id=None,
            person_id=person.synctera_user_id,
            disclosure_type=disclosure_type,
            disclosure_date=disclosure_date,
            version=disclosure_version,
            idempotent_key=idempotent_key)

        if not status.is_success(status_code):
            error_msg = "Failed to send disclosure acknowledgement to synctera"
            raise CUSTOM_ERROR_LIST.SYNCTERA_REMOTE_API_ERROR_4002(error_msg)

        acknowledgement = {
            'disclosure': disclosure,
            'acknowledged': True,
            'ack_datetime': datetime.now(pytz.timezone(settings.TIME_ZONE)),
            'data': acknowledge_response,
            'person': person
        }
        PersonAcknowledgement.objects.create(**acknowledgement)

    @classmethod
    def perform_third_party_api_call(cls, validated_data, idempotent_key):
        person_id = validated_data.get('user_id')
        person = PriyoMoneyUser.objects.get(id=person_id)
        disclosures = Disclosure.objects.filter(is_active=True, target_profile=DisclosureProfile.PERSON.value)

        for disclosure in disclosures:
            cls.acknowledge_disclosure(disclosure=disclosure, person=person)

        return {}, status.HTTP_200_OK

    @classmethod
    def perform_db_update(cls, synctera_response, validated_data):
        from core.serializers import PriyoMoneyUserSerializer

        person_id = validated_data.get('user_id')
        person = PriyoMoneyUser.objects.get(id=person_id)
        return PriyoMoneyUserSerializer(instance=person).data
