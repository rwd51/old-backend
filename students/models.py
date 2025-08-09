from django.db import models

from core.models import PriyoMoneyUser
from pay_admin.models import PayAdmin
from utilities.model_mixins import TimeStampMixin


class StudentPrimaryInfo(TimeStampMixin):
    user = models.OneToOneField(PriyoMoneyUser, on_delete=models.CASCADE, related_name="student_primary_info")
    approved_by = models.ForeignKey(PayAdmin, on_delete=models.PROTECT, null=True, blank=True, related_name='approved_students')
    approved_at = models.DateTimeField(null=True, blank=True)
    bank_side_approved_by = models.PositiveBigIntegerField(null=True, blank=True)
    bank_side_approved_at = models.DateTimeField(null=True, blank=True)

    passport_number = models.CharField(max_length=32, unique=True)
    passport_issue_place = models.CharField(max_length=128, null=True, blank=True)
    passport_issue_date = models.DateField()
    passport_expiry_date = models.DateField()

    class Meta:
        ordering = ['-created_at']

    def get_user(self):
        return self.user

    def get_user_set(self):
        return [self.user]
