import boto3
import json
import logging
import os
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler that invokes Bedrock AgentCore with payload from API request
    
    Args:
        event: Lambda event object containing API Gateway request
        context: Lambda context object
        
    Returns:
        API Gateway response with agent result
    """
    logger.info(f"Received event: {json.dumps(event)}")

    # Extract payload from request body
    body = json.loads(event.get('body', '{}'))
    payload = json.dumps(body.get('payload', {}))
    session_id = body.get('sessionId', f"session-{context.aws_request_id}")

    client = boto3.client('bedrock-agentcore', region_name='ap-southeast-2')

    response = client.invoke_agent_runtime(
        agentRuntimeArn='arn:aws:bedrock-agentcore:ap-southeast-2:354334841216:runtime/agent-pKC8v19ESw',
        runtimeSessionId=session_id,
        payload=payload,
        qualifier="DEFAULT"
    )
    response_body = response['response'].read()
    response_data = json.loads(response_body)
    logger.info("Agent Response received")

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(response_data)
    }


# For local testing
if __name__ == '__main__':
    test_event = {
        'httpMethod': 'POST',
        'path': '/cloud-engineer',
        'body': json.dumps({
            'payload': {'prompt': 'List all S3 buckets'},
            'sessionId': 'test-session-12345678901234567890123456789012'
        })
    }
    
    class MockContext:
        function_name = 'test-function'
        request_id = 'test-request-id'
    
    result = lambda_handler(test_event, MockContext())
    print(json.dumps(result, indent=2))
