import os
import openai
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

class AgentRegistry:
    """
    Stores sub-agent descriptions in a vector database (Chroma)
    and provides a method to find the most appropriate sub-agent
    based on the user's request.
    """
    def __init__(self, collection_name="agent_registry"):
        # Initialize your OpenAI API Key
        openai.api_key = os.getenv("OPENAI_API_KEY")

        # Create or load the Chroma client
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
        """
        Add a sub-agent to the registry with a textual description.
        agent_id: Unique identifier for the sub-agent.
        description: A textual summary of the agent's purpose and capabilities.
        """
        self.collection.add(
            documents=[description],
            ids=[agent_id]
        )
        print(f"[AgentRegistry] Added sub-agent '{agent_id}' to registry.")

    def search_best_agent(self, user_query: str, top_k=1):
        """
        Searches the vector DB for the most relevant sub-agent
        to handle the user's query. Returns the best match.
        """
        results = self.collection.query(
            query_texts=[user_query],
            n_results=top_k
        )
        if results and results["ids"]:
            best_match_id = results["ids"][0][0]  # top_k=1 => first result
            best_match_score = results["metadatas"][0] if results["metadatas"] else None
            return best_match_id
        return None
