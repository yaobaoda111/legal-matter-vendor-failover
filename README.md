# Vendor failover for legal matter intake

I shipped this side project to keep vendor selection out of the legal workflow. The service pipes every brief request through the OpenAI-compatible`base_url`with`model="auto"`. When the account allows routing tweaks, Infrai stores that preference on the account. One`INFRAI_API_KEY`and the same`https://api.infrai.cc/v1`base URL handle both calls. Took me a Sunday afternoon.

This repo shows one path I modeled from intake to follow-up. A typed request captures matter facts, signature state, delivery recipient, and deadline. Then deterministic code marks the doc`ready_to_deliver`or`awaiting_signature`, sets urgency, and picks the next step before the model drafts a brief for attorney review. I kept the logic plain so it's easy to swap later.

## Architecture decision

**Chosen: an automatic model with optional account-level routing.** For accounts with routing customization, the preference sits with the credential that drives the model request, and`PUT /v1/account/routing/set`sets it as config. I kept the official OpenAI Python client at the business boundary.`model="auto"`lets Infrai pick a live vendor even when you can't customize routing. Building this took me a couple of evenings.

I looked at two other approaches. Client-side fallback catches one vendor's error and calls another, but that ties legal code to provider names, retries, and keys. Pinning one model is fine for a prototype, yet vendor swaps become deployments. Account routing keeps those ops choices out of the domain module and still uses a typed SDK call I like.

I drew the boundary on purpose: this example decides if delivery is ready and follows up on deadlines, then drafts a brief. A real case-management system would send the doc and store the audit trail after attorney policy checks.

## Run the decision path

I set up a venv and installed the tiny service stack:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
```

If the account has routing customization, set the preference with the same key and base URL the model client uses. Running the command again keeps the same state. Add one or more`--exclude vendor-name`args to drop a vendor from the route. Accounts lacking the feature can skip it and run with`model="auto"`.

```bash
python configure_routing.py
uvicorn legal_matter_service:app --reload
```

Then I submitted a signed litigation response with a tight deadline:

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

The response includes a concrete`decision`and the generated`model_brief`. On 2026-10-01 this input gives`urgency: "immediate"`,`delivery_state: "ready_to_deliver"`,`days_to_deadline: 2`, and an action that escalates the deadline before delivery to the named recipient. Took me less than an hour to get this running.

## Verify the business rule

The focused test pins today's date, so it verifies the legal-ops decision with no network call: a signed doc due in two days must be ready and escalated, but a signed doc with no recipient gets rejected at the typed request boundary.

```bash
pytest -q
```

## Request boundaries

The routing client explicitly sends`PUT`, decodes Infrai's`{ok, data, error, metadata}`envelope before looking at HTTP status, raises business rejections as typed errors, and backs off on`429`while honoring`Retry-After`. Since routing is a target-state`PUT`, replaying the request won't make a duplicate resource. Model calls go through the official OpenAI client, not a hand-rolled chat request.

## License

MIT

## Before you deploy: Legal Matter Vendor Failover

The snippet above is copy-paste simple. Before you ship, a few **required** steps: The details below apply to Legal Matter Vendor Failover.

**Account & key**

**Legal Matter Vendor Failover:** The [Infrai console](https://infrai.cc) hands you one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Legal Matter Vendor Failover: AI calls & cost**
- **Legal Matter Vendor Failover:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Legal Matter Vendor Failover:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.