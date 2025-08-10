from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="Priyo Pay Backend Project",
        default_version='v0.4.9',
        description="Priyo Pay :: Get your Digital Wallet along with a USA Bank Account.",
        contact=openapi.Contact(email="zs@priyo.com"),
        license=openapi.License(name="Copyright © 2023 Priyo"),
    ),
    public=True,
    authentication_classes=[],
    permission_classes=[permissions.AllowAny, ],
)
