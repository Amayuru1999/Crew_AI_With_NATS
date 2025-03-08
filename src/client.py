import asyncio
from nats.aio.client import Client as NATS

async def send_task():
    nc = NATS()
    await nc.connect("nats://localhost:4222")

    # Define the task to send
    task_description = "Translate 'I am a Srilankan' to Sinhala"

    # ✅ Subscribe to the reply before sending
    async def reply_handler(msg):
        response = msg.data.decode()
        print(f"Received response from worker: {response}")

    await nc.subscribe("crew.tasks.reply", cb=reply_handler)

    # ✅ Send the task
    await nc.publish("crew.tasks", task_description.encode())
    print(f"Sent task: {task_description}")

    await asyncio.sleep(10)  # Wait for response

asyncio.run(send_task())
