import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as iam from "aws-cdk-lib/aws-iam";
import * as ecr from "aws-cdk-lib/aws-ecr";

export class AgentCoreStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Define trust policy via assumedBy with conditions
    // This adds extra security constraints — even though Bedrock AgentCore is the principal, it can only assume the role under these conditions:
    // 1. The source account must be <account-id> (your AWS account ID)
    // 2. The source ARN must match the pattern arn:aws:bedrock-agentcore:us-east-1:<account-id>:*
    // This ensures that only Bedrock AgentCore can assume this role, and only in the specified region and account.
    // 🔐 Why This Is Needed
    // If you're building a Bedrock Agent and assigning it a role for runtime execution (e.g., to log to CloudWatch, call ECR, X-Ray, etc.), you need to:
    // Trust bedrock-agentcore.amazonaws.com
    // Secure that trust using SourceAccount + SourceArn conditions
    // This ensures only Bedrock agents in your own account and region can assume the role — not random agents elsewhere.

    const assumedBy = new iam.PrincipalWithConditions(
      new iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
      {
        StringEquals: {
          "aws:SourceAccount": this.account,
        },
        ArnLike: {
          "aws:SourceArn": `arn:aws:bedrock-agentcore:us-east-1:${this.account}:*`,
        },
      },
    );

    // Create the IAM role with the trust policy
    const role = new iam.Role(this, "MyBedrockAgentRole", {
      assumedBy,
      roleName: "MyBedrockAgentRole",
    });

    role.attachInlinePolicy(new iam.Policy(this, 'MyConvertedPolicy', {
      document: new iam.PolicyDocument({
        statements: [
          new iam.PolicyStatement({
            sid: 'ECRImageAccess',
            effect: iam.Effect.ALLOW,
            actions: [
              'ecr:BatchGetImage',
              'ecr:GetDownloadUrlForLayer'
            ],
            resources: [
              `arn:aws:ecr:us-east-1:${this.account}:repository/*`
            ]
          }),
          new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: [
              'logs:DescribeLogStreams',
              'logs:CreateLogGroup'
            ],
            resources: [
              `arn:aws:logs:us-east-1:${this.account}:log-group:/aws/bedrock-agentcore/runtimes/*`
            ]
          }),
          new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: [
              'logs:DescribeLogGroups'
            ],
            resources: [
              `arn:aws:logs:us-east-1:${this.account}:log-group:*`
            ]
          }),
          new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: [
              'logs:CreateLogStream',
              'logs:PutLogEvents'
            ],
            resources: [
              `arn:aws:logs:us-east-1:${this.account}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*`
            ]
          }),
          new iam.PolicyStatement({
            sid: 'ECRTokenAccess',
            effect: iam.Effect.ALLOW,
            actions: [
              'ecr:GetAuthorizationToken'
            ],
            resources: ['*']
          }),
          new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: [
              'xray:PutTraceSegments',
              'xray:PutTelemetryRecords',
              'xray:GetSamplingRules',
              'xray:GetSamplingTargets'
            ],
            resources: ['*']
          }),
          new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: ['cloudwatch:PutMetricData'],
            resources: ['*'],
            conditions: {
              StringEquals: {
                'cloudwatch:namespace': 'bedrock-agentcore'
              }
            }
          }),
          new iam.PolicyStatement({
            sid: 'GetAgentAccessToken',
            effect: iam.Effect.ALLOW,
            actions: [
              'bedrock-agentcore:GetWorkloadAccessToken',
              'bedrock-agentcore:GetWorkloadAccessTokenForJWT',
              'bedrock-agentcore:GetWorkloadAccessTokenForUserId'
            ],
            resources: [
              `arn:aws:bedrock-agentcore:us-east-1:${this.account}:workload-identity-directory/default`,
              `arn:aws:bedrock-agentcore:us-east-1:${this.account}:workload-identity-directory/default/workload-identity/agentName-*`
            ]
          }),
          new iam.PolicyStatement({
            sid: 'BedrockModelInvocation',
            effect: iam.Effect.ALLOW,
            actions: [
              'bedrock:InvokeModel',
              'bedrock:InvokeModelWithResponseStream'
            ],
            resources: [
              'arn:aws:bedrock:*::foundation-model/*',
              `arn:aws:bedrock:us-east-1:${this.account}:*`
            ]
          })
        ]
      })
    }));

    // Create ECR repository
    const repository = new ecr.Repository(this, "BedrockAgentCoreRepository", {
      repositoryName: "bedrock-agentcore",
    });
    
  }
}