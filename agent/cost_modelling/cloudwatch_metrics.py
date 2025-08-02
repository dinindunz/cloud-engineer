"""
CloudWatch Integration for Bedrock Token Usage Metrics.

This module provides the TokenMetricsLogger class for publishing custom metrics
to CloudWatch for monitoring and alerting on Bedrock usage.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class TokenMetricsLogger:
    """
    CloudWatch metrics logger for Bedrock token usage.
    
    Publishes custom metrics with dimensions for Agent ID and Model ID
    to enable detailed monitoring and alerting.
    """
    
    def __init__(self, region_name: str = "ap-southeast-2", namespace: str = "BedrockUsage"):
        """
        Initialize the CloudWatch metrics logger.
        
        Args:
            region_name: AWS region for CloudWatch client
            namespace: CloudWatch namespace for metrics
        """
        self.region_name = region_name
        self.namespace = namespace
        self.cloudwatch = boto3.client('cloudwatch', region_name=region_name)
        self._metric_buffer = []
        self._buffer_size = 20  # CloudWatch allows max 20 metrics per put_metric_data call
        
    def _create_metric_data(self,
                           metric_name: str,
                           value: float,
                           unit: str,
                           dimensions: Dict[str, str],
                           timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Create metric data structure for CloudWatch.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: CloudWatch unit (Count, Currency, etc.)
            dimensions: Metric dimensions
            timestamp: Optional timestamp (defaults to now)
            
        Returns:
            CloudWatch metric data structure
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
            
        return {
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit,
            'Timestamp': timestamp,
            'Dimensions': [
                {'Name': key, 'Value': value} for key, value in dimensions.items()
            ]
        }
    
    def _flush_metrics(self) -> None:
        """
        Flush buffered metrics to CloudWatch.
        """
        if not self._metric_buffer:
            return
            
        try:
            # Send metrics in batches
            for i in range(0, len(self._metric_buffer), self._buffer_size):
                batch = self._metric_buffer[i:i + self._buffer_size]
                
                self.cloudwatch.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=batch
                )
                
            logger.info(f"Successfully published {len(self._metric_buffer)} metrics to CloudWatch")
            self._metric_buffer.clear()
            
        except ClientError as e:
            logger.error(f"Failed to publish metrics to CloudWatch: {e}")
            # Keep metrics in buffer for retry
        except Exception as e:
            logger.error(f"Unexpected error publishing metrics: {e}")
            self._metric_buffer.clear()  # Clear buffer to prevent memory issues
    
    def log_token_usage(self,
                       agent_id: str,
                       model_id: str,
                       input_tokens: int,
                       output_tokens: int,
                       estimated_cost: float,
                       incident_id: Optional[str] = None,
                       timestamp: Optional[datetime] = None) -> None:
        """
        Log token usage metrics to CloudWatch.
        
        Args:
            agent_id: Identifier for the agent
            model_id: Bedrock model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            estimated_cost: Estimated cost in USD
            incident_id: Optional incident identifier
            timestamp: Optional timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        # Base dimensions
        base_dimensions = {
            'AgentId': agent_id,
            'ModelId': model_id
        }
        
        # Add incident dimension if provided
        if incident_id:
            incident_dimensions = base_dimensions.copy()
            incident_dimensions['IncidentId'] = incident_id
        else:
            incident_dimensions = base_dimensions
        
        # Create metrics
        metrics = [
            self._create_metric_data(
                'InputTokens',
                float(input_tokens),
                'Count',
                base_dimensions,
                timestamp
            ),
            self._create_metric_data(
                'OutputTokens',
                float(output_tokens),
                'Count',
                base_dimensions,
                timestamp
            ),
            self._create_metric_data(
                'TotalTokens',
                float(input_tokens + output_tokens),
                'Count',
                base_dimensions,
                timestamp
            ),
            self._create_metric_data(
                'EstimatedCost',
                estimated_cost,
                'None',  # CloudWatch doesn't have a Currency unit, use None
                base_dimensions,
                timestamp
            )
        ]
        
        # Add incident-specific metrics if incident_id is provided
        if incident_id:
            metrics.append(
                self._create_metric_data(
                    'TotalTokensPerIncident',
                    float(input_tokens + output_tokens),
                    'Count',
                    incident_dimensions,
                    timestamp
                )
            )
        
        # Add metrics to buffer
        self._metric_buffer.extend(metrics)
        
        # Flush if buffer is getting full
        if len(self._metric_buffer) >= self._buffer_size:
            self._flush_metrics()
    
    def log_error_metric(self,
                        agent_id: str,
                        model_id: str,
                        error_code: str,
                        incident_id: Optional[str] = None,
                        timestamp: Optional[datetime] = None) -> None:
        """
        Log error metrics to CloudWatch.
        
        Args:
            agent_id: Identifier for the agent
            model_id: Bedrock model identifier
            error_code: Error code from the API
            incident_id: Optional incident identifier
            timestamp: Optional timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        dimensions = {
            'AgentId': agent_id,
            'ModelId': model_id,
            'ErrorCode': error_code
        }
        
        if incident_id:
            dimensions['IncidentId'] = incident_id
        
        error_metric = self._create_metric_data(
            'APIErrors',
            1.0,
            'Count',
            dimensions,
            timestamp
        )
        
        self._metric_buffer.append(error_metric)
        
        # Flush immediately for errors to ensure visibility
        self._flush_metrics()
    
    def publish_batch_metrics(self, metrics_data: List[Dict[str, Any]]) -> None:
        """
        Publish a batch of metrics to CloudWatch.
        
        Args:
            metrics_data: List of metric data dictionaries
        """
        try:
            # Process metrics in batches
            for i in range(0, len(metrics_data), self._buffer_size):
                batch = metrics_data[i:i + self._buffer_size]
                
                # Convert to CloudWatch format
                cloudwatch_metrics = []
                for metric in batch:
                    cloudwatch_metric = self._create_metric_data(
                        metric['metric_name'],
                        metric['value'],
                        metric['unit'],
                        metric['dimensions'],
                        metric.get('timestamp')
                    )
                    cloudwatch_metrics.append(cloudwatch_metric)
                
                # Publish batch
                self.cloudwatch.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=cloudwatch_metrics
                )
                
            logger.info(f"Successfully published {len(metrics_data)} batch metrics to CloudWatch")
            
        except ClientError as e:
            logger.error(f"Failed to publish batch metrics to CloudWatch: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error publishing batch metrics: {e}")
            raise
    
    def create_custom_metric(self,
                            metric_name: str,
                            value: float,
                            unit: str,
                            dimensions: Dict[str, str],
                            timestamp: Optional[datetime] = None) -> None:
        """
        Create and publish a custom metric.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: CloudWatch unit
            dimensions: Metric dimensions
            timestamp: Optional timestamp (defaults to now)
        """
        metric = self._create_metric_data(metric_name, value, unit, dimensions, timestamp)
        self._metric_buffer.append(metric)
        
        # Auto-flush if buffer is full
        if len(self._metric_buffer) >= self._buffer_size:
            self._flush_metrics()
    
    def flush_all_metrics(self) -> None:
        """
        Force flush all buffered metrics to CloudWatch.
        """
        self._flush_metrics()
    
    def get_metric_statistics(self,
                             metric_name: str,
                             start_time: datetime,
                             end_time: datetime,
                             period: int = 300,
                             statistics: List[str] = None,
                             dimensions: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Retrieve metric statistics from CloudWatch.
        
        Args:
            metric_name: Name of the metric
            start_time: Start time for the query
            end_time: End time for the query
            period: Period in seconds (default: 300)
            statistics: List of statistics to retrieve (default: ['Sum', 'Average'])
            dimensions: Optional dimensions to filter by
            
        Returns:
            CloudWatch metric statistics response
        """
        if statistics is None:
            statistics = ['Sum', 'Average']
        
        try:
            params = {
                'Namespace': self.namespace,
                'MetricName': metric_name,
                'StartTime': start_time,
                'EndTime': end_time,
                'Period': period,
                'Statistics': statistics
            }
            
            if dimensions:
                params['Dimensions'] = [
                    {'Name': key, 'Value': value} for key, value in dimensions.items()
                ]
            
            response = self.cloudwatch.get_metric_statistics(**params)
            return response
            
        except ClientError as e:
            logger.error(f"Failed to retrieve metric statistics: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error retrieving metric statistics: {e}")
            raise
    
    def create_alarm(self,
                    alarm_name: str,
                    metric_name: str,
                    threshold: float,
                    comparison_operator: str = 'GreaterThanThreshold',
                    evaluation_periods: int = 2,
                    period: int = 300,
                    statistic: str = 'Sum',
                    dimensions: Optional[Dict[str, str]] = None,
                    alarm_actions: Optional[List[str]] = None) -> str:
        """
        Create a CloudWatch alarm for the metric.
        
        Args:
            alarm_name: Name of the alarm
            metric_name: Name of the metric to monitor
            threshold: Alarm threshold value
            comparison_operator: Comparison operator (default: GreaterThanThreshold)
            evaluation_periods: Number of periods to evaluate (default: 2)
            period: Period in seconds (default: 300)
            statistic: Statistic to use (default: Sum)
            dimensions: Optional dimensions to filter by
            alarm_actions: Optional list of alarm actions (SNS topics, etc.)
            
        Returns:
            Alarm ARN
        """
        try:
            params = {
                'AlarmName': alarm_name,
                'ComparisonOperator': comparison_operator,
                'EvaluationPeriods': evaluation_periods,
                'MetricName': metric_name,
                'Namespace': self.namespace,
                'Period': period,
                'Statistic': statistic,
                'Threshold': threshold,
                'ActionsEnabled': True,
                'AlarmDescription': f'Alarm for {metric_name} in {self.namespace}',
                'Unit': 'None'
            }
            
            if dimensions:
                params['Dimensions'] = [
                    {'Name': key, 'Value': value} for key, value in dimensions.items()
                ]
            
            if alarm_actions:
                params['AlarmActions'] = alarm_actions
            
            response = self.cloudwatch.put_metric_alarm(**params)
            
            # Construct alarm ARN
            alarm_arn = f"arn:aws:cloudwatch:{self.region_name}:*:alarm:{alarm_name}"
            
            logger.info(f"Created CloudWatch alarm: {alarm_name}")
            return alarm_arn
            
        except ClientError as e:
            logger.error(f"Failed to create CloudWatch alarm: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating alarm: {e}")
            raise
