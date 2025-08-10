"""priyomoney_client URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include, re_path
from rest_framework.renderers import JSONOpenAPIRenderer
from rest_framework.schemas import get_schema_view, openapi
from priyomoney_client import settings

schema_view = get_schema_view(
    title='Priyo Pay REST API',
    version='0.4.4',
    generator_class=openapi.SchemaGenerator,
    renderer_classes=[JSONOpenAPIRenderer])

urlpatterns = [
    path('', include('core.urls')),
    path('', include('common.urls')),
    path('', include('accounts.urls')),
    path('', include('fees.urls')),
    path('', include('beneficiary.urls')),
    path('', include('file_uploader.urls')),
    path('', include('business.urls')),
    path('', include('disclosure.urls')),
    path('', include('invitation.urls')),
    path('', include('otp.urls')),
    path('', include('bd_transfer.urls')),
    path('', include('conversion_rate.urls')),
    path('', include('verifications.urls')),
    path('', include('external_payment.urls')),
    path('', include('ipay.urls')),
    path('', include('subscription.urls')),
    path('', include('dues.urls')),
    path('', include('products.urls')),
    path('', include('bdpay.urls')),
    path('', include('nosql.urls')),
    path('', include('topup.urls')),
    path('', include('coupon.urls')),
    path('', include('notification.urls')),
    path('', include('graph.urls')),
    path('', include('firebase.urls')),
    path('', include('payment_gateway.urls')),
    path('', include('students.urls')),
    path('', include('resource_pricing.urls')),
    path('admin/', include('pay_admin.urls')),
    path('admin/', include('admin_transfer.urls')),
    path('settings/', include('dynamic_settings.urls')),
    path('ticket/', include('ticket.urls')),
    path('webhook/', include('webhook.urls')),
    path('linked-business/', include('linked_business.urls')),
]

if settings.IS_SWAGGER_ENABLED:
    from priyomoney_client.swagger_conf import schema_view as swagger_schema_view
    urlpatterns.append(
        re_path(r'^swagger/$', swagger_schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui')
    )


