#!/usr/bin/env python3
"""
Simple Atlassian MCP Server
Supports basic Jira operations using API tokens
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List
import requests
from requests.auth import HTTPBasicAuth

# MCP protocol messages
class MCPServer:
    def __init__(self):
        self.email = os.getenv('ATLASSIAN_EMAIL')
        self.api_token = os.getenv('ATLASSIAN_API_TOKEN')
        self.instance_url = os.getenv('ATLASSIAN_INSTANCE_URL')
        
        if not all([self.email, self.api_token, self.instance_url]):
            raise ValueError("Missing required environment variables: ATLASSIAN_EMAIL, ATLASSIAN_API_TOKEN, ATLASSIAN_INSTANCE_URL")
        
        self.auth = HTTPBasicAuth(self.email, self.api_token)
        self.session = requests.Session()
        self.session.auth = self.auth

    def send_response(self, response: Dict[str, Any]):
        """Send JSON response to stdout"""
        print(json.dumps(response), flush=True)

    def send_error(self, request_id: str, code: int, message: str):
        """Send error response"""
        self.send_response({
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        })

    async def handle_initialize(self, request_id: str, params: Dict[str, Any]):
        """Handle initialization request"""
        self.send_response({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "atlassian-mcp-server",
                    "version": "1.0.0"
                }
            }
        })

    async def handle_list_tools(self, request_id: str, params: Dict[str, Any]):
        """List available tools"""
        tools = [
            {
                "name": "search_jira_issues",
                "description": "Search Jira issues using JQL",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "jql": {
                            "type": "string",
                            "description": "JQL query to search issues"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 50)",
                            "default": 50
                        }
                    },
                    "required": ["jql"]
                }
            },
            {
                "name": "get_jira_issue",
                "description": "Get details of a specific Jira issue",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "issue_key": {
                            "type": "string",
                            "description": "Jira issue key (e.g., PROJ-123)"
                        }
                    },
                    "required": ["issue_key"]
                }
            },
            {
                "name": "create_jira_issue",
                "description": "Create a new Jira issue",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {
                            "type": "string",
                            "description": "Project key"
                        },
                        "summary": {
                            "type": "string",
                            "description": "Issue summary"
                        },
                        "description": {
                            "type": "string",
                            "description": "Issue description"
                        },
                        "issue_type": {
                            "type": "string",
                            "description": "Issue type (e.g., Bug, Task, Story)",
                            "default": "Task"
                        }
                    },
                    "required": ["project_key", "summary"]
                }
            }
        ]

        self.send_response({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": tools
            }
        })

    async def handle_call_tool(self, request_id: str, params: Dict[str, Any]):
        """Handle tool execution"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        try:
            if tool_name == "search_jira_issues":
                result = await self.search_jira_issues(arguments)
            elif tool_name == "get_jira_issue":
                result = await self.get_jira_issue(arguments)
            elif tool_name == "create_jira_issue":
                result = await self.create_jira_issue(arguments)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")

            self.send_response({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            })

        except Exception as e:
            self.send_error(request_id, -32603, f"Tool execution failed: {str(e)}")

    async def search_jira_issues(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Search Jira issues using JQL"""
        jql = arguments["jql"]
        max_results = arguments.get("max_results", 50)

        url = f"{self.instance_url}/rest/api/3/search"
        params = {
            "jql": jql,
            "maxResults": max_results,
            "fields": "summary,status,assignee,created,updated,priority,issuetype"
        }

        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        return response.json()

    async def get_jira_issue(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get specific Jira issue details"""
        issue_key = arguments["issue_key"]
        
        url = f"{self.instance_url}/rest/api/3/issue/{issue_key}"
        
        response = self.session.get(url)
        response.raise_for_status()
        
        return response.json()

    async def create_jira_issue(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Jira issue"""
        project_key = arguments["project_key"]
        summary = arguments["summary"]
        description = arguments.get("description", "")
        issue_type = arguments.get("issue_type", "Task")

        url = f"{self.instance_url}/rest/api/3/issue"
        
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": description
                                }
                            ]
                        }
                    ]
                },
                "issuetype": {"name": issue_type}
            }
        }

        response = self.session.post(url, json=payload)
        response.raise_for_status()
        
        return response.json()

    async def process_request(self, request: str):
        """Process incoming JSON-RPC request"""
        try:
            data = json.loads(request.strip())
            method = data.get("method")
            request_id = data.get("id")
            params = data.get("params", {})

            if method == "initialize":
                await self.handle_initialize(request_id, params)
            elif method == "tools/list":
                await self.handle_list_tools(request_id, params)
            elif method == "tools/call":
                await self.handle_call_tool(request_id, params)
            else:
                self.send_error(request_id, -32601, f"Method not found: {method}")
                
        except json.JSONDecodeError:
            self.send_error(None, -32700, "Parse error")
        except Exception as e:
            self.send_error(None, -32603, f"Internal error: {str(e)}")

    async def run(self):
        """Main server loop"""
        try:
            for line in sys.stdin:
                if line.strip():
                    await self.process_request(line)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"Server error: {e}", file=sys.stderr)

if __name__ == "__main__":
    server = MCPServer()
    asyncio.run(server.run())