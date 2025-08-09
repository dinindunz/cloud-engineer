import json
import logging
import os
import requests

from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from strands_tools import calculator, current_time
from mcp.client.streamable_http import streamablehttp_client

# Import the AgentCore SDK
from bedrock_agentcore.runtime import BedrockAgentCoreApp

CLIENT_ID = "3a8r0k5tupqv1i2am4969a43a5"
CLIENT_SECRET = "he3fe5l9aeuk7n4j0b5qv0ojurbh7mllaubb6doi90rbvpbkbke"
TOKEN_URL = "https://agentcore-48a9ef63.auth.us-west-2.amazoncognito.com/oauth2/token"
MCP_URL = "http://CloudE-McpPr-ZTStjfTRWd3g-686078839.ap-southeast-2.elb.amazonaws.com/servers/aws-documentation/sse"

WELCOME_MESSAGE = """
Welcome to the Customer Support Assistant! How can I help you today?
"""

SYSTEM_PROMPT = """
You are an helpful customer support assistant.
When provided with a customer email, gather all necessary info and prepare the response email.
When asked about an order, look for it and tell the full description and date of the order to the customer.
Don't mention the customer ID in your reply.
"""

def fetch_access_token(client_id, client_secret, token_url):
    response = requests.post(
        token_url,
        data="grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}".format(client_id=client_id, client_secret=client_secret),
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    return response.json()['access_token']

def create_mcp_client(token: str) -> MCPClient:
    """
    Creates an MCP client with appropriate authentication.
    """
    def create_streamable_http_transport():
        return streamablehttp_client(
            MCP_URL,
            headers={"Authorization": f"Bearer {token}"}
        )
    
    return MCPClient(create_streamable_http_transport)

@tool
def get_customer_id(email_address: str) -> str:
    "Get customer ID from email address"
    if email_address == "me@example.net":
        response = { "customer_id": 123 }
    else:
        response = { "message": "customer not found" }
    try:
        return json.dumps(response)
    except Exception as e:
        return str(e)

@tool
def get_orders(customer_id: int) -> str:
    "Get orders from customer ID"
    if customer_id == 123:
        response = [{
            "order_id": 1234,
            "items": [ "smartphone", "smartphone USB-C charger", "smartphone black cover"],
            "date": "20250607"
        }]
    else:
        response = { "message": "no order found" }
    try:
        return json.dumps(response)
    except Exception as e:
        return str(e)

@tool
def get_knowledge_base_info(topic: str) -> str:
    "Get knowledge base info from topic"
    response = []
    if "smartphone" in topic:
        if "cover" in topic:
            response.append("To put on the cover, insert the bottom first, then push from the back up to the top.")
            response.append("To remove the cover, push the top and bottom of the cover at the same time.")
        if "charger" in topic:
            response.append("Input: 100-240V AC, 50/60Hz")
            response.append("Includes US/UK/EU plug adapters")
    if len(response) == 0:
        response = { "message": "no info found" }
    try:
        return json.dumps(response)
    except Exception as e:
        return str(e)

# Create an AgentCore app
app = BedrockAgentCoreApp()

# Global variables for MCP client and agent
mcp_client = None
agent = None

def initialize_agent():
    """Initialize agent with MCP tools if available, fallback to basic tools"""
    global mcp_client, agent
    
    # Basic tools that are always available
    basic_tools = [calculator, current_time, get_customer_id, get_orders, get_knowledge_base_info]
    
    try:
        # Get access token
        access_token = fetch_access_token(CLIENT_ID, CLIENT_SECRET, TOKEN_URL)
        
        # Create MCP client
        mcp_client = create_mcp_client(access_token)
        
        # Get MCP tools
        with mcp_client:
            mcp_tools = mcp_client.list_tools_sync()
            print(f"Found the following MCP tools: {[tool.name for tool in mcp_tools]}")
            
            # Combine basic tools with MCP tools
            all_tools = basic_tools + mcp_tools
            
            # Create agent with all tools
            agent = Agent(
                model="apac.amazon.nova-lite-v1:0",
                system_prompt=SYSTEM_PROMPT,
                tools=all_tools
            )
            print(f"Agent initialized with tools: {agent.tool_names}")
            
    except Exception as e:
        print(f"MCP initialization failed, using basic agent: {e}")
        # Fallback to basic agent
        agent = Agent(
            model="apac.amazon.nova-lite-v1:0",
            system_prompt=SYSTEM_PROMPT,
            tools=basic_tools
        )

# Initialize the agent at startup
initialize_agent()

# Specify the entry point function invoking the agent
@app.entrypoint
def invoke(payload):
    """Handler for agent invocation"""
    global agent, mcp_client
    
    user_message = payload.get(
        "prompt", "No prompt found in input, please guide customer to create a json payload with prompt key"
    )
    
    # If we have an MCP client, use it within context
    if mcp_client:
        with mcp_client:
            response = agent(user_message)
            return response.message['content'][0]['text']
    else:
        # Use basic agent without MCP
        response = agent(user_message)
        return response.message['content'][0]['text']

if __name__ == "__main__":
    app.run()
