import asyncio
import logging
import os
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, WebSocket
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from twilio.rest import Client
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from vision_agents.core import Agent, User
from vision_agents.plugins import (
    deepgram,
    elevenlabs,
    gemini,
    getstream,
    qdrant,
    turbopuffer,
    twilio,
)

from eburon_crm import EburonCRM

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
load_dotenv()

EXAMPLE_DIR = Path(__file__).parent
DEFAULT_DB_PATH = EXAMPLE_DIR / "eburon_crm.sqlite3"
KNOWLEDGE_DIR = EXAMPLE_DIR / "knowledge"
RAG_BACKEND = os.environ.get("RAG_BACKEND", "gemini").lower()

file_search_store: gemini.FileSearchStore | None = None
rag = None


@dataclass
class OutboundCallJob:
    call_id: str
    from_number: str
    to_number: str
    contact_id: Optional[int]
    goal: str


class OutboundCallRequest(BaseModel):
    from_number: str
    contact_id: Optional[int] = None
    to_number: Optional[str] = None
    goal: str = "Call the contact, introduce Eburon AI support, and ask how we can help."


def _public_host(configured_host: Optional[str] = None) -> str:
    host = configured_host or os.environ.get("PUBLIC_HOST") or os.environ.get("NGROK_URL")
    if not host:
        raise RuntimeError("Set NGROK_URL or PUBLIC_HOST for Twilio media streams.")
    return host.removeprefix("https://").removeprefix("http://")


def _sanitize_phone_for_user_id(phone: str) -> str:
    return (
        phone.replace("+", "")
        .replace(" ", "")
        .replace("(", "")
        .replace(")", "")
        .replace("-", "")
    )


def serialize_twilio_call(call: twilio.TwilioCall) -> dict[str, object]:
    return {
        "call_id": call.call_sid,
        "caller": call.caller or call.from_number,
        "direction": call.direction,
        "from_number": call.from_number,
        "to_number": call.to_number,
        "started_at": call.started_at.isoformat(timespec="seconds"),
        "status": "active",
    }


async def create_rag_from_directory() -> None:
    global file_search_store, rag

    if not KNOWLEDGE_DIR.exists():
        logger.warning("Knowledge directory not found: %s", KNOWLEDGE_DIR)
        return

    if RAG_BACKEND == "turbopuffer":
        logger.info("Initializing TurboPuffer RAG from %s", KNOWLEDGE_DIR)
        rag = await turbopuffer.create_rag(
            namespace="eburon-ai-support",
            knowledge_dir=KNOWLEDGE_DIR,
            extensions=[".md"],
        )
    elif RAG_BACKEND == "qdrant":
        logger.info("Initializing Qdrant RAG from %s", KNOWLEDGE_DIR)
        rag = await qdrant.create_rag(
            collection="eburon-ai-support",
            knowledge_dir=KNOWLEDGE_DIR,
            extensions=[".md"],
        )
    else:
        logger.info("Initializing Gemini File Search from %s", KNOWLEDGE_DIR)
        file_search_store = await gemini.create_file_search_store(
            name="eburon-ai-support",
            knowledge_dir=KNOWLEDGE_DIR,
            extensions=[".md"],
        )


async def create_agent() -> Agent:
    instructions = """
You are Eburon AI phone support.
Use the Eburon AI knowledge base to answer questions accurately.
Keep phone replies concise, warm, and actionable.
Ask one clarifying question at a time.
If the caller needs account-specific help, collect a concise summary and offer a follow-up.
"""

    if RAG_BACKEND in ("turbopuffer", "qdrant"):
        if rag is None:
            raise RuntimeError(f"RAG backend '{RAG_BACKEND}' is not initialized.")
        llm = gemini.LLM("gemini-flash-lite-latest")

        @llm.register_function(
            description="Search Eburon AI product, support, pricing, and escalation knowledge."
        )
        async def search_eburon_knowledge(query: str) -> str:
            return await rag.search(query, top_k=3)
    else:
        llm = gemini.LLM(
            "gemini-flash-lite-latest",
            tools=[gemini.tools.FileSearch(file_search_store)],
        )

    return Agent(
        edge=getstream.Edge(),
        agent_user=User(id="eburon-ai-agent", name="Eburon AI Support"),
        instructions=instructions,
        tts=elevenlabs.TTS(voice_id=os.environ.get("ELEVENLABS_VOICE_ID", "FGY2WhTYpPnrIDTdsKH5")),
        stt=deepgram.STT(eager_turn_detection=True),
        llm=llm,
    )


def _build_default_outbound_starter(app: FastAPI) -> Callable[[OutboundCallJob], Awaitable[None]]:
    async def start_outbound_call(job: OutboundCallJob) -> None:
        twilio_client = Client(
            os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]
        )

        async def prepare_call():
            agent = await create_agent()
            phone_user = User(
                name=f"Outbound {job.to_number}",
                id=f"phone-{_sanitize_phone_for_user_id(job.to_number)}",
            )
            await agent.edge.create_users([agent.agent_user, phone_user])
            stream_call = await agent.create_call("default", call_id=job.call_id)
            return agent, phone_user, stream_call

        twilio_call = app.state.call_registry.create(job.call_id, prepare=prepare_call)
        url = (
            f"wss://{_public_host(app.state.public_host)}"
            f"/twilio/media/{job.call_id}/{twilio_call.token}"
        )
        twilio_client.calls.create(
            twiml=twilio.create_media_stream_twiml(url),
            to=job.to_number,
            from_=job.from_number,
        )

    return start_outbound_call


def create_app(
    crm: Optional[EburonCRM] = None,
    outbound_starter: Optional[Callable[[OutboundCallJob], Awaitable[None]]] = None,
    public_host: Optional[str] = None,
) -> FastAPI:
    app = FastAPI(title="Eburon AI Phone Support")
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

    app.state.crm = crm or EburonCRM(DEFAULT_DB_PATH)
    app.state.call_registry = twilio.TwilioCallRegistry()
    app.state.public_host = public_host
    app.state.outbound_starter = outbound_starter or _build_default_outbound_starter(app)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception: %s\n%s", exc, traceback.format_exc())
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.on_event("startup")
    async def startup() -> None:
        if outbound_starter is None:
            await create_rag_from_directory()

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "online", "service": "Eburon AI Phone Support"}

    @app.get("/api/contacts")
    async def contacts(search: Optional[str] = None) -> list[dict[str, object]]:
        return app.state.crm.list_contacts(search=search)

    @app.post("/api/contacts/upload")
    async def upload_contacts(file: UploadFile = File(...)) -> dict[str, object]:
        content = await file.read()
        return app.state.crm.import_contacts_csv(content, file.filename or "contacts.csv")

    @app.get("/api/calls")
    async def calls() -> list[dict[str, object]]:
        return app.state.crm.list_calls()

    @app.get("/api/calls/active")
    async def active_calls() -> list[dict[str, object]]:
        return [
            serialize_twilio_call(call)
            for call in app.state.call_registry.list_active()
        ]

    @app.get("/api/dashboard/stats")
    async def dashboard_stats() -> dict[str, int]:
        active_count = len(app.state.call_registry.list_active())
        return app.state.crm.dashboard_stats(active_calls=active_count)

    @app.post("/api/outbound-call")
    async def outbound_call(request: OutboundCallRequest) -> dict[str, object]:
        contact_id = request.contact_id
        to_number = request.to_number

        if contact_id is not None:
            contact = app.state.crm.get_contact(contact_id)
            to_number = str(contact["phone"])

        if not to_number:
            raise HTTPException(
                status_code=400,
                detail="Provide either contact_id or to_number for outbound calls.",
            )

        call_id = str(uuid.uuid4())
        app.state.crm.create_call_record(
            call_id=call_id,
            contact_id=contact_id,
            direction="outbound",
            from_number=request.from_number,
            to_number=to_number,
            status="queued",
        )
        job = OutboundCallJob(
            call_id=call_id,
            contact_id=contact_id,
            from_number=request.from_number,
            to_number=to_number,
            goal=request.goal,
        )

        try:
            await app.state.outbound_starter(job)
        except Exception as exc:
            app.state.crm.update_call_status(call_id, "failed", ended=True, outcome=str(exc))
            raise

        return app.state.crm.get_call(call_id)

    @app.post("/twilio/voice")
    async def twilio_voice_webhook(
        _: None = Depends(twilio.verify_twilio_signature),
        data: twilio.CallWebhookInput = Depends(twilio.CallWebhookInput.as_form),
    ):
        call_id = str(uuid.uuid4())
        phone_number = data.from_number or "unknown"

        app.state.crm.create_call_record(
            call_id=call_id,
            direction="inbound",
            from_number=phone_number,
            to_number=data.to or "unknown",
            status="ringing",
        )

        async def prepare_call():
            agent = await create_agent()
            phone_user = User(
                name=f"Call from {phone_number}",
                id=f"phone-{_sanitize_phone_for_user_id(phone_number)}",
            )
            await agent.edge.create_users([agent.agent_user, phone_user])
            stream_call = await agent.create_call("default", call_id=call_id)
            return agent, phone_user, stream_call

        twilio_call = app.state.call_registry.create(
            call_id,
            data,
            prepare=prepare_call,
        )
        url = (
            f"wss://{_public_host(app.state.public_host)}"
            f"/twilio/media/{call_id}/{twilio_call.token}"
        )
        app.state.crm.update_call_status(call_id, "in_progress")
        return twilio.create_media_stream_response(url)

    @app.websocket("/twilio/media/{call_id}/{token}")
    async def media_stream(websocket: WebSocket, call_id: str, token: str):
        twilio_call = app.state.call_registry.validate(call_id, token)
        twilio_stream = twilio.TwilioMediaStream(websocket)
        await twilio_stream.accept()
        twilio_call.twilio_stream = twilio_stream

        try:
            agent, phone_user, stream_call = await twilio_call.await_prepare()
            twilio_call.stream_call = stream_call

            await twilio.attach_phone_to_call(stream_call, twilio_stream, phone_user.id)

            async with agent.join(stream_call, participant_wait_timeout=0):
                await agent.simple_response(
                    text=(
                        "Greet the caller as Eburon AI support, ask how you can help, "
                        "and use the knowledge base for accurate product answers."
                    )
                )
                await twilio_stream.run()
            app.state.crm.update_call_status(call_id, "completed", ended=True)
        finally:
            app.state.call_registry.remove(call_id)

    dashboard_dist = EXAMPLE_DIR / "dashboard" / "dist"
    if dashboard_dist.exists():
        app.mount("/", StaticFiles(directory=dashboard_dist, html=True), name="dashboard")

    return app


app = create_app()


if __name__ == "__main__":
    logger.info("Starting Eburon AI phone support with RAG_BACKEND=%s", RAG_BACKEND)
    uvicorn.run(app, host="localhost", port=8000)
