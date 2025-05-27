#!/usr/bin/env python3
# chroma_setup.py - Setup and test ChromaDB for vector storage

"""
This script demonstrates how to set up and use ChromaDB for vector storage.
It initializes a ChromaDB client, creates a test collection, and adds a document
to verify that everything is working correctly.
"""

import os
import sys
import logging
from typing import List, Dict, Any

# Import required ChromaDB modules
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def initialize_chroma_client() -> chromadb.Client:
    """
    Initialize and return a ChromaDB client.
    
    Returns:
        chromadb.Client: A configured ChromaDB client
    """
    try:
        # Initialize the ChromaDB client
        # By default, this uses an in-memory database
        # For persistence, use PersistentClient with a path
        client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",  # Use duckdb with parquet files for storage
            persist_directory="./chroma_db"    # Directory where data will be stored
        ))
        
        logger.info("ChromaDB client initialized successfully")
        return client
    
    except Exception as e:
        logger.error(f"Failed to initialize ChromaDB client: {e}")
        raise

def create_test_collection(client: chromadb.Client) -> chromadb.Collection:
    """
    Create a test collection in ChromaDB.
    
    Args:
        client (chromadb.Client): The ChromaDB client
        
    Returns:
        chromadb.Collection: The created collection
    """
    try:
        # Get or create a collection
        # If collection already exists, get_or_create_collection will return the existing one
        collection = client.get_or_create_collection(
            name="test_collection",
            metadata={"description": "Test collection for ChromaDB setup verification"}
        )
        
        logger.info(f"Collection 'test_collection' created or retrieved successfully")
        return collection
    
    except Exception as e:
        logger.error(f"Failed to create collection: {e}")
        raise

def add_test_document(collection: chromadb.Collection) -> None:
    """
    Add a test document to the collection to verify functionality.
    
    Args:
        collection (chromadb.Collection): The collection to add the document to
    """
    try:
        # Add a document to the collection
        collection.add(
            documents=["This is a test document to verify ChromaDB is working correctly."],
            metadatas=[{"source": "test_setup", "type": "verification"}],
            ids=["test_doc_1"]
        )
        
        logger.info("Test document added successfully")
        
        # Query the collection to verify the document was added correctly
        results = collection.query(
            query_texts=["test document"],
            n_results=1
        )
        
        logger.info(f"Query results: {results}")
        
    except Exception as e:
        logger.error(f"Failed to add or query test document: {e}")
        raise

def main():
    """
    Main function to set up ChromaDB and test its functionality.
    """
    try:
        # Initialize the ChromaDB client
        client = initialize_chroma_client()
        
        # Create a test collection
        collection = create_test_collection(client)
        
        # Add a test document and verify it works
        add_test_document(collection)
        
        logger.info("ChromaDB setup and verification completed successfully")
        
    except Exception as e:
        logger.error(f"ChromaDB setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

