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

        translator = Agent(
            name="Translator",
            role="Language expert",
            goal="Accurately translate texts from various languages.",
            backstory="A highly trained AI model with expertise in linguistics and translation."
        )

        task = Task(
            description=data,
            agent=translator,
            expected_output="The translated text in English."
        )

        crew = Crew(agents=[translator], tasks=[task])

        # Execute task and get the output
        result = crew.kickoff()

        # ✅ Convert result to string before publishing
        response = str(result)
        print(f"Sending response: {response}")

        await nc.publish(subject + ".reply", response.encode())

    # ✅ Fix: Subscribe **after** defining `message_handler`
    await nc.subscribe("crew.tasks", cb=message_handler)
    print("Crew AI agent is listening for tasks...")

    await asyncio.Future()  # Keeps process running

asyncio.run(crew_worker())
