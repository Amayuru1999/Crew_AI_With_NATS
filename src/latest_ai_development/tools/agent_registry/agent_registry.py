import os
import json
import asyncio
import openai
import chromadb
from nats.aio.client import Client as NATS
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

load_dotenv()

EXECUTOR_TOPIC = "agent.executor"
CREW_RESPONSES_TOPIC = "crew.responses"
CLIENT_REPLY_TOPIC = "client.final.results"


class AgentRegistry:
    """
    Stores sub-agent descriptions in a vector database (Chroma)
    and provides methods to find the most appropriate sub-agents
    based on the user's request.
    """
    def __init__(self, collection_name="agent_registry"):
        openai.api_key = os.getenv("OPENAI_API_KEY")

        # Create or load the Chroma client (persistent DB in ./chroma_db)
        self.client = chromadb.PersistentClient(path="./chroma_db")

        # Create or get the collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_functions.OpenAIEmbeddingFunction(
                api_key=openai.api_key,
                model_name="text-embedding-ada-002"
            )
        )

    def add_sub_agent(self, agent_id: str, description: str):
        """Add a sub-agent to the registry with a textual description."""
        self.collection.add(
            documents=[description],
            ids=[agent_id]
        )
        print(f"[AgentRegistry] Added sub-agent '{agent_id}' to registry.")

    def search_best_agent(self, user_query: str, top_k=1):
        """Return the single best match for the given user_query."""
        results = self.collection.query(query_texts=[user_query], n_results=top_k)
        if results and results["ids"]:
            best_match_id = results["ids"][0][0]
            return best_match_id
        return None

    def search_top_agents(self, user_query: str, top_k: int = 3):
        """Return a list of up to top_k agent IDs that best match the user_query."""
        results = self.collection.query(query_texts=[user_query], n_results=top_k)
        if not results or not results["ids"]:
            return []
        # results["ids"] is a list of lists, e.g. [[agent1, agent2, ...]]
        return results["ids"][0]


async def executor_subagent():
    """
    The main Executor Sub-Agent process. It:
      1. Connects to NATS
      2. Listens on EXECUTOR_TOPIC for tasks
      3. Uses AgentRegistry to find multiple top matching agents
      4. Publishes the task to each matching agent
      5. Collects responses from sub-agents
      6. Aggregates them and sends them back to CLIENT_REPLY_TOPIC
    """
    nc = NATS()
    await nc.connect("nats://localhost:4222")

    # Create an instance of your AgentRegistry
    registry = AgentRegistry()

    # Dictionaries to track ongoing tasks
    tasks_responses = {}       # { task_id: [list of responses from sub-agents] }
    tasks_expected_count = {}  # { task_id: number_of_subagents_we_sent_the_task_to }

    async def executor_handler(msg):
        """Handles incoming structured tasks from the PromptProcessor/Captain."""
        structured_data = json.loads(msg.data.decode())
        print(f"[Executor] Received structured data: {structured_data}")

        user_query = structured_data.get("original_task_data", {}).get("task_description", "N/A")
        task_id = structured_data.get("original_task_data", {}).get("task_id", "no-id")

        # 1. Find up to top 3 matching agents
        top_agent_ids = registry.search_top_agents(user_query, top_k=3)
        if not top_agent_ids:
            # If no matches found, return error to client
            final_result = {"task_id": task_id, "error": "No suitable sub-agent found."}
            await nc.publish(CLIENT_REPLY_TOPIC, json.dumps(final_result).encode())
            return

        # Prepare to collect responses from each matched agent
        tasks_responses[task_id] = []
        tasks_expected_count[task_id] = len(top_agent_ids)

        # 2. Publish the request to each matched agent
        for agent_id in top_agent_ids:
            subagent_data = {
                "task_id": task_id,
                "OP_CODE": structured_data.get("OP_CODE", "UNKNOWN"),
                "UserContext": structured_data.get("UserContext", {}),
                "ProcessContext": structured_data.get("ProcessContext", {}),
                "original_task_data": structured_data.get("original_task_data", {})
            }
            subagent_topic = f"agent.{agent_id}"
            print(f"[Executor] Sending to sub-agent: {subagent_topic}")
            await nc.publish(subagent_topic, json.dumps(subagent_data).encode())

    async def subagent_response_handler(msg):
        """
        Collect sub-agent responses and send the final aggregated result
        to the client once all sub-agents have responded.
        """
        result_data = json.loads(msg.data.decode())
        task_id = result_data.get("task_id", "no-id")

        print(f"[Executor] Received sub-agent response: {result_data}")

        if task_id not in tasks_responses:
            tasks_responses[task_id] = []
        tasks_responses[task_id].append(result_data)

        # Check if we have received all responses we expect
        if len(tasks_responses[task_id]) == tasks_expected_count[task_id]:
            # All sub-agents responded; aggregate results
            final_result = {
                "task_id": task_id,
                "aggregated_results": tasks_responses[task_id]
            }
            print(f"[Executor] All sub-agents responded. Sending final result: {final_result}")
            # Send final result to the client
            await nc.publish(CLIENT_REPLY_TOPIC, json.dumps(final_result).encode())
            # Clean up tracking
            tasks_responses.pop(task_id, None)
            tasks_expected_count.pop(task_id, None)

    # Subscribe to tasks from the Captain or Prompt Processor
    await nc.subscribe(EXECUTOR_TOPIC, cb=executor_handler)
    # Listen for sub-agent responses
    await nc.subscribe(CREW_RESPONSES_TOPIC, cb=subagent_response_handler)

    print("[Executor] ExecutorSubAgent is running with dynamic agent selection...")
    await asyncio.Future()  # Keep this service running indefinitely


if __name__ == "__main__":
    asyncio.run(executor_subagent())
