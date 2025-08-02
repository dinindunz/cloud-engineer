"""
Monitored Agent Wrapper for Bedrock Token Logging.

This module provides a comprehensive wrapper that integrates token logging,
CloudWatch metrics, and DynamoDB storage for Bedrock API calls.
"""

import asyncio
import logging
import functools
from contextlib import contextmanager
from typing import Dict, Any, Optional, Union, Callable
from datetime import datetime
import json

from .token_logger import BedrockTokenLogger
from .cloudwatch_metrics import TokenMetricsLogger
from .dynamo_logger import TokenDynamoLogger
from .logging_config import LoggingConfig

logger = logging.getLogger(__name__)


class MonitoredBedrockAgent:
    """
    Comprehensive monitoring wrapper for Bedrock agents.
    
    Integrates token logging, CloudWatch metrics, and DynamoDB storage
    with async logging to avoid blocking incident response.
    """
    
    def __init__(self, 
                 config: Optional[LoggingConfig] = None,
                 region_name: str = "ap-southeast-2"):
        """
        Initialize the monitored agent wrapper.
        
        Args:
            config: Logging configuration (uses defaults if None)
            region_name: AWS region for services
        """
        self.config = config or LoggingConfig()
        self.region_name = region_name
        
        # Initialize logging components based on configuration
        self.token_logger = None
        self.metrics_logger = None
        self.dynamo_logger = None
        
        if self.config.enable_token_logging:
            self.token_logger = BedrockTokenLogger(region_name=region_name)
        
        if self.config.enable_cloudwatch_metrics:
            self.metrics_logger = TokenMetricsLogger(
                region_name=region_name,
                namespace=self.config.cloudwatch_namespace
            )
        
        if self.config.enable_dynamodb_logging:
            self.dynamo_logger = TokenDynamoLogger(
                table_name=self.config.dynamodb_table_name,
                region_name=region_name,
                ttl_days=self.config.retention_days
            )
        
        # Track active incidents for context
        self._active_incidents = {}
        
    async def _async_log_usage(self,
                              log_entry: Dict[str, Any],
                              agent_id: str,
                              model_id: str,
                              input_tokens: int,
                              output_tokens: int,
                              estimated_cost: float,
                              incident_id: Optional[str] = None) -> None:
        """
        Asynchronously log usage data to all enabled services.
        
        Args:
            log_entry: Complete log entry from token logger
            agent_id: Agent identifier
            model_id: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            estimated_cost: Estimated cost
            incident_id: Optional incident identifier
        """
        tasks = []
        
        try:
            # CloudWatch metrics logging
            if self.metrics_logger:
                task = asyncio.create_task(
                    self._async_cloudwatch_log(
                        agent_id, model_id, input_tokens, 
                        output_tokens, estimated_cost, incident_id
                    )
                )
                tasks.append(task)
            
            # DynamoDB logging
            if self.dynamo_logger:
                task = asyncio.create_task(
                    self._async_dynamo_log(log_entry)
                )
                tasks.append(task)
            
            # Wait for all logging tasks to complete
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                
        except Exception as e:
            logger.error(f"Error in async logging: {e}")
    
    async def _async_cloudwatch_log(self,
                                   agent_id: str,
                                   model_id: str,
                                   input_tokens: int,
                                   output_tokens: int,
                                   estimated_cost: float,
                                   incident_id: Optional[str] = None) -> None:
        """
        Asynchronously log to CloudWatch.
        """
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.metrics_logger.log_token_usage,
                agent_id, model_id, input_tokens, 
                output_tokens, estimated_cost, incident_id
            )
        except Exception as e:
            logger.error(f"CloudWatch logging failed: {e}")
    
    async def _async_dynamo_log(self, log_entry: Dict[str, Any]) -> None:
        """
        Asynchronously log to DynamoDB.
        """
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.dynamo_logger.log_token_usage,
                log_entry['timestamp'],
                log_entry['agent_id'],
                log_entry['model_id'],
                log_entry['input_tokens'],
                log_entry['output_tokens'],
                log_entry['estimated_cost'],
                log_entry.get('incident_id'),
                log_entry.get('context')
            )
        except Exception as e:
            logger.error(f"DynamoDB logging failed: {e}")
    
    def _fire_and_forget_logging(self, coro) -> None:
        """
        Fire and forget async logging to avoid blocking.
        
        Args:
            coro: Coroutine to execute
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, create task
                asyncio.create_task(coro)
            else:
                # If no loop is running, run until complete
                asyncio.run(coro)
        except RuntimeError:
            # Fallback: create new event loop
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                new_loop.run_until_complete(coro)
                new_loop.close()
            except Exception as e:
                logger.error(f"Failed to execute async logging: {e}")
    
    def invoke_model_with_logging(self,
                                 model_id: str,
                                 body: Union[str, Dict[str, Any]],
                                 agent_id: str,
                                 incident_id: Optional[str] = None,
                                 context: Optional[Dict[str, Any]] = None,
                                 **kwargs) -> Dict[str, Any]:
        """
        Invoke Bedrock model with comprehensive logging.
        
        Args:
            model_id: Bedrock model identifier
            body: Request body
            agent_id: Agent identifier
            incident_id: Optional incident identifier
            context: Optional additional context
            **kwargs: Additional arguments for bedrock invoke_model
            
        Returns:
            Bedrock response with logging metadata
        """
        if not self.token_logger:
            logger.warning("Token logging is disabled")
            # Fallback to direct Bedrock call without logging
            import boto3
            bedrock_client = boto3.client('bedrock-runtime', region_name=self.region_name)
            if isinstance(body, dict):
                body = json.dumps(body)
            return bedrock_client.invoke_model(modelId=model_id, body=body, **kwargs)
        
        try:
            # Use token logger for the actual API call
            response = self.token_logger.invoke_with_logging(
                model_id=model_id,
                body=body,
                agent_id=agent_id,
                incident_id=incident_id,
                context=context,
                **kwargs
            )
            
            # Extract logging data
            log_entry = response.get('token_logging', {})
            
            if log_entry:
                # Fire and forget async logging
                self._fire_and_forget_logging(
                    self._async_log_usage(
                        log_entry=log_entry,
                        agent_id=agent_id,
                        model_id=model_id,
                        input_tokens=log_entry.get('input_tokens', 0),
                        output_tokens=log_entry.get('output_tokens', 0),
                        estimated_cost=log_entry.get('estimated_cost', 0.0),
                        incident_id=incident_id
                    )
                )
            
            return response
            
        except Exception as e:
            # Log error metrics if enabled
            if self.metrics_logger:
                try:
                    error_code = getattr(e, 'response', {}).get('Error', {}).get('Code', 'Unknown')
                    self.metrics_logger.log_error_metric(
                        agent_id=agent_id,
                        model_id=model_id,
                        error_code=error_code,
                        incident_id=incident_id
                    )
                except Exception as metric_error:
                    logger.error(f"Failed to log error metric: {metric_error}")
            
            raise
    
    @contextmanager
    def incident_context(self, incident_id: str, context: Optional[Dict[str, Any]] = None):
        """
        Context manager for tracking incident-level operations.
        
        Args:
            incident_id: Incident identifier
            context: Optional incident context data
            
        Usage:
            with agent.incident_context("INC-123", {"priority": "high"}):
                response = agent.invoke_model_with_logging(...)
        """
        self._active_incidents[incident_id] = {
            'start_time': datetime.utcnow().isoformat() + "Z",
            'context': context or {}
        }
        
        try:
            yield incident_id
        finally:
            # Clean up incident context
            if incident_id in self._active_incidents:
                del self._active_incidents[incident_id]
    
    def get_active_incidents(self) -> Dict[str, Any]:
        """
        Get currently active incidents.
        
        Returns:
            Dictionary of active incidents
        """
        return self._active_incidents.copy()
    
    def flush_all_metrics(self) -> None:
        """
        Flush all buffered metrics to their respective services.
        """
        try:
            if self.metrics_logger:
                self.metrics_logger.flush_all_metrics()
                logger.info("Flushed CloudWatch metrics")
        except Exception as e:
            logger.error(f"Error flushing metrics: {e}")


def token_logging_decorator(agent_id: str,
                           incident_id: Optional[str] = None,
                           context: Optional[Dict[str, Any]] = None,
                           config: Optional[LoggingConfig] = None):
    """
    Decorator for adding token logging to existing Bedrock API calls.
    
    Args:
        agent_id: Agent identifier
        incident_id: Optional incident identifier
        context: Optional additional context
        config: Optional logging configuration
        
    Usage:
        @token_logging_decorator(agent_id="cloud-engineer", incident_id="INC-123")
        def my_bedrock_call(model_id, body):
            # Your existing Bedrock API call
            return bedrock_client.invoke_model(modelId=model_id, body=body)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract model_id and body from function arguments
            model_id = kwargs.get('model_id') or kwargs.get('modelId')
            body = kwargs.get('body')
            
            if not model_id:
                logger.warning("No model_id found in function arguments, skipping logging")
                return func(*args, **kwargs)
            
            # Create monitored agent
            monitored_agent = MonitoredBedrockAgent(config=config)
            
            # Use monitored agent instead of direct call
            return monitored_agent.invoke_model_with_logging(
                model_id=model_id,
                body=body,
                agent_id=agent_id,
                incident_id=incident_id,
                context=context,
                **{k: v for k, v in kwargs.items() if k not in ['model_id', 'modelId', 'body']}
            )
        
        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern for logging failures.
    
    Prevents cascading failures when logging services are unavailable.
    """
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func: Callable, *args, **kwargs):
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result or None if circuit is open
        """
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
            else:
                logger.warning("Circuit breaker is OPEN, skipping logging call")
                return None
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            logger.error(f"Circuit breaker caught exception: {e}")
            return None
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        
        import time
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        """Handle failed call."""
        import time
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")


class ResilientMonitoredAgent(MonitoredBedrockAgent):
    """
    Monitored agent with circuit breaker protection for logging failures.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.circuit_breaker = CircuitBreaker()
    
    async def _async_log_usage(self, *args, **kwargs):
        """
        Override async logging with circuit breaker protection.
        """
        return self.circuit_breaker.call(
            super()._async_log_usage,
            *args, **kwargs
        )
