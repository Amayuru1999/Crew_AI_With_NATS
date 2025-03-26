# import asyncio
# from nats.aio.client import Client as NATS
#
# async def send_task():
#     nc = NATS()
#     await nc.connect("nats://localhost:4222")
#
#
#     tasks = [
#         "Translate '你好世界' to English",
#         "Summarize this article about artificial intelligence",
#         "What is the capital of France?"
#     ]
#
#
#     async def reply_handler(msg):
#         response = msg.data.decode()
#         print(f"Received response from worker: {response}")
#
#     await nc.subscribe("crew.tasks.reply", cb=reply_handler)
#
#
#     for task_description in tasks:
#         await nc.publish("crew.tasks", task_description.encode())
#         print(f"Sent task: {task_description}")
#
#     await asyncio.sleep(50)
#
# asyncio.run(send_task())
import asyncio
import json
from nats.aio.client import Client as NATS

CAPTAIN_TOPIC = "crew.captain"
CLIENT_REPLY_TOPIC = "client.final.results"

async def client():
    nc = NATS()
    await nc.connect("nats://localhost:4222")

    # 1. Subscribe to final output
    async def final_result_handler(msg):
        final_output = json.loads(msg.data.decode())
        print("[Client] Final Output:", final_output)

    # The client listens on 'client.final.results' for the final aggregated result
    await nc.subscribe(CLIENT_REPLY_TOPIC, cb=final_result_handler)

    # 2. Publish a sample task to the Captain Agent
    task_data = {
        "task_id": "task-0002",
        "task_description": "What new stocks should I buy this week?",
        "task_type": "stock_recommendation"
    }

    # Send the task to the Captain Agent
    await nc.publish(CAPTAIN_TOPIC, json.dumps(task_data).encode())
    print("[Client] Sent task to Captain:", task_data)

    # Keep running to receive final output
    await asyncio.sleep(180)

asyncio.run(client())
