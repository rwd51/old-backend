from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from common.email import EmailSender
from pay_admin.models import PayAdmin


@receiver(post_save, sender=PayAdmin)
def create_profile_on_user_creation(instance: PayAdmin, created, **kwargs):
    if created and settings.AUTOSEND_EMAIL:
        EmailSender(admin=instance).send_admin_email(context='new_admin_user_alert_broadcast_email')
