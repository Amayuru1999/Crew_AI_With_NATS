import asyncio
import json
from nats.aio.client import Client as NATS
from latest_ai_development.tools.agent_registry.agent_registry import AgentRegistry
from dotenv import load_dotenv

load_dotenv()

EXECUTOR_TOPIC = "agent.executor"
CREW_RESPONSES_TOPIC = "crew.responses"
CLIENT_REPLY_TOPIC = "client.final.results"

def extract_task_id(data):
    """Recursively extract task_id from nested dicts."""
    if not isinstance(data, dict):
        return "no-id"
    if "task_id" in data and data["task_id"]:
        return data["task_id"]
    for key in ["original_task_data"]:
        nested = data.get(key)
        if isinstance(nested, dict):
            tid = extract_task_id(nested)
            if tid != "no-id":
                return tid
    return "no-id"

async def executor_subagent():
    nc = NATS()
    await nc.connect("nats://localhost:4222")
    registry = AgentRegistry()

    tasks_responses = {}
    tasks_expected_count = {}

    async def executor_handler(msg):
        structured_data = json.loads(msg.data.decode())
        print(f"[Executor] Received structured data: {structured_data}")

        task_id = extract_task_id(structured_data)
        print(f"[Executor] Extracted task_id: {task_id}")

        # You may want to get agents dynamically from registry here, or keep static list:
        all_agent_ids = ["stock_news_agent", "stock_price_agent", "price_predictor_agent"]

        # Initialize response tracking only if not exists (handle retries)
        if task_id not in tasks_responses:
            tasks_responses[task_id] = []
            tasks_expected_count[task_id] = len(all_agent_ids)

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
            print(f"[Executor] Published to {subagent_topic} with task_id {task_id}")

    async def subagent_response_handler(msg):
        result_data = json.loads(msg.data.decode())
        print(f"[Executor] Received result data: {result_data}")

        task_id = extract_task_id(result_data)
        print(f"[Executor] Extracted task_id from sub-agent response: {task_id}")

        if task_id not in tasks_responses:
            tasks_responses[task_id] = []

        agent_name = result_data.get("agent")
        # Prevent duplicate agent responses
        if not any(response.get("agent") == agent_name for response in tasks_responses[task_id]):
            tasks_responses[task_id].append(result_data)

        # Check if all expected responses are collected
        expected_count = tasks_expected_count.get(task_id, 0)
        if expected_count > 0 and len(tasks_responses[task_id]) >= expected_count:
            final_result = {
                "task_id": task_id,
                "aggregated_results": tasks_responses[task_id]
            }
            await nc.publish(CLIENT_REPLY_TOPIC, json.dumps(final_result).encode())
            print(f"[Executor] Publishing final result: {final_result}")

            # Clean up tracking
            tasks_responses.pop(task_id, None)
            tasks_expected_count.pop(task_id, None)

    # Subscribe to executor commands and crew responses
    sub_executor = await nc.subscribe(EXECUTOR_TOPIC, cb=executor_handler)
    sub_responses = await nc.subscribe(CREW_RESPONSES_TOPIC, cb=subagent_response_handler)

    print("[Executor] ExecutorSubAgent is running...")

    try:
        # Keep running indefinitely
        while True:
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        # Cleanup on cancellation
        await sub_executor.unsubscribe()
        await sub_responses.unsubscribe()
        await nc.close()
        raise

if __name__ == "__main__":
    asyncio.run(executor_subagent())
