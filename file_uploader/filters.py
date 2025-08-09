from django_filters.rest_framework import filters, FilterSet
from file_uploader.enums import DocumentType
from file_uploader.models import Documents


class UserDocumentsFilter(FilterSet):
    business = filters.CharFilter(method='filter_by_business')
    linked_business = filters.CharFilter(method='filter_by_linked_business')
    purpose = filters.CharFilter(method='filter_by_purpose')
    profile = filters.CharFilter(method='filter_by_profile')

    def filter_by_business(self, queryset, name, value):
        return queryset.filter(profile__business__id=value)

    def filter_by_linked_business(self, queryset, name, value):
        return queryset.filter(profile__linked_business__id=value)

    def filter_by_purpose(self, queryset, name, value):
        if value and value.lower() == 'view':
            return queryset.filter(synctera_document__isnull=False)
        elif value and value.lower() == 'admin_view':
            identity_doc_types = [DocumentType.IDENTITY_DOCUMENTATION.value, DocumentType.PERSONA_DOCUMENT.value,
                                  DocumentType.PROFILE_IMAGE.value, DocumentType.ADDITIONAL_IDENTITY_DOCS.value,
                                  DocumentType.PORICHOY_IMAGE.value, DocumentType.NID_OR_PASSPORT.value]
            return queryset.filter(doc_type__in=identity_doc_types)
        return queryset

    def filter_by_profile(self, queryset, name, value):
        return queryset.filter(profile_id=value)

    class Meta:
        model = Documents
        fields = ['doc_type', 'doc_name', 'verification_status']
