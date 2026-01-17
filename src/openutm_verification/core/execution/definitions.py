from typing import Any, Dict, List

from pydantic import BaseModel, Field


class StepDefinition(BaseModel):
    id: str | None = Field(None, description="Unique identifier for the step. If not provided, it defaults to the step name.")
    step: str = Field(..., description="The operation/function to execute (human-readable name)")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the operation")
    needs: List[str] = Field(default_factory=list, description="List of step IDs this step depends on")
    background: bool = Field(False, description="Whether to run this step in the background")
    description: str | None = None
    if_condition: str | None = Field(None, alias="if", description="Conditional expression to determine if step should run")


class ScenarioDefinition(BaseModel):
    name: str
    description: str | None = None
    steps: List[StepDefinition]
