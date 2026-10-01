import re

from django.core.validators import RegexValidator

# Indian mobile numbers: 10 digits, starting with 6, 7, 8 or 9.
PHONE_REGEX = r"^[6-9]\d{9}$"

phone_validator = RegexValidator(
    regex=PHONE_REGEX,
    message="Enter a valid 10-digit Indian mobile number (e.g. 9876543210).",
)


def normalize_phone(value):
    """Turn '+91 98765-43210' / '09876543210' into '9876543210'.

    WHY: people type numbers in many formats; storing one format keeps phone
    numbers unique and searchable.
    """
    if not value:
        return value
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits
