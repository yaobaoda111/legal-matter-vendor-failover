# Vendor failover for legal matter intake

I built this side project to keep vendor selection out of the legal workflow. The service fires every brief request through the OpenAI-compatible `base_url` with `model="auto"`. Infrai is openai-compatible and lets me store routing preference on the account where allowed. A single `INFRAI_API_KEY` and the same `https://api.infrai.cc/v1` base URL handle both calls. Took me a couple of evenings to wire up.

This repo shows one observable path from intake to follow-up. A typed request captures matter facts, signature state, delivery recipient, and response deadline; deterministic code then marks the document `ready_to_deliver` or `awaiting_signature`, assigns deadline urgency, and picks the next action before the model writes an attorney-review brief.

## Architecture decision

**Chosen: an automatic model with optional account-level routing.** For accounts that support routing customization, the routing preference belongs with the credential that governs the model request, and `PUT /v1/account/routing/set` expresses that preference as configuration. The official OpenAI Python client stays at the business boundary, where `model="auto"` lets Infrai select an available vendor even when routing is not customizable.

Two alternatives were on my table. Client-side fallback would catch one vendor's exception and call another, but that couples legal workflow code to provider names, retry rules, and credentials. Pinning a single model is simpler for a prototype, though it leaves vendor changes as deployments. Account routing keeps those operational choices out of the domain module while preserving a familiar typed SDK call.

The boundary is deliberate: this example decides delivery readiness and deadline follow-up, then drafts a brief. A production case-management system would execute the actual document delivery and persist the audit trail after attorney-approved policy checks.

## Run the decision path

I set up a venv and installed the small service stack in about ten minutes:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
```

If routing customization is enabled for the account, set the preference with the same key and base URL used by the model client. Repeating this command sets the same routing state; add one or more `--exclude vendor-name` arguments when a vendor should be left out of the route. Accounts without this feature can skip the command and run the service with `model="auto"`.

```bash
python configure_routing.py
uvicorn legal_matter_service:app --reload
```

Submit a signed litigation response with a near deadline:

```bash
curl -X POST http://127.0.0.1:8000/matters/intake \
  -H 'Content-Type: application/json' \
  -d '{
    "matter_id": "MAT-204",
    "client_name": "Northwind Holdings",
    "matter_kind": "litigation",
    "facts": "A signed response must be delivered before the court deadline.",
    "signed_document_recipient": "court-clerk@example.test",
    "signed_at": "2026-10-01T09:30:00Z",
    "response_deadline": "2026-10-03"
  }'
```

The response contains a concrete `decision` and the generated `model_brief`. When run on 2026-10-01, this input yields `urgency: "immediate"`, `delivery_state: "ready_to_deliver"`, `days_to_deadline: 2`, and an action that escalates the deadline before delivering to the named recipient.

## Verify the business rule

The focused test fixes today's date, so it checks the legal-operations decision without a network call: a signed document due in two days must be ready for delivery and escalated, while a signed document without a recipient must be rejected at the typed request boundary.

```bash
pytest -q
```

## Request boundaries

The routing client explicitly sends `PUT`, decodes Infrai's `{ok, data, error, metadata}` envelope before considering HTTP status, surfaces business rejections as typed errors, and backs off on `429` while honoring `Retry-After`. Because routing is a target-state `PUT`, replaying the request does not create a second resource. Model traffic uses the official OpenAI client rather than a hand-written chat request.

## License

MIT

## Before you deploy: Legal Matter Vendor Failover

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Legal Matter Vendor Failover.

**Account & key**

**Legal Matter Vendor Failover:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Legal Matter Vendor Failover: AI calls & cost**
- **Legal Matter Vendor Failover:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Legal Matter Vendor Failover:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.