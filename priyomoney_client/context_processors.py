import json
import random

from django.conf import settings


def defaults(request):
    context = {
        'has_token': request.session.get('user', None) is not None,
        'is_logged_in': request.session.get('user', None) is not None,
        'profile_reviewed': request.session.get('profile_reviewed', None) is not None,
        'auth_service_base': settings.AUTH_API_BASE,
        'self_host': settings.OWN_BASE_URL,
        'user_account': request.session.get('user', None),
    }
    return context
