"""
Unit Tests for Bedrock Token Logging System.

This module provides comprehensive unit tests for all logging components
including token extraction, cost calculations, error handling, and integration tests.

Note: These tests are designed to be run in a test environment and should not
be executed in production. They include mock AWS services and test data.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import boto3
from datetime import datetime, timedelta
from typing import Dict, Any, List
import tempfile
import os

# Import modules to test
from .token_logger import BedrockTokenLogger
from .cloudwatch_metrics import TokenMetricsLogger
from .dynamo_logger import TokenDynamoLogger
from .monitored_agent import MonitoredBedrockAgent, token_logging_decorator
from .cost_analyzer import CostAnalyzer, CostSummary, TrendData
from .logging_config import LoggingConfig, ModelPricing


class TestBedrockTokenLogger(unittest.TestCase):
    """Test cases for BedrockTokenLogger."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.logger = BedrockTokenLogger(region_name="us-east-1")
        
        # Mock Bedrock response
        self.mock_response = {
            'body': Mock(),
            'contentType': 'application/json',
            'ResponseMetadata': {
                'HTTPHeaders': {
                    'x-amzn-bedrock-input-token-count': '100',
                    'x-amzn-bedrock-output-token-count': '50'
                }
            }
        }
        
        # Mock response body
        self.mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Test response'}],
            'usage': {
                'input_tokens': 100,
                'output_tokens': 50
            }
        }).encode('utf-8')
    
    @patch('boto3.client')
    def test_invoke_with_logging_success(self, mock_boto_client):
        """Test successful Bedrock API call with logging."""
        # Setup mock client
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.invoke_model.return_value = self.mock_response
        
        # Test the call
        response = self.logger.invoke_with_logging(
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            body=json.dumps({"messages": [{"role": "user", "content": "Hello"}]}),
            agent_id="test-agent",
            incident_id="INC-123"
        )
        
        # Verify response structure
        self.assertIn('token_logging', response)
        self.assertIn('bedrock_response', response)
        
        # Verify token logging data
        log_data = response['token_logging']
        self.assertEqual(log_data['input_tokens'], 100)
        self.assertEqual(log_data['output_tokens'], 50)
        self.assertEqual(log_data['total_tokens'], 150)
        self.assertEqual(log_data['agent_id'], 'test-agent')
        self.assertEqual(log_data['incident_id'], 'INC-123')
        self.assertGreater(log_data['estimated_cost'], 0)
    
    def test_extract_token_usage_from_headers(self):
        """Test token extraction from response headers."""
        tokens = self.logger._extract_token_usage(self.mock_response)
        
        self.assertEqual(tokens['input_tokens'], 100)
        self.assertEqual(tokens['output_tokens'], 50)
        self.assertEqual(tokens['total_tokens'], 150)
    
    def test_extract_token_usage_from_body(self):
        """Test token extraction from response body when headers are missing."""
        # Remove headers
        response_without_headers = {
            'body': self.mock_response['body'],
            'contentType': 'application/json',
            'ResponseMetadata': {'HTTPHeaders': {}}
        }
        
        tokens = self.logger._extract_token_usage(response_without_headers)
        
        self.assertEqual(tokens['input_tokens'], 100)
        self.assertEqual(tokens['output_tokens'], 50)
        self.assertEqual(tokens['total_tokens'], 150)
    
    def test_calculate_cost_sonnet_4(self):
        """Test cost calculation for Sonnet 4 model."""
        cost = self.logger._calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0"
        )
        
        # Expected: (1000/1000000 * 3.0) + (500/1000000 * 15.0) = 0.003 + 0.0075 = 0.0105
        expected_cost = 0.0105
        self.assertAlmostEqual(cost, expected_cost, places=6)
    
    def test_calculate_cost_unknown_model(self):
        """Test cost calculation for unknown model (should use default)."""
        cost = self.logger._calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            model_id="unknown.model"
        )
        
        # Should use Sonnet 4 pricing as default
        expected_cost = 0.0105
        self.assertAlmostEqual(cost, expected_cost, places=6)
    
    @patch('boto3.client')
    def test_invoke_with_logging_api_error(self, mock_boto_client):
        """Test handling of Bedrock API errors."""
        # Setup mock client to raise exception
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.invoke_model.side_effect = Exception("API Error")
        
        # Test that exception is re-raised
        with self.assertRaises(Exception):
            self.logger.invoke_with_logging(
                model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
                body=json.dumps({"messages": [{"role": "user", "content": "Hello"}]}),
                agent_id="test-agent"
            )


class TestCloudWatchMetricsLogger(unittest.TestCase):
    """Test cases for CloudWatch metrics logging."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.metrics_logger = TokenMetricsLogger(
            region_name="us-east-1",
            namespace="TestBedrockUsage"
        )
    
    @patch('boto3.client')
    def test_log_token_usage(self, mock_boto_client):
        """Test CloudWatch metrics logging."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        self.metrics_logger.log_token_usage(
            agent_id="test-agent",
            model_id="test-model",
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.01,
            incident_id="INC-123"
        )
        
        # Verify put_metric_data was called
        mock_client.put_metric_data.assert_called_once()
        
        # Verify metric data structure
        call_args = mock_client.put_metric_data.call_args
        self.assertEqual(call_args[1]['Namespace'], 'TestBedrockUsage')
        
        metric_data = call_args[1]['MetricData']
        self.assertEqual(len(metric_data), 4)  # InputTokens, OutputTokens, EstimatedCost, TotalTokens
    
    @patch('boto3.client')
    def test_log_error_metric(self, mock_boto_client):
        """Test error metric logging."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        self.metrics_logger.log_error_metric(
            agent_id="test-agent",
            model_id="test-model",
            error_code="ThrottlingException"
        )
        
        # Verify put_metric_data was called
        mock_client.put_metric_data.assert_called_once()
        
        # Verify error metric
        call_args = mock_client.put_metric_data.call_args
        metric_data = call_args[1]['MetricData']
        self.assertEqual(len(metric_data), 1)
        self.assertEqual(metric_data[0]['MetricName'], 'APIErrors')


class TestDynamoLogger(unittest.TestCase):
    """Test cases for DynamoDB logging."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.dynamo_logger = TokenDynamoLogger(
            table_name="test-bedrock-token-usage",
            region_name="us-east-1",
            ttl_days=30
        )
    
    @patch('boto3.resource')
    def test_log_token_usage(self, mock_boto_resource):
        """Test DynamoDB logging."""
        mock_table = Mock()
        mock_dynamodb = Mock()
        mock_boto_resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        self.dynamo_logger.log_token_usage(
            timestamp=timestamp,
            agent_id="test-agent",
            model_id="test-model",
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.01,
            incident_id="INC-123"
        )
        
        # Verify put_item was called
        mock_table.put_item.assert_called_once()
        
        # Verify item structure
        call_args = mock_table.put_item.call_args
        item = call_args[1]['Item']
        self.assertEqual(item['agent_id'], 'test-agent')
        self.assertEqual(item['input_tokens'], 100)
        self.assertEqual(item['output_tokens'], 50)
        self.assertEqual(item['estimated_cost'], 0.01)
    
    @patch('boto3.resource')
    def test_query_by_date_range(self, mock_boto_resource):
        """Test querying by date range."""
        mock_table = Mock()
        mock_dynamodb = Mock()
        mock_boto_resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        
        # Mock scan response
        mock_table.scan.return_value = {
            'Items': [
                {
                    'timestamp': '2024-01-01T10:00:00Z',
                    'agent_id': 'test-agent',
                    'estimated_cost': 0.01
                }
            ]
        }
        
        results = self.dynamo_logger.query_by_date_range(
            start_date="2024-01-01",
            end_date="2024-01-01"
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['agent_id'], 'test-agent')


class TestMonitoredAgent(unittest.TestCase):
    """Test cases for MonitoredBedrockAgent."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = LoggingConfig()
        self.config.enable_cloudwatch_metrics = False  # Disable for testing
        self.config.enable_dynamodb_logging = False
        
        self.agent = MonitoredBedrockAgent(config=self.config)
    
    @patch('cloud_engineer.cost_modelling.token_logger.BedrockTokenLogger')
    def test_invoke_model_with_logging(self, mock_token_logger_class):
        """Test monitored agent invoke_model_with_logging."""
        # Setup mock token logger
        mock_token_logger = Mock()
        mock_token_logger_class.return_value = mock_token_logger
        
        mock_response = {
            'token_logging': {
                'input_tokens': 100,
                'output_tokens': 50,
                'estimated_cost': 0.01,
                'agent_id': 'test-agent'
            },
            'bedrock_response': {'content': 'test response'}
        }
        mock_token_logger.invoke_with_logging.return_value = mock_response
        
        # Create new agent to use the mock
        agent = MonitoredBedrockAgent(config=self.config)
        
        response = agent.invoke_model_with_logging(
            model_id="test-model",
            body={"messages": [{"role": "user", "content": "Hello"}]},
            agent_id="test-agent"
        )
        
        self.assertIn('token_logging', response)
        self.assertEqual(response['token_logging']['agent_id'], 'test-agent')
    
    def test_incident_context_manager(self):
        """Test incident context manager."""
        with self.agent.incident_context("INC-123", {"priority": "high"}) as incident_id:
            self.assertEqual(incident_id, "INC-123")
            active_incidents = self.agent.get_active_incidents()
            self.assertIn("INC-123", active_incidents)
            self.assertEqual(active_incidents["INC-123"]["context"]["priority"], "high")
        
        # After context manager exits, incident should be removed
        active_incidents = self.agent.get_active_incidents()
        self.assertNotIn("INC-123", active_incidents)


class TestCostAnalyzer(unittest.TestCase):
    """Test cases for CostAnalyzer."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = LoggingConfig()
        self.analyzer = CostAnalyzer(config=self.config)
        
        # Mock data for testing
        self.mock_records = [
            {
                'timestamp': '2024-01-01T10:00:00Z',
                'agent_id': 'agent-1',
                'model_id': 'model-1',
                'incident_id': 'INC-123',
                'input_tokens': 100,
                'output_tokens': 50,
                'total_tokens': 150,
                'estimated_cost': 0.01
            },
            {
                'timestamp': '2024-01-01T11:00:00Z',
                'agent_id': 'agent-2',
                'model_id': 'model-1',
                'incident_id': 'INC-124',
                'input_tokens': 200,
                'output_tokens': 100,
                'total_tokens': 300,
                'estimated_cost': 0.02
            }
        ]
    
    @patch('cloud_engineer.cost_modelling.dynamo_logger.TokenDynamoLogger')
    def test_generate_daily_cost_report(self, mock_dynamo_logger_class):
        """Test daily cost report generation."""
        # Setup mock dynamo logger
        mock_dynamo_logger = Mock()
        mock_dynamo_logger_class.return_value = mock_dynamo_logger
        mock_dynamo_logger.query_by_date_range.return_value = self.mock_records
        
        # Create analyzer with mock
        analyzer = CostAnalyzer(config=self.config)
        analyzer.dynamo_logger = mock_dynamo_logger
        
        report = analyzer.generate_daily_cost_report("2024-01-01")
        
        self.assertIsInstance(report, CostSummary)
        self.assertEqual(report.total_cost, 0.03)
        self.assertEqual(report.total_tokens, 450)
        self.assertEqual(report.total_requests, 2)
        self.assertIn('by_agent', report.breakdown)
        self.assertIn('by_model', report.breakdown)
    
    def test_breakdown_by_field(self):
        """Test breakdown by field functionality."""
        breakdown = self.analyzer._breakdown_by_field(self.mock_records, 'agent_id')
        
        self.assertIn('agent-1', breakdown)
        self.assertIn('agent-2', breakdown)
        self.assertEqual(breakdown['agent-1']['cost'], 0.01)
        self.assertEqual(breakdown['agent-1']['tokens'], 150)
        self.assertEqual(breakdown['agent-1']['requests'], 1)
    
    def test_export_to_csv(self):
        """Test CSV export functionality."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            output_file = temp_file.name
        
        try:
            result_file = self.analyzer._export_to_csv(self.mock_records, output_file)
            self.assertEqual(result_file, output_file)
            
            # Verify file exists and has content
            self.assertTrue(os.path.exists(output_file))
            with open(output_file, 'r') as f:
                content = f.read()
                self.assertIn('timestamp', content)
                self.assertIn('agent_id', content)
                self.assertIn('agent-1', content)
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)
    
    def test_export_to_json(self):
        """Test JSON export functionality."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            output_file = temp_file.name
        
        try:
            result_file = self.analyzer._export_to_json(self.mock_records, output_file)
            self.assertEqual(result_file, output_file)
            
            # Verify file exists and has valid JSON
            self.assertTrue(os.path.exists(output_file))
            with open(output_file, 'r') as f:
                data = json.load(f)
                self.assertIn('export_timestamp', data)
                self.assertIn('record_count', data)
                self.assertEqual(data['record_count'], 2)
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)


class TestLoggingConfig(unittest.TestCase):
    """Test cases for LoggingConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = LoggingConfig()
        
        self.assertTrue(config.enable_token_logging)
        self.assertTrue(config.enable_cloudwatch_metrics)
        self.assertTrue(config.enable_dynamodb_logging)
        self.assertEqual(config.aws_region, 'ap-southeast-2')
        self.assertEqual(config.cloudwatch_namespace, 'BedrockUsage')
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Test invalid retention days
        with self.assertRaises(ValueError):
            LoggingConfig(retention_days=-1)
        
        # Test invalid batch size
        with self.assertRaises(ValueError):
            LoggingConfig(batch_size=0)
        
        # Test invalid batch size (too large)
        with self.assertRaises(ValueError):
            LoggingConfig(batch_size=30)
    
    def test_model_pricing(self):
        """Test model pricing functionality."""
        config = LoggingConfig()
        
        # Test getting pricing for known model
        pricing = config.get_model_pricing("anthropic.claude-3-5-sonnet-20241022-v2:0")
        self.assertIsNotNone(pricing)
        self.assertEqual(pricing.input_cost_per_million, 3.0)
        self.assertEqual(pricing.output_cost_per_million, 15.0)
        
        # Test adding custom pricing
        config.add_custom_model_pricing(
            key="custom-model",
            model_id="custom.model.id",
            input_cost_per_million=1.0,
            output_cost_per_million=5.0,
            description="Custom test model"
        )
        
        custom_pricing = config.get_model_pricing("custom.model.id")
        self.assertIsNotNone(custom_pricing)
        self.assertEqual(custom_pricing.input_cost_per_million, 1.0)
    
    def test_config_serialization(self):
        """Test configuration serialization and deserialization."""
        config = LoggingConfig()
        config.add_custom_model_pricing(
            key="test-model",
            model_id="test.model",
            input_cost_per_million=2.0,
            output_cost_per_million=10.0
        )
        
        # Convert to dict
        config_dict = config.to_dict()
        self.assertIn('enable_token_logging', config_dict)
        self.assertIn('custom_pricing', config_dict)
        
        # Convert back to config
        new_config = LoggingConfig.from_dict(config_dict)
        self.assertEqual(new_config.enable_token_logging, config.enable_token_logging)
        self.assertEqual(new_config.aws_region, config.aws_region)
        
        # Test custom pricing is preserved
        test_pricing = new_config.get_model_pricing("test.model")
        self.assertIsNotNone(test_pricing)
        self.assertEqual(test_pricing.input_cost_per_million, 2.0)


class TestTokenLoggingDecorator(unittest.TestCase):
    """Test cases for token logging decorator."""
    
    @patch('cloud_engineer.cost_modelling.monitored_agent.MonitoredBedrockAgent')
    def test_decorator_functionality(self, mock_monitored_agent_class):
        """Test token logging decorator."""
        # Setup mock monitored agent
        mock_agent = Mock()
        mock_monitored_agent_class.return_value = mock_agent
        mock_agent.invoke_model_with_logging.return_value = {'response': 'test'}
        
        # Create decorated function
        @token_logging_decorator(agent_id="test-agent", incident_id="INC-123")
        def test_bedrock_call(model_id, body):
            return {'original': 'response'}
        
        # Call decorated function
        result = test_bedrock_call(model_id="test-model", body="test body")
        
        # Verify monitored agent was used
        mock_agent.invoke_model_with_logging.assert_called_once_with(
            model_id="test-model",
            body="test body",
            agent_id="test-agent",
            incident_id="INC-123",
            context=None
        )
        
        self.assertEqual(result, {'response': 'test'})


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete logging system."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.config = LoggingConfig()
        # Disable actual AWS calls for integration tests
        self.config.enable_cloudwatch_metrics = False
        self.config.enable_dynamodb_logging = False
    
    @patch('boto3.client')
    def test_end_to_end_logging_flow(self, mock_boto_client):
        """Test complete end-to-end logging flow."""
        # Setup mock Bedrock client
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        mock_response = {
            'body': Mock(),
            'contentType': 'application/json',
            'ResponseMetadata': {
                'HTTPHeaders': {
                    'x-amzn-bedrock-input-token-count': '1000',
                    'x-amzn-bedrock-output-token-count': '500'
                }
            }
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Integration test response'}]
        }).encode('utf-8')
        mock_client.invoke_model.return_value = mock_response
        
        # Create monitored agent
        agent = MonitoredBedrockAgent(config=self.config)
        
        # Test the complete flow
        with agent.incident_context("INC-INTEGRATION-TEST") as incident_id:
            response = agent.invoke_model_with_logging(
                model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
                body=json.dumps({
                    "messages": [{"role": "user", "content": "Integration test"}],
                    "max_tokens": 500
                }),
                agent_id="integration-test-agent",
                incident_id=incident_id
            )
        
        # Verify response structure
        self.assertIn('token_logging', response)
        self.assertIn('bedrock_response', response)
        
        # Verify logging data
        log_data = response['token_logging']
        self.assertEqual(log_data['input_tokens'], 1000)
        self.assertEqual(log_data['output_tokens'], 500)
        self.assertEqual(log_data['agent_id'], 'integration-test-agent')
        self.assertEqual(log_data['incident_id'], 'INC-INTEGRATION-TEST')
        
        # Verify cost calculation
        expected_cost = (1000/1000000 * 3.0) + (500/1000000 * 15.0)  # Sonnet 4 pricing
        self.assertAlmostEqual(log_data['estimated_cost'], expected_cost, places=6)


class TestPerformance(unittest.TestCase):
    """Performance tests for high-volume scenarios."""
    
    def setUp(self):
        """Set up performance test fixtures."""
        self.config = LoggingConfig()
        self.config.enable_cloudwatch_metrics = False
        self.config.enable_dynamodb_logging = False
    
    @patch('boto3.client')
    def test_high_volume_logging(self, mock_boto_client):
        """Test logging performance with high volume of requests."""
        import time
        
        # Setup mock client
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        mock_response = {
            'body': Mock(),
            'contentType': 'application/json',
            'ResponseMetadata': {
                'HTTPHeaders': {
                    'x-amzn-bedrock-input-token-count': '100',
                    'x-amzn-bedrock-output-token-count': '50'
                }
            }
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Performance test'}]
        }).encode('utf-8')
        mock_client.invoke_model.return_value = mock_response
        
        # Create monitored agent
        agent = MonitoredBedrockAgent(config=self.config)
        
        # Test multiple rapid requests
        start_time = time.time()
        num_requests = 10
        
        for i in range(num_requests):
            response = agent.invoke_model_with_logging(
                model_id="test-model",
                body=json.dumps({"messages": [{"role": "user", "content": f"Request {i}"}]}),
                agent_id="performance-test-agent",
                incident_id=f"INC-PERF-{i}"
            )
            self.assertIn('token_logging', response)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify performance (should complete within reasonable time)
        self.assertLess(total_time, 5.0, "High volume logging took too long")
        
        # Verify all requests were processed
        self.assertEqual(mock_client.invoke_model.call_count, num_requests)


def run_all_tests():
    """Run all test suites."""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestBedrockTokenLogger,
        TestCloudWatchMetricsLogger,
        TestDynamoLogger,
        TestMonitoredAgent,
        TestCostAnalyzer,
        TestLoggingConfig,
        TestTokenLoggingDecorator,
        TestIntegration,
        TestPerformance
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    """Run tests when executed directly."""
    print("Running Bedrock Token Logging Tests...")
    print("=" * 50)
    
    success = run_all_tests()
    
    if success:
        print("\n" + "=" * 50)
        print("All tests passed successfully!")
    else:
        print("\n" + "=" * 50)
        print("Some tests failed. Please review the output above.")
        exit(1)
