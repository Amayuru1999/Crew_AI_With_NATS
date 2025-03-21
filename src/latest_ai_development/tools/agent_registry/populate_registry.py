# populate_registry.py
from agent_registry import AgentRegistry
from dotenv import load_dotenv
import shutil
import os
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import RateLimitError, APIError, Timeout

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
# Remove the entire DB directory
# Remove the entire DB directory if it exists
if os.path.exists("./chroma_db"):
    try:
        shutil.rmtree("./chroma_db")
        logger.info("Removed existing chroma_db directory")
    except Exception as e:
        logger.error(f"Error removing chroma_db directory: {e}")
@retry(
    retry=retry_if_exception_type((RateLimitError, APIError, Timeout)),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5)
)
def add_agent_with_retry(registry, agent_id, description):
    """Add an agent to the registry with retry logic for API rate limits."""
    try:
        registry.add_sub_agent(
            agent_id=agent_id,
            description=description
        )
        logger.info(f"Successfully added {agent_id} to registry")
        return True
    except Exception as e:
        logger.error(f"Error adding {agent_id} to registry: {e}")
        raise

def populate_registry():
    try:
        registry = AgentRegistry()
        logger.info("Created Agent Registry instance")
        
        # Add stock news agent
        add_agent_with_retry(
            registry,
            agent_id="stock_news_agent",
            description="Fetches latest stock market news..."
        )
        logger.info("Registry contents after adding stock_news_agent")
        
        # Add stock price agent
        add_agent_with_retry(
            registry,
            agent_id="stock_price_agent",
            description="Retrieves historical stock prices..."
        )
        logger.info("Registry contents after adding stock_price_agent")
        
        # Add price predictor agent
        add_agent_with_retry(
            registry, 
            agent_id="price_predictor_agent",
            description="Generates buy/sell recommendations..."
        )
        logger.info("Registry contents after adding price_predictor_agent")
        
        logger.info("Successfully populated registry with all agents")
    except Exception as e:
        logger.error(f"Failed to populate registry: {e}")
        raise

if __name__ == "__main__":
    populate_registry()
