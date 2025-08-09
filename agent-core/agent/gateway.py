import requests
import json

CLIENT_ID = "3a8r0k5tupqv1i2am4969a43a5"
CLIENT_SECRET = "he3fe5l9aeuk7n4j0b5qv0ojurbh7mllaubb6doi90rbvpbkbke"
TOKEN_URL = "https://agentcore-48a9ef63.auth.us-west-2.amazoncognito.com/oauth2/token"

def fetch_access_token(client_id, client_secret, token_url):
  response = requests.post(
    token_url,
    data="grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}".format(client_id=client_id, client_secret=client_secret),
    headers={'Content-Type': 'application/x-www-form-urlencoded'}
  )

  return response.json()['access_token']

def list_tools(gateway_url, access_token):
  headers = {
      "Content-Type": "application/json",
      "Authorization": f"Bearer {access_token}"
  }

  payload = {
      "jsonrpc": "2.0",
      "id": "list-tools-request",
      "method": "tools/list"
  }

  response = requests.post(gateway_url, headers=headers, json=payload)
  return response.json()

# Example usage
gateway_url = "https://testgateway8133eb36-xv3qkhhwnh.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp"
access_token = fetch_access_token(CLIENT_ID, CLIENT_SECRET, TOKEN_URL)
tools = list_tools(gateway_url, access_token)
print(json.dumps(tools, indent=2))