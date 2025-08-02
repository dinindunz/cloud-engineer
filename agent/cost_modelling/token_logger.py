"""
Core Token Logger Implementation for Bedrock API calls.

This module provides the BedrockTokenLogger class that wraps Bedrock API calls
to capture token usage and calculate cost estimates.
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, Union
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class BedrockTokenLogger:
    """
    Core token logger that wraps Bedrock API calls to capture usage metrics.
    
    Supports different model IDs and provides cost estimation based on current
    Sonnet 4 pricing ($3/M input, $15/M output tokens).
    """
    
    # Current pricing per 1M tokens (in USD)
    PRICING = {
        "apac.anthropic.claude-sonnet-4-20250514-v1:0": {
            "input": 3.0,
            "output": 15.0
        },
        "anthropic.claude-3-5-sonnet-20241022-v2:0": {
            "input": 3.0,
            "output": 15.0
        },
        "anthropic.claude-3-sonnet-20240229-v1:0": {
            "input": 3.0,
            "output": 15.0
        },
        # Default pricing for unknown models
        "default": {
            "input": 3.0,
            "output": 15.0
        }
    }
    
    def __init__(self, region_name: str = "ap-southeast-2"):
        """
        Initialize the token logger.
        
        Args:
            region_name: AWS region for Bedrock client
        """
        self.region_name = region_name
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=region_name)
        
    def _extract_token_usage(self, response: Dict[str, Any]) -> Dict[str, int]:
        """
        Extract token usage from Bedrock response metadata.
        
        Args:
            response: Bedrock API response
            
        Returns:
            Dictionary with input_tokens and output_tokens
        """
        try:
            # Check for usage in response metadata
            if 'usage' in response:
                usage = response['usage']
                return {
                    'input_tokens': usage.get('input_tokens', 0),
                    'output_tokens': usage.get('output_tokens', 0)
                }
            
            # Alternative location for token usage
            if 'ResponseMetadata' in response and 'usage' in response['ResponseMetadata']:
                usage = response['ResponseMetadata']['usage']
                return {
                    'input_tokens': usage.get('input_tokens', 0),
                    'output_tokens': usage.get('output_tokens', 0)
                }
            
            # Check in body if it's a streaming response
            if 'body' in response:
                body = response['body']
                if hasattr(body, 'read'):
                    # For streaming responses, we'll need to handle differently
                    logger.warning("Streaming response detected - token counting may be incomplete")
                    return {'input_tokens': 0, 'output_tokens': 0}
            
            logger.warning("No token usage found in response")
            return {'input_tokens': 0, 'output_tokens': 0}
            
        except Exception as e:
            logger.error(f"Error extracting token usage: {e}")
            return {'input_tokens': 0, 'output_tokens': 0}
    
    def _calculate_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost estimate based on token usage and model pricing.
        
        Args:
            model_id: Bedrock model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        try:
            # Get pricing for the specific model or use default
            pricing = self.PRICING.get(model_id, self.PRICING["default"])
            
            # Calculate cost (pricing is per 1M tokens)
            input_cost = (input_tokens / 1_000_000) * pricing["input"]
            output_cost = (output_tokens / 1_000_000) * pricing["output"]
            
            return round(input_cost + output_cost, 6)  # Round to 6 decimal places
            
        except Exception as e:
            logger.error(f"Error calculating cost: {e}")
            return 0.0
    
    def _create_log_entry(self, 
                         agent_id: str,
                         incident_id: Optional[str],
                         model_id: str,
                         input_tokens: int,
                         output_tokens: int,
                         estimated_cost: float,
                         context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create structured log entry for token usage.
        
        Args:
            agent_id: Identifier for the agent making the call
            incident_id: Optional incident identifier
            model_id: Bedrock model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            estimated_cost: Calculated cost estimate
            context: Optional additional context metadata
            
        Returns:
            Structured log entry dictionary
        """
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent_id": agent_id,
            "incident_id": incident_id,
            "model_id": model_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "estimated_cost": estimated_cost,
            "context": context or {}
        }
    
    def invoke_with_logging(self,
                           model_id: str,
                           body: Union[str, Dict[str, Any]],
                           agent_id: str,
                           incident_id: Optional[str] = None,
                           context: Optional[Dict[str, Any]] = None,
                           **kwargs) -> Dict[str, Any]:
        """
        Invoke Bedrock model with token usage logging.
        
        Args:
            model_id: Bedrock model identifier
            body: Request body (string or dict)
            agent_id: Identifier for the agent making the call
            incident_id: Optional incident identifier
            context: Optional additional context metadata
            **kwargs: Additional arguments for bedrock invoke_model
            
        Returns:
            Bedrock response with added logging metadata
            
        Raises:
            ClientError: If Bedrock API call fails
        """
        start_time = time.time()
        
        try:
            # Ensure body is a string
            if isinstance(body, dict):
                body = json.dumps(body)
            
            # Make the Bedrock API call
            response = self.bedrock_client.invoke_model(
                modelId=model_id,
                body=body,
                **kwargs
            )
            
            # Extract token usage
            token_usage = self._extract_token_usage(response)
            input_tokens = token_usage['input_tokens']
            output_tokens = token_usage['output_tokens']
            
            # Calculate cost
            estimated_cost = self._calculate_cost(model_id, input_tokens, output_tokens)
            
            # Create log entry
            log_entry = self._create_log_entry(
                agent_id=agent_id,
                incident_id=incident_id,
                model_id=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost=estimated_cost,
                context=context
            )
            
            # Add execution time to context
            execution_time = time.time() - start_time
            log_entry["context"]["execution_time_seconds"] = round(execution_time, 3)
            
            # Log the usage
            logger.info(f"Bedrock token usage: {json.dumps(log_entry)}")
            
            # Add logging metadata to response
            response['token_logging'] = log_entry
            
            return response
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            # Log the error
            error_log = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "agent_id": agent_id,
                "incident_id": incident_id,
                "model_id": model_id,
                "error": True,
                "error_code": error_code,
                "error_message": error_message,
                "execution_time_seconds": round(time.time() - start_time, 3)
            }
            
            logger.error(f"Bedrock API error: {json.dumps(error_log)}")
            raise
            
        except Exception as e:
            # Log unexpected errors
            error_log = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "agent_id": agent_id,
                "incident_id": incident_id,
                "model_id": model_id,
                "error": True,
                "error_message": str(e),
                "execution_time_seconds": round(time.time() - start_time, 3)
            }
            
            logger.error(f"Unexpected error in token logging: {json.dumps(error_log)}")
            raise
    
    def get_model_pricing(self, model_id: str) -> Dict[str, float]:
        """
        Get pricing information for a specific model.
        
        Args:
            model_id: Bedrock model identifier
            
        Returns:
            Dictionary with input and output pricing per 1M tokens
        """
        return self.PRICING.get(model_id, self.PRICING["default"])
    
    def estimate_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for given token usage without making API call.
        
        Args:
            model_id: Bedrock model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        return self._calculate_cost(model_id, input_tokens, output_tokens)
