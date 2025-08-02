"""
DynamoDB Storage for Bedrock Token Usage Data.

This module provides the TokenDynamoLogger class for storing detailed
token usage data in DynamoDB with TTL and efficient querying capabilities.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal

logger = logging.getLogger(__name__)


class TokenDynamoLogger:
    """
    DynamoDB logger for detailed Bedrock token usage tracking.
    
    Stores comprehensive usage data with TTL for automatic cleanup
    and GSI for efficient querying by agent_id and incident_id.
    """
    
    def __init__(self, 
                 table_name: str = "bedrock-token-usage",
                 region_name: str = "ap-southeast-2",
                 ttl_days: int = 90):
        """
        Initialize the DynamoDB logger.
        
        Args:
            table_name: Name of the DynamoDB table
            region_name: AWS region for DynamoDB client
            ttl_days: Number of days to retain data (default: 90)
        """
        self.table_name = table_name
        self.region_name = region_name
        self.ttl_days = ttl_days
        self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
        self.table = self.dynamodb.Table(table_name)
        self._batch_items = []
        self._batch_size = 25  # DynamoDB batch_writer max size
        
    def _convert_floats_to_decimal(self, obj: Any) -> Any:
        """
        Convert float values to Decimal for DynamoDB compatibility.
        
        Args:
            obj: Object to convert
            
        Returns:
            Object with floats converted to Decimal
        """
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {key: self._convert_floats_to_decimal(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_floats_to_decimal(item) for item in obj]
        else:
            return obj
    
    def _calculate_ttl(self) -> int:
        """
        Calculate TTL timestamp for automatic data cleanup.
        
        Returns:
            Unix timestamp for TTL expiration
        """
        expiration_date = datetime.utcnow() + timedelta(days=self.ttl_days)
        return int(expiration_date.timestamp())
    
    def _create_partition_key(self, timestamp: str) -> str:
        """
        Create partition key from timestamp for better distribution.
        Uses date-based partitioning (YYYY-MM-DD format).
        
        Args:
            timestamp: ISO timestamp string
            
        Returns:
            Partition key string
        """
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d')
        except Exception as e:
            logger.warning(f"Error parsing timestamp {timestamp}: {e}")
            return datetime.utcnow().strftime('%Y-%m-%d')
    
    def _create_sort_key(self, timestamp: str, agent_id: str) -> str:
        """
        Create sort key from timestamp and agent_id.
        
        Args:
            timestamp: ISO timestamp string
            agent_id: Agent identifier
            
        Returns:
            Sort key string
        """
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_part = dt.strftime('%H:%M:%S.%f')[:-3]  # Include milliseconds
            return f"{time_part}#{agent_id}"
        except Exception as e:
            logger.warning(f"Error creating sort key: {e}")
            return f"{datetime.utcnow().strftime('%H:%M:%S.%f')[:-3]}#{agent_id}"
    
    def log_token_usage(self,
                       timestamp: str,
                       agent_id: str,
                       model_id: str,
                       input_tokens: int,
                       output_tokens: int,
                       estimated_cost: float,
                       incident_id: Optional[str] = None,
                       context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Log token usage data to DynamoDB.
        
        Args:
            timestamp: ISO timestamp string
            agent_id: Agent identifier
            model_id: Bedrock model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            estimated_cost: Estimated cost in USD
            incident_id: Optional incident identifier
            context: Optional additional context data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            partition_key = self._create_partition_key(timestamp)
            sort_key = self._create_sort_key(timestamp, agent_id)
            
            item = {
                'date_partition': partition_key,
                'timestamp_agent': sort_key,
                'timestamp': timestamp,
                'agent_id': agent_id,
                'model_id': model_id,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': input_tokens + output_tokens,
                'estimated_cost': estimated_cost,
                'ttl': self._calculate_ttl()
            }
            
            if incident_id:
                item['incident_id'] = incident_id
            
            if context:
                item['context'] = context
            
            # Convert floats to Decimal for DynamoDB
            item = self._convert_floats_to_decimal(item)
            
            # Put item to DynamoDB
            self.table.put_item(Item=item)
            
            logger.debug(f"Successfully logged token usage to DynamoDB: {agent_id}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to log token usage to DynamoDB: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error logging to DynamoDB: {e}")
            return False
    
    def batch_log_token_usage(self, usage_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Log multiple token usage records in batch.
        
        Args:
            usage_records: List of usage record dictionaries
            
        Returns:
            Dictionary with success/failure counts and any unprocessed items
        """
        success_count = 0
        failure_count = 0
        unprocessed_items = []
        
        try:
            with self.table.batch_writer() as batch:
                for record in usage_records:
                    try:
                        partition_key = self._create_partition_key(record['timestamp'])
                        sort_key = self._create_sort_key(record['timestamp'], record['agent_id'])
                        
                        item = {
                            'date_partition': partition_key,
                            'timestamp_agent': sort_key,
                            'timestamp': record['timestamp'],
                            'agent_id': record['agent_id'],
                            'model_id': record['model_id'],
                            'input_tokens': record['input_tokens'],
                            'output_tokens': record['output_tokens'],
                            'total_tokens': record['input_tokens'] + record['output_tokens'],
                            'estimated_cost': record['estimated_cost'],
                            'ttl': self._calculate_ttl()
                        }
                        
                        if record.get('incident_id'):
                            item['incident_id'] = record['incident_id']
                        
                        if record.get('context'):
                            item['context'] = record['context']
                        
                        # Convert floats to Decimal
                        item = self._convert_floats_to_decimal(item)
                        
                        batch.put_item(Item=item)
                        success_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing record in batch: {e}")
                        failure_count += 1
                        unprocessed_items.append(record)
            
            logger.info(f"Batch logged {success_count} records to DynamoDB, {failure_count} failures")
            
            return {
                'success_count': success_count,
                'failure_count': failure_count,
                'unprocessed_items': unprocessed_items
            }
            
        except Exception as e:
            logger.error(f"Batch logging failed: {e}")
            return {
                'success_count': 0,
                'failure_count': len(usage_records),
                'unprocessed_items': usage_records
            }
    
    def query_by_agent(self,
                      agent_id: str,
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None,
                      limit: int = 100) -> List[Dict[str, Any]]:
        """
        Query token usage by agent ID using GSI.
        
        Args:
            agent_id: Agent identifier
            start_date: Start date in YYYY-MM-DD format (optional)
            end_date: End date in YYYY-MM-DD format (optional)
            limit: Maximum number of items to return
            
        Returns:
            List of usage records
        """
        try:
            # Use GSI for agent_id queries
            query_params = {
                'IndexName': 'agent-id-timestamp-index',
                'KeyConditionExpression': 'agent_id = :agent_id',
                'ExpressionAttributeValues': {':agent_id': agent_id},
                'Limit': limit,
                'ScanIndexForward': False  # Most recent first
            }
            
            # Add date range filter if provided
            if start_date or end_date:
                filter_expressions = []
                
                if start_date:
                    query_params['ExpressionAttributeValues'][':start_date'] = start_date
                    filter_expressions.append('date_partition >= :start_date')
                
                if end_date:
                    query_params['ExpressionAttributeValues'][':end_date'] = end_date
                    filter_expressions.append('date_partition <= :end_date')
                
                if filter_expressions:
                    query_params['FilterExpression'] = ' AND '.join(filter_expressions)
            
            response = self.table.query(**query_params)
            
            # Convert Decimal back to float for JSON serialization
            items = []
            for item in response.get('Items', []):
                converted_item = self._convert_decimals_to_float(item)
                items.append(converted_item)
            
            return items
            
        except ClientError as e:
            logger.error(f"Failed to query by agent: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error querying by agent: {e}")
            return []
    
    def query_by_incident(self,
                         incident_id: str,
                         limit: int = 100) -> List[Dict[str, Any]]:
        """
        Query token usage by incident ID using GSI.
        
        Args:
            incident_id: Incident identifier
            limit: Maximum number of items to return
            
        Returns:
            List of usage records
        """
        try:
            response = self.table.query(
                IndexName='incident-id-timestamp-index',
                KeyConditionExpression='incident_id = :incident_id',
                ExpressionAttributeValues={':incident_id': incident_id},
                Limit=limit,
                ScanIndexForward=False  # Most recent first
            )
            
            # Convert Decimal back to float
            items = []
            for item in response.get('Items', []):
                converted_item = self._convert_decimals_to_float(item)
                items.append(converted_item)
            
            return items
            
        except ClientError as e:
            logger.error(f"Failed to query by incident: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error querying by incident: {e}")
            return []
    
    def query_by_date_range(self,
                           start_date: str,
                           end_date: str,
                           agent_id: Optional[str] = None,
                           limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Query token usage by date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            agent_id: Optional agent filter
            limit: Maximum number of items to return
            
        Returns:
            List of usage records
        """
        try:
            all_items = []
            current_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
            
            while current_date <= end_date_obj and len(all_items) < limit:
                date_partition = current_date.strftime('%Y-%m-%d')
                
                query_params = {
                    'KeyConditionExpression': 'date_partition = :date_partition',
                    'ExpressionAttributeValues': {':date_partition': date_partition},
                    'Limit': limit - len(all_items)
                }
                
                # Add agent filter if provided
                if agent_id:
                    query_params['FilterExpression'] = 'agent_id = :agent_id'
                    query_params['ExpressionAttributeValues'][':agent_id'] = agent_id
                
                response = self.table.query(**query_params)
                
                for item in response.get('Items', []):
                    converted_item = self._convert_decimals_to_float(item)
                    all_items.append(converted_item)
                
                current_date += timedelta(days=1)
            
            # Sort by timestamp (most recent first)
            all_items.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return all_items[:limit]
            
        except Exception as e:
            logger.error(f"Error querying by date range: {e}")
            return []
    
    def _convert_decimals_to_float(self, obj: Any) -> Any:
        """
        Convert Decimal values back to float for JSON serialization.
        
        Args:
            obj: Object to convert
            
        Returns:
            Object with Decimals converted to float
        """
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {key: self._convert_decimals_to_float(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_decimals_to_float(item) for item in obj]
        else:
            return obj
    
    def get_usage_summary(self,
                         start_date: str,
                         end_date: str,
                         group_by: str = 'agent_id') -> Dict[str, Any]:
        """
        Get usage summary statistics for a date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            group_by: Group results by 'agent_id', 'model_id', or 'incident_id'
            
        Returns:
            Dictionary with usage summary statistics
        """
        try:
            records = self.query_by_date_range(start_date, end_date, limit=10000)
            
            summary = {}
            total_cost = 0
            total_tokens = 0
            
            for record in records:
                group_key = record.get(group_by, 'unknown')
                
                if group_key not in summary:
                    summary[group_key] = {
                        'total_tokens': 0,
                        'input_tokens': 0,
                        'output_tokens': 0,
                        'total_cost': 0,
                        'request_count': 0
                    }
                
                summary[group_key]['total_tokens'] += record.get('total_tokens', 0)
                summary[group_key]['input_tokens'] += record.get('input_tokens', 0)
                summary[group_key]['output_tokens'] += record.get('output_tokens', 0)
                summary[group_key]['total_cost'] += record.get('estimated_cost', 0)
                summary[group_key]['request_count'] += 1
                
                total_cost += record.get('estimated_cost', 0)
                total_tokens += record.get('total_tokens', 0)
            
            return {
                'summary_by_' + group_by: summary,
                'total_cost': round(total_cost, 6),
                'total_tokens': total_tokens,
                'total_requests': len(records),
                'date_range': {
                    'start_date': start_date,
                    'end_date': end_date
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating usage summary: {e}")
            return {}
    
    def cleanup_expired_data(self) -> Dict[str, int]:
        """
        Manually cleanup expired data (TTL should handle this automatically).
        
        Returns:
            Dictionary with cleanup statistics
        """
        try:
            current_time = int(time.time())
            deleted_count = 0
            
            # Scan for expired items (this is expensive, use sparingly)
            response = self.table.scan(
                FilterExpression='#ttl < :current_time',
                ExpressionAttributeNames={'#ttl': 'ttl'},
                ExpressionAttributeValues={':current_time': current_time},
                ProjectionExpression='date_partition, timestamp_agent'
            )
            
            # Delete expired items in batches
            with self.table.batch_writer() as batch:
                for item in response.get('Items', []):
                    batch.delete_item(
                        Key={
                            'date_partition': item['date_partition'],
                            'timestamp_agent': item['timestamp_agent']
                        }
                    )
                    deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} expired records")
            
            return {
                'deleted_count': deleted_count,
                'cleanup_timestamp': current_time
            }
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {'deleted_count': 0, 'error': str(e)}
