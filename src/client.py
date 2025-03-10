import asyncio
from nats.aio.client import Client as NATS

async def send_task():
    nc = NATS()
    await nc.connect("nats://localhost:4222")


    tasks = [
        "Translate '你好世界' to English",
        "Summarize this article about artificial intelligence",
        "What is the capital of France?"
    ]


    async def reply_handler(msg):
        response = msg.data.decode()
        print(f"Received response from worker: {response}")

    await nc.subscribe("crew.tasks.reply", cb=reply_handler)


    for task_description in tasks:
        await nc.publish("crew.tasks", task_description.encode())
        print(f"Sent task: {task_description}")

    await asyncio.sleep(50)

asyncio.run(send_task())
