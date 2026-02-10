import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class PasswordComplexityValidator:
    """
    Requires at least one lowercase, one uppercase, one digit, and one symbol.
    """

    def validate(self, password, user=None):
        if not re.search(r"[a-z]", password):
            raise ValidationError(
                _("Password must contain at least one lowercase letter."),
                code="password_no_lower",
            )
        if not re.search(r"[A-Z]", password):
            raise ValidationError(
                _("Password must contain at least one uppercase letter."),
                code="password_no_upper",
            )
        if not re.search(r"\d", password):
            raise ValidationError(
                _("Password must contain at least one digit."),
                code="password_no_digit",
            )
        if not re.search(r"[^A-Za-z0-9]", password):
            raise ValidationError(
                _("Password must contain at least one symbol."),
                code="password_no_symbol",
            )

    def get_help_text(self):
        return _(
            "Your password must contain at least one lowercase letter, "
            "one uppercase letter, one digit, and one symbol."
        )
