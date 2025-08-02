# Bedrock Cost Tracking with Application Inference Profiles

This implementation uses AWS Application Inference Profiles for native cost tracking instead of complex custom logging infrastructure.

## Overview

Application Inference Profiles provide a simpler, more native approach to tracking Bedrock costs by:

1. **Creating a tagged inference profile** that wraps the foundation model
2. **Using cost allocation tags** for automatic cost categorization
3. **Leveraging AWS Cost Explorer** for cost analysis and reporting
4. **Eliminating custom infrastructure** (no DynamoDB, CloudWatch metrics, etc.)

## Implementation

### 1. Infrastructure (CDK)

The CDK stack creates:
- **Application Inference Profile** with cost allocation tags
- **Simplified CloudWatch Dashboard** (for reference)
- **IAM permissions** for the inference profile

### 2. Application Code

The agent code:
- Uses the **inference profile ARN** instead of the model ID
- Provides **cost summary tools** that direct users to Cost Explorer
- **Eliminates complex token logging** and custom metrics

### 3. Cost Tracking

Costs are tracked automatically through:
- **AWS Cost Explorer** - Filter by Service: Amazon Bedrock
- **Cost allocation tags** - Group by Application, Environment, CostCenter
- **Native AWS billing** - No custom infrastructure to maintain

## Benefits

1. **Simplicity** - No custom logging infrastructure to maintain
2. **Native AWS integration** - Uses built-in cost tracking capabilities
3. **Reliability** - No risk of logging failures affecting agent performance
4. **Cost efficiency** - No additional infrastructure costs for monitoring
5. **Compliance** - Uses AWS native cost allocation and reporting

## Usage

### Viewing Costs

1. Go to AWS Cost Explorer
2. Filter by Service: Amazon Bedrock
3. Group by Cost Allocation Tags
4. Look for tags:
   - Application=CloudEngineer
   - Environment=Production
   - CostCenter=Engineering

### Agent Tools

The agent provides two cost-related tools:

- `get_cost_summary()` - Explains how to view costs in Cost Explorer
- `get_cost_explorer_link()` - Provides direct link to Cost Explorer

## Migration from Complex Logging

This approach replaces the previous complex implementation that included:
- ❌ Custom DynamoDB tables for token storage
- ❌ CloudWatch custom metrics and dashboards
- ❌ Complex token counting and cost calculation logic
- ❌ Async logging infrastructure
- ❌ Cost analysis and reporting functions

With a simple, native approach:
- ✅ Application Inference Profile with tags
- ✅ Native AWS cost tracking
- ✅ Cost Explorer for analysis
- ✅ No custom infrastructure to maintain

## Configuration

The inference profile is configured in the CDK stack with:

```typescript
const bedrockInferenceProfile = new cdk.CfnResource(this, 'BedrockInferenceProfile', {
  type: 'AWS::Bedrock::ApplicationInferenceProfile',
  properties: {
    InferenceProfileName: 'cloud-engineer-profile',
    Description: 'Application Inference Profile for Cloud Engineer cost tracking',
    ModelSource: {
      CopyFrom: 'arn:aws:bedrock:ap-southeast-2::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0'
    },
    Tags: [
      { Key: 'Application', Value: 'CloudEngineer' },
      { Key: 'Environment', Value: 'Production' },
      { Key: 'CostCenter', Value: 'Engineering' }
    ]
  }
});
```

The agent uses the inference profile ARN from the environment variable:
```python
model_id = os.environ.get("BEDROCK_MODEL_ID", "fallback-model-id")
```

## References

- [AWS Application Inference Profiles Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles.html)
- [AWS Cost Explorer User Guide](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/ce-what-is.html)
- [Cost Allocation Tags](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/cost-alloc-tags.html)
