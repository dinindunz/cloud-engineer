import os
import logging
from strands import Agent
from strands.tools.mcp import MCPClient
from strands.models import BedrockModel
from mcp import StdioServerParameters, stdio_client
from strands_tools import use_aws
from typing import Dict, List, Optional, Any, Union
import json
import re
import pathlib

custom_env = os.environ.copy()
custom_env["UV_CACHE_DIR"] = "/tmp/uv_cache"
custom_env["XDG_CACHE_HOME"] = "/tmp"

# Use logger configured in lambda_handler
logger = logging.getLogger(__name__)

# Global variables for MCP client and agent
agent = None
mcp_initialized = False

# Model creation will happen during agent initialization
bedrock_model = None

# Enhanced system prompt for the agent
system_prompt = """
You are an expert AWS Cloud Engineer assistant integrated with Slack. Your job is to help with AWS infrastructure 
management, optimization, security, and best practices.

When triggered by an error in CloudWatch logs, you must:
1. Analyze the CloudWatch log error and summarize the issue.
2. Use the Jira MCP server to create a new Jira ticket describing the issue. The ticket should have an appropriate heading and a clear, actionable description based on the log error.
3. Use the GitHub MCP server to raise a new Pull Request (PR) in the relevant GitHub repository (the repository name can be determined from the tag provided by the agent). The PR should reference the Jira ticket and include any necessary changes or notes to address the issue.

You also have access to the AWS Documentation MCP server. Use it to look up official AWS documentation, best practices, and step-by-step guides when needed to provide authoritative answers or to support your recommendations.

**GENERAL INSTRUCTIONS:**
- Always use the AWS region specified in the AWS_REGION environment variable for all operations.
- Provide clear, actionable advice with specific AWS CLI commands or console steps when applicable.
- Focus on security best practices and cost optimization in your recommendations.
- When users ask to "list" resources, provide a clear, organized list format.
- Be specific and direct in your responses.
- Never include <thinking> tags or expose your internal thought process.

**CONTEXT AWARENESS:**
- You're responding to Slack messages, so keep responses concise but informative.
- Users expect quick, accurate answers to their AWS questions.
- If a user asks for something specific (like "list stack names"), focus only on that request.
- Don't provide unnecessary background information unless specifically asked.
- Always operate in the region specified by AWS_REGION environment variable.

**JIRA & GITHUB INTEGRATION:**
- When an error is detected in CloudWatch logs, always:
    - Summarize the error.
    - Create a Jira ticket using the Jira MCP server with a relevant heading and description.
    - Raise a new PR in the appropriate GitHub repository using the GitHub MCP server, referencing the Jira ticket.
    - Ensure all actions are logged and clearly communicated in your response.

**AWS DOCUMENTATION MCP SERVER:**
- Use the AWS Documentation MCP server to search for and cite official AWS documentation, best practices, and implementation details as needed.
- Reference documentation links or summaries in your responses when it helps the user.
"""


def create_bedrock_model() -> BedrockModel:
    """Create a BedrockModel with fallback options"""
    region = os.environ.get("AWS_REGION", "ap-southeast-2")

    # List of model IDs to try in order of preference
    model_ids = [
        "anthropic.claude-3-5-sonnet-20241022-v2:0",  # Claude 3.5 Sonnet V2
        "anthropic.claude-3-5-sonnet-20240620-v1:0",  # Claude 3.5 Sonnet V1
        "anthropic.claude-3-haiku-20240307-v1:0",  # Claude 3 Haiku
        "anthropic.claude-3-sonnet-20240229-v1:0",  # Claude 3 Sonnet
    ]

    for model_id in model_ids:
        try:
            logger.info(f"Trying to create Bedrock model with ID: {model_id}")
            model = BedrockModel(
                model_id=model_id,
                region_name=region,
                temperature=0.1,  # Lower temperature for more focused responses
                max_tokens=2000,  # Reasonable limit for Slack responses
            )
            logger.info(f"Successfully created Bedrock model: {model_id}")
            return model
        except Exception as e:
            logger.warning(f"Model {model_id} not available: {e}")
            continue

    # If all models fail, raise the last exception
    raise Exception(
        "No Claude models are available in your AWS Bedrock account. Please check your AWS console."
    )


def initialize_mcp_client() -> Optional[List]:
    """Initialize multiple MCP clients from a server list in the MCP_SERVERS environment variable and return all tools"""

    global mcp_initialized

    # Get MCP server list from environment variable (expects a JSON array string)
    mcp_servers = json.loads(os.environ.get("MCP_SERVERS", "[]"))

    all_tools = []
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
            all_tools.extend(tools)
            logger.info(
                f"MCP client '{mcp_server}' initialized successfully with {len(tools)} tools"
            )
            mcp_initialized = True

        except ImportError as e:
            logger.warning(f"MCP dependencies not available for {mcp_server}: {e}")
        except Exception as e:
            logger.warning(f"Failed to initialize MCP client '{mcp_server}': {e}")
            logger.info(f"Agent will continue without {mcp_server} tools")

    return all_tools


def get_agent() -> Agent:
    """Get or create the agent instance"""
    global agent, bedrock_model

    if agent is None:
        # Create the Bedrock model if not already created
        if bedrock_model is None:
            bedrock_model = create_bedrock_model()

        # Initialize all MCP clients and get all tools
        all_mcp_tools = initialize_mcp_client()

        # Compose the agent with AWS tools and all MCP tools
        all_tools = [use_aws] + (all_mcp_tools or [])
        agent = Agent(tools=all_tools, model=bedrock_model, system_prompt=system_prompt)

    return agent


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


def execute_custom_task(task_description: str) -> str:
    """Execute a custom cloud engineering task based on description"""
    try:
        # Get the agent instance (will initialize if needed)
        agent_instance = get_agent()

        # Execute the agent
        response = agent_instance(task_description)

        logger.debug(f"Agent response type: {type(response)}")
        logger.debug(f"Agent response: {response}")

        # Clean and format the response
        result = clean_agent_response(response)

        return result
    except Exception as e:
        error_message = f"Error executing AWS task: {str(e)}"
        logger.error(error_message)
        return error_message


def health_check() -> Dict[str, Any]:
    """Health check function to verify system status"""
    return {
        "mcp_initialized": mcp_initialized,
        "agent_ready": agent is not None,
        "aws_region": os.environ.get("AWS_REGION", "ap-southeast-2"),
        "bedrock_model_ready": bedrock_model is not None,
    }


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
