from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from models import ChaoticInternAction, ChaoticInternObservation
except ImportError:
    from ..models import ChaoticInternAction, ChaoticInternObservation

try:
    from server.tasks import get_task, list_tasks
    from server.tools import use_tool, reset_email_log
    from server.graders import grade
except ImportError:
    from tasks import get_task, list_tasks
    from tools import use_tool, reset_email_log
    from graders import grade


class ChaoticInternEnvironment(Environment):

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._task_id = None
        self._task = None
        self._action_history = []
        self._done = False
        self._score = 0.0

    def reset(self, task_id: str = None) -> ChaoticInternObservation:
        # Pick task — cycle through tasks if none specified
        tasks = list_tasks()
        if task_id and task_id in tasks:
            self._task_id = task_id
        else:
            current_index = 0
            if self._task_id in tasks:
                current_index = (tasks.index(self._task_id) + 1) % len(tasks)
            self._task_id = tasks[current_index]

        self._task = get_task(self._task_id)
        self._action_history = []
        self._done = False
        self._score = 0.0
        self._state = State(episode_id=str(uuid4()), step_count=0)
        reset_email_log()

        return ChaoticInternObservation(
            task_id=self._task_id,
            task_description=self._task["description"],
            inbox=self._task["inbox"],
            tool_result=None,
            current_step=0,
            budget_remaining=self._task["max_steps"],
            score_so_far=0.0,
            done=False,
            reward=0.0,
            info={"available_tools": ["database", "email", "calendar", "calculator"]}
        )

    def step(self, action: ChaoticInternAction) -> ChaoticInternObservation:
        if self._done:
            return self._terminal_observation()

        self._state.step_count += 1
        budget_remaining = self._task["max_steps"] - self._state.step_count

        # Record action
        action_dict = {
            "action_type": action.action_type,
            "tool_name": action.tool_name,
            "tool_args": action.tool_args,
            "reasoning": action.reasoning,
            "decision_value": action.decision_value
        }
        self._action_history.append(action_dict)

        # Execute tool if needed
        tool_result = None
        if action.action_type == "USE_TOOL":
            tool_result = use_tool(action.tool_name, action.tool_args)

        # Compute step reward
        reward = self._compute_step_reward(action, tool_result)
        self._score += reward

        # If budget exhausted and no decision made, force one from last reasoning
        if budget_remaining <= 0 and action.action_type != "MAKE_DECISION":
            self._action_history.append({
                "action_type": "MAKE_DECISION",
                "tool_name": None,
                "tool_args": None,
                "reasoning": action.reasoning,
                "decision_value": action.reasoning[:200]
            })

        # Check if done
        if action.action_type == "MAKE_DECISION" or budget_remaining <= 0:
            self._done = True
            final_score, breakdown = grade(self._task_id, self._action_history)
            self._score = final_score
            return ChaoticInternObservation(
                task_id=self._task_id,
                task_description=self._task["description"],
                inbox=self._task["inbox"],
                tool_result=tool_result,
                current_step=self._state.step_count,
                budget_remaining=max(budget_remaining, 0),
                score_so_far=final_score,
                done=True,
                reward=final_score,
                info={"final_breakdown": breakdown}
            )

        return ChaoticInternObservation(
            task_id=self._task_id,
            task_description=self._task["description"],
            inbox=self._task["inbox"],
            tool_result=tool_result,
            current_step=self._state.step_count,
            budget_remaining=budget_remaining,
            score_so_far=round(self._score, 2),
            done=False,
            reward=round(reward, 2),
            info={}
        )

    def _compute_step_reward(
        self,
        action: ChaoticInternAction,
        tool_result: dict
    ) -> float:
        reward = 0.0

        # Reward useful tool calls
        if action.action_type == "USE_TOOL":
            if tool_result and tool_result.get("status") == "found":
                reward += 0.05
            elif tool_result and tool_result.get("status") == "error":
                reward -= 0.05

        # Small reward for non-empty reasoning
        if action.reasoning and len(action.reasoning.strip()) > 20:
            reward += 0.02

        # Penalise repeated identical tool calls
        if action.action_type == "USE_TOOL":
            duplicates = [
                a for a in self._action_history[:-1]
                if a.get("action_type") == "USE_TOOL"
                and a.get("tool_name") == action.tool_name
                and a.get("tool_args") == action.tool_args
            ]
            if duplicates:
                reward -= 0.05

        return reward

    def _terminal_observation(self) -> ChaoticInternObservation:
        return ChaoticInternObservation(
            task_id=self._task_id,
            task_description=self._task["description"],
            inbox=self._task["inbox"],
            tool_result=None,
            current_step=self._state.step_count,
            budget_remaining=0,
            score_so_far=self._score,
            done=True,
            reward=0.0,
            info={"note": "Episode already finished"}
        )

    @property
    def state(self) -> State:
        return self._state