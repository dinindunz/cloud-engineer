import os
import logging
import atexit
from strands import Agent, tool
from strands.tools.mcp import MCPClient
from strands.models import BedrockModel
from mcp import StdioServerParameters, stdio_client
from strands_tools import use_aws
from typing import Dict, List, Optional, Any, Union
import json
import re
import pathlib

# Import cost modelling components
try:
    from cost_modelling.monitored_agent import MonitoredBedrockAgent
    from cost_modelling.logging_config import LoggingConfig
    COST_LOGGING_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Cost modelling not available: {e}")
    COST_LOGGING_AVAILABLE = False

custom_env = os.environ.copy()
custom_env["UV_CACHE_DIR"] = "/tmp/uv_cache"
custom_env["XDG_CACHE_HOME"] = "/tmp"

# Use logger configured in lambda_handler
logger = logging.getLogger(__name__)

# Global variables for MCP client and agent
orchestrator_agent = None
mcp_initialized = False
mcp_clients = []  # Track all MCP clients for cleanup

# Model creation will happen during agent initialization
bedrock_model = None

# Cost monitoring setup
cost_monitoring_agent = None
cost_config = None
current_incident_id = None

# Enhanced system prompt for the agent
system_prompt = pathlib.Path("prompts/system/orchestrator.md").read_text()

# Specialized agents
knowledge_base_agent = None
error_analysis_agent = None
jira_agent = None
pr_agent = None
operations_agent = None

# MCP tools storage
aws_documentation_tools = []
atlassian_mcp_tools = []
aws_cdk_tools = []
github_mcp_tools = []


def initialize_cost_monitoring():
    """Initialize cost monitoring components"""
    global cost_monitoring_agent, cost_config
    
    if not COST_LOGGING_AVAILABLE:
        logger.info("Cost monitoring not available - continuing without token logging")
        return
    
    try:
        # Initialize cost monitoring configuration
        cost_config = LoggingConfig()
        cost_monitoring_agent = MonitoredBedrockAgent(
            config=cost_config,
            region_name=os.environ.get("AWS_REGION", "ap-southeast-2")
        )
        logger.info("Cost monitoring initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize cost monitoring: {e}")
        cost_monitoring_agent = None


def create_bedrock_model() -> BedrockModel:
    """Create a BedrockModel with fallback options"""
    region = os.environ.get("AWS_REGION", "ap-southeast-2")
    model_id = "apac.anthropic.claude-sonnet-4-20250514-v1:0"

    try:
        logger.info(f"Trying to create Bedrock model with ID: {model_id}")
        model = BedrockModel(
            model_id=model_id,
            region_name=region,
            temperature=0.1,  # Lower temperature for more focused responses
            max_tokens=2000,  # Reasonable limit for Slack responses
        )
        logger.info(f"Successfully created Bedrock model: {model_id}")
        
        # Initialize cost monitoring
        initialize_cost_monitoring()
        
        return model
    except Exception as e:
        logger.warning(f"Model {model_id} not available: {e}")


# Register cleanup handler for MCP clients
def cleanup():
    """Clean up MCP client resources"""
    global mcp_clients, mcp_initialized

    try:
        if mcp_clients and mcp_initialized:
            for i, mcp_client in enumerate(mcp_clients):
                try:
                    # Use context manager exit method if available
                    if hasattr(mcp_client, "__exit__"):
                        mcp_client.__exit__(None, None, None)
                    else:
                        # Fallback to stop method if it exists
                        if hasattr(mcp_client, "stop"):
                            mcp_client.stop()
                    logger.info(f"MCP client {i+1} stopped")
                except Exception as e:
                    logger.error(f"Error stopping MCP client {i+1}: {e}")
            mcp_clients.clear()  # Clear the list after cleanup
    except Exception as e:
        logger.error(f"Error during MCP clients cleanup: {e}")
    finally:
        mcp_initialized = False


def initialize_mcp_clients():
    """Initialize multiple MCP clients and categorize tools by server"""
    global mcp_initialized, mcp_clients, aws_documentation_tools, atlassian_mcp_tools, aws_cdk_tools, github_mcp_tools

    # Get MCP server list from environment variable (expects a JSON array string)
    mcp_servers = json.loads(os.environ.get("MCP_SERVERS", "[]"))

    mcp_initialized = False

    for mcp_server in mcp_servers:
        logger.info(f"Initializing MCP client for server: {mcp_server}")
        try:
            mcp_client = MCPClient(
                lambda: stdio_client(
                    StdioServerParameters(
                        command="mcp-proxy",
                        args=[
                            f"http://{os.environ.get('MCP_PROXY_DNS')}/servers/{mcp_server}/sse"
                        ],
                        env=custom_env,
                    )
                )
            )
            mcp_client.start()
            tools = mcp_client.list_tools_sync()

            # Add client to tracking list for cleanup
            mcp_clients.append(mcp_client)

            # Categorize tools by server
            if mcp_server == "aws-documentation":
                aws_documentation_tools.extend(tools)
            elif mcp_server == "atlassian":
                atlassian_mcp_tools.extend(tools)
            elif mcp_server == "aws-cdk":
                aws_cdk_tools.extend(tools)
            elif mcp_server == "github":
                github_mcp_tools.extend(tools)

            logger.info(
                f"MCP client '{mcp_server}' initialized successfully with {len(tools)} tools"
            )
            mcp_initialized = True

        except ImportError as e:
            logger.warning(f"MCP dependencies not available for {mcp_server}: {e}")
        except Exception as e:
            logger.warning(f"Failed to initialize MCP client '{mcp_server}': {e}")
            logger.info(f"Agent will continue without {mcp_server} tools")


def create_monitored_bedrock_model(agent_id: str, incident_id: Optional[str] = None) -> BedrockModel:
    """Create a BedrockModel with cost monitoring wrapper"""
    region = os.environ.get("AWS_REGION", "ap-southeast-2")
    model_id = "apac.anthropic.claude-sonnet-4-20250514-v1:0"
    
    if not COST_LOGGING_AVAILABLE or cost_monitoring_agent is None:
        # Fallback to regular model if cost monitoring not available
        return BedrockModel(
            model_id=model_id,
            region_name=region,
            temperature=0.1,
            max_tokens=2000,
        )
    
    # Create a wrapper class that integrates cost monitoring
    class MonitoredBedrockModel(BedrockModel):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.agent_id = agent_id
            self.incident_id = incident_id
        
        def invoke(self, messages, **kwargs):
            """Override invoke to add cost monitoring"""
            try:
                # Convert messages to the format expected by cost monitoring
                if isinstance(messages, list):
                    # Convert Strands message format to Bedrock format
                    body = {
                        "messages": messages,
                        "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                        "temperature": kwargs.get("temperature", self.temperature)
                    }
                else:
                    body = messages
                
                # Use cost monitoring agent for the API call
                response = cost_monitoring_agent.invoke_model_with_logging(
                    model_id=self.model_id,
                    body=body,
                    agent_id=self.agent_id,
                    incident_id=self.incident_id,
                    context={"strands_integration": True}
                )
                
                # Extract the Bedrock response and return in expected format
                bedrock_response = response.get('bedrock_response', response)
                
                # Log cost information
                if 'token_logging' in response:
                    log_data = response['token_logging']
                    logger.info(f"Token usage - Agent: {self.agent_id}, "
                              f"Tokens: {log_data.get('total_tokens', 0)}, "
                              f"Cost: ${log_data.get('estimated_cost', 0):.6f}")
                
                return bedrock_response
                
            except Exception as e:
                logger.error(f"Error in monitored Bedrock call: {e}")
                # Fallback to regular model call
                return super().invoke(messages, **kwargs)
    
    return MonitoredBedrockModel(
        model_id=model_id,
        region_name=region,
        temperature=0.1,
        max_tokens=2000,
    )


def initialize_specialized_agents():
    """Initialize the 5 specialized agents with cost monitoring"""
    global knowledge_base_agent, error_analysis_agent, jira_agent, pr_agent, operations_agent, bedrock_model

    # Create the Bedrock model if not already created
    if bedrock_model is None:
        bedrock_model = create_bedrock_model()

    # Initialize MCP clients and categorize tools
    initialize_mcp_clients()

    # Agent 1: Knowledge Base Agent
    knowledge_base_prompt = pathlib.Path("prompts/agents/knowledge_base.md").read_text()
    knowledge_base_agent = Agent(
        system_prompt=knowledge_base_prompt,
        tools=aws_documentation_tools,
        model=create_monitored_bedrock_model("knowledge-base", current_incident_id),
    )

    # Agent 2: Error Analysis Agent
    error_analysis_prompt = pathlib.Path("prompts/agents/error_analysis.md").read_text()
    error_analysis_agent = Agent(
        system_prompt=error_analysis_prompt,
        tools=[use_aws],
        model=create_monitored_bedrock_model("error-analysis", current_incident_id),
    )

    # Agent 3: JIRA Agent
    jira_prompt = pathlib.Path("prompts/agents/jira.md").read_text()
    jira_agent = Agent(
        system_prompt=jira_prompt,
        tools=atlassian_mcp_tools,
        model=create_monitored_bedrock_model("jira", current_incident_id),
    )

    # Agent 4: PR Agent
    pr_prompt = pathlib.Path("prompts/agents/pr.md").read_text()
    pr_agent = Agent(
        system_prompt=pr_prompt,
        tools=aws_cdk_tools + github_mcp_tools,
        model=create_monitored_bedrock_model("pr", current_incident_id),
    )

    # Agent 5: Operations Agent
    operations_prompt = pathlib.Path("prompts/agents/operations.md").read_text()
    operations_agent = Agent(
        system_prompt=operations_prompt,
        tools=[use_aws],
        model=create_monitored_bedrock_model("operations", current_incident_id),
    )


# Convert specialized agents into tools for the orchestrator
@tool
def knowledge_base_specialist(query: str) -> str:
    """Get AWS knowledge and documentation information"""
    if knowledge_base_agent is None:
        initialize_specialized_agents()
    response = knowledge_base_agent(query)
    return str(response)


@tool
def error_analysis_specialist(query: str) -> str:
    """Analyze CloudWatch logs and errors to suggest code changes"""
    if error_analysis_agent is None:
        initialize_specialized_agents()
    response = error_analysis_agent(query)
    return str(response)


@tool
def jira_specialist(query: str) -> str:
    """Create JIRA tickets for infrastructure issues"""
    if jira_agent is None:
        initialize_specialized_agents()
    response = jira_agent(query)
    return str(response)


@tool
def pr_specialist(query: str) -> str:
    """Create GitHub repositories and pull requests for code changes"""
    if pr_agent is None:
        initialize_specialized_agents()
    response = pr_agent(query)
    return str(response)


@tool
def operations_specialist(query: str) -> str:
    """Perform operational tasks on AWS resources"""
    if operations_agent is None:
        initialize_specialized_agents()
    response = operations_agent(query)
    return str(response)


def get_agent() -> Agent:
    """Get or create the orchestrator agent instance"""
    global orchestrator_agent, bedrock_model

    if orchestrator_agent is None:
        # Create the Bedrock model if not already created
        if bedrock_model is None:
            bedrock_model = create_bedrock_model()

        # Initialize specialized agents
        initialize_specialized_agents()

        # Create orchestrator agent with specialist tools and cost monitoring
        orchestrator_agent = Agent(
            tools=[
                knowledge_base_specialist,
                error_analysis_specialist,
                jira_specialist,
                pr_specialist,
                operations_specialist,
                get_cost_summary,
                flush_cost_metrics,
            ],
            model=create_monitored_bedrock_model("cloud-engineer", current_incident_id),
            system_prompt=system_prompt,
        )

    return orchestrator_agent


def extract_text_from_response(response: Any) -> str:
    """Extract text from various response formats"""
    if response is None:
        return "No response generated"

    # If it's already a string, return it
    if isinstance(response, str):
        return response

    # If it's a dict, try to extract text content
    if isinstance(response, dict):
        # Check for common dict structures
        if "message" in response:
            return extract_text_from_response(response["message"])

        if "content" in response:
            content = response["content"]
            if isinstance(content, list):
                # Extract text from list of content items
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                    elif isinstance(item, str):
                        text_parts.append(item)
                return " ".join(text_parts)
            elif isinstance(content, str):
                return content

        if "text" in response:
            return response["text"]

        # If it's a dict with role and content (common LLM response format)
        if "role" in response and "content" in response:
            return extract_text_from_response(response["content"])

        # Try to convert dict to JSON string for debugging
        try:
            json_str = json.dumps(response, indent=2)
            logger.debug(f"Unhandled dict response format: {json_str}")
            # Try to extract any text value from the dict
            for key, value in response.items():
                if isinstance(value, str) and len(value) > 10:
                    return value
        except:
            pass

    # If it has a message attribute, try to extract it
    if hasattr(response, "message"):
        return extract_text_from_response(response.message)

    # If it has a content attribute, try to extract it
    if hasattr(response, "content"):
        return extract_text_from_response(response.content)

    # If it has a text attribute, try to extract it
    if hasattr(response, "text"):
        return extract_text_from_response(response.text)

    # Last resort: convert to string
    try:
        return str(response)
    except Exception as e:
        logger.warning(f"Could not extract text from response: {e}")
        return f"Error: Could not extract text from response of type {type(response)}"


def clean_agent_response(response: Union[str, Dict, Any]) -> str:
    """Clean up agent response for better Slack formatting"""
    # First, extract text from the response
    text_response = extract_text_from_response(response)

    if not text_response:
        return "No response generated"

    # Remove any remaining thinking tags
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", text_response, flags=re.DOTALL)

    # Remove excessive whitespace
    cleaned = re.sub(r"\n\s*\n\s*\n", "\n\n", cleaned)

    # Ensure response isn't too long for Slack
    if len(cleaned) > 2500:
        cleaned = cleaned[:2400] + "\n\n... (truncated)"

    return cleaned.strip()


def execute_custom_task(task_description: str, incident_id: Optional[str] = None) -> str:
    """Execute a custom cloud engineering task based on description with cost tracking"""
    global current_incident_id
    
    # Set current incident ID for cost tracking
    if incident_id:
        current_incident_id = incident_id
        logger.info(f"Starting task execution for incident: {incident_id}")
    
    try:
        # Use incident context if cost monitoring is available
        if COST_LOGGING_AVAILABLE and cost_monitoring_agent and incident_id:
            with cost_monitoring_agent.incident_context(incident_id) as tracked_incident_id:
                # Get the agent instance (will initialize if needed)
                agent_instance = get_agent()
                
                # Execute the agent
                response = agent_instance(task_description)
                
                logger.debug(f"Agent response type: {type(response)}")
                logger.debug(f"Agent response: {response}")
                
                # Clean and format the response
                result = clean_agent_response(response)
                
                # Log incident completion
                logger.info(f"Task completed for incident: {tracked_incident_id}")
                
                return result
        else:
            # Fallback to regular execution without incident tracking
            agent_instance = get_agent()
            response = agent_instance(task_description)
            
            logger.debug(f"Agent response type: {type(response)}")
            logger.debug(f"Agent response: {response}")
            
            result = clean_agent_response(response)
            return result
            
    except Exception as e:
        error_message = f"Error executing AWS task: {str(e)}"
        logger.error(error_message)
        return error_message
    finally:
        # Clear current incident ID
        current_incident_id = None


def health_check() -> Dict[str, Any]:
    """Health check function to verify system status"""
    return {
        "mcp_initialized": mcp_initialized,
        "orchestrator_agent_ready": orchestrator_agent is not None,
        "aws_region": os.environ.get("AWS_REGION", "ap-southeast-2"),
        "bedrock_model_ready": bedrock_model is not None,
        "cost_monitoring_available": COST_LOGGING_AVAILABLE,
        "cost_monitoring_agent_ready": cost_monitoring_agent is not None,
    }


@tool
def get_cost_summary(date: Optional[str] = None) -> str:
    """Get cost summary for Bedrock usage"""
    if not COST_LOGGING_AVAILABLE or cost_monitoring_agent is None:
        return "Cost monitoring not available"
    
    try:
        from cost_modelling.cost_analyzer import CostAnalyzer
        from datetime import datetime
        
        if not date:
            date = datetime.utcnow().strftime('%Y-%m-%d')
        
        analyzer = CostAnalyzer(config=cost_config)
        report = analyzer.generate_daily_cost_report(date)
        
        summary = f"""**Daily Cost Report for {date}**
        
**Summary:**
- Total Cost: ${report.total_cost:.6f}
- Total Tokens: {report.total_tokens:,}
- Total Requests: {report.total_requests}
- Avg Cost/Request: ${report.average_cost_per_request:.6f}

**By Agent:**"""
        
        for agent_id, data in report.breakdown.get('by_agent', {}).items():
            summary += f"\n- {agent_id}: ${data['cost']:.6f} ({data['tokens']:,} tokens, {data['requests']} requests)"
        
        return summary
        
    except Exception as e:
        return f"Error generating cost summary: {e}"


@tool 
def flush_cost_metrics() -> str:
    """Flush any buffered cost metrics to CloudWatch"""
    if not COST_LOGGING_AVAILABLE or cost_monitoring_agent is None:
        return "Cost monitoring not available"
    
    try:
        cost_monitoring_agent.flush_all_metrics()
        return "Cost metrics flushed successfully"
    except Exception as e:
        return f"Error flushing metrics: {e}"


if __name__ == "__main__":
    # Example usage
    logger.info("Initializing Cloud Engineer...")
    logger.info(f"Health check: {health_check()}")

    # Test with different tasks
    test_cases = [
        "List all CloudFormation stacks",
        "Show me EC2 instances",
        "What S3 buckets do I have?",
    ]

    for task in test_cases:
        logger.info(f"Testing: {task}")
        result = execute_custom_task(task)
        logger.info(f"Result: {result}")

    logger.info(f"Final health check: {health_check()}")


# Register cleanup handler for MCP clients
atexit.register(cleanup)
