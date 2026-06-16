# Eburon AI Phone Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an Eburon AI phone support operations dashboard inside `examples/03_phone_and_rag_example` with CSV CRM import, SQLite persistence, outbound AI calling, inbound AI call monitoring, and a shadcn/ui React dashboard.

**Architecture:** Keep the example self-contained. Add focused backend modules for CRM storage and FastAPI/Twilio orchestration, then add a Vite + React + TypeScript dashboard that talks to JSON APIs and polls active calls.

**Tech Stack:** Python, FastAPI, SQLite, pytest, Twilio Media Streams, Vision Agents, Vite, React, TypeScript, shadcn/ui-style components, lucide-react.

---

### Task 1: Backend CRM Persistence

**Files:**
- Create: `examples/03_phone_and_rag_example/eburon_crm.py`
- Create: `examples/03_phone_and_rag_example/test_eburon_crm.py`

- [ ] Write tests for CSV import, metadata preservation, invalid-row reporting, contact listing, call records, and dashboard stats.
- [ ] Run `uv run pytest examples/03_phone_and_rag_example/test_eburon_crm.py -v` and verify tests fail because `eburon_crm` does not exist.
- [ ] Implement `EburonCRM` with SQLite schema for `contacts`, `uploads`, `calls`, and `notes`.
- [ ] Re-run the CRM tests and verify they pass.

### Task 2: Unified Phone Support App

**Files:**
- Create: `examples/03_phone_and_rag_example/eburon_support_app.py`
- Create: `examples/03_phone_and_rag_example/test_eburon_support_app.py`
- Create: `examples/03_phone_and_rag_example/knowledge/eburon_ai.md`
- Modify: `examples/03_phone_and_rag_example/pyproject.toml`

- [ ] Write tests for outbound request validation and API serialization without creating real Twilio calls.
- [ ] Run `uv run pytest examples/03_phone_and_rag_example/test_eburon_support_app.py -v` and verify tests fail because app helpers do not exist.
- [ ] Implement FastAPI routes for `/api/contacts`, `/api/contacts/upload`, `/api/calls`, `/api/calls/active`, `/api/dashboard/stats`, `/api/outbound-call`, `/twilio/voice`, and `/twilio/media/{call_id}/{token}`.
- [ ] Implement Eburon AI agent creation using `knowledge/eburon_ai.md` and the existing Gemini/Turbopuffer/Qdrant RAG options.
- [ ] Re-run support app tests and CRM tests.

### Task 3: Dashboard Frontend

**Files:**
- Create: `examples/03_phone_and_rag_example/dashboard/package.json`
- Create: `examples/03_phone_and_rag_example/dashboard/index.html`
- Create: `examples/03_phone_and_rag_example/dashboard/tsconfig.json`
- Create: `examples/03_phone_and_rag_example/dashboard/vite.config.ts`
- Create: `examples/03_phone_and_rag_example/dashboard/src/App.tsx`
- Create: `examples/03_phone_and_rag_example/dashboard/src/main.tsx`
- Create: `examples/03_phone_and_rag_example/dashboard/src/styles.css`
- Create: `examples/03_phone_and_rag_example/dashboard/src/lib/api.ts`
- Create: `examples/03_phone_and_rag_example/dashboard/src/components/ui/*`

- [ ] Add a Vite React TypeScript app using shadcn/ui-style primitives and lucide icons.
- [ ] Implement dashboard summary cards, CSV uploader, contact table, outbound call dialog, active call monitor, and call history.
- [ ] Run `npm install` in `dashboard/` if dependencies are missing, then `npm run build`.

### Task 4: Docs and Verification

**Files:**
- Modify: `examples/03_phone_and_rag_example/README.md`

- [ ] Document Eburon AI support setup, dashboard commands, required environment variables, CSV columns, and Twilio webhook URL.
- [ ] Run focused Python tests: `uv run pytest examples/03_phone_and_rag_example/test_eburon_crm.py examples/03_phone_and_rag_example/test_eburon_support_app.py -v`.
- [ ] Run frontend build: `npm run build` from `examples/03_phone_and_rag_example/dashboard`.
- [ ] Start the backend with `uv run python eburon_support_app.py` from the phone example directory and report the local dashboard URL.

## Self-Review

Spec coverage: CRM CSV import, SQLite persistence, Eburon knowledge, inbound/outbound Twilio calls, dashboard APIs, dashboard UI, and tests are covered. The plan intentionally does not include real CRM integration or browser softphone behavior because those are out of scope.

Placeholder scan: no placeholder steps remain. All files and commands are concrete.

Type consistency: backend modules are named `eburon_crm.py` and `eburon_support_app.py`; tests use the same names.
