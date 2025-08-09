from rest_framework.serializers import ModelSerializer
from core.models import UserEducation, UserExperience, UserForeignUniversity, UserFinancialInfo, UserFinancerInfo
from students.models import StudentPrimaryInfo
from core.serializers import PriyoMoneyUserSerializer
from rest_framework import serializers
from utilities.serializer_mixin import USDCentConversionSerializerMixin


class StudentPrimaryInfoSerializer(ModelSerializer):
    class Meta:
        model = StudentPrimaryInfo
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class UserEducationSerializer(ModelSerializer):
    class Meta:
        model = UserEducation
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class UserExperienceSerializer(ModelSerializer):
    class Meta:
        model = UserExperience
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class UserForeignUniversitySerializer(USDCentConversionSerializerMixin, ModelSerializer):
    cent_field_to_usd_field_mapper = {
        'annual_exp_tuition_fee_in_cent': 'annual_exp_tuition_fee_in_usd',
        'annual_exp_other_fees_in_cent': 'annual_exp_other_fees_in_usd',
        'advance_remittance_amount_in_cent': 'advance_remittance_amount_in_usd',
    }

    class Meta:
        model = UserForeignUniversity
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class UserFinancialInfoSerializer(USDCentConversionSerializerMixin, ModelSerializer):
    cent_field_to_usd_field_mapper = {
        'purchased_currency_amount_in_cent': 'purchased_currency_amount_in_usd',
        'scholarship_amount_in_cent': 'scholarship_amount_in_usd',
        'estimated_income_in_cent_from_part_time_per_month': 'estimated_income_in_usd_from_part_time_per_month',
    }

    class Meta:
        model = UserFinancialInfo
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class UserFinancerInfoSerializer(ModelSerializer):
    class Meta:
        model = UserFinancerInfo
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


# Serializer to expose extra fields from StudentPrimaryInfo on the student-users endpoint


class StudentUserSerializer(PriyoMoneyUserSerializer):
    university = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()

    class Meta(PriyoMoneyUserSerializer.Meta):
        base_fields = PriyoMoneyUserSerializer.Meta.fields
        if base_fields == '__all__':
            fields = '__all__'
        else:
            fields = base_fields + ('university', 'department',)

    def get_university(self, instance):
        education = instance.educations.order_by('-created_at').first()
        return education.institution_name if education else None

    def get_department(self, instance):
        education = instance.educations.order_by('-created_at').first()
        return education.field_of_study if education else None
