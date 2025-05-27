import asyncio
import json
from nats.aio.client import Client as NATS
from openai import OpenAI
import os

api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise EnvironmentError("Missing OPENAI_API_KEY environment variable.")

client = OpenAI(api_key=api_key)
async def stock_news_agent():
    nc = NATS()
    await nc.connect("nats://localhost:4222")

    async def stock_news_handler(msg):
        task_data = json.loads(msg.data.decode())
        task_id = task_data.get("task_id")
        task_description = task_data.get("original_task_data", {}).get("task_description", "")

        print(f"[StockNewsAgent] Received: {task_data}")

        prompt = f"Provide a brief stock market news summary relevant to this user prompt: '{task_description}'. Keep it short and relevant."

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You provide stock market news summaries."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=100,
                temperature=0.5,
            )
            news_summary = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[StockNewsAgent] OpenAI API error: {e}")
            news_summary = "Could not retrieve stock news at this time."

        result = {
            "task_id": task_id,
            "agent": "StockNewsAgent",
            "info": news_summary,
        }

        await nc.publish("client.final.results", json.dumps(result).encode())
        print(f"[StockNewsAgent] Published result for task_id {task_id}")

    await nc.subscribe("agent.stock_news_agent", cb=stock_news_handler)
    print("[StockNewsAgent] Listening for tasks...")

    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(stock_news_agent())
