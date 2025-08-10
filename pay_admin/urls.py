from django.urls import path, include
from rest_framework.routers import SimpleRouter
from pay_admin.views import AdminRegisterViewSet, ChangePasswordViewSet, AdminUserViewSet, \
    AdminTokenObtainPairView, AdminTokenRefreshView, AdminLogoutView, AdminUpdateViewSet, MetabaseResourceViewSet

router = SimpleRouter(trailing_slash=True)
router.register(r'register', AdminRegisterViewSet)
router.register(r'change_password', ChangePasswordViewSet)
router.register(r'users', AdminUserViewSet)
router.register(r'update', AdminUpdateViewSet)
router.register(r'metabase-resource', MetabaseResourceViewSet)

urlpatterns = [
    path('login/', AdminTokenObtainPairView.as_view(), name='login_obtain_pair'),
    path('login/refresh/', AdminTokenRefreshView.as_view(), name='login_refresh'),
    path('logout/', AdminLogoutView.as_view(), name='token_refresh'),
    path('', include(router.urls)),
]
