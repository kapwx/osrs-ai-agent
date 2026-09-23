import os
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from gemini_client import GeminiBrain, AgentAction

load_dotenv()

app = FastAPI(
    title="OSRS AI Agent Brain",
    description="Middleware connecting RuneLite game telemetry to Gemini API decision engine",
    version="1.0.0"
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

brain = GeminiBrain(
    api_key=os.getenv("GEMINI_API_KEY"),
    model_name=os.getenv("MODEL_NAME", "gemini-3.8-flash")
)

def process_state_decision(state: Dict[str, Any]):
    global latest_action
    action = brain.analyze_game_state(state)
    latest_action = action
    print(f"[BRAIN DECISION] {action.action_type} -> {action.target_name or 'N/A'}: {action.reasoning}")

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
    global latest_game_state
    latest_game_state = state

    # Run AI inference in the background so HTTP response to game client remains fast (<10ms)
    background_tasks.add_task(process_state_decision, state)

    return {"status": "received", "tick": state.get("stats", {}).get("hp_current")}

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
