from mcp.server.fastmcp import FastMCP
import asyncio
import json
import logging
import random
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers

# Configure logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
mcp = FastMCP("CrewAI MCP Gateway")

# Generate consistent task ID format
def generate_task_id():
    return f"task-{random.randint(1000, 9999)}"

@mcp.tool()
async def recommend_stocks(prompt: str) -> str:
    try:
        logging.info(f"[MCP] Received prompt: {prompt}")
        task_id = generate_task_id()
        return await send_to_captain_and_wait(prompt, task_id)
    except Exception as e:
        logging.error(f"[MCP] Unexpected failure in recommend_stocks: {e}")
        return f"❌ Internal error: {str(e)}"

async def send_to_captain_and_wait(prompt: str, task_id: str) -> str:
    task_data = {
        "task_id": task_id,
        "task_description": prompt,
        "task_type": "stock_recommendation"
    }

    try:
        nc = NATS()
        await nc.connect("nats://localhost:4222")
        logging.info("[NATS] Connected to server.")

        response_future = asyncio.Future()

        async def result_handler(msg):
            try:
                result = json.loads(msg.data.decode())
                incoming_task_id = (
                    result.get("task_id")
                    or result.get("original_task_data", {}).get("task_id")
                    or "no-id"
                )

                logging.info(
                    f"[Result Handler] Got task_id: {incoming_task_id} (expected: {task_id})"
                )

                if incoming_task_id == task_id and not response_future.done():
                    response_future.set_result(result)
                else:
                    logging.debug(f"[Result Handler] Ignored message for task_id: {incoming_task_id}")
            except Exception as e:
                logging.error(f"[Result Handler] Failed to parse or match result: {e}")

        await nc.subscribe("client.final.results", cb=result_handler)

        await nc.publish("crew.captain", json.dumps(task_data).encode())
        logging.info(f"[NATS] Sent task to crew.captain: {task_data}")
        logging.info(f"[NATS] 🕓 Waiting for response to task_id: {task_id}")

        try:
            result = await asyncio.wait_for(response_future, timeout=60)
            formatted_result = json.dumps(result, indent=2)
            logging.info(f"[MCP] Final response received: {formatted_result}")
            return f"✅ Recommendation:\n{formatted_result}"
        except asyncio.TimeoutError:
            logging.warning(f"[MCP] Timeout waiting for task_id: {task_id}")
            return "⏳ Timeout: No response received from CrewAI system. Please check that all agents are running."

    except (ErrNoServers, ErrConnectionClosed, ErrTimeout) as net_err:
        logging.error(f"[NATS] Connection error: {net_err}")
        return "❌ Could not connect to NATS server. Is it running on localhost:4222?"

    except Exception as e:
        logging.error(f"[MCP] Unexpected error in send_to_captain_and_wait: {e}")
        return f"❌ Error occurred: {str(e)}"

if __name__ == "__main__":
    logging.info("[MCP] Starting CrewAI MCP Gateway...")
    mcp.run()
