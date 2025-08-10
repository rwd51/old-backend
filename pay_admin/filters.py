from django_filters import FilterSet

from pay_admin.models import MetabaseResource


class MetabaseResourceFilter(FilterSet):
    class Meta:
        model = MetabaseResource
        fields = ['resource_type', 'is_active', 'resource_name']