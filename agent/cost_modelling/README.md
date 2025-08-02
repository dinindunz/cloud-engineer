# Bedrock Token Logging Implementation

A comprehensive token usage logging and cost analysis system for AWS Bedrock API calls in the Cloud Engineer agent system.

## Overview

This system provides real-time token usage tracking, cost estimation, and comprehensive reporting for all Bedrock API interactions. It includes multiple logging backends, cost analysis tools, and monitoring capabilities to help optimize AI usage costs.

## Features

- **Real-time Token Logging**: Automatic extraction and logging of token usage from Bedrock API responses
- **Cost Estimation**: Accurate cost calculations based on current model pricing
- **Multiple Storage Backends**: CloudWatch Metrics, DynamoDB, and structured logging
- **Comprehensive Reporting**: Daily, agent-level, and incident-specific cost reports
- **Trend Analysis**: Historical cost trends and forecasting
- **Cost Alerting**: Configurable thresholds with SNS notifications
- **Performance Optimized**: Async logging with circuit breaker patterns
- **Highly Configurable**: Environment-based configuration with validation

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌───────────────────┐
│   Cloud Agent   │───▶│ MonitoredAgent   │───▶│ BedrockTokenLogger│
└─────────────────┘    └──────────────────┘    └───────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │ Async Logging    │    │ Token Extraction│
                       │ Queue            │    │ & Cost Calc     │
                       └──────────────────┘    └─────────────────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
            ┌──────────────┐ ┌──────────┐ ┌──────────────┐
            │ CloudWatch   │ │ DynamoDB │ │ Structured   │
            │ Metrics      │ │ Storage  │ │ Logs         │
            └──────────────┘ └──────────┘ └──────────────┘
                    │           │           │
                    └───────────┼───────────┘
                                ▼
                       ┌──────────────────┐
                       │ Cost Analyzer    │
                       │ & Reporting      │
                       └──────────────────┘
```

## Quick Start

### 1. Installation

```bash
# Install required dependencies
pip install boto3 asyncio

# Set up environment variables
export ENABLE_TOKEN_LOGGING=true
export AWS_REGION=ap-southeast-2
export DYNAMODB_TABLE_NAME=bedrock-token-usage
export CLOUDWATCH_NAMESPACE=BedrockUsage
```

### 2. Basic Usage

```python
from cost_modelling.monitored_agent import MonitoredBedrockAgent
from cost_modelling.logging_config import LoggingConfig

# Initialize with default configuration
config = LoggingConfig()
agent = MonitoredBedrockAgent(config=config)

# Use with incident context
with agent.incident_context("INC-12345") as incident_id:
    response = agent.invoke_model_with_logging(
        model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
        body=json.dumps({
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1000
        }),
        agent_id="cloud-engineer",
        incident_id=incident_id
    )
    
    # Access logging data
    token_data = response['token_logging']
    print(f"Cost: ${token_data['estimated_cost']:.6f}")
    print(f"Tokens: {token_data['total_tokens']}")
```

### 3. Integration with Existing Agent

```python
from cost_modelling.monitored_agent import token_logging_decorator

class CloudEngineer:
    @token_logging_decorator(agent_id="cloud-engineer")
    def invoke_model(self, model_id, body, incident_id=None):
        # Your existing Bedrock API call
        return bedrock_client.invoke_model(
            modelId=model_id,
            body=body
        )
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_TOKEN_LOGGING` | `true` | Enable/disable token logging |
| `ENABLE_CLOUDWATCH_METRICS` | `true` | Enable CloudWatch metrics |
| `ENABLE_DYNAMODB_LOGGING` | `true` | Enable DynamoDB storage |
| `AWS_REGION` | `ap-southeast-2` | AWS region |
| `DYNAMODB_TABLE_NAME` | `bedrock-token-usage` | DynamoDB table name |
| `CLOUDWATCH_NAMESPACE` | `BedrockUsage` | CloudWatch namespace |
| `RETENTION_DAYS` | `90` | Data retention period |
| `DAILY_COST_THRESHOLD` | `100.0` | Daily cost alert threshold |
| `HOURLY_COST_THRESHOLD` | `10.0` | Hourly cost alert threshold |

### Configuration File

```python
from cost_modelling.logging_config import LoggingConfig

# Load from environment
config = LoggingConfig()

# Or customize
config = LoggingConfig(
    enable_token_logging=True,
    enable_cloudwatch_metrics=True,
    enable_dynamodb_logging=True,
    aws_region="us-east-1",
    daily_cost_threshold=50.0,
    retention_days=30
)

# Add custom model pricing
config.add_custom_model_pricing(
    key="custom-model",
    model_id="custom.model.id",
    input_cost_per_million=2.0,
    output_cost_per_million=10.0
)
```

## Cost Analysis and Reporting

### Daily Cost Reports

```python
from cost_modelling.cost_analyzer import CostAnalyzer

analyzer = CostAnalyzer(config=config)

# Generate daily report
report = analyzer.generate_daily_cost_report("2024-01-15")
print(f"Total cost: ${report.total_cost:.6f}")
print(f"Total tokens: {report.total_tokens}")
print(f"Requests: {report.total_requests}")

# Breakdown by agent
for agent_id, data in report.breakdown['by_agent'].items():
    print(f"{agent_id}: ${data['cost']:.6f}")
```

### Agent Cost Breakdown

```python
# Get agent costs for date range
breakdown = analyzer.generate_agent_cost_breakdown(
    start_date="2024-01-01",
    end_date="2024-01-31"
)

for agent_id, data in breakdown['agents'].items():
    print(f"{agent_id}:")
    print(f"  Total cost: ${data['total_cost']:.6f}")
    print(f"  Requests: {data['total_requests']}")
    print(f"  Models used: {data['models_used']}")
```

### Incident Analysis

```python
# Analyze specific incident
incident_analysis = analyzer.generate_incident_cost_analysis("INC-12345")
print(f"Incident cost: ${incident_analysis['summary']['total_cost']:.6f}")
print(f"Duration: {incident_analysis['summary']['duration_minutes']:.1f} minutes")
```

### Cost Trends and Forecasting

```python
# Get cost trends
trends = analyzer.get_cost_trends(
    start_date="2024-01-01",
    end_date="2024-01-31",
    granularity="daily"
)

# Generate forecasts
forecasts = analyzer.forecast_costs(
    historical_days=30,
    forecast_days=7
)

for forecast in forecasts:
    print(f"{forecast.period}: ${forecast.predicted_cost:.6f} ({forecast.trend_direction})")
```

### Data Export

```python
# Export to CSV
csv_file = analyzer.export_usage_data(
    start_date="2024-01-01",
    end_date="2024-01-31",
    format="csv",
    output_file="usage_report.csv"
)

# Export to JSON
json_file = analyzer.export_usage_data(
    start_date="2024-01-01",
    end_date="2024-01-31",
    format="json"
)
```

## Monitoring and Alerting

### CloudWatch Metrics

The system publishes the following metrics to CloudWatch:

- `InputTokens` - Number of input tokens used
- `OutputTokens` - Number of output tokens generated
- `EstimatedCost` - Estimated cost in USD
- `TotalTokens` - Total tokens (input + output)
- `APIErrors` - Number of API errors

Metrics are dimensioned by:
- `AgentId` - The agent making the request
- `ModelId` - The Bedrock model used
- `IncidentId` - The incident context (optional)

### Cost Thresholds

```python
# Check current cost thresholds
threshold_check = analyzer.check_cost_thresholds()

if threshold_check['alert_required']:
    print("Cost threshold exceeded!")
    print(f"Daily cost: ${threshold_check['daily_cost']:.6f}")
    print(f"Threshold: ${threshold_check['daily_threshold']:.6f}")
```

### CloudWatch Alarms

Set up CloudWatch alarms for cost monitoring:

```python
# Example alarm configuration (add to CDK stack)
cloudwatch.Alarm(
    self, "HighDailyCost",
    metric=cloudwatch.Metric(
        namespace="BedrockUsage",
        metric_name="EstimatedCost",
        statistic="Sum",
        period=Duration.hours(24)
    ),
    threshold=100.0,
    evaluation_periods=1,
    alarm_description="Daily Bedrock cost exceeded $100"
)
```

## Performance Considerations

### Async Logging

The system uses async logging to avoid blocking Bedrock API calls:

```python
# Logging happens asynchronously
response = agent.invoke_model_with_logging(...)
# API call completes immediately, logging happens in background
```

### Circuit Breaker

Built-in circuit breaker prevents logging failures from affecting agent operations:

```python
config = LoggingConfig(
    enable_circuit_breaker=True,
    circuit_breaker_failure_threshold=5,
    circuit_breaker_recovery_timeout=60
)
```

### Batch Processing

CloudWatch metrics and DynamoDB writes are batched for efficiency:

```python
config = LoggingConfig(
    batch_size=25,  # Max batch size
    flush_interval_seconds=60  # Max wait time
)
```

## Error Handling

The system includes comprehensive error handling:

1. **Graceful Degradation**: If logging fails, the original Bedrock response is still returned
2. **Retry Logic**: Automatic retries for transient failures
3. **Circuit Breaker**: Prevents cascading failures
4. **Error Metrics**: Failed logging attempts are tracked in CloudWatch

## Testing

Run the comprehensive test suite:

```bash
# Run all tests (DO NOT RUN IN PRODUCTION)
python -m cost_modelling.test_token_logging

# Run specific test class
python -m unittest cost_modelling.test_token_logging.TestBedrockTokenLogger

# Run with coverage
coverage run -m cost_modelling.test_token_logging
coverage report
```

## Troubleshooting

### Common Issues

1. **Missing Token Data**
   - Check if model supports token headers
   - Verify response body parsing
   - Enable debug logging

2. **High Costs**
   - Review model usage patterns
   - Check for inefficient prompts
   - Analyze token usage reports

3. **Logging Failures**
   - Verify AWS permissions
   - Check DynamoDB table exists
   - Review CloudWatch logs

### Debug Mode

Enable debug logging for troubleshooting:

```python
config = LoggingConfig(log_level=LogLevel.DEBUG)
config.setup_logging()
```

### AWS Permissions

Required IAM permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "dynamodb:PutItem",
                "dynamodb:Query",
                "dynamodb:Scan",
                "cloudwatch:PutMetricData",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "*"
        }
    ]
}
```

## Contributing

1. Follow the existing code style and patterns
2. Add comprehensive tests for new features
3. Update documentation for any API changes
4. Ensure all tests pass before submitting

## License

This project is licensed under the MIT License - see the LICENSE file for details.
