"""Deterministic business decisions for a legal matter intake."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class MatterKind(str, Enum):
    CONTRACT = "contract"
    LITIGATION = "litigation"
    REGULATORY = "regulatory"


class MatterIntake(BaseModel):
    matter_id: str = Field(min_length=1)
    client_name: str = Field(min_length=1)
    matter_kind: MatterKind
    facts: str = Field(min_length=20)
    signed_document_recipient: str | None = None
    signed_at: datetime | None = None
    response_deadline: date

    @model_validator(mode="after")
    def signed_delivery_has_recipient(self) -> "MatterIntake":
        if self.signed_at and not self.signed_document_recipient:
            raise ValueError("a signed document needs a delivery recipient")
        return self


class MatterDecision(BaseModel):
    matter_id: str
    urgency: str
    delivery_state: str
    next_action: str
    days_to_deadline: int


class IntakeResult(BaseModel):
    decision: MatterDecision
    model_brief: str


def decide_matter(intake: MatterIntake, *, today: date) -> MatterDecision:
    """Expose the deadline and delivery transition before asking a model for prose."""
    days_left = (intake.response_deadline - today).days
    if days_left < 0:
        urgency = "overdue"
    elif days_left <= 3:
        urgency = "immediate"
    elif days_left <= 14:
        urgency = "soon"
    else:
        urgency = "routine"

    if intake.signed_at:
        delivery_state = "ready_to_deliver"
        next_action = f"deliver signed document to {intake.signed_document_recipient}"
    else:
        delivery_state = "awaiting_signature"
        next_action = "collect signature before delivery"

    if urgency in {"overdue", "immediate"}:
        next_action = f"escalate deadline; {next_action}"

    return MatterDecision(
        matter_id=intake.matter_id,
        urgency=urgency,
        delivery_state=delivery_state,
        next_action=next_action,
        days_to_deadline=days_left,
    )
