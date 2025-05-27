import asyncio
import json
from nats.aio.client import Client as NATS
from openai import OpenAI
import os

PROMPT_PROCESSOR_TOPIC = "agent.prompt_processor"
EXECUTOR_TOPIC = "agent.executor"

api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise EnvironmentError("Missing OPENAI_API_KEY environment variable.")

client = OpenAI(api_key=api_key)
async def prompt_processor_subagent():
    nc = NATS()
    await nc.connect("nats://localhost:4222")

    async def prompt_processor_handler(msg):
        task_data = json.loads(msg.data.decode())

        # Attempt to get user prompt from possible nested keys
        user_prompt = (
            task_data.get("task_description")
            or task_data.get("original_task_data", {}).get("task_description")
            or task_data.get("original_task_data", {}).get("original_task_data", {}).get("task_description")
            or ""
        )

        print(f"[PromptProcessor] Received prompt: {user_prompt}")

        if not user_prompt.strip():
            print("[PromptProcessor] Warning: Received empty task description!")
            user_prompt = "No task description provided"

        try:
            # Run the synchronous create call in a separate thread to avoid blocking the event loop
            response = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                                                "role": "system",
                                                "content": (
                        "You are a prompt processor that extracts exactly these keys from the user's message: "
                        "'OP_CODE' (string), 'UserContext' (JSON object), and 'ProcessContext' (JSON object). "
                        "If the message is about stock recommendations, set 'OP_CODE' to 'STOCK_RECOMMENDATION'. "
                        "Try to infer user preferences such as 'risk_level', 'investment_horizon', or 'sectors_of_interest' "
                        "and include them in 'UserContext'. "
                        "If the user references past conversation or other context, include it in 'ProcessContext'. "
                        "If unclear or unrelated, set 'OP_CODE' to 'UNKNOWN' and keep contexts empty. "
                        "Respond only with a JSON object, no explanations. "
                        "Example output: "
                        '{"OP_CODE": "STOCK_RECOMMENDATION", '
                        '"UserContext": {"preference": "short_term_gains", "risk_level": "medium"}, '
                        '"ProcessContext": {"history": "user asked about tech stocks last week"}}'
                    )

                        },
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=150,
                    temperature=0.0,
                )
            )

            output_text = response.choices[0].message.content.strip()
            print(f"[PromptProcessor] OpenAI output: {output_text}")

            structured_data = json.loads(output_text)

            # Extract task_id from nested fields if available
            task_id = (
                task_data.get("task_id")
                or task_data.get("original_task_data", {}).get("task_id")
                or task_data.get("original_task_data", {}).get("original_task_data", {}).get("task_id")
                or None
            )

            structured_data["task_id"] = task_id
            structured_data["original_task_data"] = task_data

        except json.JSONDecodeError as jde:
            print(f"[PromptProcessor] JSON decode error: {jde}")
            structured_data = {
                "task_id": task_data.get("task_id"),
                "OP_CODE": "UNKNOWN",
                "UserContext": {},
                "ProcessContext": {},
                "original_task_data": task_data,
            }
        except Exception as e:
            print(f"[PromptProcessor] Error during OpenAI processing or JSON parsing: {e}")
            structured_data = {
                "task_id": task_data.get("task_id"),
                "OP_CODE": "UNKNOWN",
                "UserContext": {},
                "ProcessContext": {},
                "original_task_data": task_data,
            }

        await nc.publish(EXECUTOR_TOPIC, json.dumps(structured_data).encode())
        print(f"[PromptProcessor] Published structured data for task_id {structured_data.get('task_id')}")

    await nc.subscribe(PROMPT_PROCESSOR_TOPIC, cb=prompt_processor_handler)
    print("[PromptProcessor] Listening for prompts...")

    await asyncio.Future()  # Keep running forever

if __name__ == "__main__":
    asyncio.run(prompt_processor_subagent())
