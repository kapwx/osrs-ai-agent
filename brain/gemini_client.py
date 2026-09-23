import json
import os
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

class AgentAction(BaseModel):
    action_type: str = Field(
        description="The primary action to take: 'IDLE', 'ATTACK_NPC', 'CLICK_OBJECT', 'WALK_TO', 'EAT_FOOD', 'BANK_DEPOSIT'"
    )
    target_id: Optional[int] = Field(
        default=None,
        description="ID of the target entity, object, or item"
    )
    target_name: Optional[str] = Field(
        default=None,
        description="Name of the target entity, object, or item (e.g. 'Goblin', 'Tree', 'Lobster')"
    )
    coordinates: Optional[Dict[str, int]] = Field(
        default=None,
        description="Destination coordinates {'x': ..., 'y': ...} if moving"
    )
    reasoning: str = Field(
        description="Detailed strategic explanation of why this action was decided based on current HP, inventory, and surroundings"
    )

class GeminiBrain:
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.8-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

        self.system_instruction = (
            "You are an autonomous AI decision-maker controlling a character in an Old School RuneScape (OSRS) "
            "sandboxed research environment.\n"
            "You are fed real-time game telemetry every 1-2 game ticks (health, prayer, run energy, animation status, "
            "inventory items, and nearby NPCs/objects).\n\n"
            "Decision Rules:\n"
            "1. Survival first: If HP is below 50% and food exists in inventory, immediately select 'EAT_FOOD'.\n"
            "2. If current animation is active (e.g. woodcutting, mining, attacking) and not in danger, return 'IDLE' to avoid spamming actions.\n"
            "3. If inventory is full (inventory_count >= 28), stop gathering and decide to deposit at the nearest bank or drop items.\n"
            "4. Choose logical targets based on distance and character safety.\n"
            "Always return a valid structured AgentAction JSON object."
        )

    def analyze_game_state(self, game_state: Dict[str, Any]) -> AgentAction:
        if not self.client:
            return AgentAction(
                action_type="IDLE",
                reasoning="Gemini API Key is not configured. Please set GEMINI_API_KEY in your .env file."
            )

        prompt = (
            f"Current OSRS Game State:\n"
            f"```json\n{json.dumps(game_state, indent=2)}\n```\n\n"
            f"Analyze the situation and decide the next optimal action."
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    response_mime_type="application/json",
                    response_schema=AgentAction,
                    temperature=0.2
                )
            )

            result = response.parsed
            if isinstance(result, AgentAction):
                return result
            elif isinstance(result, dict):
                return AgentAction(**result)
            elif response.text:
                return AgentAction.model_validate_json(response.text)
            else:
                return AgentAction(action_type="IDLE", reasoning="Empty model response received.")
        except Exception as e:
            return AgentAction(
                action_type="IDLE",
                reasoning=f"Error during Gemini inference: {str(e)}"
            )
