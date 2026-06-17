import asyncio
import json
import logging
import os
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from vision_agents.core import Agent, User
from vision_agents.plugins import deepgram, elevenlabs, gemini, getstream

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Vision Agents Vercel API")

class StartAgentRequest(BaseModel):
    call_id: str
    call_type: str = "default"

@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.post("/api/token")
async def get_token(user_id: str):
    """Generate a Stream token for the frontend client."""
    api_key = os.getenv("STREAM_API_KEY")
    api_secret = os.getenv("STREAM_API_SECRET")
    
    if not api_key or not api_secret:
        raise HTTPException(status_code=500, detail="Stream credentials missing")
    
    # Simple token generation logic (using getstream plugin if available or direct)
    try:
        from getstream import Stream
        client = Stream(api_key=api_key, api_secret=api_secret)
        token = client.create_token(user_id)
        return {"token": token, "api_key": api_key}
    except Exception as e:
        logger.error(f"Token generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def run_agent_stream(call_id: str, call_type: str):
    """
    Streaming response generator to keep the Vercel function alive 
    while the agent is active.
    """
    try:
        # 1. Setup Agent
        llm = gemini.LLM("gemini-1.5-flash-latest")
        agent = Agent(
            edge=getstream.Edge(),
            agent_user=User(name="Vercel Agent", id="vercel-agent"),
            instructions="You're a friendly AI assistant running on Vercel. Keep it brief.",
            llm=llm,
            tts=elevenlabs.TTS(),
            stt=deepgram.STT(eager_turn_detection=True),
        )
        
        yield f"data: {json.dumps({'status': 'initializing', 'call_id': call_id})}\n\n"
        
        # 2. Join Call
        call = await agent.create_call(call_type, call_id)
        
        async with agent.join(call):
            yield f"data: {json.dumps({'status': 'joined', 'call_id': call_id})}\n\n"
            
            # Use simple_response to greet
            await agent.simple_response("Hello! I'm joining from Vercel.")
            
            # Keep alive loop
            start_time = asyncio.get_event_loop().time()
            # Vercel timeout is typically 10-60s. We'll run for up to 55s.
            MAX_RUNTIME = 55 
            
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > MAX_RUNTIME:
                    yield f"data: {json.dumps({'status': 'timeout_approaching', 'elapsed': elapsed})}\n\n"
                    break
                
                # Yield heartbeat to keep connection alive
                yield f"data: {json.dumps({'status': 'active', 'elapsed': elapsed})}\n\n"
                await asyncio.sleep(5)
                
            await agent.finish()
            yield f"data: {json.dumps({'status': 'finished'})}\n\n"
            
    except Exception as e:
        logger.error(f"Agent stream error: {e}")
        yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

@app.post("/api/start-agent")
async def start_agent(request: StartAgentRequest):
    """Trigger the agent to join a call via an SSE stream."""
    return StreamingResponse(
        run_agent_stream(request.call_id, request.call_type),
        media_type="text/event-stream"
    )
