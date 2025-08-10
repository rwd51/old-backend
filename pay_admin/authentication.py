from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from core.enums import ServiceList


class PayAdminAuth(JWTAuthentication):
    def authenticate(self, request):
        if request.service != ServiceList.ADMIN.value:
            return None

        user = super().authenticate(request)
        if not user:
            raise AuthenticationFailed('Authentication credentials were not provided')
        return user
