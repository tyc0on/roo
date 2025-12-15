"""
Roo Standalone - FastAPI Application

Main entrypoint for the Roo AI agent service.
"""
import json
import hmac
import hashlib
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse

from .config import get_settings, Settings
from .agent import RooAgent, get_agent
from .slack_client import post_message


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    settings = get_settings()
    print(f"🦘 Roo Standalone starting...")
    print(f"   LLM Provider: {settings.default_llm_provider}")
    print(f"   Skills Dir: {settings.SKILLS_DIR}")
    
    # Initialize agent on startup
    agent = get_agent()
    print(f"   Loaded {len(agent.skills)} skills")
    
    yield
    
    print("🦘 Roo Standalone shutting down...")


app = FastAPI(
    title="Roo Standalone",
    description="AI Agent Service with Skills-based Architecture",
    version="1.0.0",
    lifespan=lifespan
)


def verify_slack_signature(
    request: Request,
    settings: Settings = Depends(get_settings)
) -> bool:
    """Verify Slack request signature."""
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    
    # Check timestamp is recent (within 5 minutes)
    try:
        ts = int(timestamp)
        if abs(time.time() - ts) > 300:
            raise HTTPException(status_code=403, detail="Request timestamp too old")
    except ValueError:
        raise HTTPException(status_code=403, detail="Invalid timestamp")
    
    return True  # Full verification in middleware


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "roo",
        "message": "G'day! Roo is awake and ready 🦘"
    }


@app.post("/slack/events")
async def slack_events(request: Request):
    """
    Slack Events API webhook.
    
    Handles:
    - url_verification challenges
    - app_mention events
    - direct messages
    """
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Handle URL verification challenge
    if payload.get("type") == "url_verification":
        print("✅ Slack URL verification challenge")
        return {"challenge": payload.get("challenge")}
    
    # Handle events
    event = payload.get("event", {})
    event_type = event.get("type")
    
    print(f"📨 Received Slack event: {event_type}")
    
    if event_type == "app_mention":
        # Process mention asynchronously
        import asyncio
        asyncio.create_task(_handle_mention(event))
        return JSONResponse(status_code=200, content={})
    
    if event_type == "message" and not event.get("bot_id") and not event.get("subtype"):
        is_dm = event.get("channel_type") == "im"
        if is_dm:
            print(f"📨 Received DM from {event.get('user')}")
            import asyncio
            asyncio.create_task(_handle_mention(event))
            return JSONResponse(status_code=200, content={})
    
    return JSONResponse(status_code=200, content={})


async def _handle_mention(event: dict):
    """Handle an @Roo mention asynchronously."""
    try:
        user_id = event.get("user")
        text = event.get("text", "")
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        
        print(f"\n🦘 ROO MENTION: from {user_id} in {channel_id}")
        print(f"   Text: {text[:100]}...")
        
        agent = get_agent()
        result = await agent.handle_mention(
            text=text,
            user_id=user_id,
            channel_id=channel_id,
            thread_ts=thread_ts
        )
        
        if result.get("message"):
            post_message(
                channel=channel_id,
                text=result["message"],
                thread_ts=thread_ts
            )
        
        print(f"✅ Mention handled successfully (skill: {result.get('skill_used')})")
        
    except Exception as e:
        print(f"❌ Error handling mention: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            post_message(
                channel=event.get("channel"),
                text="Sorry mate, I ran into a bit of trouble. Mind trying again? 🤔",
                thread_ts=event.get("thread_ts") or event.get("ts")
            )
        except Exception:
            pass


@app.post("/slack/commands")
async def slack_commands(request: Request):
    """Slack Slash Commands webhook."""
    form = await request.form()
    command = form.get("command", "")
    text = form.get("text", "")
    user_id = form.get("user_id", "")
    
    print(f"📨 Slash command: {command} from {user_id}")
    
    return {
        "response_type": "ephemeral",
        "text": f"Command '{command}' received! (Not yet implemented)"
    }


@app.post("/api/mention")
async def api_mention(request: Request):
    """
    Direct API endpoint for triggering Roo mentions.
    
    Can be called from mlai-backend or other services.
    """
    payload = await request.json()
    
    text = payload.get("text", "")
    user_id = payload.get("user_id", "")
    channel_id = payload.get("channel_id")
    thread_ts = payload.get("thread_ts")
    
    agent = get_agent()
    result = await agent.handle_mention(
        text=text,
        user_id=user_id,
        channel_id=channel_id,
        thread_ts=thread_ts
    )
    
    return result
