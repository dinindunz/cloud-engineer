# Cloud Engineer Agent - Complete Architecture

## Overview
This architecture represents a comprehensive cloud engineer agent solution built on AWS, using Slack as the user interface, powered by Amazon Bedrock's Claude model, and enhanced with MCP servers and Strands tools for extended functionality.

## Architecture Components

```
┌─────────────┐    ┌─────────────────┐    ┌─────────────────────────────────────────────────────┐
│    Slack    │───▶│   API Gateway   │───▶│                    Lambda Function                  │
│  Interface  │    │                 │    │                     (AWS Strands)                   │
└─────────────┘    └─────────────────┘    │                                                     │
                                          │ ┌───────────────┐ ┌───────────────┐ ┌─────────────┐ │
                   ┌─────────────────┐    │ │ aws_doc_tools │ │ aws_cdk_tools | │ github_tools│ │
                   │ CloudWatch Logs │───▶│ └───────────────┘ └───────────────┘ └─────────────┘ │
                   └─────────────────┘    │ ┌────────────────┐ ┌──────────────┐ ┌─────────────┐ │
                                          │ │ atlassian_tools│ │   use_aws    │ │    memory   │ │
                                          │ └────────────────┘ └──────────────┘ └─────────────┘ │
                                          └─────────────────────────────────────────────────────┘
                                                                 │
                            ┌────────────────────────────────────┼───────────────────────────────────────────┐
                            │                                    │                                           │
                            ▼                                    ▼                                           ▼
                  ┌─────────────────┐            ┌──────────────────────────────────┐    ┌──────────────────────────────────────┐
                  │ MCP Proxy (ALB) │            │          Amazon Bedrock          │    │            Cost Metrics              │
                  │ ┌─────────────┐ │            │                                  │    │                                      │  
                  │ │ Forgate     │ │            │ ┌─────────────┐  ┌─────────────┐ │    │  ┌───────────────┐ ┌───────────────┐ │
                  │ │ Task        │ │            │ │   Model     │  │  Knowledge  │ │    │  │ Cost Explorer │ │  CloudWatch   │ │
                  │ └─────────────┘ │            │ └─────────────┘  │  Base (RAG) │ │    │  └───────────────┘ │  Dashboard    │ │
                  └─────────────────┘            │                  └─────────────┘ │    │                    └───────────────┘ │
                            │                    │ ┌─────────────┐                  │    └──────────────────────────────────────┘  
                            │                    │ │ Guardrails  │                  │       
                            │                    │ └─────────────┘                  │    
                            ▼                    └──────────────────────────────────┘  
    ┌───────────────────────────────────────────────────┐                               
    │                   MCP Servers                     │             
    │                                                   │         ┌─────────────────┐           
    │ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │         │    External     │           
    │ │AWS Docs MCP │ │ Atlassian   │ │  AWS CDK    │   │         │    Services     │         
    │ │Srv (ALB)    │ │MCP Srv (ALB)│ │MCP Srv (ALB)│   │         │                 │           
    │ │             │ │             │ │             │   │         │ ┌─────────────┐ │                              
    │ │ ┌─────────┐ │ │ ┌─────────┐ │ │ ┌─────────┐ │   │         │ │   GitHub    │ │                              
    │ │ │Fargate  │ │ │ │Fargate  │ │ │ │Fargate  │ │   │         │ │    API      │ │        
    │ │ │Task     │ │ │ │Task     │ │ │ │Task     │ │   │         │ └─────────────┘ │      
    │ │ └─────────┘ │ │ └─────────┘ │ │ └─────────┘ │   │────────▶│                 │       
    │ └─────────────┘ └─────────────┘ └─────────────┘   │         │ ┌─────────────┐ │       
    │ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │         │ │  Atlassian  │ │        
    │ │   GitHub    │ │             │ │             │   │         │ │    API      │ │      
    │ │MCP Srv (ALB)│ │             │ │             │   │         │ └─────────────┘ │     
    │ │             │ │             │ │             │   │         │                 │ 
    │ │ ┌─────────┐ │ │             │ │             │   │         │ ┌─────────────┐ │                   
    │ │ │Fargate  │ │ │             │ │             │   │         │ │    AWS      │ │
    │ │ │Task     │ │ │             │ │             │   │         │ │Documentation│ │        
    │ │ └─────────┘ │ │             │ │             │   │         │ │             │ │        
    │ └─────────────┘ └─────────────┘ └─────────────┘   │         │ └─────────────┘ │         
    └───────────────────────────────────────────────────┘         └─────────────────┘    
▼                                                                      
                                                                         
```
![Architecture Diagram](generated-diagrams/cloud-engineer-architecture.png)

## System Context

This Lambda function is triggered by two primary sources:
- **Slack Messages**: User interactions through Slack interface for cloud engineering queries and operations
- **CloudWatch Log Events**: Automated error detection and response workflow for infrastructure monitoring

The system behavior is defined in `agent/system_prompt.md`, which outlines the agent's capabilities for AWS operations management and automated error response workflows.

## Enhanced Data Flow

1. **Input Sources**: 
   - Users interact through Slack with cloud engineering queries
   - CloudWatch Logs trigger automated error response workflows

2. **API Gateway**: Slack webhook and CloudWatch events trigger AWS API Gateway

3. **Lambda Processing**: AWS Strands-powered Lambda function processes requests using integrated tools:
   - **aws_doc_tools**: Access to AWS documentation and best practices
   - **aws_cdk_tools**: CDK-specific operations and guidance  
   - **github_tools**: Repository management and pull request operations
   - **atlassian_tools**: Jira integration for issue tracking and project management
   - **use_aws**: Direct AWS service interactions and resource management
   - **memory**: Context retention and conversation history

4. **External Service Integration**:
   - **MCP Proxy (ALB)**: Load-balanced access to containerized MCP servers running on Fargate
   - **Amazon Bedrock**: Claude model for AI processing, Knowledge Base for RAG, and Guardrails for content safety
   - **Cost Metrics**: Integration with Cost Explorer and CloudWatch Dashboard for cost monitoring
   - **External APIs**: GitHub API, Atlassian API, and AWS Documentation services

5. **Response Processing**: Lambda aggregates responses from all integrated services and tools

6. **Output Delivery**: Processed responses flow back to Slack, with automated Jira ticket creation and GitHub PR generation for error response workflows

## Key Components

### MCP Servers
- **AWS Documentation MCP Server**: Provides real-time access to AWS documentation, best practices, and technical guides
- **AWS Cost Explorer MCP Server**: Delivers cost analysis, billing insights, and optimization recommendations

### Strands Tools
- **use_aws Tool**: Enables direct interaction with AWS services for operational tasks, resource management, and configuration changes

### Amazon Bedrock Services
- **Claude Model**: Advanced language model for understanding and generating responses
- **Guardrails**: Content filtering and safety validation
- **Knowledge Base**: RAG implementation with internal knowledge repository

## Enhanced Capabilities

### Documentation & Learning
- Real-time AWS documentation lookup
- Best practices and architectural guidance
- Service-specific technical references
- Troubleshooting guides and solutions

### Cost Management
- Real-time cost analysis and reporting
- Budget monitoring and alerts
- Cost optimization recommendations
- Resource utilization insights

### AWS Operations
- Direct AWS service interactions
- Resource provisioning and management
- Configuration changes and updates
- Infrastructure monitoring and control

### AI-Powered Assistance
- Natural language query processing
- Context-aware responses
- Multi-service orchestration
- Intelligent recommendation engine

## Security & Compliance

- API Gateway security and rate limiting
- Lambda execution environment isolation
- MCP server secure communication protocols
- Bedrock Guardrails for content safety
- AWS IAM for granular access control
- Audit logging for all operations

## Demos

Explore the Cloud Engineer Agent capabilities through interactive demonstrations:

- **[Automated Error Response](demos/automated-error-response/README.md)** - Complete workflow from CloudWatch error detection to automated Jira ticket creation and GitHub PR generation
- **[Cloud Operations](demos/cloud-ops/README.md)** - Direct AWS service interactions, resource management, and infrastructure operations
- **[General Queries](demos/general-queries/README.md)** - AWS documentation lookup, best practices guidance, and expert recommendations

## File Structure

```
cloud-engineer/
├── README.md                           # Main project documentation
├── package.json                        # Node.js dependencies and scripts
├── cdk.json                            # CDK configuration
├── tsconfig.json                       # TypeScript configuration
├── jest.config.js                      # Jest testing configuration
├── LICENSE.md                          # Project license
├── .gitignore                          # Git ignore patterns
├── .npmignore                          # NPM ignore patterns
├── cdk.context.json                    # CDK context cache
├── cloud-engineer-agent-architecture.png # Legacy architecture diagram
│
├── agent/                              # Lambda function source code
│   ├── agent.py                        # Main Lambda handler
│   ├── cloud_engineer.py               # Core agent implementation
│   ├── system_prompt.md                # Agent behavior definition
│   ├── requirements.txt                # Python dependencies
│   └── Dockerfile                      # Container configuration
│
├── bin/                                # CDK application entry point
│   └── cloud-engineer.ts               # CDK app definition
│
├── lib/                                # CDK infrastructure code
│   └── cloud-engineer-stack.ts         # Main infrastructure stack
│
├── mcp-proxy/                          # MCP server proxy configuration
│   ├── Dockerfile                      # Proxy container configuration
│   ├── entrypoint.sh                   # Container startup script
│   └── mcp-servers.json                # MCP server definitions
│
├── demos/                              # Demo screenshots and documentation
│   ├── automated-error-response/       # Error response workflow demos
│   ├── cloud-ops/                      # AWS operations demos
│   └── general-queries/                # Documentation query demos
│
├── generated-diagrams/                 # Architecture diagrams
│   └── cloud-engineer-architecture.png # Current system architecture
│
└── tests/                              # Test files
    └── test_cloud_engineer.py          # Agent unit tests
```

## Scalability & Performance

- Auto-scaling Lambda functions
- Distributed MCP server architecture
- Cached documentation and cost data
- Optimized Bedrock service calls
- Efficient knowledge base queries
