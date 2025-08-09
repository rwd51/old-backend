import uuid
from django.db.models.signals import pre_save
from django.dispatch import receiver

from business.models import Business
from core.enums import ProfileType
from core.models import PriyoMoneyUser, Profile
from linked_business.models import LinkedBusiness


def attach_profile_on_instance(instance, profile_type):
    if hasattr(instance, 'profile'):
        return

    profile = Profile.objects.create(profile_type=profile_type)
    profile.full_clean()
    instance.profile = profile


@receiver(pre_save, sender=PriyoMoneyUser, dispatch_uid=uuid.uuid4())
def create_profile_on_user_creation(instance, **kwargs):
    attach_profile_on_instance(instance, profile_type=ProfileType.PERSON.value)


@receiver(pre_save, sender=Business, dispatch_uid=uuid.uuid4())
def create_profile_on_business_creation(instance, **kwargs):
    attach_profile_on_instance(instance, profile_type=ProfileType.BUSINESS.value)


@receiver(pre_save, sender=LinkedBusiness, dispatch_uid=uuid.uuid4())
def create_profile_on_linked_business_creation(instance, **kwargs):
    attach_profile_on_instance(instance, profile_type=ProfileType.LINKED_BUSINESS.value)
