import asyncio
import json
from nats.aio.client import Client as NATS

CAPTAIN_TOPIC = "crew.captain"          # Captain receives tasks here
PROMPT_PROCESSOR_TOPIC = "agent.prompt_processor"
CAPTAIN_RESPONSE_TOPIC = "crew.captain.responses"

async def captain_agent():
    nc = NATS()
    await nc.connect("nats://localhost:4222")

    async def captain_handler(msg):
        """Handles user tasks and sends them to the PromptProcessorSubAgent."""
        task_data = json.loads(msg.data.decode())
        print(f"[Captain] Received Task: {task_data}")

        # Forward to PromptProcessorSubAgent
        await nc.publish(PROMPT_PROCESSOR_TOPIC, json.dumps(task_data).encode())

    # Subscribe to tasks from the client
    await nc.subscribe(CAPTAIN_TOPIC, cb=captain_handler)
    print("[Captain] Captain Agent is listening for tasks...")

    # Listen for final aggregated results from the ExecutorSubAgent
    async def final_result_handler(msg):
        result = json.loads(msg.data.decode())
        print(f"[Captain] Final Aggregated Result: {result}")
        # In a real system, you'd forward this back to the client

    await nc.subscribe(CAPTAIN_RESPONSE_TOPIC, cb=final_result_handler)

    await asyncio.Future()  # Keep the Captain Agent running

if __name__ == "__main__":
    asyncio.run(captain_agent())
