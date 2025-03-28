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
    tasks_expected_count={}

    async def executor_handler(msg):
        structured_data = json.loads(msg.data.decode())
        print(f"[Executor] Received structured data: {structured_data}")

        user_query = structured_data.get("original_task_data", {}).get("task_description", "N/A")
        task_id = structured_data.get("original_task_data", {}).get("task_id", "no-id")

        # Instead of searching for a single best agent, broadcast to all three
        all_agent_ids = ["stock_news_agent", "stock_price_agent", "price_predictor_agent"]

        # Prepare the tasks_responses entry so we can collect 3 responses
        tasks_responses[task_id] = []
        # We'll store how many sub-agents we expect
        tasks_expected_count[task_id] = len(all_agent_ids)

        # Publish to each sub-agent
        for agent_id in all_agent_ids:
            subagent_data = {
                "task_id": task_id,
                "OP_CODE": structured_data.get("OP_CODE", "UNKNOWN"),
                "UserContext": structured_data.get("UserContext", {}),
                "ProcessContext": structured_data.get("ProcessContext", {}),
                "original_task_data": structured_data.get("original_task_data", {})
            }
            subagent_topic = f"agent.{agent_id}"
            await nc.publish(subagent_topic, json.dumps(subagent_data).encode())

    async def subagent_response_handler(msg):
        result_data = json.loads(msg.data.decode())
        task_id = result_data.get("task_id", "no-id")

        print(f"[Executor] Received sub-agent response: {result_data}")

        # Store the response
        if task_id not in tasks_responses:
            tasks_responses[task_id] = []
        tasks_responses[task_id].append(result_data)

        # Check if we have received all the responses we expect
        if len(tasks_responses[task_id]) == tasks_expected_count[task_id]:
            # All sub-agents responded, aggregate
            final_result = {
                "task_id": task_id,
                "aggregated_results": tasks_responses[task_id]
            }
            # Send final result to the client
            await nc.publish(CLIENT_REPLY_TOPIC, json.dumps(final_result).encode())
            # Cleanup
            tasks_responses.pop(task_id, None)
            tasks_expected_count.pop(task_id, None)

    await nc.subscribe(EXECUTOR_TOPIC, cb=executor_handler)
    await nc.subscribe(CREW_RESPONSES_TOPIC, cb=subagent_response_handler)

    print("[Executor] ExecutorSubAgent is running with dynamic agent selection...")
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(executor_subagent())
