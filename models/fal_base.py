import os
import time
import fal_client # type: ignore
from typing import Dict, Any, Optional, Callable

# Assuming model_utils.py is in the same directory or accessible in PYTHONPATH
from .model_utils import logger, sanitize_for_logging

class FALModel:
    """Handles FAL API specific interactions, including API key management and retries."""
    
    def __init__(self, api_key_env_var: str = "FAL_API_KEY", max_retries: int = 3):
        self.api_key = os.getenv(api_key_env_var)
        if not self.api_key:
            msg = f"{api_key_env_var} environment variable not set. Please ensure it is correctly configured."
            logger.error(msg)
            raise RuntimeError(msg)
        
        fal_client.api_key = self.api_key 
        self.max_retries = max_retries
        logger.debug(f"FALModel initialized. Max retries: {self.max_retries}. FAL API key configured.")

    def _call_fal_subscribe_with_retries(
        self, 
        endpoint: str, 
        arguments: Dict[str, Any], 
        on_queue_update_callback: Optional[Callable[[Any], None]] = None
    ) -> Dict[str, Any]:
        logger.info(f"Attempting to call FAL endpoint '{endpoint}' (max {self.max_retries} retries).")
        logger.debug(f"API arguments (sanitized): {sanitize_for_logging(arguments)}")

        last_exception: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                result = fal_client.subscribe(
                    endpoint,
                    arguments=arguments,
                    with_logs=True, 
                    on_queue_update=on_queue_update_callback
                )
                logger.debug(f"FAL API raw response (sanitized): {sanitize_for_logging(result)}")
                return result # type: ignore
            
            except Exception as e:
                last_exception = e
                logger.error(f"Error during FAL call to '{endpoint}' (Attempt {attempt + 1}/{self.max_retries}) with error type {type(e).__name__}: {sanitize_for_logging(str(e))}")
                if hasattr(e, 'status_code') and e.status_code == 403: # type: ignore
                    logger.error("Received 403 Forbidden. Please check your FAL_API_KEY and its permissions for this endpoint.")
                if attempt < self.max_retries - 1:
                    backoff = 2 ** attempt
                    logger.info(f"Retrying FAL call in {backoff}s...")
                    time.sleep(backoff)
                else:
                    logger.error(f"Max retries reached for FalClientError on endpoint '{endpoint}'.")
            
            except Exception as e: 
                last_exception = e
                logger.error(f"Generic error during FAL call to '{endpoint}' (Attempt {attempt + 1}/{self.max_retries}): {sanitize_for_logging(str(e))}", exc_info=False)
                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying FAL call in 2s due to generic error...")
                    time.sleep(2) 
                else:
                    logger.error(f"Max retries reached for generic error on endpoint '{endpoint}'.")
        
        if last_exception:
            raise RuntimeError(f"FAL API call to '{endpoint}' failed after {self.max_retries} attempts: {sanitize_for_logging(str(last_exception))}") from last_exception
        raise RuntimeError(f"Failed to call FAL endpoint '{endpoint}' after {self.max_retries} retries without specific error logged.") 