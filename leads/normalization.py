import re
import unicodedata

import phonenumbers


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.sub(r"[^\w\s]", " ", value).split())


def normalize_phone(value: str, region: str = "IN") -> str:
    try:
        phone = phonenumbers.parse(value, region)
    except phonenumbers.NumberParseException as exc:
        raise ValueError("Invalid phone number") from exc
    if phone.extension or not phonenumbers.is_valid_number(phone):
        raise ValueError("Invalid phone number or unsupported extension")
    return phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.E164)


def normalize_email(value: str) -> str:
    return value.strip().casefold()
