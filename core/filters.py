from django.db.models import Q, Subquery
from django_filters.rest_framework import filters, FilterSet

from common.models import UserSMSLog
from core.enums import ProfileApprovalStatus, AddressType, OnboardingSteps
from core.helpers import get_note_item_choices
from core.models import PriyoMoneyUser, UserAdditionalInfo, UserLocation, UserAddress, UserIdentification, \
    UserOnboardingStep, UserSourceOfIncome, UserSourceOfHearing, UserMetaData, Note, UserContactReference
from external_payment.enums import ExternalPaymentStatus, ExternalPaymentType
from external_payment.models import ExternalPayment
from verifications.enums import PersonaInquiryStatus
from verifications.models import PersonaVerification


class UserFilter(FilterSet):
    search_text = filters.CharFilter(method='filter_by_search_text')
    from_date = filters.DateFilter(field_name='created_at', lookup_expr='gte')
    to_date = filters.DateFilter(field_name='created_at', lookup_expr='lte')
    profile_status = filters.CharFilter(method='filter_by_profile_status')
    country = filters.CharFilter(method='filter_by_country')
    subscription = filters.ChoiceFilter(method='filter_by_subscription', choices=ExternalPaymentStatus.choices())
    has_billing_address = filters.BooleanFilter(method='filter_by_has_billing_address')
    verification = filters.ChoiceFilter(method='filter_by_verification', choices=PersonaInquiryStatus.choices())
    last_onboarding_step = filters.ChoiceFilter(method='filter_by_last_onboarding_step',
                                                choices=OnboardingSteps.choices())
    admin_approved = filters.CharFilter(method='filter_by_admin_approved')

    def filter_by_last_onboarding_step(self, queryset, name, value):
        steps_after = OnboardingSteps.get_possible_steps_after(value)
        users_in_later_steps = UserOnboardingStep.objects.filter(step__in=steps_after).values('user')
        users_in_step = (UserOnboardingStep.objects.filter(step=value).values('user').difference(users_in_later_steps))
        return queryset.filter(id__in=Subquery(users_in_step))

    def filter_by_search_text(self, queryset, name, value):
        q = Q()
        for token in value.split():
            q |= Q(first_name__icontains=token) | Q(middle_name__icontains=token) | \
                 Q(last_name__icontains=token) | Q(email_address__icontains=token) | \
                 Q(user_mobile_number__mobile_number__icontains=token)
        return queryset.filter(q)

    def filter_by_profile_status(self, queryset, name, value):
        signup_complete_status = ProfileApprovalStatus.AWAITING_SIGNUP_COMPLETION.value
        if value == 'TOKEN_VERIFIED':
            queryset = queryset.filter(is_verified_internal_user=True,
                                       user_mobile_number__mobile_number__isnull=True,
                                       profile_approval_status=signup_complete_status)
        elif value == 'MOBILE_VERIFIED':
            queryset = queryset.filter(user_mobile_number__mobile_number__isnull=False,
                                       profile_approval_status=signup_complete_status)
        elif value == signup_complete_status:
            queryset = queryset.filter(profile_approval_status=value,
                                       is_verified_internal_user=False,
                                       user_mobile_number__mobile_number__isnull=True)
        else:
            queryset = queryset.filter(profile_approval_status=value)

        return queryset

    def filter_by_country(self, queryset, name, value):
        if value == 'unidentified':
            users_with_country = UserAddress.objects.filter(address_type=AddressType.LEGAL.value,
                                                            country__isnull=False).values('user')
            return queryset.filter(~Q(id__in=Subquery(users_with_country)))
        else:
            users = UserAddress.objects.filter(address_type=AddressType.LEGAL.value, country=value).values('user')
            return queryset.filter(id__in=Subquery(users))

    def filter_by_subscription(self, queryset, name, value):
        payments = ExternalPayment.objects.filter(status=value, is_active=True,
                                                  payment_type=ExternalPaymentType.ONBOARDING_FEE.value).values('user')
        return queryset.filter(id__in=Subquery(payments))

    def filter_by_has_billing_address(self, queryset, name, value):
        users_with_billing_address = UserAddress.objects.filter(address_type=AddressType.BILLING.value).values('user')
        if value:
            return queryset.filter(Q(id__in=Subquery(users_with_billing_address)))
        else:
            return queryset.filter(~Q(id__in=Subquery(users_with_billing_address)))

    def filter_by_verification(self, queryset, name, value):
        filtered_users = PersonaVerification.objects.filter(is_active=True, status=value).values('user')
        return queryset.filter(id__in=Subquery(filtered_users))

    def filter_by_admin_approved(self, queryset, name, value):
        if value.upper() == 'Y':
            filtered_users = UserMetaData.objects.filter(profile_approved_by__isnull=False,
                                                         profile_verified_by__isnull=True).values('user')
            return queryset.filter(id__in=Subquery(filtered_users))
        else:
            return queryset

    class Meta:
        model = PriyoMoneyUser
        fields = ['one_auth_uuid', 'id', 'profile_approval_status', 'profile_type', 'is_terminated', 'admin_review_status']


class UserSMSLogFilter(FilterSet):
    mobile_number = filters.CharFilter(field_name="mobile_number", lookup_expr="icontains")
    sms_purpose = filters.CharFilter(field_name="sms_purpose", lookup_expr="iexact")

    class Meta:
        model = UserSMSLog
        fields = ['user']


class UserAdditionalInfoFilter(FilterSet):
    class Meta:
        model = UserAdditionalInfo
        fields = ['person']


class UserLocationFilter(FilterSet):
    class Meta:
        model = UserLocation
        fields = '__all__'


class UserAddressFilter(FilterSet):
    class Meta:
        model = UserAddress
        fields = ['address_type', 'user']


class UserSourceOfIncomeFilter(FilterSet):
    class Meta:
        model = UserSourceOfIncome
        fields = ['user']


class UserContactReferenceFilter(FilterSet):
    class Meta:
        model = UserContactReference
        fields = ['user']


class UserIdentityNumberFilterSet(FilterSet):
    class Meta:
        model = UserIdentification
        fields = '__all__'


class UserOnboardingStepFilter(FilterSet):
    class Meta:
        model = UserOnboardingStep
        fields = '__all__'


class UserSourceOfHearingFilterSet(FilterSet):
    class Meta:
        model = UserSourceOfHearing
        fields = '__all__'


class NoteFilterSet(FilterSet):
    item_type = filters.CharFilter(method='filter_by_item_type')
    item_ids = filters.BaseInFilter(field_name='item_id')

    def filter_by_item_type(self, queryset, name, value):
        item_type = None
        for (key, content_type) in get_note_item_choices():
            if key == value:
                item_type = content_type
        if item_type:
            return queryset.filter(item_type_id=item_type.pk)
        else:
            return queryset

    class Meta:
        model = Note
        fields = ['item_id']

