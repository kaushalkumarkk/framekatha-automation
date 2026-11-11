from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
)

from leads.normalization import normalize_name

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Channel = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
]
LeadStatus = Literal["new", "qualified", "contacted", "won", "lost", "archived"]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LeadIngest(StrictInput):
    business_name: Name
    phone: str | None = Field(default=None, min_length=3, max_length=64)
    email: EmailStr | None = None
    website: HttpUrl | None = None
    city: ShortText | None = None
    locality: ShortText | None = None
    channel: Channel
    external_id: str | None = Field(default=None, min_length=1, max_length=300)
    source_url: HttpUrl | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)
    opted_out: bool = False
    opt_out_reason: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("business_name")
    @classmethod
    def meaningful_name(cls, value: str) -> str:
        if not normalize_name(value):
            raise ValueError("Business name must contain letters or numbers")
        return value


class SourceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    channel: str
    external_id: str | None
    source_url: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    hit_count: int


class IdentityView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kind: str
    normalized_value: str


class LeadView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_name: str
    primary_phone: str | None
    primary_email: str | None
    website: str | None
    city: str | None
    locality: str | None
    status: LeadStatus
    opted_out: bool
    opted_out_at: datetime | None
    opt_out_reason: str | None
    created_at: datetime
    updated_at: datetime
    identities: list[IdentityView]
    sources: list[SourceView]


class IngestResponse(BaseModel):
    outcome: Literal["created", "merged"]
    lead: LeadView


class LeadPage(BaseModel):
    items: list[LeadView]
    total: int
    limit: int
    offset: int


class StatusUpdate(StrictInput):
    status: LeadStatus


class OptOutUpdate(StrictInput):
    opted_out: Literal[True] = True
    reason: str | None = Field(default=None, max_length=2000)
