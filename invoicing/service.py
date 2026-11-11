from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from core.models import SuspensionNotice


def studio_today():
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


def evaluate(db, invoice, project, today=None):
    # Caller holds the project row lock. Evaluating repeatedly never duplicates a notice.
    overdue_days = max(0, ((today or studio_today()) - invoice.due_date).days)
    notice = db.scalar(select(SuspensionNotice).where(SuspensionNotice.invoice_id == invoice.id))
    if invoice.status in {"paid", "cancelled"}:
        action, milestone = "none", None
    elif invoice.status == "disputed":
        action, milestone = "human_review", None
    elif overdue_days >= 15:
        action, milestone = "pause_work_and_review_notice", 15
        project.work_paused = True
        if notice is None:
            notice = SuspensionNotice(
                invoice_id=invoice.id,
                content=(
                    f"DRAFT — HUMAN APPROVAL REQUIRED\n\nDear {invoice.client_name},\n\n"
                    f"Invoice {invoice.external_id} for {invoice.currency} {invoice.amount:.2f}, "
                    f"due {invoice.due_date.isoformat()}, remains unpaid. Work on "
                    f"{project.name} is paused pending payment review. Please contact "
                    "Frame Katha Studio to confirm payment or discuss the invoice. "
                    "A human will confirm the next production schedule.\n\nFrame Katha Studio"
                ),
            )
            db.add(notice)
            db.flush()
    elif overdue_days >= 10:
        action, milestone = "final_reminder", 10
    elif overdue_days >= 5:
        action, milestone = "follow_up", 5
    elif overdue_days >= 1:
        action, milestone = "gentle_reminder", 1
    else:
        action, milestone = "none", None
    return {
        "invoice": invoice,
        "days_overdue": overdue_days,
        "milestone": milestone,
        "action": action,
        "work_paused": project.work_paused,
        "notice": notice,
        "sent": False,
        "action_key": f"invoice:{invoice.id}:milestone:{milestone or action}",
    }
