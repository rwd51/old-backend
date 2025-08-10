from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from common.email import EmailSender
from pay_admin.models import PayAdmin, MetabaseResource


class AdminRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = PayAdmin
        fields = ('username', 'email', 'password', 'password2')

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        admin = PayAdmin.objects.create(
            username=validated_data['username'],
            email=validated_data['email'],
        )
        admin.set_password(validated_data['password'])
        admin.save()

        email_data = {'password': validated_data['password']}
        EmailSender(admin=admin, kwargs=email_data).send_user_email(context='new_admin_registration_email')
        return admin


class ChangePasswordSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    old_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = PayAdmin
        fields = ('old_password', 'password', 'password2')

    def validate(self, attrs):
        attrs = super().validate(attrs)
        admin = self.context['request'].user
        if self.instance != admin:
            raise serializers.ValidationError({"user": "You can't change password for other admins"})
        if not admin.check_password(attrs['old_password']):
            raise serializers.ValidationError({"old_password": "Old password is not correct"})
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def update(self, instance: PayAdmin, validated_data):
        instance.set_password(validated_data['password'])
        instance.save()
        return instance


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayAdmin
        fields = ('id', 'last_login', 'is_superuser', 'username', 'first_name', 'last_name', 'is_active',
                  'date_joined', 'email')


class AdminUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayAdmin
        fields = ('first_name', 'last_name')


class PayAdminObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user: PayAdmin):
        token = super().get_token(user)
        token['username'] = user.username
        token['email'] = user.email
        return token


class MetabaseResourceSerializer(serializers.ModelSerializer):
    embed_url = serializers.SerializerMethodField(read_only=True)

    def get_embed_url(self, instance: MetabaseResource):
        return instance.get_embed_url()

    class Meta:
        model = MetabaseResource
        fields = '__all__'
        read_only_fields = ('id', 'embed_url')
