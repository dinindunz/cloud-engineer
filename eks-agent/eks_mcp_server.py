#!/usr/bin/env python3
"""
Custom EKS MCP Server
Provides EKS-specific tools and resources via the Model Context Protocol
"""

import asyncio
import json
import logging
import subprocess
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the MCP server
server = Server("eks-mcp-server")

def run_aws_command(command: List[str]) -> Dict[str, Any]:
    """Execute AWS CLI command and return result"""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            try:
                # Try to parse as JSON if possible
                output = json.loads(result.stdout) if result.stdout.strip() else {}
            except json.JSONDecodeError:
                # If not JSON, return as text
                output = result.stdout.strip()
            
            return {
                "success": True,
                "output": output,
                "error": None
            }
        else:
            return {
                "success": False,
                "output": None,
                "error": result.stderr.strip()
            }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": None,
            "error": "Command timed out after 30 seconds"
        }
    except Exception as e:
        return {
            "success": False,
            "output": None,
            "error": str(e)
        }

@server.list_tools()
async def handle_list_tools() -> ListToolsResult:
    """List available EKS tools"""
    return ListToolsResult(
        tools=[
            Tool(
                name="list_eks_clusters",
                description="List all EKS clusters in the current region",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "region": {
                            "type": "string",
                            "description": "AWS region (optional, uses default if not specified)"
                        }
                    }
                }
            ),
            Tool(
                name="describe_eks_cluster",
                description="Get detailed information about a specific EKS cluster",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "cluster_name": {
                            "type": "string",
                            "description": "Name of the EKS cluster"
                        },
                        "region": {
                            "type": "string",
                            "description": "AWS region (optional, uses default if not specified)"
                        }
                    },
                    "required": ["cluster_name"]
                }
            ),
            Tool(
                name="list_eks_nodegroups",
                description="List node groups for a specific EKS cluster",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "cluster_name": {
                            "type": "string",
                            "description": "Name of the EKS cluster"
                        },
                        "region": {
                            "type": "string",
                            "description": "AWS region (optional, uses default if not specified)"
                        }
                    },
                    "required": ["cluster_name"]
                }
            ),
            Tool(
                name="describe_eks_nodegroup",
                description="Get detailed information about a specific EKS node group",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "cluster_name": {
                            "type": "string",
                            "description": "Name of the EKS cluster"
                        },
                        "nodegroup_name": {
                            "type": "string",
                            "description": "Name of the node group"
                        },
                        "region": {
                            "type": "string",
                            "description": "AWS region (optional, uses default if not specified)"
                        }
                    },
                    "required": ["cluster_name", "nodegroup_name"]
                }
            ),
            Tool(
                name="list_eks_addons",
                description="List add-ons for a specific EKS cluster",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "cluster_name": {
                            "type": "string",
                            "description": "Name of the EKS cluster"
                        },
                        "region": {
                            "type": "string",
                            "description": "AWS region (optional, uses default if not specified)"
                        }
                    },
                    "required": ["cluster_name"]
                }
            ),
            Tool(
                name="describe_eks_addon",
                description="Get detailed information about a specific EKS add-on",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "cluster_name": {
                            "type": "string",
                            "description": "Name of the EKS cluster"
                        },
                        "addon_name": {
                            "type": "string",
                            "description": "Name of the add-on"
                        },
                        "region": {
                            "type": "string",
                            "description": "AWS region (optional, uses default if not specified)"
                        }
                    },
                    "required": ["cluster_name", "addon_name"]
                }
            ),
            Tool(
                name="get_eks_cluster_health",
                description="Check the health status of an EKS cluster",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "cluster_name": {
                            "type": "string",
                            "description": "Name of the EKS cluster"
                        },
                        "region": {
                            "type": "string",
                            "description": "AWS region (optional, uses default if not specified)"
                        }
                    },
                    "required": ["cluster_name"]
                }
            ),
            Tool(
                name="list_eks_fargate_profiles",
                description="List Fargate profiles for a specific EKS cluster",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "cluster_name": {
                            "type": "string",
                            "description": "Name of the EKS cluster"
                        },
                        "region": {
                            "type": "string",
                            "description": "AWS region (optional, uses default if not specified)"
                        }
                    },
                    "required": ["cluster_name"]
                }
            )
        ]
    )

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """Handle tool calls"""
    
    try:
        if name == "list_eks_clusters":
            command = ["aws", "eks", "list-clusters"]
            if arguments.get("region"):
                command.extend(["--region", arguments["region"]])
            
            result = run_aws_command(command)
            
            if result["success"]:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"EKS Clusters:\n{json.dumps(result['output'], indent=2)}"
                        )
                    ]
                )
            else:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"Error listing EKS clusters: {result['error']}"
                        )
                    ],
                    isError=True
                )
        
        elif name == "describe_eks_cluster":
            command = ["aws", "eks", "describe-cluster", "--name", arguments["cluster_name"]]
            if arguments.get("region"):
                command.extend(["--region", arguments["region"]])
            
            result = run_aws_command(command)
            
            if result["success"]:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"EKS Cluster Details:\n{json.dumps(result['output'], indent=2)}"
                        )
                    ]
                )
            else:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"Error describing EKS cluster: {result['error']}"
                        )
                    ],
                    isError=True
                )
        
        elif name == "list_eks_nodegroups":
            command = ["aws", "eks", "list-nodegroups", "--cluster-name", arguments["cluster_name"]]
            if arguments.get("region"):
                command.extend(["--region", arguments["region"]])
            
            result = run_aws_command(command)
            
            if result["success"]:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"EKS Node Groups:\n{json.dumps(result['output'], indent=2)}"
                        )
                    ]
                )
            else:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"Error listing node groups: {result['error']}"
                        )
                    ],
                    isError=True
                )
        
        elif name == "describe_eks_nodegroup":
            command = [
                "aws", "eks", "describe-nodegroup",
                "--cluster-name", arguments["cluster_name"],
                "--nodegroup-name", arguments["nodegroup_name"]
            ]
            if arguments.get("region"):
                command.extend(["--region", arguments["region"]])
            
            result = run_aws_command(command)
            
            if result["success"]:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"EKS Node Group Details:\n{json.dumps(result['output'], indent=2)}"
                        )
                    ]
                )
            else:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"Error describing node group: {result['error']}"
                        )
                    ],
                    isError=True
                )
        
        elif name == "list_eks_addons":
            command = ["aws", "eks", "list-addons", "--cluster-name", arguments["cluster_name"]]
            if arguments.get("region"):
                command.extend(["--region", arguments["region"]])
            
            result = run_aws_command(command)
            
            if result["success"]:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"EKS Add-ons:\n{json.dumps(result['output'], indent=2)}"
                        )
                    ]
                )
            else:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"Error listing add-ons: {result['error']}"
                        )
                    ],
                    isError=True
                )
        
        elif name == "describe_eks_addon":
            command = [
                "aws", "eks", "describe-addon",
                "--cluster-name", arguments["cluster_name"],
                "--addon-name", arguments["addon_name"]
            ]
            if arguments.get("region"):
                command.extend(["--region", arguments["region"]])
            
            result = run_aws_command(command)
            
            if result["success"]:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"EKS Add-on Details:\n{json.dumps(result['output'], indent=2)}"
                        )
                    ]
                )
            else:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"Error describing add-on: {result['error']}"
                        )
                    ],
                    isError=True
                )
        
        elif name == "get_eks_cluster_health":
            # Get cluster details and check health indicators
            command = ["aws", "eks", "describe-cluster", "--name", arguments["cluster_name"]]
            if arguments.get("region"):
                command.extend(["--region", arguments["region"]])
            
            result = run_aws_command(command)
            
            if result["success"]:
                cluster_info = result["output"]
                cluster = cluster_info.get("cluster", {})
                status = cluster.get("status", "UNKNOWN")
                health = cluster.get("health", {})
                
                health_summary = {
                    "cluster_name": cluster.get("name"),
                    "status": status,
                    "health": health,
                    "version": cluster.get("version"),
                    "endpoint": cluster.get("endpoint"),
                    "created_at": cluster.get("createdAt")
                }
                
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"EKS Cluster Health:\n{json.dumps(health_summary, indent=2, default=str)}"
                        )
                    ]
                )
            else:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"Error checking cluster health: {result['error']}"
                        )
                    ],
                    isError=True
                )
        
        elif name == "list_eks_fargate_profiles":
            command = ["aws", "eks", "list-fargate-profiles", "--cluster-name", arguments["cluster_name"]]
            if arguments.get("region"):
                command.extend(["--region", arguments["region"]])
            
            result = run_aws_command(command)
            
            if result["success"]:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"EKS Fargate Profiles:\n{json.dumps(result['output'], indent=2)}"
                        )
                    ]
                )
            else:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"Error listing Fargate profiles: {result['error']}"
                        )
                    ],
                    isError=True
                )
        
        else:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Unknown tool: {name}"
                    )
                ],
                isError=True
            )
    
    except Exception as e:
        logger.error(f"Error in tool call {name}: {e}")
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Error executing tool {name}: {str(e)}"
                )
            ],
            isError=True
        )

async def main():
    """Main entry point for the EKS MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="eks-mcp-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities=None,
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
