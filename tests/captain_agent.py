import asyncio
import json
from nats.aio.client import Client as NATS

CAPTAIN_TOPIC = "crew.captain"          # Captain receives tasks here
PROMPT_PROCESSOR_TOPIC = "agent.prompt_processor"
CAPTAIN_RESPONSE_TOPIC = "crew.captain.responses"

async def captain_agent():
    nc = NATS()
    await nc.connect("nats://localhost:4222")
    running = True

    async def captain_handler(msg):
        task_data = json.loads(msg.data.decode())
        print(f"[Captain] Received Task: {task_data}")
        
        # Wrap the task data
        wrapped_data = {
            "original_task_data": task_data
        }
        await nc.publish(PROMPT_PROCESSOR_TOPIC, json.dumps(wrapped_data).encode())

    # Subscribe to tasks from the client
    sub1 = await nc.subscribe(CAPTAIN_TOPIC, cb=captain_handler)
    print("[Captain] Captain Agent is listening for tasks...")

    # Listen for final aggregated results
    async def final_result_handler(msg):
        result = json.loads(msg.data.decode())
        print(f"[Captain] Final Aggregated Result: {result}")

    sub2 = await nc.subscribe(CAPTAIN_RESPONSE_TOPIC, cb=final_result_handler)

    try:
        while running:
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        await sub1.unsubscribe()
        await sub2.unsubscribe()
        await nc.close()

if __name__ == "__main__":
    asyncio.run(captain_agent())

