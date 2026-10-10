import os
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from models import AgentAction

load_dotenv()

app = FastAPI(
    title="OSRS AI Agent Brain",
    description="Middleware connecting RuneLite game telemetry to AI decision engine (GPT-6 Astra / Gemini)",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Shared in-memory state
latest_game_state: Optional[Dict[str, Any]] = None
latest_action: AgentAction = AgentAction(
    action_type="IDLE",
    reasoning="Awaiting initial game state from RuneLite plugin..."
)

# Determine LLM Provider
provider = os.getenv("LLM_PROVIDER", "").strip().lower()
if not provider:
    if os.getenv("OPENAI_API_KEY"):
        provider = "openai"
    else:
        provider = "gemini"

if provider in ["openai", "astra"]:
    from astra_client import AstraBrain
    model_name = os.getenv("MODEL_NAME", "gpt-6-astra")
    print(f"[INIT] Initializing AstraBrain (Model: {model_name})")
    brain = AstraBrain(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name=model_name,
        base_url=os.getenv("OPENAI_BASE_URL")
    )
else:
    from gemini_client import GeminiBrain
    model_name = os.getenv("MODEL_NAME", "gemini-3.8-flash")
    print(f"[INIT] Initializing GeminiBrain (Model: {model_name})")
    brain = GeminiBrain(
        api_key=os.getenv("GEMINI_API_KEY"),
        model_name=model_name
    )

is_processing = False

def process_state_decision(state: Dict[str, Any]):
    global latest_action, is_processing
    try:
        action = brain.analyze_game_state(state)
        latest_action = action
        print(f"[BRAIN DECISION] {action.action_type} -> {action.target_name or 'N/A'}: {action.reasoning}")
    finally:
        is_processing = False

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "OSRS AI Agent Brain Middleware",
        "has_game_state": latest_game_state is not None
    }

@app.post("/api/state")
def receive_game_state(state: Dict[str, Any], background_tasks: BackgroundTasks):
    """
    Endpoint receiving game telemetry from RuneLite AgentPlugin
    """
    global latest_game_state, is_processing
    latest_game_state = state

    # Only spawn inference if not already processing
    if not is_processing:
        is_processing = True
        background_tasks.add_task(process_state_decision, state)

    return {
        "status": "received",
        "action": latest_action.model_dump() if latest_action else None
    }

@app.get("/api/action", response_model=AgentAction)
def get_current_action():
    """
    Endpoint polled by the Executor to retrieve the latest AI decision
    """
    return latest_action

@app.get("/api/state")
def get_latest_state():
    """
    Inspection endpoint for telemetry debugging
    """
    return latest_game_state or {"status": "No state received yet"}

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    print(f"Starting OSRS Brain Middleware on http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)
