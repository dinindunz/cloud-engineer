import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecsPatterns from 'aws-cdk-lib/aws-ecs-patterns';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as assets from 'aws-cdk-lib/aws-ecr-assets'; 
import { Construct } from 'constructs';
import * as path from 'path';

export class CloudEngineerStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const vpc = new ec2.Vpc(this, 'McpProxyVpc', {
      maxAzs: 2,
      natGateways: 1, // For private subnets with internet access
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: 'public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: 'private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
      ],
    });

    // Load Balanced Fargate Service with CDK Docker build
    const loadBalancedFargateService = new ecsPatterns.ApplicationLoadBalancedFargateService(this, 'McpProxyService', {
      cluster: new ecs.Cluster(this, 'McpProxyCluster', {
        vpc,
        clusterName: 'mcp-proxy-cluster',
      }),
      memoryLimitMiB: 1024,
      cpu: 512,
      enableExecuteCommand: true,
      taskImageOptions: {
        image: ecs.ContainerImage.fromAsset(path.join(__dirname, '../mcp-proxy'), {
          file: 'Dockerfile',
          platform: assets.Platform.LINUX_AMD64,
        }),
        containerPort: 8096,
        environment: {
          GITHUB_PERSONAL_ACCESS_TOKEN: process.env.GITHUB_PERSONAL_ACCESS_TOKEN || '',
        },
        logDriver: ecs.LogDrivers.awsLogs({
          streamPrefix: 'mcp-proxy',
          logGroup: new logs.LogGroup(this, 'McpProxyLogGroup', {
            logGroupName: '/ecs/mcp-proxy',
            retention: logs.RetentionDays.ONE_WEEK,
            removalPolicy: cdk.RemovalPolicy.DESTROY,
          }),
        }),
      },
      containerCpu: 256,
      containerMemoryLimitMiB: 512,
      minHealthyPercent: 100,
      listenerPort: 80,
      assignPublicIp: true,
    });

    // Allow traffic on port 8096
    loadBalancedFargateService.service.connections.allowFromAnyIpv4(
      ec2.Port.tcp(8096),
      'Allow MCP Proxy traffic'
    );

    // Configure health check for MCP Proxy
    loadBalancedFargateService.targetGroup.configureHealthCheck({
      path: "/",
      port: "8096",
      healthyHttpCodes: "200,404", // 404 might is ok if no health endpoint
      interval: cdk.Duration.seconds(30),
      timeout: cdk.Duration.seconds(5),
      healthyThresholdCount: 2,
      unhealthyThresholdCount: 3,
    });    

    // Create IAM role for Lambda function
    const lambdaRole = new iam.Role(this, 'CloudEngineerLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'IAM role for Cloud Engineer Lambda function',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
        iam.ManagedPolicy.fromAwsManagedPolicyName('AdministratorAccess'),
      ],
    });
    
    // Read MCP server configuration
    let config = require(path.join(__dirname, '../mcp-proxy/mcp-servers.json'));

    // If wrapped in a top-level object, unwrap it
    const firstValue = Object.values(config)[0];
    if (Object.keys(config).length === 1 && typeof firstValue === 'object') {
      config = firstValue;
    }

    // Get server names
    const mcpServers = Object.keys(config);

    // Create Lambda function
    const cloudEngineerFunction = new lambda.DockerImageFunction(this, 'CloudEngineerFunction', {
      code: lambda.DockerImageCode.fromImageAsset(path.join(__dirname, '../agent'), {
        platform: assets.Platform.LINUX_AMD64,
      }),
      reservedConcurrentExecutions: 1,
      role: lambdaRole,
      timeout: cdk.Duration.minutes(15),
      memorySize: 512,
      environment: {
        MCP_PROXY_DNS: loadBalancedFargateService.loadBalancer.loadBalancerDnsName,
        MCP_SERVERS: JSON.stringify(mcpServers),
        SLACK_SIGNING_SECRET: process.env.SLACK_SIGNING_SECRET || '',
        SLACK_BOT_TOKEN: process.env.SLACK_BOT_TOKEN || '',
        SLACK_BOT_USER_ID: process.env.SLACK_BOT_USER_ID || '',
      },
      description: 'AWS Cloud Engineer for Slack integration',
    });

    const api = new apigateway.LambdaRestApi(this, 'CloudEngineerApi', {
      handler: cloudEngineerFunction,
      proxy: false,
    });

    const root = api.root.addResource('cloud-engineer');
    root.addMethod('POST');

    cdk.Tags.of(this).add('DoNotNuke', 'True');

    // Output the API Gateway URL
    new cdk.CfnOutput(this, 'CloudEngineerSlackEndpoint', {
      value: `${api.url}cloud-engineer`,
      description: 'API Gateway URL for Slack webhook',
    });
  }
}
