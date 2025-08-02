"""
Cost Analysis and Reporting for Bedrock Token Usage.

This module provides comprehensive cost analysis, reporting, and forecasting
capabilities for Bedrock token usage data.
"""

import logging
import json
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from collections import defaultdict
import statistics

from .dynamo_logger import TokenDynamoLogger
from .cloudwatch_metrics import TokenMetricsLogger
from .logging_config import LoggingConfig

logger = logging.getLogger(__name__)


@dataclass
class CostSummary:
    """Summary of cost analysis results."""
    total_cost: float
    total_tokens: int
    total_requests: int
    average_cost_per_request: float
    average_tokens_per_request: float
    date_range: Dict[str, str]
    breakdown: Dict[str, Any]


@dataclass
class TrendData:
    """Trend analysis data point."""
    date: str
    cost: float
    tokens: int
    requests: int


@dataclass
class ForecastData:
    """Cost forecast data."""
    period: str
    predicted_cost: float
    confidence_interval: Tuple[float, float]
    trend_direction: str  # 'increasing', 'decreasing', 'stable'


class CostAnalyzer:
    """
    Comprehensive cost analysis and reporting for Bedrock usage.
    
    Provides cost aggregation, trend analysis, forecasting, and
    various reporting formats for token usage data.
    """
    
    def __init__(self, 
                 config: Optional[LoggingConfig] = None,
                 region_name: str = "ap-southeast-2"):
        """
        Initialize the cost analyzer.
        
        Args:
            config: Logging configuration
            region_name: AWS region
        """
        self.config = config or LoggingConfig()
        self.region_name = region_name
        
        # Initialize data sources
        self.dynamo_logger = None
        self.metrics_logger = None
        
        if self.config.enable_dynamodb_logging:
            self.dynamo_logger = TokenDynamoLogger(
                table_name=self.config.dynamodb_table_name,
                region_name=region_name,
                ttl_days=self.config.retention_days
            )
        
        if self.config.enable_cloudwatch_metrics:
            self.metrics_logger = TokenMetricsLogger(
                region_name=region_name,
                namespace=self.config.cloudwatch_namespace
            )
    
    def generate_daily_cost_report(self,
                                  date: str,
                                  agent_ids: Optional[List[str]] = None) -> CostSummary:
        """
        Generate daily cost report for specified date.
        
        Args:
            date: Date in YYYY-MM-DD format
            agent_ids: Optional list of agent IDs to filter by
            
        Returns:
            CostSummary with daily cost breakdown
        """
        if not self.dynamo_logger:
            raise ValueError("DynamoDB logging must be enabled for cost reports")
        
        try:
            # Query data for the specific date
            records = self.dynamo_logger.query_by_date_range(
                start_date=date,
                end_date=date,
                limit=10000
            )
            
            # Filter by agent IDs if specified
            if agent_ids:
                records = [r for r in records if r.get('agent_id') in agent_ids]
            
            # Calculate totals
            total_cost = sum(r.get('estimated_cost', 0) for r in records)
            total_tokens = sum(r.get('total_tokens', 0) for r in records)
            total_requests = len(records)
            
            # Calculate averages
            avg_cost_per_request = total_cost / total_requests if total_requests > 0 else 0
            avg_tokens_per_request = total_tokens / total_requests if total_requests > 0 else 0
            
            # Generate breakdowns
            breakdown = {
                'by_agent': self._breakdown_by_field(records, 'agent_id'),
                'by_model': self._breakdown_by_field(records, 'model_id'),
                'by_hour': self._breakdown_by_hour(records),
                'top_incidents': self._get_top_incidents(records, limit=10)
            }
            
            return CostSummary(
                total_cost=round(total_cost, 6),
                total_tokens=total_tokens,
                total_requests=total_requests,
                average_cost_per_request=round(avg_cost_per_request, 6),
                average_tokens_per_request=round(avg_tokens_per_request, 2),
                date_range={'start_date': date, 'end_date': date},
                breakdown=breakdown
            )
            
        except Exception as e:
            logger.error(f"Error generating daily cost report: {e}")
            raise
    
    def generate_agent_cost_breakdown(self,
                                    start_date: str,
                                    end_date: str,
                                    agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate agent-level cost breakdown for date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            agent_id: Optional specific agent ID
            
        Returns:
            Dictionary with agent cost breakdown
        """
        if not self.dynamo_logger:
            raise ValueError("DynamoDB logging must be enabled for cost reports")
        
        try:
            # Query data for date range
            records = self.dynamo_logger.query_by_date_range(
                start_date=start_date,
                end_date=end_date,
                agent_id=agent_id,
                limit=50000
            )
            
            # Group by agent
            agent_data = defaultdict(lambda: {
                'total_cost': 0,
                'total_tokens': 0,
                'total_requests': 0,
                'models_used': set(),
                'incidents': set(),
                'daily_breakdown': defaultdict(lambda: {'cost': 0, 'tokens': 0, 'requests': 0})
            })
            
            for record in records:
                agent_id = record.get('agent_id', 'unknown')
                cost = record.get('estimated_cost', 0)
                tokens = record.get('total_tokens', 0)
                model_id = record.get('model_id', 'unknown')
                incident_id = record.get('incident_id')
                
                # Extract date from timestamp
                timestamp = record.get('timestamp', '')
                try:
                    date = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                except:
                    date = 'unknown'
                
                # Update agent totals
                agent_data[agent_id]['total_cost'] += cost
                agent_data[agent_id]['total_tokens'] += tokens
                agent_data[agent_id]['total_requests'] += 1
                agent_data[agent_id]['models_used'].add(model_id)
                
                if incident_id:
                    agent_data[agent_id]['incidents'].add(incident_id)
                
                # Update daily breakdown
                agent_data[agent_id]['daily_breakdown'][date]['cost'] += cost
                agent_data[agent_id]['daily_breakdown'][date]['tokens'] += tokens
                agent_data[agent_id]['daily_breakdown'][date]['requests'] += 1
            
            # Convert sets to lists and format data
            result = {}
            for agent_id, data in agent_data.items():
                result[agent_id] = {
                    'total_cost': round(data['total_cost'], 6),
                    'total_tokens': data['total_tokens'],
                    'total_requests': data['total_requests'],
                    'average_cost_per_request': round(data['total_cost'] / data['total_requests'], 6) if data['total_requests'] > 0 else 0,
                    'average_tokens_per_request': round(data['total_tokens'] / data['total_requests'], 2) if data['total_requests'] > 0 else 0,
                    'models_used': list(data['models_used']),
                    'unique_incidents': len(data['incidents']),
                    'daily_breakdown': dict(data['daily_breakdown'])
                }
            
            return {
                'date_range': {'start_date': start_date, 'end_date': end_date},
                'agents': result,
                'summary': {
                    'total_agents': len(result),
                    'total_cost': round(sum(a['total_cost'] for a in result.values()), 6),
                    'total_tokens': sum(a['total_tokens'] for a in result.values()),
                    'total_requests': sum(a['total_requests'] for a in result.values())
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating agent cost breakdown: {e}")
            raise
    
    def generate_incident_cost_analysis(self,
                                      incident_id: str) -> Dict[str, Any]:
        """
        Generate cost analysis for a specific incident.
        
        Args:
            incident_id: Incident identifier
            
        Returns:
            Dictionary with incident cost analysis
        """
        if not self.dynamo_logger:
            raise ValueError("DynamoDB logging must be enabled for cost reports")
        
        try:
            # Query data for the incident
            records = self.dynamo_logger.query_by_incident(incident_id, limit=1000)
            
            if not records:
                return {
                    'incident_id': incident_id,
                    'error': 'No data found for incident'
                }
            
            # Calculate totals
            total_cost = sum(r.get('estimated_cost', 0) for r in records)
            total_tokens = sum(r.get('total_tokens', 0) for r in records)
            total_requests = len(records)
            
            # Get time range
            timestamps = [r.get('timestamp') for r in records if r.get('timestamp')]
            start_time = min(timestamps) if timestamps else None
            end_time = max(timestamps) if timestamps else None
            
            # Calculate duration
            duration_minutes = 0
            if start_time and end_time:
                try:
                    start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    duration_minutes = (end_dt - start_dt).total_seconds() / 60
                except:
                    pass
            
            # Generate breakdowns
            agent_breakdown = self._breakdown_by_field(records, 'agent_id')
            model_breakdown = self._breakdown_by_field(records, 'model_id')
            
            # Timeline analysis
            timeline = self._generate_timeline(records)
            
            return {
                'incident_id': incident_id,
                'summary': {
                    'total_cost': round(total_cost, 6),
                    'total_tokens': total_tokens,
                    'total_requests': total_requests,
                    'duration_minutes': round(duration_minutes, 2),
                    'cost_per_minute': round(total_cost / duration_minutes, 6) if duration_minutes > 0 else 0,
                    'start_time': start_time,
                    'end_time': end_time
                },
                'breakdown': {
                    'by_agent': agent_breakdown,
                    'by_model': model_breakdown
                },
                'timeline': timeline
            }
            
        except Exception as e:
            logger.error(f"Error generating incident cost analysis: {e}")
            raise
    
    def get_cost_trends(self,
                       start_date: str,
                       end_date: str,
                       granularity: str = 'daily') -> List[TrendData]:
        """
        Get cost trends over time.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            granularity: 'daily', 'weekly', or 'monthly'
            
        Returns:
            List of TrendData objects
        """
        if not self.dynamo_logger:
            raise ValueError("DynamoDB logging must be enabled for trend analysis")
        
        try:
            # Query data for date range
            records = self.dynamo_logger.query_by_date_range(
                start_date=start_date,
                end_date=end_date,
                limit=100000
            )
            
            # Group data by time period
            grouped_data = defaultdict(lambda: {'cost': 0, 'tokens': 0, 'requests': 0})
            
            for record in records:
                timestamp = record.get('timestamp', '')
                cost = record.get('estimated_cost', 0)
                tokens = record.get('total_tokens', 0)
                
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    
                    if granularity == 'daily':
                        period_key = dt.strftime('%Y-%m-%d')
                    elif granularity == 'weekly':
                        # Get Monday of the week
                        monday = dt - timedelta(days=dt.weekday())
                        period_key = monday.strftime('%Y-%m-%d')
                    elif granularity == 'monthly':
                        period_key = dt.strftime('%Y-%m')
                    else:
                        period_key = dt.strftime('%Y-%m-%d')
                    
                    grouped_data[period_key]['cost'] += cost
                    grouped_data[period_key]['tokens'] += tokens
                    grouped_data[period_key]['requests'] += 1
                    
                except Exception as e:
                    logger.warning(f"Error parsing timestamp {timestamp}: {e}")
                    continue
            
            # Convert to TrendData objects
            trends = []
            for period, data in sorted(grouped_data.items()):
                trends.append(TrendData(
                    date=period,
                    cost=round(data['cost'], 6),
                    tokens=data['tokens'],
                    requests=data['requests']
                ))
            
            return trends
            
        except Exception as e:
            logger.error(f"Error getting cost trends: {e}")
            raise
    
    def forecast_costs(self,
                      historical_days: int = 30,
                      forecast_days: int = 7) -> List[ForecastData]:
        """
        Generate cost forecasts based on historical data.
        
        Args:
            historical_days: Number of historical days to analyze
            forecast_days: Number of days to forecast
            
        Returns:
            List of ForecastData objects
        """
        try:
            # Get historical data
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
            start_date = (datetime.utcnow() - timedelta(days=historical_days)).strftime('%Y-%m-%d')
            
            trends = self.get_cost_trends(start_date, end_date, granularity='daily')
            
            if len(trends) < 7:
                logger.warning("Insufficient historical data for forecasting")
                return []
            
            # Extract cost values
            costs = [trend.cost for trend in trends]
            
            # Simple linear regression for trend
            n = len(costs)
            x_values = list(range(n))
            
            # Calculate slope and intercept
            x_mean = statistics.mean(x_values)
            y_mean = statistics.mean(costs)
            
            numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, costs))
            denominator = sum((x - x_mean) ** 2 for x in x_values)
            
            if denominator == 0:
                slope = 0
            else:
                slope = numerator / denominator
            
            intercept = y_mean - slope * x_mean
            
            # Calculate standard deviation for confidence intervals
            predictions = [slope * x + intercept for x in x_values]
            residuals = [actual - pred for actual, pred in zip(costs, predictions)]
            std_dev = statistics.stdev(residuals) if len(residuals) > 1 else 0
            
            # Determine trend direction
            if abs(slope) < 0.01:
                trend_direction = 'stable'
            elif slope > 0:
                trend_direction = 'increasing'
            else:
                trend_direction = 'decreasing'
            
            # Generate forecasts
            forecasts = []
            base_date = datetime.utcnow() + timedelta(days=1)
            
            for i in range(forecast_days):
                forecast_date = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')
                x_forecast = n + i
                predicted_cost = max(0, slope * x_forecast + intercept)  # Ensure non-negative
                
                # 95% confidence interval (approximately 2 standard deviations)
                confidence_margin = 2 * std_dev
                lower_bound = max(0, predicted_cost - confidence_margin)
                upper_bound = predicted_cost + confidence_margin
                
                forecasts.append(ForecastData(
                    period=forecast_date,
                    predicted_cost=round(predicted_cost, 6),
                    confidence_interval=(round(lower_bound, 6), round(upper_bound, 6)),
                    trend_direction=trend_direction
                ))
            
            return forecasts
            
        except Exception as e:
            logger.error(f"Error generating cost forecast: {e}")
            return []
    
    def export_usage_data(self,
                         start_date: str,
                         end_date: str,
                         format: str = 'csv',
                         output_file: Optional[str] = None) -> str:
        """
        Export usage data to CSV or JSON format.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            format: 'csv' or 'json'
            output_file: Optional output file path
            
        Returns:
            Path to exported file or data as string
        """
        if not self.dynamo_logger:
            raise ValueError("DynamoDB logging must be enabled for data export")
        
        try:
            # Query data for date range
            records = self.dynamo_logger.query_by_date_range(
                start_date=start_date,
                end_date=end_date,
                limit=100000
            )
            
            if not records:
                logger.warning("No data found for export")
                return ""
            
            # Generate filename if not provided
            if not output_file:
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                output_file = f"bedrock_usage_export_{timestamp}.{format}"
            
            if format.lower() == 'csv':
                return self._export_to_csv(records, output_file)
            elif format.lower() == 'json':
                return self._export_to_json(records, output_file)
            else:
                raise ValueError(f"Unsupported export format: {format}")
                
        except Exception as e:
            logger.error(f"Error exporting usage data: {e}")
            raise
    
    def _breakdown_by_field(self, records: List[Dict[str, Any]], field: str) -> Dict[str, Any]:
        """Generate breakdown by specified field."""
        breakdown = defaultdict(lambda: {'cost': 0, 'tokens': 0, 'requests': 0})
        
        for record in records:
            field_value = record.get(field, 'unknown')
            breakdown[field_value]['cost'] += record.get('estimated_cost', 0)
            breakdown[field_value]['tokens'] += record.get('total_tokens', 0)
            breakdown[field_value]['requests'] += 1
        
        # Convert to regular dict and round costs
        result = {}
        for key, data in breakdown.items():
            result[key] = {
                'cost': round(data['cost'], 6),
                'tokens': data['tokens'],
                'requests': data['requests']
            }
        
        return result
    
    def _breakdown_by_hour(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate breakdown by hour of day."""
        breakdown = defaultdict(lambda: {'cost': 0, 'tokens': 0, 'requests': 0})
        
        for record in records:
            timestamp = record.get('timestamp', '')
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                hour = dt.strftime('%H:00')
                
                breakdown[hour]['cost'] += record.get('estimated_cost', 0)
                breakdown[hour]['tokens'] += record.get('total_tokens', 0)
                breakdown[hour]['requests'] += 1
            except:
                continue
        
        # Convert to regular dict and round costs
        result = {}
        for hour, data in sorted(breakdown.items()):
            result[hour] = {
                'cost': round(data['cost'], 6),
                'tokens': data['tokens'],
                'requests': data['requests']
            }
        
        return result
    
    def _get_top_incidents(self, records: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
        """Get top incidents by cost."""
        incident_costs = defaultdict(lambda: {'cost': 0, 'tokens': 0, 'requests': 0})
        
        for record in records:
            incident_id = record.get('incident_id')
            if incident_id:
                incident_costs[incident_id]['cost'] += record.get('estimated_cost', 0)
                incident_costs[incident_id]['tokens'] += record.get('total_tokens', 0)
                incident_costs[incident_id]['requests'] += 1
        
        # Sort by cost and return top incidents
        sorted_incidents = sorted(
            incident_costs.items(),
            key=lambda x: x[1]['cost'],
            reverse=True
        )
        
        result = []
        for incident_id, data in sorted_incidents[:limit]:
            result.append({
                'incident_id': incident_id,
                'cost': round(data['cost'], 6),
                'tokens': data['tokens'],
                'requests': data['requests']
            })
        
        return result
    
    def _generate_timeline(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate timeline of requests for an incident."""
        timeline = []
        
        for record in records:
            timestamp = record.get('timestamp')
            if timestamp:
                timeline.append({
                    'timestamp': timestamp,
                    'agent_id': record.get('agent_id'),
                    'model_id': record.get('model_id'),
                    'cost': round(record.get('estimated_cost', 0), 6),
                    'tokens': record.get('total_tokens', 0)
                })
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x['timestamp'])
        
        return timeline
    
    def _export_to_csv(self, records: List[Dict[str, Any]], output_file: str) -> str:
        """Export records to CSV format."""
        if not records:
            return ""
        
        # Define CSV headers
        headers = [
            'timestamp', 'agent_id', 'model_id', 'incident_id',
            'input_tokens', 'output_tokens', 'total_tokens', 'estimated_cost'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            
            for record in records:
                row = {header: record.get(header, '') for header in headers}
                writer.writerow(row)
        
        logger.info(f"Exported {len(records)} records to {output_file}")
        return output_file
    
    def _export_to_json(self, records: List[Dict[str, Any]], output_file: str) -> str:
        """Export records to JSON format."""
        export_data = {
            'export_timestamp': datetime.utcnow().isoformat() + "Z",
            'record_count': len(records),
            'records': records
        }
        
        with open(output_file, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_data, jsonfile, indent=2, default=str)
        
        logger.info(f"Exported {len(records)} records to {output_file}")
        return output_file
    
    def check_cost_thresholds(self,
                             date: Optional[str] = None) -> Dict[str, Any]:
        """
        Check if current costs exceed configured thresholds.
        
        Args:
            date: Date to check (defaults to today)
            
        Returns:
            Dictionary with threshold check results
        """
        if not date:
            date = datetime.utcnow().strftime('%Y-%m-%d')
        
        try:
            # Get daily cost report
            daily_report = self.generate_daily_cost_report(date)
            
            # Check thresholds
            daily_exceeded = daily_report.total_cost > self.config.daily_cost_threshold
            
            # For hourly threshold, get last hour's data
            hourly_exceeded = False
            current_hour_cost = 0
            
            if 'by_hour' in daily_report.breakdown:
                current_hour = datetime.utcnow().strftime('%H:00')
                current_hour_cost = daily_report.breakdown['by_hour'].get(current_hour, {}).get('cost', 0)
                hourly_exceeded = current_hour_cost > self.config.hourly_cost_threshold
            
            return {
                'date': date,
                'daily_threshold_exceeded': daily_exceeded,
                'hourly_threshold_exceeded': hourly_exceeded,
                'daily_cost': daily_report.total_cost,
                'daily_threshold': self.config.daily_cost_threshold,
                'current_hour_cost': current_hour_cost,
                'hourly_threshold': self.config.hourly_cost_threshold,
                'alert_required': daily_exceeded or hourly_exceeded
            }
            
        except Exception as e:
            logger.error(f"Error checking cost thresholds: {e}")
            return {
                'date': date,
                'error': str(e),
                'alert_required': False
            }
