import asyncio
import json
import os
import sys
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "https://api.groq.com/openai/v1")
API_KEY = os.getenv("API_KEY") or os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "llama-3.1-8b-instant")

MAX_STEPS = 10
SUCCESS_SCORE_THRESHOLD = 0.5
BENCHMARK = "chaotic_intern_env"
TASKS = ["invoice_processor", "meeting_scheduler", "budget_reallocation"]


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


def build_prompt(obs_dict: dict, history: List[str]) -> str:
    inbox_text = ""
    for msg in obs_dict.get("inbox", []):
        inbox_text += (
            f"\nFrom: {msg.get('from', '')}"
            f"\nSubject: {msg.get('subject', '')}"
            f"\nTime: {msg.get('timestamp', '')}"
            f"\nBody: {msg.get('body', '')}\n---"
        )

    tool_result = obs_dict.get("tool_result")
    tool_text = (
        f"\nLast tool result: {json.dumps(tool_result)}" if tool_result else ""
    )

    history_text = "\n".join(history[-5:]) if history else "None"

    return f"""You are an intern at a tech startup called Veltra AI.

Your task: {obs_dict.get('task_description', '')}

Your inbox:
{inbox_text}
{tool_text}

Steps taken so far: {obs_dict.get('current_step', 0)}
Budget remaining: {obs_dict.get('budget_remaining', 0)}
Score so far: {obs_dict.get('score_so_far', 0.0)}

Recent actions:
{history_text}

Available tools: database, email, calendar, calculator

You must respond with a JSON object only. No explanation outside the JSON.
Choose ONE action from: USE_TOOL, SEND_MESSAGE, MAKE_DECISION, ASK_CLARIFICATION

For USE_TOOL:
{{"action_type": "USE_TOOL", "tool_name": "database", "tool_args": {{"query": "your query"}}, "reasoning": "why you are querying this", "decision_value": null}}

For SEND_MESSAGE:
{{"action_type": "SEND_MESSAGE", "tool_name": "email", "tool_args": {{"to": "email@example.com", "subject": "Subject", "body": "Body text"}}, "reasoning": "why you are sending this", "decision_value": null}}

For MAKE_DECISION:
{{"action_type": "MAKE_DECISION", "tool_name": null, "tool_args": null, "reasoning": "your full reasoning", "decision_value": "your final answer"}}

RULES:
- If budget_remaining is 3 or less, you MUST use MAKE_DECISION immediately.
- MAKE_DECISION requires a non-null decision_value. Never leave it null.
- For invoice tasks: decision_value must be the payment amount as digits only e.g. "1450"
- For meeting tasks: decision_value must be the day and time e.g. "Wednesday 10am"
- For budget tasks: decision_value must say what you block, approve, and escalate e.g. "Block 8000 marketing spend, escalate to priya.nair@veltra.ai, approve 85 office supplies"
- Query the database ONCE then decide. Do not repeat the same query.
- Think carefully. Some messages are misleading. Verify before deciding.
"""


def get_model_action(client: OpenAI, obs_dict: dict, history: List[str]) -> dict:
    prompt = build_prompt(obs_dict, history)
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content.strip()

        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        return json.loads(content)

    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        return {
            "action_type": "MAKE_DECISION",
            "tool_name": None,
            "tool_args": None,
            "reasoning": "Fallback decision due to model error",
            "decision_value": "unknown"
        }


def run_task(task_id: str) -> float:
    sys.path.insert(0, ".")
    from server.chaotic_intern_env_environment import ChaoticInternEnvironment
    from models import ChaoticInternAction

    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    env = ChaoticInternEnvironment()

    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    try:
        obs = env.reset(task_id)
        obs_dict = obs.model_dump()

        for step in range(1, MAX_STEPS + 1):
            if obs_dict.get("done"):
                break

            action_dict = get_model_action(client, obs_dict, history)
            action_str = action_dict.get("action_type", "MAKE_DECISION")

            try:
                action = ChaoticInternAction(
                    action_type=action_dict.get("action_type", "MAKE_DECISION"),
                    tool_name=action_dict.get("tool_name"),
                    tool_args=action_dict.get("tool_args"),
                    reasoning=action_dict.get("reasoning", ""),
                    decision_value=action_dict.get("decision_value")
                )
            except Exception as e:
                print(f"[DEBUG] Action parse error: {e}", flush=True)
                action = ChaoticInternAction(
                    action_type="MAKE_DECISION",
                    tool_name=None,
                    tool_args=None,
                    reasoning="Parse error fallback",
                    decision_value="unknown"
                )
                action_str = "MAKE_DECISION"

            obs = env.step(action)
            obs_dict = obs.model_dump()

            reward = obs_dict.get("reward", 0.0)
            done = obs_dict.get("done", False)
            rewards.append(reward)
            steps_taken = step

            log_step(
                step=step,
                action=action_str,
                reward=reward,
                done=done,
                error=None
            )

            history.append(
                f"Step {step}: {action_str} -> reward {reward:+.2f}"
            )

            if done:
                break

        score = obs_dict.get("score_so_far", 0.0)
        score = round(min(max(score, 0.0), 1.0), 4)
        success = score >= SUCCESS_SCORE_THRESHOLD

    except Exception as e:
        print(f"[DEBUG] Episode error: {e}", flush=True)

    finally:
        log_end(
            success=success,
            steps=steps_taken,
            score=score,
            rewards=rewards
        )

    return score


def main():
    all_scores = []
    for task_id in TASKS:
        print(f"[DEBUG] Running task: {task_id}", flush=True)
        score = run_task(task_id)
        all_scores.append(score)
        print(f"[DEBUG] Task {task_id} score: {score}", flush=True)

    avg = round(sum(all_scores) / len(all_scores), 4)
    print(f"[DEBUG] All scores: {all_scores}", flush=True)
    print(f"[DEBUG] Average score: {avg}", flush=True)


if __name__ == "__main__":
    main()