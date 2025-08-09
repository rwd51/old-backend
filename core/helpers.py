from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers
from core.enums import ProfileApprovalStatus, ServiceList
from utilities.constants import COUNTRIES
from utilities.helpers import make_dummy_request
from verifications.enums import PersonaInquiryStatus


def get_dial_code_list():
    lst = []
    for x in COUNTRIES:
        lst.append(
            (x['dial_code'], "{country_code} ({dial_code})".format(country_code=x['name'], dial_code=x['dial_code'])))
    return lst


def get_country_choices():
    country_list = []
    for country in COUNTRIES:
        country_list.append((country['code'], country['name']))
    return country_list


def is_profile_completed(user):
    return user.profile_approval_status == ProfileApprovalStatus.PROFILE_COMPLETED.value


def upload_persona_documents_to_synctera(user, async_upload=False):
    """
    This method will upload persona documents to synctera asynchronously
    Throws exception if persona verification is not complete
    """

    from verifications.celery_tasks.synctera_doc_upload import SyncteraDocumentUploadManager
    request = make_dummy_request(user=user, service=ServiceList.CLIENT.value, method='POST')
    manager = SyncteraDocumentUploadManager()
    manager.upload_documents_with_celery(request, async_upload=async_upload)


def get_user_gender(user):
    """
        Returns M(default)/F/N. Try to fetch from persona and identification details if possible
    """
    default_gender = "M"
    # trying to fetch from identification details
    for identification in user.related_identifications.all():
        for identification_detail in identification.get_details():
            if identification_detail.gender:
                if identification_detail.gender.lower() == "male":
                    return "M"
                elif identification_detail.gender.lower() == "female":
                    return "F"
    # trying to fetch from successful persona verification
    user_verification = user.persona_verifications.filter(status__in=PersonaInquiryStatus.success_statuses(),
                                                          is_active=True).first()
    try:
        if user_verification:
            gender = user_verification.persona_response["included"][0]["attributes"]["sex"]
            if gender is not None:
                if gender.lower() == "male":
                    return "M"
                elif gender.lower() == "female":
                    return "F"
    except KeyError:
        pass
    return default_gender


class ContentTypeField(serializers.Field):
    def __init__(self, choices, **kwargs):
        self.choices = choices
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        try:
            for (key, content_type) in self.choices():
                if data == key:
                    return content_type
            raise ValueError()
        except (LookupError, TypeError, ValueError):
            raise serializers.ValidationError(f"Invalid data: {data}")

    def to_representation(self, value):
        for (key, content_type) in self.choices():
            if content_type == value:
                return key
        raise ValueError()


def get_note_item_choices():
    from core.models import PriyoMoneyUser
    from accounts.models.holds import AccountBalanceHold
    from business.models import Business
    from linked_business.models import LinkedBusiness
    from bdpay.models import BatchPaymentForUSDToBDTTransfer
    from subscription.models import Tariff
    return [
        ('user', ContentType.objects.get_for_model(PriyoMoneyUser)),
        ('hold_balance', ContentType.objects.get_for_model(AccountBalanceHold)),
        ('business', ContentType.objects.get_for_model(Business)),
        ('linked_business', ContentType.objects.get_for_model(LinkedBusiness)),
        ('batch_payment', ContentType.objects.get_for_model(BatchPaymentForUSDToBDTTransfer)),
        ('tariff', ContentType.objects.get_for_model(Tariff)),
    ]

