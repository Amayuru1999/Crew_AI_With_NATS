import asyncio
from nats.aio.client import Client as NATS
from crewai import Agent, Task, Crew

async def crew_worker():
    nc = NATS()
    await nc.connect("nats://localhost:4222")  # Connect to NATS server

    async def message_handler(msg):
        """Handles incoming tasks from NATS."""
        subject = msg.subject
        data = msg.data.decode()

        print(f"Received task: {data}")

        # Create a Crew AI agent
        translator = Agent(name="Translator", role="Language expert")
        task = Task(description=data, agent=translator)
        crew = Crew(agents=[translator], tasks=[task])

        # Execute task
        result = crew.kickoff()

        # Send back the result
        await nc.publish(subject + ".reply", result.encode())

    await nc.subscribe("crew.tasks", cb=message_handler)
    print("Crew AI agent is listening for tasks...")
    await asyncio.Future()  # Keeps process running

asyncio.run(crew_worker())
