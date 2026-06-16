# Eburon AI Phone Support Design

## Goal

Create an Eburon AI phone support demo inside `examples/03_phone_and_rag_example` that lets operators upload CRM contacts from CSV, start outbound AI calls, monitor inbound AI-handled calls, and review call activity from a CRM dashboard.

This is an agent operations dashboard, not a browser softphone. Calls are handled by the Vision Agents + Twilio media-stream agent.

## Scope

In scope:

- Unified FastAPI app for inbound calls, outbound calls, CRM APIs, and dashboard serving.
- Eburon AI RAG knowledge in `knowledge/eburon_ai.md`.
- SQLite persistence for contacts, uploaded CRM data, call records, notes, lead status, and call direction/status.
- CSV upload for local demo CRM data.
- React frontend using shadcn-style UI components and assets.
- Dashboard views for summary metrics, contacts, outbound dialing, active call monitoring, and call history.

Out of scope:

- Human browser answering/speaking on calls.
- Real CRM integrations.
- Production authentication, billing, or multi-tenant account management.

## Architecture

Add `eburon_support_app.py` as the primary example server. It reuses the existing Twilio inbound webhook and media WebSocket flow, plus the outbound call flow from `outbound_phone_example.py`.

The backend owns:

- Twilio webhook routes: `/twilio/voice`, `/twilio/media/{call_id}/{token}`.
- CRM routes: contacts, CSV upload, notes, status updates, call history, dashboard stats.
- Outbound route: start an AI call to a selected contact or typed phone number.
- Persistence through SQLite in the example directory.
- RAG initialization from `knowledge/eburon_ai.md`.

The frontend lives under `examples/03_phone_and_rag_example/dashboard/` as a Vite + React + TypeScript app and talks to the FastAPI JSON APIs.

## Data Model

Use SQLite tables for:

- `contacts`: name, phone, email, company, status, source upload, metadata JSON, timestamps.
- `calls`: call id, contact id, direction, from/to number, status, started/ended timestamps, summary, outcome.
- `notes`: contact id, call id, note text, timestamp.
- `uploads`: filename, row counts, imported timestamp.

CSV import accepts common columns such as `name`, `phone`, `email`, `company`, and `status`. Unknown columns are preserved in metadata JSON. Phone numbers should be normalized enough for display and Twilio submission, but invalid rows should be reported instead of crashing the upload.

## Agent Behavior

The support agent uses `knowledge/eburon_ai.md` as the editable Eburon AI knowledge base. Instructions should make it concise, helpful, and escalation-aware. For inbound calls, the agent greets the caller and asks how it can help with Eburon AI. For outbound calls, the initiating dashboard request provides the call goal, contact context, and any CRM notes.

## Frontend

Build a work-focused CRM operations dashboard:

- Summary cards for active calls, total contacts, calls today, and follow-ups.
- CSV upload panel with import results.
- Contact table with search/filter, lead status badges, and call action.
- Dialer form for selected contact or manual number.
- Active call monitor polling backend state.
- Call history table with direction, status, duration, and notes.

Use shadcn/ui components for `Button`, `Card`, `Table`, `Input`, `Dialog`, `Badge`, `Tabs`, and `Toast`, with lucide icons for actions. Keep layout dense and operational, not a marketing landing page. Active call monitoring uses short polling against the backend stats and active-calls APIs.

## Testing

Add backend tests for CSV import parsing, SQLite persistence, dashboard stats, and outbound-call request validation. Avoid real Twilio calls in unit tests. UI verification should cover rendering, upload flow states, and API error handling where practical.

## Implementation Constraints

Use Vite + React + TypeScript for the dashboard and short polling for active-call updates. Do not introduce a real CRM dependency; CSV + SQLite remains the source of truth for this demo.
