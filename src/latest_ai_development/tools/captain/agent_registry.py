import logging
import random
from typing import Dict, List, Optional, Any, Tuple, Union

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AgentRegistry")

class AgentRegistry:
    """
    A registry for agents that provides vector similarity search functionality
    to find the most appropriate agent for a given query.
    """
    
    def __init__(self):
        """Initialize the agent registry with empty collections of agents."""
        self.agents = {}  # Dict to store agent information
        self.agent_embeddings = {}  # Dict to store agent embeddings for similarity search
        logger.info("AgentRegistry initialized")
        
    def register_agent(self, agent_id: str, capabilities: List[str], description: str):
        """
        Register a new agent in the registry.
        
        Args:
            agent_id: Unique identifier for the agent
            capabilities: List of capabilities the agent has
            description: Detailed description of what the agent does
        """
        self.agents[agent_id] = {
            "id": agent_id,
            "capabilities": capabilities,
            "description": description
        }
        
        # Simulate creating an embedding for the agent
        # In a real implementation, this would use an embedding model
        # For simulation, we'll just use random values
        self.agent_embeddings[agent_id] = [random.random() for _ in range(384)]
        logger.info(f"Agent {agent_id} registered successfully")
    
    def search_best_agent(self, query: str, top_k: int = 1) -> Optional[str]:
        """
        Find the best matching agent(s) for a given query using simulated vector similarity search.
        
        Args:
            query: The user query to match against agent capabilities
            top_k: Number of top results to return
            
        Returns:
            The ID of the best matching agent, or None if no matches are found
        """
        if not query:
            logger.warning("Empty query provided to search_best_agent")
            return None
            
        if not self.agents:
            logger.warning("No agents registered in the registry")
            return None
        
        # Simulate vector similarity search
        # In a real implementation, this would:
        # 1. Convert the query to an embedding
        # 2. Find similar embeddings in the vector database
        # 3. Return the closest matches
        
        try:
            # Simulate search results
            results = self._simulate_vector_search(query, top_k)
            
            # Check if results exist
            if not results or not results.get("ids") or len(results["ids"]) == 0:
                logger.info(f"No matching agents found for query: {query}")
                return None
                
            # Ensure the first result exists
            if len(results["ids"]) > 0 and len(results["ids"][0]) > 0:
                best_match_id = results["ids"][0][0]  # top_k=1 => first result
                logger.info(f"Best matching agent found: {best_match_id}")
                return best_match_id
            else:
                logger.info(f"No matching agents found for query: {query}")
                return None
                
        except Exception as e:
            logger.error(f"Error during agent search: {str(e)}")
            return None
    
    def _simulate_vector_search(self, query: str, top_k: int) -> Dict[str, List]:
        """
        Simulate vector similarity search.
        In a real implementation, this would call a vector database.
        
        Args:
            query: The query to search for
            top_k: Number of results to return
            
        Returns:
            Dictionary containing search results with IDs and scores
        """
        # In a real implementation, we would:
        # 1. Convert query to embedding
        # 2. Find closest embeddings in vector database
        # 3. Return matches
        
        # For simulation, we'll randomly decide whether to return results or not
        # to demonstrate the error handling
        if random.random() < 0.7 and self.agents:  # 70% chance to find agents if they exist
            # Get a random subset of agents
            agent_ids = list(self.agents.keys())
            if len(agent_ids) > top_k:
                selected_agents = random.sample(agent_ids, top_k)
            else:
                selected_agents = agent_ids
                
            # Create simulated results
            ids = [[agent_id] for agent_id in selected_agents]
            scores = [[random.random()] for _ in selected_agents]
            
            return {
                "ids": ids,
                "scores": scores
            }
        else:
            # Simulate no results found
            return {
                "ids": [],
                "scores": []
            }
            
    def get_agent_details(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific agent.
        
        Args:
            agent_id: The ID of the agent to retrieve
            
        Returns:
            A dictionary with agent details or None if not found
        """
        return self.agents.get(agent_id)

