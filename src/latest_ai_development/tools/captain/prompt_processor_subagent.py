import asyncio
import json
from nats.aio.client import Client as NATS

PROMPT_PROCESSOR_TOPIC = "agent.prompt_processor"
EXECUTOR_TOPIC = "agent.executor"

async def prompt_processor_subagent():
    nc = NATS()
    await nc.connect("nats://localhost:4222")

    async def prompt_processor_handler(msg):
        """Parses the user prompt into OP_CODE, user context, and process context."""
        task_data = json.loads(msg.data.decode())
        user_prompt = task_data.get("task_description", "N/A")

        print(f"[PromptProcessor] Processing prompt: {user_prompt}")

        # Example: Convert prompt to OP_CODE and contexts
        structured_data = {
            "task_id": task_data.get("task_id"),  # ← ensure task_id is accessible
            "OP_CODE": "STOCK_RECOMMENDATION",
            "UserContext": {"preference": "short_term_gains"},
            "ProcessContext": {"history": "some conversation data"},
            "original_task_data": task_data
        }

        # Forward to ExecutorSubAgent
        await nc.publish(EXECUTOR_TOPIC, json.dumps(structured_data).encode())

    await nc.subscribe(PROMPT_PROCESSOR_TOPIC, cb=prompt_processor_handler)
    print("[PromptProcessor] Listening for prompts...")

    await asyncio.Future()  # Keep running

if __name__ == "__main__":
    asyncio.run(prompt_processor_subagent())
