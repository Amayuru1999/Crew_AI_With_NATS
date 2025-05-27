import sys
sys.path.append("/Users/amayuruamarasinghe/Documents/MetaRune Labs/AI Agents/latest_ai_development/src")
import asyncio
import json
import uuid
import subprocess
import os
from fastapi import FastAPI
from pydantic import BaseModel
from nats.aio.client import Client as NATS
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
nc = NATS()
agent_processes = []
nats_process = None  # Variable to store the NATS subprocess

# Allow frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# List of CrewAI scripts to run
AGENT_SCRIPTS = [
    "/Users/amayuruamarasinghe/Documents/MetaRune Labs/AI Agents/latest_ai_development/src/latest_ai_development/tools/captain/captain_agent.py",
    "/Users/amayuruamarasinghe/Documents/MetaRune Labs/AI Agents/latest_ai_development/src/latest_ai_development/tools/captain/prompt_processor_subagent.py",
    "/Users/amayuruamarasinghe/Documents/MetaRune Labs/AI Agents/latest_ai_development/src/latest_ai_development/tools/agent_registry/executor_subagent.py",
    "/Users/amayuruamarasinghe/Documents/MetaRune Labs/AI Agents/latest_ai_development/src/latest_ai_development/tools/sub_agents/stock_news_agent.py",
    "/Users/amayuruamarasinghe/Documents/MetaRune Labs/AI Agents/latest_ai_development/src/latest_ai_development/tools/sub_agents/stock_price_agent.py",
    "/Users/amayuruamarasinghe/Documents/MetaRune Labs/AI Agents/latest_ai_development/src/latest_ai_development/tools/sub_agents/price_predictor_agent.py",
]

class TaskRequest(BaseModel):
    task_description: str


def start_agents():
    env = os.environ.copy()
    # Add your src directory to PYTHONPATH for subprocesses
    env["PYTHONPATH"] = "/Users/amayuruamarasinghe/Documents/MetaRune Labs/AI Agents/latest_ai_development/src"

    for script in AGENT_SCRIPTS:
        process = subprocess.Popen(
            ["python", script],
            env=env  # Pass modified environment
        )
        agent_processes.append(process)


def stop_agents():
    for proc in agent_processes:
        try:
            proc.terminate()
        except Exception:
            pass

def start_nats_server():
    global nats_process
    # Start NATS server as a subprocess
    nats_process = subprocess.Popen(["nats-server"])
    print("NATS server started.")

def stop_nats_server():
    global nats_process
    if nats_process:
        try:
            nats_process.terminate()  # Stop the NATS server subprocess
            nats_process.wait()  # Wait for the subprocess to terminate
            print("NATS server stopped.")
        except Exception as e:
            print(f"Error stopping NATS server: {e}")

@app.on_event("startup")
async def startup_event():
    # Start NATS server
    start_nats_server()
    # Start the agents
    start_agents()
    # Connect to the NATS server
    await nc.connect("nats://localhost:4222")

@app.on_event("shutdown")
async def shutdown_event():
    # Disconnect from NATS
    await nc.close()
    # Stop agents
    stop_agents()
    # Stop NATS server
    stop_nats_server()

@app.post("/start-task")
async def start_task(request: TaskRequest):
    task_id = str(uuid.uuid4())
    task_data = {
        "task_id": task_id,
        "task_description": request.task_description,
        "task_type": "stock_recommendation"
    }

    future = asyncio.Future()

    async def result_handler(msg):
        try:
            result = json.loads(msg.data.decode())
            incoming_id = (
                result.get("task_id")
                or result.get("original_task_data", {}).get("task_id")
                or "no-id"
            )
            if incoming_id == task_id and not future.done():
                future.set_result(result)
        except Exception as e:
            print("Result parse error:", e)

    subscription = await nc.subscribe("client.final.results", cb=result_handler)
    await nc.publish("crew.captain", json.dumps(task_data).encode())

    try:
        result = await asyncio.wait_for(future, timeout=60)
        await subscription.unsubscribe()
        return result
    except asyncio.TimeoutError:
        await subscription.unsubscribe()
        return {"error": "Timeout waiting for response from agents"}
