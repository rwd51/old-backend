# Create your views here.
from django.utils import timezone

import jwt
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenBlacklistView

from core.permissions import IsAdmin
from pay_admin.filters import MetabaseResourceFilter
from pay_admin.models import PayAdmin, MetabaseResource
from pay_admin.serializers import AdminRegisterSerializer, ChangePasswordSerializer, AdminUserSerializer, \
    AdminUpdateSerializer, MetabaseResourceSerializer
from django.conf import settings

from priyomoney_client.settings import METABASE_SECRET_KEY, METABASE_SITE_URL


class AdminRegisterViewSet(ModelViewSet):
    http_method_names = ['post']
    permission_classes = [IsAdmin]

    queryset = PayAdmin.objects.all()
    serializer_class = AdminRegisterSerializer


class ChangePasswordViewSet(ModelViewSet):
    http_method_names = ['patch']
    permission_classes = [IsAdmin]

    queryset = PayAdmin.objects.all()
    serializer_class = ChangePasswordSerializer


class AdminUserViewSet(ReadOnlyModelViewSet):
    http_method_names = ['get']
    permission_classes = [IsAdmin]

    queryset = PayAdmin.objects.all()
    serializer_class = AdminUserSerializer


class AdminUpdateViewSet(ModelViewSet):
    http_method_names = ['patch']
    permission_classes = [IsAdmin]

    queryset = PayAdmin.objects.all()
    serializer_class = AdminUpdateSerializer

    def get_queryset(self):
        return PayAdmin.objects.filter(id=self.request.user.id)


class AdminTokenObtainPairView(TokenObtainPairView):
    http_method_names = ['post']
    permission_classes = [IsAdmin]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        return response


class AdminTokenRefreshView(TokenRefreshView):
    http_method_names = ['post']
    permission_classes = [IsAdmin]


class AdminLogoutView(TokenBlacklistView):
    http_method_names = ['post']
    permission_classes = [IsAdmin]


class MetabaseResourceViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch']
    permission_classes = [IsAdmin]
    serializer_class = MetabaseResourceSerializer
    filterset_class = MetabaseResourceFilter
    queryset = MetabaseResource.objects.all()
