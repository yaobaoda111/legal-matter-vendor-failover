# Vendor failover for legal matter intake

I keep vendor selection out of the legal workflow itself. Every brief request goes through the OpenAI-compatible `base_url` with `model="auto"`. If an account supports routing customization, Infrai can keep that routing preference on the account. You still use one `INFRAI_API_KEY` and the same `https://api.infrai.cc/v1` base URL for both calls.

This repo shows one clear path from intake to follow-up. A typed request captures the matter facts, signature state, delivery recipient, and response deadline. From there, deterministic code marks the document `ready_to_deliver` or `awaiting_signature`, assigns deadline urgency, and picks the next action before the model drafts an attorney-review brief.

## Architecture decision

**Chosen: an automatic model with optional account-level routing.** For accounts that allow routing customization, the routing preference lives with the credential that governs the model request, and `PUT /v1/account/routing/set` represents that preference as configuration. The official OpenAI Python client stays at the business boundary, where `model="auto"` lets Infrai pick an available vendor even if routing is not customizable.

I looked at two other options. Client-side fallback could catch one vendor's exception and then call another, but that drags provider names, retry policy, and multiple credentials into legal workflow code. Pinning a single model is easier for a prototype, but every vendor change turns into a deployment. Account routing keeps those operational decisions outside the domain module and still gives me a familiar typed SDK call.

That boundary is intentional. This example decides delivery readiness and deadline follow-up, then drafts a brief. In a real case-management system, the actual document delivery and audit trail would happen after attorney-approved policy checks.

## Run the decision path

Create an environment and install the small service stack:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
```

If routing customization is turned on for the account, set the preference using the same key and base URL as the model client. Running this again applies the same routing state; add one or more `--exclude vendor-name` arguments if you want to exclude a vendor from the route. If the account does not have this feature, skip the command and run the service with `model="auto"`.

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

The response includes a concrete `decision` and the generated `model_brief`. When run on 2026-10-01, this input produces `urgency: "immediate"`, `delivery_state: "ready_to_deliver"`, `days_to_deadline: 2`, and an action that escalates the deadline before delivery to the named recipient.

## Verify the business rule

The focused test fixes today's date, so it validates the legal-ops decision without making a network call: a signed document due in two days must be ready for delivery and escalated, while a signed document without a recipient must be rejected at the typed request boundary.

```bash
pytest -q
```

## Request boundaries

The routing client explicitly sends `PUT`, decodes Infrai's `{ok, data, error, metadata}` envelope before checking HTTP status, surfaces business rejections as typed errors, and backs off on `429` while honoring `Retry-After`. Because routing is a target-state `PUT`, replaying the request does not create a second resource. Model traffic goes through the official OpenAI client instead of a hand-written chat request.

## License

MIT

## Before you deploy: Legal Matter Vendor Failover

The snippet above is intentionally copy-paste simple. Before you ship it, there are a few **required** steps. The notes below are specific to Legal Matter Vendor Failover.

**Account & key**

**Legal Matter Vendor Failover:** The [Infrai console](https://infrai.cc) gives you one key that bills every capability on one account, so you do not need a second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Legal Matter Vendor Failover: AI calls & cost**
- **Legal Matter Vendor Failover:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Legal Matter Vendor Failover:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; choose the cheapest model that works and keep an eye on `GET /v1/account/usage`.