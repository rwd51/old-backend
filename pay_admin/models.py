import jwt
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from pay_admin.enums import MetabaseResourceType
from django.conf import settings


# Create your models here.
class PayAdmin(AbstractUser):
    email = models.EmailField(unique=True)

    class Meta:
        verbose_name = _("pay_admin_user")
        verbose_name_plural = _("pay_admin_users")


class MetabaseResource(models.Model):
    resource_name = models.CharField(max_length=255, unique=True, primary_key=True)
    resource_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    resource_type = models.CharField(max_length=255, choices=MetabaseResourceType.choices())

    def get_embed_url(self, start_time=None):
        if not start_time:
            start_time = timezone.now()

        payload = {
            "resource": {self.resource_type.lower(): self.resource_id},
            "params": {},
            "exp": round(start_time.timestamp()) + (60 * settings.METABASE_EMBED_URL_EXPIRATION_MINUTES)
        }
        token = jwt.encode(payload, settings.METABASE_SECRET_KEY, algorithm="HS256")
        iframeUrl = settings.METABASE_SITE_URL + "/embed/dashboard/" + token
        return iframeUrl
