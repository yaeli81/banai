# AI agent protocol (Phase 5)

The chat agent turns a customer's request into **domain ops** and returns them as a **signed proposal**.
Nothing changes until the customer presses **Confirm**. Implements `docs/architecture.md` §5–6.

## Flow
1. **Send.** `POST /api/chat {messages, design, revision}`. The frontend always sends the latest committed design.
   The agent is called only for customer messages, never for manual edits.
2. **Agent turn** (`backend/app/agent/orchestrator.py`).
   - The system prompt holds the rules. The design and catalog go in a separate message, as data only.
   - The model must call one of two tools:
     - `propose_changes {summary, ops[]}`. The `ops` schema is generated from `app/domain/ops.py::Op`.
     - `ask_clarification {question}`.
   - Tool arguments are parsed with the domain op models, then dry-run with `apply_ops` on the design.
   - If an op is invalid, its `{code, path, message}` goes back to the model to fix. This happens at most 2 times;
     after that the customer gets a clarification reply.
3. **Proposal** `{proposalId, baseRevision, baseHash, ops, summary, changes, signature}`.
   - `ops` is the canonical parsed form.
   - `changes` is written by the server from the ops (`agent/describe.py`), so the card shows what will actually be applied.
   - `signature = HMAC-SHA256(PROPOSAL_SIGNING_KEY, {proposalId, ops, baseRevision, baseHash})`.
   - `baseHash` is the SHA-256 of the canonical design JSON.
   - The server stores nothing.
4. **Confirm.** `POST /api/proposals/apply {design, revision, proposal}`.
   - 403 `BAD_SIGNATURE` if the signature doesn't match.
   - 409 `STALE` if the revision or design hash differs.
   - Otherwise the ops are applied and the response is `{design, revision + 1}`. The frontend commits it with
     `store.commitDesign`, and the viewer and editor re-render.
5. **Cancel** happens on the client only. A manual edit while a proposal is pending bumps the revision, so the card turns
   stale and Confirm is disabled.

## Errors (envelope `{success, data, error:{code, message}}`)
| Status | Code | When |
|---|---|---|
| 422 | `INVALID_REQUEST` / domain code | Malformed request or invalid design. The input is never echoed back. |
| 429 | `RATE_LIMITED` | More than `CHAT_RATE_LIMIT_PER_MINUTE` (default 20) requests per client. In-memory and per process. |
| 413 | `TOO_LARGE` | Body over 512 KB. |
| 503 | `AGENT_UNAVAILABLE` | No `OPENAI_API_KEY`. |
| 502 | `AGENT_ERROR` | OpenAI failed or timed out (30 s). Details are only logged. |

## Limits
- At most 20 messages of up to 2000 characters each, and the last one must come from the customer.
- At most 3 LLM calls per turn.
- The summary is capped at 300 characters and the question at 500.
- Control, zero-width, bidi and tag characters are stripped from model text.

## Configuration (backend env)
| Variable | Default | Notes |
|---|---|---|
| `OPENAI_API_KEY` | none | Without it, `/api/chat` returns 503. |
| `OPENAI_CHAT_MODEL` | `gpt-5.4-mini-2026-03-17` | A configurable default, not a business rule. |
| `PROPOSAL_SIGNING_KEY` | random per process | **Required in production.** If you rotate it, pending proposals stop working. |
| `AGENT_MODE` | `openai` | `fake` runs the scripted `FakeLlm`. It's allowed only with `APP_ENV=test`/`e2e`, and Playwright uses it. |

## Tests
- `backend/tests/agent/` and `backend/tests/test_api_agent.py` use a scripted LLM and make no network calls.
- `frontend/tests/unit/chat/chatAgent.test.js` and `client.test.js`.
- `frontend/tests/e2e/ux.spec.js` › "AI chat agent" runs the full stack with the fake agent.
