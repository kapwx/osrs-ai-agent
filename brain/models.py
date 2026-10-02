from typing import Optional
from pydantic import BaseModel, Field

class Coordinates(BaseModel):
    x: int = Field(default=0, description="X coordinate")
    y: int = Field(default=0, description="Y coordinate")

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
    coordinates: Optional[Coordinates] = Field(
        default=None,
        description="Destination coordinates if moving"
    )
    reasoning: str = Field(
        description="Detailed strategic explanation of why this action was decided based on current HP, inventory, and surroundings"
    )
