from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, select

from ai.client import generate_json
from api.schemas.studio import FeeProposal, NegotiateInput, TalentInput
from core.models import Negotiation, Project, Talent
from leads.dedup import lock_ingestion
from leads.normalization import normalize_email, normalize_phone


def import_talent(db, payload: TalentInput, region: str):
    data = payload.model_dump(mode="json")
    data["fee_rate"] = payload.fee_rate
    data["email"] = normalize_email(str(payload.email)) if payload.email else None
    try:
        data["phone"] = normalize_phone(payload.phone, region) if payload.phone else None
    except ValueError:
        raise HTTPException(422, "Invalid phone number") from None
    predicates = [
        getattr(Talent, key) == data[key]
        for key in ("email", "phone", "portfolio_url")
        if data[key]
    ]
    lock_ingestion(db)
    matches = list(db.scalars(select(Talent).where(or_(*predicates))))
    if len(matches) > 1:
        raise HTTPException(409, "Contact identities belong to different talent records")
    talent = matches[0] if matches else Talent()
    for key, value in data.items():
        # Re-imports may update skills, availability and fees, but do not erase contacts.
        if key in {"email", "phone", "portfolio_url"} and value is None:
            continue
        setattr(talent, key, value)
    talent.has_portfolio = bool(talent.portfolio_url)
    db.add(talent)
    db.flush()
    return talent


def match_talent(db, project: Project):
    required = set(project.required_skills)
    candidates = db.scalars(
        select(Talent).where(
            Talent.available.is_(True),
            Talent.currency == project.currency,
            Talent.fee_rate <= project.max_fee,
        )
    )
    ranked = []
    for talent in candidates:
        if project.shoot_date and project.shoot_date.isoformat() in talent.unavailable_dates:
            continue
        overlap = required & set(talent.skills)
        skill_score = len(overlap) / len(required) if required else 1
        if required and not overlap:
            continue
        budget_score = 1 - float(talent.fee_rate / project.max_fee) if project.max_fee else 1
        score = round(85 * skill_score + 15 * max(0, budget_score), 2)
        ranked.append(
            {
                "talent": talent,
                "score": score,
                "matched_skills": sorted(overlap),
                "suggested_fee": max(talent.fee_rate, project.min_fee),
            }
        )
    return sorted(ranked, key=lambda item: (-item["score"], item["talent"].name))


def negotiate(db, talent: Talent, project: Project, payload: NegotiateInput):
    if talent.currency != project.currency:
        raise HTTPException(409, "Talent and project currencies differ")
    result = generate_json(
        "You assist a studio negotiating an actor/model fee. Propose an amount within "
        "the project's inclusive minimum and maximum. Never confirm, accept or bind a fee. "
        "Return only a fee proposal and rationale for human review; no outgoing message.",
        {
            "talent_name": talent.name,
            "listed_fee": str(talent.fee_rate),
            "minimum": str(project.min_fee),
            "maximum": str(project.max_fee),
            "currency": project.currency,
            "conversation": [message.model_dump() for message in payload.conversation],
        },
        FeeProposal,
        "talent_negotiation",
    )
    fee = Decimal(result.proposed_fee)
    if not project.min_fee <= fee <= project.max_fee:
        raise HTTPException(422, "AI proposed a fee outside the project limits; no proposal saved")
    # All model-produced prose stays in an internal rationale. The actual next reply
    # uses a deterministic non-binding template, so prompting cannot confirm a fee.
    reply = (
        f"For discussion, a fee of {project.currency} {fee:.2f} has been proposed. "
        "This is subject to human approval and is not a confirmed booking or agreement."
    )
    lock_ingestion(db)
    state = db.scalar(
        select(Negotiation).where(
            Negotiation.project_id == project.id,
            Negotiation.talent_id == talent.id,
        )
    )
    if state is None:
        state = Negotiation(project_id=project.id, talent_id=talent.id)
        db.add(state)
    state.conversation = [message.model_dump() for message in payload.conversation] + [
        {"role": "assistant", "content": reply},
    ]
    state.proposed_fee = fee
    state.status = "human_review_required"
    db.flush()
    return {
        "id": state.id,
        "next_reply": reply,
        "proposed_fee": fee,
        "currency": project.currency,
        "rationale": result.rationale,
        "requires_human_approval": True,
        "confirmed": False,
    }


def entity(db, model, identity: UUID):
    result = db.get(model, identity)
    if result is None:
        raise HTTPException(404, f"{model.__name__} not found")
    return result
