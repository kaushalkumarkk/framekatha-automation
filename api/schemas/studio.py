from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import EmailStr, Field, HttpUrl, StringConstraints, field_validator, model_validator

from api.schemas.leads import Name, StrictInput

Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]


def tags(values: list[str]) -> list[str]:
    cleaned = sorted({v.strip().casefold() for v in values if v.strip()})
    if any(len(v) > 80 for v in cleaned):
        raise ValueError("Skill tags cannot exceed 80 characters")
    return cleaned


class ProjectInput(StrictInput):
    name: Name
    client_name: Name
    client_email: EmailStr | None = None
    requirement: str = Field(min_length=1, max_length=20000)
    required_skills: list[str] = Field(default_factory=list, max_length=50)
    min_fee: Money = Decimal("0")
    max_fee: Money
    currency: Currency = "INR"
    shoot_date: date | None = None
    location: str | None = Field(default=None, max_length=500)
    call_time: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    cinematographer: Name | None = None

    @field_validator("required_skills")
    @classmethod
    def normalize_tags(cls, value):
        return tags(value)

    @model_validator(mode="after")
    def fee_range(self):
        if self.max_fee < self.min_fee:
            raise ValueError("max_fee must be at least min_fee")
        return self


class TalentInput(StrictInput):
    name: Name
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=64)
    portfolio_url: HttpUrl | None = None
    skills: list[str] = Field(default_factory=list, max_length=50)
    fee_rate: Money
    currency: Currency = "INR"
    followers: int = Field(default=0, ge=0)
    available: bool = True
    unavailable_dates: list[date] = Field(default_factory=list, max_length=366)

    @field_validator("skills")
    @classmethod
    def normalize_tags(cls, value):
        return tags(value)

    @model_validator(mode="after")
    def contact_required(self):
        if not (self.email or self.phone or self.portfolio_url):
            raise ValueError("Provide email, phone or portfolio URL")
        return self


class Message(StrictInput):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=10000)


class NegotiateInput(StrictInput):
    project_id: UUID
    conversation: list[Message] = Field(min_length=1, max_length=100)


class FeeProposal(StrictInput):
    proposed_fee: Money
    rationale: str = Field(min_length=1, max_length=2000)


class SelectionInput(StrictInput):
    talent_id: UUID
    proposed_fee: Money


class ApprovalInput(StrictInput):
    selection_id: UUID
    decision: Literal["approved", "rejected"]
    approved_by: Name
    note: str | None = Field(default=None, max_length=2000)
