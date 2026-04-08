from typing import Optional
from pydantic import Field
from openenv.core.env_server.types import Action, Observation


class ChaoticInternAction(Action):
    action_type: str = Field(
        ...,
        description="USE_TOOL | SEND_MESSAGE | MAKE_DECISION | ASK_CLARIFICATION"
    )
    tool_name: Optional[str] = Field(
        default=None,
        description="database | email | calendar | calculator | approval_system"
    )
    tool_args: Optional[dict] = Field(
        default=None,
        description="Arguments for the tool call e.g. {'query': 'vacation policy'}"
    )
    reasoning: str = Field(
        ...,
        description="Why the agent is taking this action"
    )
    decision_value: Optional[str] = Field(
        default=None,
        description="Final answer when action_type is MAKE_DECISION"
    )


class ChaoticInternObservation(Observation):
    task_id: str = Field(
        ...,
        description="Which task is active: invoice_processor | meeting_scheduler | budget_reallocation"
    )
    task_description: str = Field(
        ...,
        description="What the agent needs to accomplish"
    )
    inbox: list[dict] = Field(
        default_factory=list,
        description="Current messages visible to the agent"
    )
    tool_result: Optional[dict] = Field(
        default=None,
        description="Result from the last tool call"
    )
    current_step: int = Field(
        default=0,
        description="How many steps have been taken"
    )
    budget_remaining: int = Field(
        default=10,
        description="How many steps are left"
    )
    score_so_far: float = Field(
        default=0.0,
        description="Cumulative score in this episode"
    )
    done: bool = Field(
        default=False,
        description="Whether the episode is over"
    )
    reward: float = Field(
        default=0.0,
        description="Reward from the last step"
    )
    info: dict = Field(
        default_factory=dict,
        description="Extra grader info for debugging"
    )