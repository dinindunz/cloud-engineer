# Bedrock Token Logging Monitoring Guide

This document provides comprehensive monitoring, alerting, and troubleshooting guidance for the Bedrock token logging system.

## Table of Contents

1. [Monitoring Overview](#monitoring-overview)
2. [CloudWatch Metrics](#cloudwatch-metrics)
3. [CloudWatch Dashboards](#cloudwatch-dashboards)
4. [Alerting and Alarms](#alerting-and-alarms)
5. [Log Analysis](#log-analysis)
6. [Performance Monitoring](#performance-monitoring)
7. [Cost Monitoring](#cost-monitoring)
8. [Troubleshooting](#troubleshooting)
9. [Runbooks](#runbooks)

## Monitoring Overview

The Bedrock token logging system provides comprehensive monitoring across multiple dimensions:

- **Cost Monitoring**: Track spending across agents, models, and incidents
- **Performance Monitoring**: Monitor API latency and logging performance
- **Error Monitoring**: Track API failures and logging errors
- **Usage Monitoring**: Analyze token consumption patterns
- **System Health**: Monitor the logging infrastructure itself

## CloudWatch Metrics

### Core Metrics

The system publishes the following metrics to the `BedrockUsage` namespace:

#### Token Usage Metrics

| Metric Name | Unit | Description | Dimensions |
|-------------|------|-------------|------------|
| `InputTokens` | Count | Number of input tokens consumed | AgentId, ModelId, IncidentId |
| `OutputTokens` | Count | Number of output tokens generated | AgentId, ModelId, IncidentId |
| `TotalTokens` | Count | Total tokens (input + output) | AgentId, ModelId, IncidentId |
| `EstimatedCost` | None (USD) | Estimated cost in USD | AgentId, ModelId, IncidentId |

#### Performance Metrics

| Metric Name | Unit | Description | Dimensions |
|-------------|------|-------------|------------|
| `APILatency` | Milliseconds | Bedrock API response time | AgentId, ModelId |
| `LoggingLatency` | Milliseconds | Time to complete logging | AgentId, LoggingBackend |
| `RequestsPerSecond` | Count/Second | API request rate | AgentId, ModelId |

#### Error Metrics

| Metric Name | Unit | Description | Dimensions |
|-------------|------|-------------|------------|
| `APIErrors` | Count | Bedrock API errors | AgentId, ModelId, ErrorCode |
| `LoggingErrors` | Count | Logging system errors | AgentId, LoggingBackend, ErrorType |
| `CircuitBreakerTrips` | Count | Circuit breaker activations | AgentId, Component |

#### System Health Metrics

| Metric Name | Unit | Description | Dimensions |
|-------------|------|-------------|------------|
| `LoggingQueueDepth` | Count | Pending logging operations | AgentId |
| `BatchProcessingTime` | Milliseconds | Time to process metric batches | LoggingBackend |
| `DynamoDBThrottles` | Count | DynamoDB throttling events | TableName |

### Metric Dimensions

#### AgentId
- `cloud-engineer` - Main cloud engineering agent
- `knowledge-base` - Knowledge base agent
- `error-analysis` - Error analysis agent
- `jira` - JIRA integration agent
- `operations` - Operations agent

#### ModelId
- `anthropic.claude-3-5-sonnet-20241022-v2:0` - Claude 3.5 Sonnet
- `anthropic.claude-3-haiku-20240307-v1:0` - Claude 3 Haiku
- Custom model IDs as configured

#### IncidentId
- Format: `INC-YYYYMMDD-NNNN`
- Used to track costs per incident

## CloudWatch Dashboards

### Main Dashboard: Bedrock Usage Overview

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["BedrockUsage", "EstimatedCost", {"stat": "Sum"}],
          [".", "TotalTokens", {"stat": "Sum"}]
        ],
        "period": 3600,
        "stat": "Sum",
        "region": "ap-southeast-2",
        "title": "Hourly Cost and Token Usage"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["BedrockUsage", "EstimatedCost", "AgentId", "cloud-engineer"],
          ["...", "knowledge-base"],
          ["...", "error-analysis"],
          ["...", "jira"],
          ["...", "operations"]
        ],
        "period": 3600,
        "stat": "Sum",
        "region": "ap-southeast-2",
        "title": "Cost by Agent"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["BedrockUsage", "APIErrors", {"stat": "Sum"}],
          [".", "LoggingErrors", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "ap-southeast-2",
        "title": "Error Rates"
      }
    }
  ]
}
```

### Performance Dashboard

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["BedrockUsage", "APILatency", {"stat": "Average"}],
          [".", "LoggingLatency", {"stat": "Average"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "ap-southeast-2",
        "title": "Latency Metrics"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["BedrockUsage", "RequestsPerSecond"]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "ap-southeast-2",
        "title": "Request Rate"
      }
    }
  ]
}
```

## Alerting and Alarms

### Cost Alarms

#### Daily Cost Threshold
```python
# CDK Configuration
daily_cost_alarm = cloudwatch.Alarm(
    self, "DailyCostAlarm",
    metric=cloudwatch.Metric(
        namespace="BedrockUsage",
        metric_name="EstimatedCost",
        statistic="Sum",
        period=Duration.hours(24)
    ),
    threshold=100.0,
    evaluation_periods=1,
    alarm_description="Daily Bedrock cost exceeded $100",
    alarm_name="BedrockUsage-DailyCostHigh",
    treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
)

# Add SNS notification
daily_cost_alarm.add_alarm_action(
    cloudwatch_actions.SnsAction(cost_alert_topic)
)
```

#### Hourly Cost Spike
```python
hourly_cost_alarm = cloudwatch.Alarm(
    self, "HourlyCostAlarm",
    metric=cloudwatch.Metric(
        namespace="BedrockUsage",
        metric_name="EstimatedCost",
        statistic="Sum",
        period=Duration.hours(1)
    ),
    threshold=10.0,
    evaluation_periods=1,
    alarm_description="Hourly Bedrock cost exceeded $10",
    alarm_name="BedrockUsage-HourlyCostSpike"
)
```

### Error Rate Alarms

#### API Error Rate
```python
api_error_alarm = cloudwatch.Alarm(
    self, "APIErrorAlarm",
    metric=cloudwatch.Metric(
        namespace="BedrockUsage",
        metric_name="APIErrors",
        statistic="Sum",
        period=Duration.minutes(5)
    ),
    threshold=5,
    evaluation_periods=2,
    alarm_description="High API error rate detected",
    alarm_name="BedrockUsage-APIErrorsHigh"
)
```

#### Logging System Errors
```python
logging_error_alarm = cloudwatch.Alarm(
    self, "LoggingErrorAlarm",
    metric=cloudwatch.Metric(
        namespace="BedrockUsage",
        metric_name="LoggingErrors",
        statistic="Sum",
        period=Duration.minutes(5)
    ),
    threshold=10,
    evaluation_periods=2,
    alarm_description="High logging error rate detected",
    alarm_name="BedrockUsage-LoggingErrorsHigh"
)
```

### Performance Alarms

#### High API Latency
```python
latency_alarm = cloudwatch.Alarm(
    self, "HighLatencyAlarm",
    metric=cloudwatch.Metric(
        namespace="BedrockUsage",
        metric_name="APILatency",
        statistic="Average",
        period=Duration.minutes(5)
    ),
    threshold=5000,  # 5 seconds
    evaluation_periods=3,
    alarm_description="High API latency detected",
    alarm_name="BedrockUsage-HighLatency"
)
```

### System Health Alarms

#### Circuit Breaker Trips
```python
circuit_breaker_alarm = cloudwatch.Alarm(
    self, "CircuitBreakerAlarm",
    metric=cloudwatch.Metric(
        namespace="BedrockUsage",
        metric_name="CircuitBreakerTrips",
        statistic="Sum",
        period=Duration.minutes(5)
    ),
    threshold=1,
    evaluation_periods=1,
    alarm_description="Circuit breaker activated",
    alarm_name="BedrockUsage-CircuitBreakerTripped"
)
```

## Log Analysis

### CloudWatch Logs Groups

The system writes to the following log groups:

- `/aws/lambda/cloud-engineer-token-logging` - Main logging events
- `/aws/lambda/cloud-engineer-cost-analyzer` - Cost analysis logs
- `/aws/lambda/cloud-engineer-metrics-publisher` - Metrics publishing logs

### Log Queries

#### Find High-Cost Requests
```sql
fields @timestamp, agent_id, model_id, estimated_cost, total_tokens
| filter estimated_cost > 0.01
| sort @timestamp desc
| limit 100
```

#### Analyze Error Patterns
```sql
fields @timestamp, level, message, agent_id, error_code
| filter level = "ERROR"
| stats count() by error_code, agent_id
| sort count desc
```

#### Token Usage Analysis
```sql
fields @timestamp, agent_id, model_id, input_tokens, output_tokens, total_tokens
| filter @timestamp > @timestamp - 1h
| stats avg(input_tokens), avg(output_tokens), sum(total_tokens) by agent_id, model_id
```

#### Performance Analysis
```sql
fields @timestamp, agent_id, api_latency_ms, logging_latency_ms
| filter api_latency_ms > 1000
| sort api_latency_ms desc
| limit 50
```

## Performance Monitoring

### Key Performance Indicators (KPIs)

1. **API Response Time**: < 2 seconds (95th percentile)
2. **Logging Latency**: < 100ms (average)
3. **Error Rate**: < 1% of total requests
4. **Cost Efficiency**: Track cost per successful incident resolution

### Performance Queries

#### API Latency Distribution
```python
from cost_modelling.cost_analyzer import CostAnalyzer

analyzer = CostAnalyzer()

# Get performance metrics for the last hour
performance_data = analyzer.get_performance_metrics(
    start_time=datetime.utcnow() - timedelta(hours=1),
    end_time=datetime.utcnow()
)

print(f"Average API latency: {performance_data['avg_api_latency']:.2f}ms")
print(f"95th percentile: {performance_data['p95_api_latency']:.2f}ms")
```

#### Throughput Analysis
```python
# Analyze request throughput
throughput_data = analyzer.get_throughput_metrics(
    granularity="5min",
    lookback_hours=24
)

for data_point in throughput_data:
    print(f"{data_point['timestamp']}: {data_point['requests_per_second']:.2f} req/s")
```

## Cost Monitoring

### Cost Tracking Strategies

1. **Daily Cost Reports**: Automated daily cost summaries
2. **Agent-Level Budgets**: Track spending per agent
3. **Incident Cost Analysis**: Cost per incident resolution
4. **Model Efficiency**: Cost per token by model type

### Cost Optimization Queries

#### Most Expensive Agents
```python
# Get top spending agents for the last 30 days
cost_breakdown = analyzer.generate_agent_cost_breakdown(
    start_date=(datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d'),
    end_date=datetime.utcnow().strftime('%Y-%m-%d')
)

sorted_agents = sorted(
    cost_breakdown['agents'].items(),
    key=lambda x: x[1]['total_cost'],
    reverse=True
)

for agent_id, data in sorted_agents[:5]:
    print(f"{agent_id}: ${data['total_cost']:.6f}")
```

#### Cost Trends
```python
# Analyze cost trends over time
trends = analyzer.get_cost_trends(
    start_date="2024-01-01",
    end_date="2024-01-31",
    granularity="daily"
)

# Calculate week-over-week growth
weekly_costs = {}
for trend in trends:
    week = datetime.strptime(trend.date, '%Y-%m-%d').isocalendar()[1]
    weekly_costs[week] = weekly_costs.get(week, 0) + trend.cost

for week, cost in sorted(weekly_costs.items()):
    print(f"Week {week}: ${cost:.6f}")
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Missing Token Data

**Symptoms:**
- Zero token counts in logs
- Missing cost calculations
- Empty CloudWatch metrics

**Diagnosis:**
```python
# Check token extraction
from cost_modelling.token_logger import BedrockTokenLogger

logger = BedrockTokenLogger()
# Enable debug logging
logger.logger.setLevel(logging.DEBUG)

# Test with a sample response
test_response = {
    'ResponseMetadata': {
        'HTTPHeaders': {
            'x-amzn-bedrock-input-token-count': '100',
            'x-amzn-bedrock-output-token-count': '50'
        }
    }
}

tokens = logger._extract_token_usage(test_response)
print(f"Extracted tokens: {tokens}")
```

**Solutions:**
- Verify model supports token headers
- Check response body parsing logic
- Enable debug logging for detailed analysis

#### 2. High Logging Latency

**Symptoms:**
- Slow API responses
- High `LoggingLatency` metrics
- Timeout errors

**Diagnosis:**
```bash
# Check CloudWatch logs for latency patterns
aws logs filter-log-events \
  --log-group-name "/aws/lambda/cloud-engineer-token-logging" \
  --filter-pattern "{ $.logging_latency_ms > 1000 }" \
  --start-time $(date -d '1 hour ago' +%s)000
```

**Solutions:**
- Enable async logging
- Increase batch sizes
- Check DynamoDB and CloudWatch API limits

#### 3. DynamoDB Throttling

**Symptoms:**
- `DynamoDBThrottles` metric increasing
- Logging errors in CloudWatch logs
- Data loss in cost reports

**Diagnosis:**
```python
# Check DynamoDB metrics
import boto3

cloudwatch = boto3.client('cloudwatch')
response = cloudwatch.get_metric_statistics(
    Namespace='AWS/DynamoDB',
    MetricName='ThrottledRequests',
    Dimensions=[
        {'Name': 'TableName', 'Value': 'bedrock-token-usage'}
    ],
    StartTime=datetime.utcnow() - timedelta(hours=1),
    EndTime=datetime.utcnow(),
    Period=300,
    Statistics=['Sum']
)

for datapoint in response['Datapoints']:
    print(f"{datapoint['Timestamp']}: {datapoint['Sum']} throttles")
```

**Solutions:**
- Increase DynamoDB provisioned capacity
- Enable auto-scaling
- Implement exponential backoff
- Use batch writing

#### 4. Cost Calculation Errors

**Symptoms:**
- Incorrect cost estimates
- Missing pricing for models
- Zero costs for valid requests

**Diagnosis:**
```python
# Test cost calculation
from cost_modelling.logging_config import LoggingConfig

config = LoggingConfig()
pricing = config.get_model_pricing("anthropic.claude-3-5-sonnet-20241022-v2:0")

if pricing:
    print(f"Input cost: ${pricing.input_cost_per_million}/M tokens")
    print(f"Output cost: ${pricing.output_cost_per_million}/M tokens")
else:
    print("No pricing found for model")

# Test calculation
cost = (1000 / 1000000) * pricing.input_cost_per_million + \
       (500 / 1000000) * pricing.output_cost_per_million
print(f"Expected cost for 1000 input + 500 output tokens: ${cost:.6f}")
```

**Solutions:**
- Update model pricing configuration
- Add custom pricing for new models
- Verify token extraction accuracy

## Runbooks

### Runbook 1: High Daily Cost Alert

**Trigger:** Daily cost exceeds $100

**Steps:**
1. **Immediate Assessment**
   ```bash
   # Get today's cost breakdown
   python -c "
   from cost_modelling.cost_analyzer import CostAnalyzer
   from datetime import datetime
   
   analyzer = CostAnalyzer()
   report = analyzer.generate_daily_cost_report(datetime.utcnow().strftime('%Y-%m-%d'))
   print(f'Total cost: ${report.total_cost:.6f}')
   print('Top agents:')
   for agent, data in sorted(report.breakdown['by_agent'].items(), key=lambda x: x[1]['cost'], reverse=True)[:5]:
       print(f'  {agent}: ${data[\"cost\"]:.6f}')
   "
   ```

2. **Identify Root Cause**
   - Check for unusual incident volume
   - Look for inefficient prompts or loops
   - Verify no runaway processes

3. **Immediate Actions**
   - If runaway process detected, stop the agent
   - Review recent incidents for anomalies
   - Check for model changes or configuration updates

4. **Follow-up**
   - Implement cost controls if needed
   - Update alerting thresholds
   - Document findings

### Runbook 2: API Error Rate Spike

**Trigger:** API error rate > 5 errors in 5 minutes

**Steps:**
1. **Check Error Types**
   ```bash
   # Query recent errors
   aws logs filter-log-events \
     --log-group-name "/aws/lambda/cloud-engineer-token-logging" \
     --filter-pattern "ERROR" \
     --start-time $(date -d '10 minutes ago' +%s)000 \
     --query 'events[*].[timestamp,message]' \
     --output table
   ```

2. **Common Error Responses**
   - **ThrottlingException**: Reduce request rate, implement backoff
   - **ValidationException**: Check request format and parameters
   - **ServiceUnavailableException**: AWS service issue, monitor status page
   - **AccessDeniedException**: Check IAM permissions

3. **Mitigation Steps**
   - Enable circuit breaker if not already active
   - Implement exponential backoff
   - Switch to fallback model if available

### Runbook 3: Circuit Breaker Activation

**Trigger:** Circuit breaker trips

**Steps:**
1. **Assess Impact**
   - Check which component triggered the breaker
   - Verify logging is still functional
   - Confirm agent operations continue

2. **Root Cause Analysis**
   - Review error logs leading to trip
   - Check AWS service health
   - Verify network connectivity

3. **Recovery**
   - Wait for automatic recovery (default: 60 seconds)
   - If persistent, investigate underlying issue
   - Manual reset if necessary (use with caution)

### Runbook 4: Missing Cost Data

**Trigger:** No cost data for extended period

**Steps:**
1. **Check Data Pipeline**
   ```python
   # Verify each component
   from cost_modelling.logging_config import LoggingConfig
   from cost_modelling.dynamo_logger import TokenDynamoLogger
   from cost_modelling.cloudwatch_metrics import TokenMetricsLogger
   
   config = LoggingConfig()
   
   # Test DynamoDB connectivity
   dynamo_logger = TokenDynamoLogger(config.dynamodb_table_name)
   try:
       dynamo_logger.log_token_usage(
           timestamp=datetime.utcnow().isoformat() + "Z",
           agent_id="test",
           model_id="test",
           input_tokens=1,
           output_tokens=1,
           estimated_cost=0.000001
       )
       print("DynamoDB: OK")
   except Exception as e:
       print(f"DynamoDB: ERROR - {e}")
   
   # Test CloudWatch connectivity
   metrics_logger = TokenMetricsLogger()
   try:
       metrics_logger.log_token_usage(
           agent_id="test",
           model_id="test",
           input_tokens=1,
           output_tokens=1,
           estimated_cost=0.000001
       )
       print("CloudWatch: OK")
   except Exception as e:
       print(f"CloudWatch: ERROR - {e}")
   ```

2. **Verify Configuration**
   - Check environment variables
   - Verify IAM permissions
   - Confirm table/namespace existence

3. **Recovery Actions**
   - Restart logging services
   - Check for configuration drift
   - Verify AWS service availability

## Best Practices

### Monitoring Best Practices

1. **Set Appropriate Thresholds**
   - Start with conservative thresholds
   - Adjust based on historical data
   - Account for business cycles

2. **Use Multiple Alert Channels**
   - Email for non-urgent alerts
   - Slack/Teams for immediate attention
   - PagerDuty for critical issues

3. **Regular Review**
   - Weekly cost reviews
   - Monthly threshold adjustments
   - Quarterly system health assessments

### Cost Optimization Best Practices

1. **Regular Analysis**
   - Daily cost reports
   - Weekly trend analysis
   - Monthly optimization reviews

2. **Proactive Monitoring**
   - Set up forecasting alerts
   - Monitor usage patterns
   - Track efficiency metrics

3. **Continuous Improvement**
   - Optimize prompts for efficiency
   - Use appropriate models for tasks
   - Implement caching where possible

This monitoring guide provides comprehensive coverage of the Bedrock token logging system's observability features. Regular review and updates of these monitoring practices will ensure optimal system performance and cost efficiency.
