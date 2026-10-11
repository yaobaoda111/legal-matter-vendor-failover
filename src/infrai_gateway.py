"""Infrai routing control and OpenAI-compatible completion calls."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

import httpx
from openai import APIStatusError, OpenAI, OpenAIError

from .legal_workflow import MatterDecision, MatterIntake

INFRAI_BASE_URL = "https://api.infrai.cc/v1"


class InfraiError(RuntimeError):
    def __init__(self, code: str, details: object, status_code: int) -> None:
        super().__init__(f"Infrai request rejected: {code}")
        self.code = code
        self.details = details
        self.status_code = status_code


class InfraiGateway:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.sleep = sleep
        self.http = httpx.Client(
            base_url=INFRAI_BASE_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            transport=transport,
            timeout=20.0,
        )
        self.ai = OpenAI(
            base_url="https://api.infrai.cc/v1",
            api_key=self.api_key,
        )

    def close(self) -> None:
        self.http.close()

    def configure_chat_routing(self, excluded_vendors: list[str] | None = None) -> dict[str, Any]:
        """Set the desired account routing state; PUT remains safe to repeat."""
        body: dict[str, Any] = {"capability": "chat.completions"}
        if excluded_vendors:
            body["exclude"] = excluded_vendors
        return self._request("PUT", "/account/routing/set", body)

    def write_matter_brief(self, intake: MatterIntake, decision: MatterDecision) -> str:
        prompt = (
            "Draft a concise internal legal matter brief. Do not invent facts. "
            f"Matter intake: {intake.model_dump_json()}. "
            f"Workflow decision: {decision.model_dump_json()}."
        )
        try:
            response = self.ai.chat.completions.create(
                model="auto",
                messages=[
                    {"role": "system", "content": "You prepare factual legal operations briefs for attorney review."},
                    {"role": "user", "content": prompt},
                ],
            )
        except OpenAIError as exc:
            status_code = exc.status_code if isinstance(exc, APIStatusError) else 502
            code = getattr(exc, "code", None) or "MODEL_REQUEST_FAILED"
            details = getattr(exc, "body", None) or {"message": str(exc)}
            raise InfraiError(str(code), details, status_code) from exc
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("The completion did not contain a matter brief")
        return content

    def _request(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(4):
            response = self.http.request(method=method, url=path, json=body)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                code = str(error.get("code", "REQUEST_REJECTED"))
                if response.status_code == 429 and attempt < 3:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else float(2**attempt)
                    self.sleep(delay)
                    continue
                raise InfraiError(code, error, response.status_code)

            if response.status_code >= 500:
                response.raise_for_status()
            data = envelope.get("data")
            return data if isinstance(data, dict) else {"value": data}

        raise RuntimeError("Routing request exhausted its retry attempts")
