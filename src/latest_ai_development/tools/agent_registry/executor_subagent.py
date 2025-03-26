import asyncio
import json
from nats.aio.client import Client as NATS
from agent_registry import AgentRegistry
from dotenv import load_dotenv
load_dotenv()
EXECUTOR_TOPIC = "agent.executor"
CREW_RESPONSES_TOPIC = "crew.responses"
CLIENT_REPLY_TOPIC = "client.final.results"


# We'll assume sub-agents each have a NATS topic named: agent.<agent_id>
# e.g. agent.stock_news_agent, agent.stock_price_agent, etc.

async def executor_subagent():
    nc = NATS()
    await nc.connect("nats://localhost:4222")

    # Instantiate the Agent Registry
    registry = AgentRegistry()

    # We might receive multiple tasks in parallel,
    # so we store responses by task_id
    tasks_responses = {}

    async def executor_handler(msg):
        """
        Decides which sub-agent(s) to call using the agent registry.
        """
        structured_data = json.loads(msg.data.decode())
        print(f"[Executor] Received structured data: {structured_data}")

        # The user query might be in structured_data["original_task_data"]["task_description"]
        # or something similar. Let's assume:
        user_query = structured_data.get("original_task_data", {}).get("task_description", "N/A")
        task_id = structured_data.get("original_task_data", {}).get("task_id", "no-id")

        # 1. Search the registry for the best sub-agent
        best_agent_id = registry.search_best_agent(user_query, top_k=1)
        print(f"[Executor] Best match for '{user_query}' is: {best_agent_id}")

        if not best_agent_id:
            # Fallback: no match found
            final_result = {"task_id": task_id, "error": "No suitable sub-agent found."}
            await nc.publish(CLIENT_REPLY_TOPIC, json.dumps(final_result).encode())
            return

        # 2. Publish the request to that sub-agent
        subagent_data = {
            "task_id": task_id,
            "OP_CODE": structured_data.get("OP_CODE", "UNKNOWN"),
            "UserContext": structured_data.get("UserContext", {}),
            "ProcessContext": structured_data.get("ProcessContext", {}),
            "original_task_data": structured_data.get("original_task_data", {})
        }

        # e.g. agent.stock_news_agent
        subagent_topic = f"agent.{best_agent_id}"
        await nc.publish(subagent_topic, json.dumps(subagent_data).encode())

        # Prepare to receive exactly 1 response for this example
        tasks_responses[task_id] = []

    async def subagent_response_handler(msg):
        """
        Collect sub-agent responses and send final output to the client.
        """
        result_data = json.loads(msg.data.decode())
        task_id = result_data.get("task_id", "no-id")

        print(f"[Executor] Received sub-agent response: {result_data}")

        # Store the response
        if task_id not in tasks_responses:
            tasks_responses[task_id] = []
        tasks_responses[task_id].append(result_data)

        # For this example, we assume we only expect 1 sub-agent response
        # If you want multiple sub-agents, you'd wait for all or do parallel logic
        final_result = {
            "task_id": task_id,
            "aggregated_results": tasks_responses[task_id]
        }
        # Send final result to the client
        await nc.publish(CLIENT_REPLY_TOPIC, json.dumps(final_result).encode())
        # Clear the data for next request
        tasks_responses.pop(task_id, None)

    await nc.subscribe(EXECUTOR_TOPIC, cb=executor_handler)
    await nc.subscribe(CREW_RESPONSES_TOPIC, cb=subagent_response_handler)

    print("[Executor] ExecutorSubAgent is running with dynamic agent selection...")
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(executor_subagent())
