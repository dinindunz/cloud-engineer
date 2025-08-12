import json
import os
import logging
from strands import Agent
from strands_tools import calculator, current_time, use_aws
from strands.tools.mcp import MCPClient
from mcp import StdioServerParameters, stdio_client

# Import the AgentCore SDK
from bedrock_agentcore.runtime import BedrockAgentCoreApp

custom_env = os.environ.copy()
custom_env["UV_CACHE_DIR"] = "/tmp/uv_cache"
custom_env["XDG_CACHE_HOME"] = "/tmp"

# Use logger configured in lambda_handler
logger = logging.getLogger(__name__)

WELCOME_MESSAGE = """
Welcome to the EKS Support Assistant! How can I help you today?
"""

SYSTEM_PROMPT = """
You are an EKS expert with deep knowledge of Amazon Elastic Kubernetes Service (EKS).
You can help with:
- EKS cluster management and troubleshooting
- Kubernetes workload deployment and management
- EKS networking and security configurations
- Node group management and autoscaling
- EKS add-ons and integrations
- Best practices for EKS operations

Use the available AWS tools to inspect, diagnose, and help resolve EKS-related issues.
"""

# Create an AgentCore app
app = BedrockAgentCoreApp()

# Global variable for agent
agent = None

def initialize_agent():
    """Initialize the EKS agent with available tools"""
    global agent

    if agent is None:
        # Initialize custom EKS MCP client
        eks_tools = []
        try:
            eks_mcp_client = MCPClient(
                lambda: stdio_client(
                    StdioServerParameters(
                        command="python",
                        args=[os.path.join(os.path.dirname(__file__), "eks_mcp_server.py")],
                        env=custom_env,
                    )
                )
            )
            eks_mcp_client.start()
            eks_tools = eks_mcp_client.list_tools_sync()
            logger.info(f"EKS MCP client initialized successfully with {len(eks_tools)} tools")
        except Exception as e:
            logger.warning(f"Failed to initialize EKS MCP client: {e}")
            logger.info("Agent will continue without EKS-specific tools")

        # Combine basic tools with EKS-specific tools
        all_tools = [calculator, current_time, use_aws] + eks_tools
        
        agent = Agent(
            model="apac.anthropic.claude-sonnet-4-20250514-v1:0",
            system_prompt=SYSTEM_PROMPT,
            tools=all_tools,
        )

    return agent

# Specify the entry point function invoking the agent
@app.entrypoint
def invoke(payload):
    """Handler for agent invocation"""
    user_message = payload.get(
        "prompt", "No prompt found in input, please guide customer to create a json payload with prompt key"
    )
    agent = initialize_agent()
    response = agent(user_message)
    return response.message['content'][0]['text']
    
if __name__ == "__main__":
    app.run()
