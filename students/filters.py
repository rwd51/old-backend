from django_filters.rest_framework import filters, FilterSet
from core.models import UserEducation, UserExperience, UserForeignUniversity, UserFinancialInfo, UserFinancerInfo
from students.models import StudentPrimaryInfo


class StudentPrimaryInfoFilterSet(FilterSet):
    class Meta:
        model = StudentPrimaryInfo
        fields = '__all__'


class UserEducationFilterSet(FilterSet):
    class Meta:
        model = UserEducation
        fields = '__all__'


class UserExperienceFilterSet(FilterSet):
    class Meta:
        model = UserExperience
        fields = '__all__'


class UserForeignUniversityFilterSet(FilterSet):
    class Meta:
        model = UserForeignUniversity
        fields = '__all__'


class UserFinancialInfoFilterSet(FilterSet):
    class Meta:
        model = UserFinancialInfo
        fields = '__all__'


class UserFinancerInfoFilterSet(FilterSet):
    class Meta:
        model = UserFinancerInfo
        fields = '__all__'
