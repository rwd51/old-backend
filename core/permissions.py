from rest_framework.permissions import BasePermission
from core.enums import ServiceList
from utilities.helpers import get_priyo_business


def is_admin(request):
    return hasattr(request, 'service') and request.service == ServiceList.ADMIN.value


def is_client(request):
    return hasattr(request, 'service') and request.service == ServiceList.CLIENT.value


def is_synctera(request):
    return hasattr(request, 'service') and request.service == ServiceList.SYNCTERA.value


def is_persona(request):
    return hasattr(request, 'service') and request.service == ServiceList.PERSONA.value


def is_priyo_business(request):
    return hasattr(request, 'service') and request.service == ServiceList.PRIYO_BUSINESS.value


def is_bdpay(request):
    return hasattr(request, 'service') and request.service == ServiceList.BDPAY.value


class IsSynctera(BasePermission):
    message = 'You do not have necessary permission'

    def has_permission(self, request, view):
        return is_synctera(request)


class IsPersona(BasePermission):
    message = 'You do not have necessary permission'

    def has_permission(self, request, view):
        return is_persona(request)


class IsPriyoBusiness(BasePermission):
    """Priyo Business can access objects if priyo business account is in the user set of the object"""
    message = 'You do not have necessary permission'

    def has_permission(self, request, view):
        return is_priyo_business(request)

    def has_object_permission(self, request, view, obj):
        return obj.belongs_to_priyo_business()


class IsAdmin(BasePermission):
    message = 'You do not have necessary permission'

    def has_permission(self, request, view):
        return is_admin(request)

    def has_object_permission(self, request, view, obj):
        return is_admin(request)


class IsOwner(BasePermission):
    """User can access objects if obj.get_user_set() contains user"""
    message = 'You do not have necessary permissions'

    def has_permission(self, request, view):
        return is_client(request)

    def has_object_permission(self, request, view, obj):
        return request.user in obj.get_user_set()


class IsBDPay(BasePermission):
    message = 'You do not have necessary permissions'

    def has_permission(self, request, view):
        return is_bdpay(request)


class IsClient(BasePermission):
    """All authenticated users can access objects"""
    message = 'You do not have necessary permissions'

    def has_permission(self, request, view):
        return is_client(request)


class CanGet(BasePermission):
    message = 'Method not allowed'

    def has_permission(self, request, view):
        return request.method.upper() == "GET"


ReadOnlyAdmin = IsAdmin & CanGet
ReadOnlyOwner = IsOwner & CanGet
ReadOnlyClient = IsClient & CanGet
ReadOnlyPriyoBusiness = IsPriyoBusiness & CanGet
