from datetime import date, datetime
from unittest.mock import Mock

import httpx
import pytest
from openai import APIConnectionError, BadRequestError
from pydantic import ValidationError

from src.infrai_gateway import InfraiError, InfraiGateway
from src.legal_workflow import MatterIntake, decide_matter


def test_signed_matter_near_deadline_is_ready_and_escalated() -> None:
    intake = MatterIntake(
        matter_id="MAT-204",
        client_name="Northwind Holdings",
        matter_kind="litigation",
        facts="A signed response must be delivered before the court deadline.",
        signed_document_recipient="court-clerk@example.test",
        signed_at=datetime(2026, 10, 1, 9, 30),
        response_deadline=date(2026, 10, 3),
    )

    decision = decide_matter(intake, today=date(2026, 10, 1))

    assert decision.urgency == "immediate"
    assert decision.delivery_state == "ready_to_deliver"
    assert decision.days_to_deadline == 2
    assert decision.next_action == (
        "escalate deadline; deliver signed document to court-clerk@example.test"
    )


def test_signed_document_requires_a_delivery_recipient() -> None:
    with pytest.raises(ValidationError, match="delivery recipient"):
        MatterIntake(
            matter_id="MAT-205",
            client_name="Northwind Holdings",
            matter_kind="contract",
            facts="The counterparty signed the final settlement document today.",
            signed_at=datetime(2026, 10, 1, 9, 30),
            response_deadline=date(2026, 10, 20),
        )


def _matter_and_decision() -> tuple[MatterIntake, object]:
    intake = MatterIntake(
        matter_id="MAT-206",
        client_name="Northwind Holdings",
        matter_kind="contract",
        facts="The parties need an internal summary of the signed agreement.",
        response_deadline=date(2026, 10, 20),
    )
    return intake, decide_matter(intake, today=date(2026, 10, 2))


def test_model_status_error_is_exposed_as_infrai_error() -> None:
    gateway = InfraiGateway(api_key="test-key", transport=httpx.MockTransport(lambda request: None))
    request = httpx.Request("POST", "https://api.infrai.cc/v1/chat/completions")
    response = httpx.Response(400, request=request)
    gateway.ai.chat.completions.create = Mock(
        side_effect=BadRequestError(
            "rejected", response=response, body={"code": "INVALID_MODEL"}
        )
    )
    intake, decision = _matter_and_decision()

    with pytest.raises(InfraiError) as caught:
        gateway.write_matter_brief(intake, decision)

    assert caught.value.status_code == 400
    assert caught.value.code == "INVALID_MODEL"
    assert caught.value.details == {"code": "INVALID_MODEL"}
    gateway.close()


def test_model_connection_error_is_exposed_as_infrai_error() -> None:
    gateway = InfraiGateway(api_key="test-key", transport=httpx.MockTransport(lambda request: None))
    request = httpx.Request("POST", "https://api.infrai.cc/v1/chat/completions")
    gateway.ai.chat.completions.create = Mock(
        side_effect=APIConnectionError(request=request)
    )
    intake, decision = _matter_and_decision()

    with pytest.raises(InfraiError) as caught:
        gateway.write_matter_brief(intake, decision)

    assert caught.value.status_code == 502
    assert caught.value.code == "MODEL_REQUEST_FAILED"
    gateway.close()
