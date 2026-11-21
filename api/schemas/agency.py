from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, HttpUrl, StringConstraints, model_validator

from api.schemas.leads import Name, StrictInput

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
Texts = Annotated[list[Text], Field(max_length=100)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
DocumentKind = Literal[
    "proposal",
    "brand_strategy",
    "content_calendar",
    "meeting_summary",
    "campaign_copy",
    "monthly_report",
]


class OnboardingInput(StrictInput):
    name: Name
    business_category: Name
    target_audience: Text
    business_location: Name
    brand_objectives: Texts
    competitors: Texts = Field(default_factory=list)
    marketing_channels: Texts = Field(default_factory=list)
    brand_guidelines: Text = "No guidelines supplied"
    asset_urls: list[HttpUrl] = Field(default_factory=list, max_length=100)
    previous_campaigns: Texts = Field(default_factory=list)
    monthly_budget: Money
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] = "INR"
    kpis: Texts
    tone_of_voice: Text = "Professional and warm"
    products: Texts = Field(default_factory=list)
    preferred_languages: Texts = Field(default_factory=lambda: ["English"])
    approved_facts: Texts = Field(default_factory=list)


class SalesInput(StrictInput):
    assigned_to: Name | None = None
    industry: Name | None = None
    follow_up_start: date | None = None


class SalesEvent(StrictInput):
    event_id: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    event: Literal["responded", "declined", "contacted", "meeting_booked", "follow_up_completed"]
    channel: Literal["email", "whatsapp", "phone", "meeting", "manual"] = "manual"
    note: Text | None = None
    milestone: Literal[1, 3, 5, 8, 14] | None = None

    @model_validator(mode="after")
    def completion_has_milestone(self):
        if (self.event == "follow_up_completed") != (self.milestone is not None):
            raise ValueError("Only follow-up completion requires a milestone")
        return self


class LeadIntelligence(StrictInput):
    score: int = Field(ge=0, le=100)
    rationale: Text
    opportunities: Texts
    evidence_gaps: Texts
    estimated_monthly_budget: Money | None = None
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] = "INR"
    budget_is_prediction: Literal[True] = True


class GenerationInput(StrictInput):
    instructions: Text = "Use the project brief and client profile."
    start_date: date | None = None
    end_date: date | None = None
    deliverable_count: int = Field(default=26, ge=1, le=60)
    transcript: Annotated[str, Field(max_length=30000)] | None = None


class Proposal(StrictInput):
    introduction: Text
    requirements: Texts
    objectives: Texts
    strategy: Text
    scope_of_work: Texts
    deliverables: Texts
    timeline: Text
    monthly_charges: Money
    advertising_budget: Money
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
    terms: Texts
    payment_terms: Text


class BrandStrategy(StrictInput):
    positioning: Text
    audience_personas: Texts
    competitor_analysis: Texts
    usp: Text
    content_opportunities: Texts
    marketing_funnel: Texts
    advertising_strategy: Text
    monthly_objectives: Texts
    assumptions: Texts


class CalendarItem(StrictInput):
    day: date
    content_type: Name
    topic: Name
    channel: Name
    objective: Text
    production_notes: Text


class ContentCalendar(StrictInput):
    start_date: date
    items: list[CalendarItem] = Field(min_length=1, max_length=60)

    @model_validator(mode="after")
    def within_thirty_days(self):
        if any(
            not self.start_date <= item.day < self.start_date + timedelta(days=30)
            for item in self.items
        ):
            raise ValueError("Calendar entries must fall inside the 30-day window")
        return self


class MeetingSummary(StrictInput):
    summary: Text
    client_requirements: Texts
    expected_budget: Money | None = None
    proposed_services: Texts
    action_items: Texts
    follow_up_date: date | None = None
    uncertainties: Texts


class CampaignCopy(StrictInput):
    concept: Text
    caption: Text
    hashtags: Texts
    advertisement_copy: Text
    thumbnail_ideas: Texts
    claims_to_verify: Texts


class MonthlyReport(StrictInput):
    summary: Text
    content_published: Text
    reach_and_engagement: Text
    ad_performance: Text
    leads_generated: Text
    campaign_insights: Texts
    next_month_recommendations: Texts
    missing_data: Texts


class BusinessAnalysis(StrictInput):
    summary: Text
    sales_insights: Texts
    profitability_insights: Texts
    overdue_payment_actions: Texts
    revenue_recommendations: Texts
    planning_estimates: Texts
    missing_data: Texts
    estimates_are_predictions: Literal[True] = True


class OutreachDraft(StrictInput):
    subject: Name
    message: Text
    proposed_services: Texts
    claims_to_verify: Texts


class DocumentImport(StrictInput):
    output: dict


DOCUMENT_SCHEMAS = {
    "proposal": Proposal,
    "brand_strategy": BrandStrategy,
    "content_calendar": ContentCalendar,
    "meeting_summary": MeetingSummary,
    "campaign_copy": CampaignCopy,
    "monthly_report": MonthlyReport,
}


class ReviewInput(StrictInput):
    stage: Literal["director", "client"]
    decision: Literal["approved", "rejected"]
    reviewed_by: Name
    note: Text


QC_ITEMS = {
    "aspect_ratio",
    "resolution",
    "audio_levels",
    "subtitles",
    "brand_logo",
    "contact_details",
    "spelling",
    "colour_consistency",
    "deliverables",
    "export_settings",
    "copyright",
    "brand_compliance",
}


class ProductionInput(StrictInput):
    stage: Literal["planning", "shooting", "editing", "qc", "ready", "delivered"] = "planning"
    crew: Texts = Field(default_factory=list)
    equipment: Texts = Field(default_factory=list)
    props: Texts = Field(default_factory=list)
    costumes: Texts = Field(default_factory=list)
    backup_primary_verified: bool = False
    backup_secondary_verified: bool = False
    qc: dict[str, bool] = Field(default_factory=dict, max_length=12)
    final_approved_by: Name | None = None
    notes: Text | None = None

    @model_validator(mode="after")
    def delivery_gates(self):
        if set(self.qc) - QC_ITEMS:
            raise ValueError("Unknown QC checks")
        if self.stage in {"ready", "delivered"}:
            if not (
                self.backup_primary_verified
                and self.backup_secondary_verified
                and self.final_approved_by
                and all(self.qc.get(key) for key in QC_ITEMS)
            ):
                raise ValueError("Final approval, both backups and every QC check are required")
        return self


class ExpenseInput(StrictInput):
    external_id: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    category: Literal["production", "advertising", "operating"]
    description: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    amount: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
    incurred_on: date
    recorded_by: Name


class MetricValues(StrictInput):
    impressions: int = Field(ge=0)
    reach: int = Field(ge=0)
    clicks: int = Field(ge=0)
    leads: int = Field(ge=0)
    conversions: int = Field(ge=0)
    spend: Money
    attributed_revenue: Money | None = None
    published_content: int = Field(default=0, ge=0)
    engagements: int = Field(default=0, ge=0)
    audience_growth: int = 0


class MetricInput(StrictInput):
    platform: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    campaign_id: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    day: date
    metrics: MetricValues
