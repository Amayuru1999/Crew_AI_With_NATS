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

        # ✅ Multiple Agents
        translator = Agent(
            name="Translator",
            role="Language expert",
            goal="Accurately translate texts from various languages.",
            backstory="A highly trained AI model with expertise in linguistics and translation."
        )

        summarizer = Agent(
            name="Summarizer",
            role="Content summarizer",
            goal="Summarize long texts into short, concise summaries.",
            backstory="An AI model trained in text summarization and NLP."
        )

        qa_agent = Agent(
            name="QA Bot",
            role="Question Answering system",
            goal="Answer questions based on the given context.",
            backstory="An AI that specializes in answering user queries."
        )


        # ✅ Agent Selection Based on Task
        if "translate" in data.lower():
            selected_agent = translator
        elif "summarize" in data.lower():
            selected_agent = summarizer
        elif "question" in data.lower():
            selected_agent = qa_agent
        else:
            selected_agent = translator  # Default agent

        task = Task(
            description=data,
            agent=selected_agent,
            expected_output="A processed text output based on the request."
        )

        crew = Crew(agents=[translator, summarizer, qa_agent], tasks=[task])

        # Execute task and get the output
        result = crew.kickoff()

        # ✅ Convert result to string before publishing
        response = str(result)
        print(f"Sending response: {response}")

        await nc.publish(subject + ".reply", response.encode())

    # ✅ Subscribe before running the event loop
    await nc.subscribe("crew.tasks", cb=message_handler)
    print("Crew AI agents are listening for tasks...")

    await asyncio.Future()  # Keeps process running

asyncio.run(crew_worker())
