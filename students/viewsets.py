import logging

from django.db.models import Q
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from core.permissions import IsOwner
from core.models import PriyoMoneyUser
from core.permissions import is_admin, IsAdmin
# from core.serializers import PriyoMoneyUserSerializer  # replaced by StudentUserSerializer
from students.serializers import StudentUserSerializer
from core.filters import UserFilter
from core.models import UserEducation, UserExperience, UserForeignUniversity, UserFinancialInfo, UserFinancerInfo
from students.models import StudentPrimaryInfo
from students.filters import UserEducationFilterSet, UserExperienceFilterSet, UserFinancerInfoFilterSet, \
    UserFinancialInfoFilterSet, UserForeignUniversityFilterSet, StudentPrimaryInfoFilterSet
from students.serializers import (UserEducationSerializer, UserExperienceSerializer, UserForeignUniversitySerializer,
                                  UserFinancialInfoSerializer, UserFinancerInfoSerializer, StudentPrimaryInfoSerializer)

logger = logging.getLogger(__name__)


class StudentPrimaryInfoViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch']
    permission_classes = [IsAdmin | IsOwner]

    queryset = StudentPrimaryInfo.objects.all()
    serializer_class = StudentPrimaryInfoSerializer
    filterset_class = StudentPrimaryInfoFilterSet

    def get_queryset(self):
        if is_admin(self.request):
            return StudentPrimaryInfo.objects.all()
        return StudentPrimaryInfo.objects.filter(Q(user=self.request.user))


class UserEducationViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch']
    permission_classes = [IsAdmin | IsOwner]

    queryset = UserEducation.objects.all()
    serializer_class = UserEducationSerializer
    filterset_class = UserEducationFilterSet

    def get_queryset(self):
        if is_admin(self.request):
            return UserEducation.objects.all()
        return UserEducation.objects.filter(Q(user=self.request.user))


class UserExperienceViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch']
    permission_classes = [IsAdmin | IsOwner]

    queryset = UserExperience.objects.all()
    serializer_class = UserExperienceSerializer
    filterset_class = UserExperienceFilterSet

    def get_queryset(self):
        if is_admin(self.request):
            return UserExperience.objects.all()
        return UserExperience.objects.filter(Q(user=self.request.user))


class UserForeignUniversityViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch']
    permission_classes = [IsAdmin | IsOwner]

    queryset = UserForeignUniversity.objects.all()
    serializer_class = UserForeignUniversitySerializer
    filterset_class = UserForeignUniversityFilterSet

    def get_queryset(self):
        if is_admin(self.request):
            return UserForeignUniversity.objects.all()
        return UserForeignUniversity.objects.filter(Q(user=self.request.user))


class UserFinancialInfoViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch']
    permission_classes = [IsAdmin | IsOwner]

    queryset = UserFinancialInfo.objects.all()
    serializer_class = UserFinancialInfoSerializer
    filterset_class = UserFinancialInfoFilterSet

    def get_queryset(self):
        if is_admin(self.request):
            return UserFinancialInfo.objects.all()
        return UserFinancialInfo.objects.filter(Q(user=self.request.user))


class UserFinancerInfoViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch']
    permission_classes = [IsAdmin | IsOwner]

    queryset = UserFinancerInfo.objects.all()
    serializer_class = UserFinancerInfoSerializer
    filterset_class = UserFinancerInfoFilterSet

    def get_queryset(self):
        if is_admin(self.request):
            return UserFinancerInfo.objects.all()
        return UserFinancerInfo.objects.filter(Q(user=self.request.user))


class StudentUserViewSet(ReadOnlyModelViewSet):
    http_method_names = ['get']
    permission_classes = [IsAdmin]

    queryset = PriyoMoneyUser.objects.all()
    serializer_class = StudentUserSerializer
    filterset_class = UserFilter

    def get_serializer_context(self):
        return super().get_serializer_context() | {'include_profile_image_icon': is_admin(self.request)}

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PriyoMoneyUser.objects.none()

        return PriyoMoneyUser.objects.filter(student_primary_info__isnull=False).order_by('-created_at')
