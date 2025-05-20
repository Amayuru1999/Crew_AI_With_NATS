import asyncio
import json
from nats.aio.client import Client as NATS

STOCK_PRICE_TOPIC = "agent.stock_price_agent"
CREW_RESPONSES_TOPIC = "crew.responses"

def extract_task_id(data):
    try:
        return (
            data.get("task_id")
            or data.get("original_task_data", {}).get("task_id")
            or data.get("original_task_data", {}).get("original_task_data", {}).get("task_id")
            or "no-id"
        )
    except Exception:
        return "no-id"

async def stock_price_agent():
    nc = NATS()
    await nc.connect("nats://localhost:4222")

    async def price_handler(msg):
        data = json.loads(msg.data.decode())
        task_id = extract_task_id(data)
        print(f"[StockPriceAgent] Received: {data}")

        # Simulate retrieving historical price data
        result = {
            "task_id": task_id,
            "agent": "StockPriceAgent",
            "info": "Historical price data retrieved..."
        }

        await nc.publish(CREW_RESPONSES_TOPIC, json.dumps(result).encode())

    await nc.subscribe(STOCK_PRICE_TOPIC, cb=price_handler)
    print("[StockPriceAgent] Listening for tasks...")
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(stock_price_agent())
