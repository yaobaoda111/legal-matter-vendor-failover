"""Explanatory entry point for intake, signed delivery, and deadline follow-up."""

from datetime import date

from fastapi import FastAPI, HTTPException

from src.infrai_gateway import InfraiError, InfraiGateway
from src.legal_workflow import IntakeResult, MatterIntake, decide_matter

app = FastAPI(title="Legal matter intake with vendor failover")


@app.post("/matters/intake", response_model=IntakeResult)
def intake_matter(intake: MatterIntake) -> IntakeResult:
    decision = decide_matter(intake, today=date.today())
    gateway = InfraiGateway()
    try:
        brief = gateway.write_matter_brief(intake, decision)
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail={"code": exc.code}) from exc
    finally:
        gateway.close()
    return IntakeResult(decision=decision, model_brief=brief)


@app.put("/routing/chat")
def set_chat_routing(exclude: list[str] | None = None) -> dict[str, object]:
    gateway = InfraiGateway()
    try:
        return gateway.configure_chat_routing(exclude)
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail={"code": exc.code}) from exc
    finally:
        gateway.close()
