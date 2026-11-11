import pytest
from pydantic import ValidationError

from api.schemas.leads import LeadIngest
from leads.normalization import normalize_email, normalize_name, normalize_phone


@pytest.mark.parametrize("phone", ["9876543210", "+91 98765 43210", "09876543210"])
def test_indian_phone_variants(phone):
    assert normalize_phone(phone) == "+919876543210"


def test_international_phone():
    assert normalize_phone("+44 20 7946 0958") == "+442079460958"


@pytest.mark.parametrize("phone", ["123", "not-a-phone", "+91 9876543210 ext 12"])
def test_invalid_phone(phone):
    with pytest.raises(ValueError):
        normalize_phone(phone)


def test_names_and_emails():
    assert normalize_name("  Frame Katha, STUDIO! ") == "frame katha studio"
    assert normalize_email(" Studio@Example.COM ") == "studio@example.com"


def test_reject_punctuation_only_business():
    with pytest.raises(ValidationError):
        LeadIngest(business_name="!!!", channel="manual")
