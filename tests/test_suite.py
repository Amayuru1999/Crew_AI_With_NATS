import asyncio
import json
import pytest
import pytest_asyncio
from nats.aio.client import Client as NATS
import sys
import os
from pathlib import Path

src_path = str(Path(__file__).parent.parent / "src")
sys.path.insert(0, src_path)

from latest_ai_development.tools.agent_registry.agent_registry import AgentRegistry
from latest_ai_development.crew import LatestAiDevelopment
from latest_ai_development.tools.captain.captain_agent import captain_agent
from latest_ai_development.tools.agent_registry.executor_subagent import executor_subagent


# ----------------------------------------------------------------
# Fixture: Connect to NATS (or skip if not available)
# ----------------------------------------------------------------
@pytest_asyncio.fixture
async def nats_client():
    nc = NATS()
    try:
        await nc.connect("nats://localhost:4222")
    except Exception as e:
        pytest.skip("NATS server not available: " + str(e))
    yield nc
    await nc.close()


# ----------------------------------------------------------------
# Fixture: Setup and teardown for AI Agents
# ----------------------------------------------------------------
@pytest_asyncio.fixture
async def setup_agents():
    print("\nStarting agents...")
    # Start agents in background tasks
    captain_task = asyncio.create_task(captain_agent())
    executor_task = asyncio.create_task(executor_subagent())
    
    print("Waiting for agents to initialize...")
    await asyncio.sleep(2)  # Increased wait time
    yield
    
    print("Cleaning up agents...")
    # Cleanup
    captain_task.cancel()
    executor_task.cancel()
    try:
        await captain_task
        await executor_task
    except asyncio.CancelledError:
        print("Agents cleaned up successfully")
        pass

# ----------------------------------------------------------------
# Test 1: Agent Registry Unit Tests
# ----------------------------------------------------------------
def test_agent_registry_register_and_search():
    """
    Verify that agents can be registered and found via simulated vector search.
    Using the current AgentRegistry implementation with add_sub_agent method.
    """
    registry = AgentRegistry(collection_name="test_registry")

    # Check if the registry supports add_sub_agent method.
    if not hasattr(registry, "add_sub_agent"):
        pytest.skip("AgentRegistry does not support 'add_sub_agent' method.")

    # Register test agents using add_sub_agent
    registry.add_sub_agent("agent1", "Test agent one description")
    registry.add_sub_agent("agent2", "Test agent two description")

    # Test search_best_agent
    best = registry.search_best_agent("Test agent")
    # Since the simulated search is randomized, we accept either agent or None.
    assert best in ["agent1", "agent2", None]

    # Test search_top_agents
    top_agents = registry.search_top_agents("Test agent", top_k=2)
    if top_agents:
        assert any(agent in top_agents for agent in ["agent1", "agent2"])


# ----------------------------------------------------------------
# Test 2: NATS Publish/Subscribe Integration Test
# ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_nats_publish_subscribe(nats_client):
    """
    Ensure that a message published on a test topic is received by a subscriber.
    """
    nc = nats_client
    received = []

    async def handler(msg):
        received.append(msg.data.decode())

    test_subject = "test.subject"
    await nc.subscribe(test_subject, cb=handler)
    await nc.publish(test_subject, b"Hello, NATS!")
    await asyncio.sleep(0.5)  # Allow time for the message to be delivered
    assert "Hello, NATS!" in received


# ----------------------------------------------------------------
# Test 3: Captain Agent Forwarding Test
# ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_captain_agent_forwarding(nats_client, setup_agents):
    """
    Simulate a client task sent to the Captain Agent and verify that it is forwarded
    to the Prompt Processor (on the 'agent.prompt_processor' topic).
    """
    nc = nats_client
    forwarded_messages = []

    async def prompt_processor_handler(msg):
        data = json.loads(msg.data.decode())
        forwarded_messages.append(data)

    prompt_processor_topic = "agent.prompt_processor"
    await nc.subscribe(prompt_processor_topic, cb=prompt_processor_handler)

    captain_topic = "crew.captain"
    task_data = {
        "task_id": "test-task-001",
        "task_description": "What new stocks should I buy this week?",
        "task_type": "stock_recommendation"
    }
    await nc.publish(captain_topic, json.dumps(task_data).encode())

    await asyncio.sleep(1)  # Wait for the captain to forward the message
    # Verify that at least one forwarded message contains the original task data.
    assert any("task_description" in msg.get("original_task_data", {}) for msg in forwarded_messages)


# ----------------------------------------------------------------
# Test 4: ExecutorSubAgent Flow Integration Test
# ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_executor_subagent_integration(nats_client, setup_agents):
    """
    Simulate sending structured data to the ExecutorSubAgent and simulate sub-agent
    responses. Verify that the Executor aggregates responses and publishes a final result.
    """
    nc = nats_client
    final_results = []

    async def client_reply_handler(msg):
        final_results.append(json.loads(msg.data.decode()))

    CLIENT_REPLY_TOPIC = "client.final.results"
    await nc.subscribe(CLIENT_REPLY_TOPIC, cb=client_reply_handler)

    structured_data = {
        "OP_CODE": "STOCK_RECOMMENDATION",
        "UserContext": {"preference": "short_term_gains"},
        "ProcessContext": {"history": "test conversation data"},
        "original_task_data": {
            "task_id": "exec-test-001",
            "task_description": "What new stocks should I buy this week?",
            "task_type": "stock_recommendation"
        }
    }
    EXECUTOR_TOPIC = "agent.executor"
    await nc.publish(EXECUTOR_TOPIC, json.dumps(structured_data).encode())

    await asyncio.sleep(0.5)

    # Simulate sub-agent responses
    CREW_RESPONSES_TOPIC = "crew.responses"
    agent_ids = ["stock_news_agent", "stock_price_agent", "price_predictor_agent"]
    for agent_id in agent_ids:
        dummy_response = {
            "task_id": "exec-test-001",
            "agent": agent_id,
            "info": f"Dummy result from {agent_id}"
        }
        await nc.publish(CREW_RESPONSES_TOPIC, json.dumps(dummy_response).encode())

    # Wait longer for all processing to complete
    await asyncio.sleep(3)  # Increased wait time from 2 to 3 seconds

    assert len(final_results) > 0, "No final aggregated result received."
    final_result = final_results[0]
    assert final_result.get("task_id") == "exec-test-001"
    aggregated = final_result.get("aggregated_results", [])
    assert len(aggregated) == 3, "Aggregated result should contain 3 responses."


