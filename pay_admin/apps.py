from django.apps import AppConfig


class PayAdminConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pay_admin'

    def ready(self):
        import pay_admin.signals
