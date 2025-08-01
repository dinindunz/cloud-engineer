# Multi-Agent Cloud Engineer Platform Refactoring

## Objective
Refactor the existing cloud engineer system into a multi-agent platform using the Strands framework pattern.

## Files to Modify
**ONLY modify these two files:**
- `/cloud-engineer/agent/cloud_engineer.py`
- `/cloud-engineer/agent/agent.py`

## Required Changes

### 1. Create 5 Specialized Agents

#### Agent 1: Knowledge Base Agent
- **Purpose**: Answer AWS-related questions
- **System Prompt**: "You are an AWS knowledge specialist who provides accurate information about AWS services, best practices, and troubleshooting guidance"
- **Tools**: 
  - aws_documentation_search (connects to aws-documentation MCP server)

#### Agent 2: Error Analysis Agent
- **Purpose**: Analyze CloudWatch logs and user queries to suggest code changes
- **System Prompt**: "You are a cloud infrastructure analyst who examines errors from CloudWatch logs and user queries to recommend specific code fixes and infrastructure changes"
- **Tools**:
  - use_aws_tool (existing AWS tool)

#### Agent 3: JIRA Agent
- **Purpose**: Create tickets for issues found by the error analysis agent
- **System Prompt**: "You are a project management specialist who creates well-structured JIRA tickets for infrastructure issues and code changes"
- **Tools**:
  - atlassian_mcp

#### Agent 4: PR Agent
- **Purpose**: Create GitHub repositories and pull requests for code changes
- **System Prompt**: "You are a DevOps automation specialist who creates GitHub repositories and pull requests for infrastructure code changes"
- **Tools**:
  - aws_cdk (connects to aws-cdk MCP server)
  - github_mcp

#### Agent 5: Operations Agent
- **Purpose**: Perform operational tasks on AWS resources
- **System Prompt**: "You are a cloud operations specialist who can perform any operational task on AWS resources including monitoring, scaling, and maintenance"
- **Tools**:
  - use_aws_tool (existing AWS tool)


### 4. Agent Orchestration
- Keep existing main class structure but integrate the 5 agents

### 5. Constraints
- **DO NOT** modify any other files
- **DO NOT** change existing public API interfaces
- **PRESERVE** all existing functionality
- **USE** existing AWS credentials and configurations
- **DO NOT** write any mcp server code. its already available

### 6. Expected Structure from a different setup
```python
from strands import Agent, tool 
from strands_tools import calculator, file_write, python_repl, journal 

@tool 
def web_search(query: str) -> str: 
    return "Dummy web search results here!" 

# Create specialized agents 
research_analyst_agent = Agent( 
    system_prompt="You are a research specialist who gathers and analyzes information about local startup markets", 
    tools=[web_search, calculator, file_write, python_repl] 
) 

travel_advisor_agent = Agent( 
    system_prompt="You are a travel expert who helps with trip planning and destination advice", 
    tools=[web_search, journal] 
) 

# Convert the agents into tools 
@tool 
def research_analyst(query: str) -> str: 
    response = research_analyst_agent(query) 
    return str(response) 

@tool 
def travel_advisor(query: str) -> str: 
    response = travel_advisor_agent(query) 
    return str(response) 

# Orchestrator naturally delegates to specialists 
executive_assistant = Agent(  
    tools=[research_analyst, travel_advisor]  
) 

result = executive_assistant("I have a business meeting in Portland next week. Suggest a nice place to stay near the local startup scene, and suggest a few startups to visit")

```

## Success Criteria
- All 5 agents are properly defined with appropriate tools
- Existing functionality remains intact
- No need to run any tests or deployments