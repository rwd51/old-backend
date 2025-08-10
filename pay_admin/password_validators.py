from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext as _


class PayAdminPasswordValidator:
    def __init__(self, min_length=8, min_uppercase=0, min_lowercase=0, min_digits=0, min_special=0, special_chars=None):
        self.min_length = min_length
        self.min_uppercase = min_uppercase
        self.min_lowercase = min_lowercase
        self.min_digits = min_digits
        self.min_special = min_special
        self.special_chars = special_chars

    def validate(self, password, user=None):
        errors = []
        if len(password) < self.min_length:
            errors.append(f"Password must be at least {self.min_length} characters long.")

        if sum(1 for c in password if c.isupper()) < self.min_uppercase:
            errors.append(f"Password must contain at least {self.min_uppercase} uppercase characters.")

        if sum(1 for c in password if c.islower()) < self.min_lowercase:
            errors.append(f"Password must contain at least {self.min_lowercase} lowercase characters.")

        if sum(1 for c in password if c.isdigit()) < self.min_digits:
            errors.append(f"Password must contain at least {self.min_digits} digits.")

        if self.special_chars and sum(1 for c in password if c in self.special_chars) < self.min_special:
            errors.append(f"Password must contain at least {self.min_special} special characters.")

        if self.special_chars is not None and any(c not in self.special_chars for c in password):
            errors.append(f"Password must contain only the following special characters: {self.special_chars}")

        if errors:
            raise ValidationError(errors, code='password_too_weak')

    def get_help_text(self):
        texts = [f"Your password must contain at least {self.min_length} characters."]

        if self.min_digits > 0:
            texts.append(f"Your password must contain at least {self.min_digits} digits.")

        if self.min_lowercase > 0:
            texts.append(f"Your password must contain at least {self.min_lowercase} lowercase characters.")

        if self.min_uppercase > 0:
            texts.append(f"Your password must contain at least {self.min_uppercase} uppercase characters.")

        if self.min_special > 0:
            texts.append(f"Your password must contain at least {self.min_special} special characters.")

        if self.special_chars is not None:
            texts.append(f"Your password must contain only the following special characters: {self.special_chars}")

        return " ".join(texts)