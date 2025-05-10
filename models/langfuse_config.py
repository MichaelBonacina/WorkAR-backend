"""
Langfuse Configuration Module

This module initializes the Langfuse client with environment variables.
"""

import os
import traceback
from dotenv import load_dotenv
from langfuse import Langfuse
import logging

def initialize_langfuse():
    """
    Initialize Langfuse from environment variables.
    Should be called once at application startup.
    
    Environment variables required:
    - LANGFUSE_PUBLIC_KEY: Your Langfuse public key
    - LANGFUSE_SECRET_KEY: Your Langfuse secret key
    - LANGFUSE_HOST: (Optional) Langfuse host URL, defaults to 'https://cloud.langfuse.com'
    """
    load_dotenv()
    
    # Check if the required environment variables are set
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    
    if not public_key or not secret_key:
        logging.warning("Langfuse keys not configured. Monitoring will not be available.")
        return None
    
    try:
        # Initialize the Langfuse client
        langfuse = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host
        )
        logging.info(f"Langfuse monitoring initialized with host: {host}")
        return langfuse
    except Exception as e:
        logging.error(f"Failed to initialize Langfuse: {e}")
        traceback.print_exc()
        return None 