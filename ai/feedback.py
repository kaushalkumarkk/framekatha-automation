from importlib.resources import files
from typing import Literal

from pydantic import Field, model_validator

from ai.client import generate_json
from api.schemas.leads import Name, StrictInput


class FeedbackInput(StrictInput):
    text: str = Field(min_length=1, max_length=20000)


class EditOperation(StrictInput):
    operation: Literal["trim", "remove", "swap_music", "colour_change"]
    scene_id: str | None = Field(default=None, max_length=100)
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, ge=0)
    value: str | None = Field(default=None, max_length=2000)
    reason: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_operation(self):
        if self.operation in {"trim", "remove"} and not self.scene_id:
            raise ValueError("A scene is required for trim/remove")
        if self.operation == "trim" and (
            self.start_seconds is None
            or self.end_seconds is None
            or self.end_seconds <= self.start_seconds
        ):
            raise ValueError("A trim needs an ordered time range")
        if self.operation in {"swap_music", "colour_change"} and not self.value:
            raise ValueError("Music/colour changes require a description")
        return self


class FeedbackOperations(StrictInput):
    operations: list[EditOperation] = Field(max_length=100)
    clarification_needed: list[str] = Field(default_factory=list, max_length=20)


class ReviewInput(StrictInput):
    decision: Literal["approved", "rejected"]
    reviewed_by: Name


def parse_feedback(text: str):
    return generate_json(
        files("ai").joinpath("prompts/feedback.v1.txt").read_text(),
        {"feedback": text},
        FeedbackOperations,
        "feedback_parser",
    )
