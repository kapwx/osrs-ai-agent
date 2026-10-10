import json
import os
import time
import re
from dotenv import load_dotenv

load_dotenv()
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

from models import AgentAction

COMMON_FOODS = {
    "shrimps", "cooked chicken", "cooked meat", "bread", "trout", 
    "salmon", "tuna", "lobster", "bass", "swordfish", "monkfish", 
    "shark", "karambwan", "manta ray", "cake", "meat pie"
}

class GeminiBrain:
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.8-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.client = genai.Client(api_key=self.api_key) if (genai and self.api_key) else None

        # Free tier limit: 5 requests per minute -> min 13s between calls
        self.min_interval = float(os.getenv("GEMINI_MIN_INTERVAL", "13.0"))
        self.last_call_time = 0.0
        self.cooldown_until = 0.0
        self.last_decision = AgentAction(
            action_type="IDLE",
            reasoning="Initializing Gemini brain..."
        )

        self.system_instruction = (
            "You are an autonomous AI decision-maker controlling a character in an Old School RuneScape (OSRS) "
            "sandboxed research environment.\n"
            "You are fed real-time game telemetry every few seconds (health, prayer, run energy, animation status, "
            "inventory items, and nearby NPCs/objects).\n\n"
            "Decision Rules:\n"
            "1. Survival first: If HP is below 50% and food exists in inventory, immediately select 'EAT_FOOD'.\n"
            "2. If current animation is active (e.g. woodcutting, mining, attacking) and not in danger, return 'IDLE' to avoid spamming actions.\n"
            "3. If inventory is full (inventory_count >= 28), stop gathering and decide to deposit at the nearest bank or drop items.\n"
            "4. Choose logical targets based on distance and character safety.\n"
            "Always return a valid structured AgentAction JSON object."
        )

    def _check_local_reflexes(self, game_state: Dict[str, Any]) -> Optional[AgentAction]:
        """
        Fast local heuristics that execute instantly without consuming Gemini API tokens.
        """
        stats = game_state.get("stats", {})
        hp_current = stats.get("hp_current", 10)
        hp_max = stats.get("hp_max", 10)
        inventory = game_state.get("inventory", [])
        animation = game_state.get("animation")

        # 1. Emergency eating reflex
        if hp_max > 0 and (hp_current / hp_max) <= 0.4:
            for item in inventory:
                name = item.get("name", "").lower()
                if any(food in name for food in COMMON_FOODS) or "food" in name:
                    return AgentAction(
                        action_type="EAT_FOOD",
                        target_id=item.get("id"),
                        target_name=item.get("name"),
                        reasoning=f"Emergency Reflex: HP is critical ({hp_current}/{hp_max}). Consuming {item.get('name')} immediately."
                    )

        # 2. Animation active reflex (player already busy chopping, mining, attacking)
        if animation is not None and animation > 0:
            return AgentAction(
                action_type="IDLE",
                reasoning=f"Active Animation Reflex: Character is currently performing action (animation {animation}). Holding."
            )

        return None

    def analyze_game_state(self, game_state: Dict[str, Any]) -> AgentAction:
        if not genai:
            return AgentAction(
                action_type="IDLE",
                reasoning="The 'google-genai' library is not installed. Run 'pip install google-genai'."
            )
        if not self.client:
            return AgentAction(
                action_type="IDLE",
                reasoning="Gemini API Key is not configured. Please set GEMINI_API_KEY in your .env file."
            )

        now = time.time()

        # Step 1: Check fast local heuristics (0 ms, 0 API quota used)
        reflex_action = self._check_local_reflexes(game_state)
        if reflex_action:
            self.last_decision = reflex_action
            return reflex_action

        # Step 2: Check if in 429 quota backoff
        if now < self.cooldown_until:
            rem = int(self.cooldown_until - now)
            return AgentAction(
                action_type=self.last_decision.action_type,
                target_id=self.last_decision.target_id,
                target_name=self.last_decision.target_name,
                coordinates=self.last_decision.coordinates,
                reasoning=f"Free Tier 429 cooldown active ({rem}s remaining). Holding last action."
            )

        # Step 3: Rate limiting (enforce >= 13s between calls to stay under 5 RPM)
        time_since_last = now - self.last_call_time
        if time_since_last < self.min_interval:
            wait_rem = int(self.min_interval - time_since_last)
            return AgentAction(
                action_type=self.last_decision.action_type,
                target_id=self.last_decision.target_id,
                target_name=self.last_decision.target_name,
                coordinates=self.last_decision.coordinates,
                reasoning=f"Rate limiting ({wait_rem}s to next thought). {self.last_decision.reasoning}"
            )

        # Step 4: Perform Gemini inference
        prompt = (
            f"Current OSRS Game State:\n"
            f"```json\n{json.dumps(game_state, indent=2)}\n```\n\n"
            f"Analyze the situation and decide the next optimal action."
        )

        try:
            self.last_call_time = time.time()
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
                self.last_decision = result
                return result
            elif isinstance(result, dict):
                action = AgentAction(**result)
                self.last_decision = action
                return action
            elif response.text:
                action = AgentAction.model_validate_json(response.text)
                self.last_decision = action
                return action
            else:
                return AgentAction(action_type="IDLE", reasoning="Empty model response received.")

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                # Look for retry delay in error message (e.g. 'retry in 9.20s' or 'retryDelay: 57s')
                retry_match = re.search(r'retry in\s+([0-9\.]+)\s*s', err_str, re.IGNORECASE)
                if not retry_match:
                    retry_match = re.search(r'retryDelay[\'":\s]+([0-9]+)\s*s', err_str, re.IGNORECASE)
                
                cooldown_secs = float(retry_match.group(1)) + 1.0 if retry_match else 60.0
                cooldown_secs = max(cooldown_secs, 15.0)
                self.cooldown_until = time.time() + cooldown_secs

                print(f"[RATE LIMIT] Gemini 429 quota reached. Pausing API calls for {int(cooldown_secs)}s.")
                action = AgentAction(
                    action_type="IDLE",
                    reasoning=f"Rate limit reached (Free tier 5 RPM). Pausing API calls for {int(cooldown_secs)}s."
                )
                self.last_decision = action
                return action

            return AgentAction(
                action_type="IDLE",
                reasoning=f"Error during Gemini inference: {err_str}"
            )
