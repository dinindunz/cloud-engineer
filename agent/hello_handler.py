import boto3
import json
import logging
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Simple hello world Lambda handler for testing
    
    Args:
        event: Lambda event object
        context: Lambda context object
        
    Returns:
        API Gateway response with hello world message
    """
    logger.info(f"Received event: {json.dumps(event)}")

    client = boto3.client('bedrock-agentcore', region_name='ap-southeast-2')
    payload = json.dumps({"prompt": "Explain machine learning in simple terms"})

    response = client.invoke_agent_runtime(
        agentRuntimeArn='arn:aws:bedrock-agentcore:ap-southeast-2:354334841216:runtime/CloudEngineer-YxQzQ7DZlo',
        runtimeSessionId='dfmeoagmreaklgmrkleafremoigrmtesogmtrskhmtkrlshmt',  # Must be 33+ chars
        payload=payload,
        qualifier="DEFAULT" # Optional
    )
    response_body = response['response'].read()
    response_data = json.loads(response_body)
    print("Agent Response:", response_data)
    

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
        'body': json.dumps({'test': 'data'})
    }
    
    class MockContext:
        function_name = 'test-function'
        request_id = 'test-request-id'
    
    result = lambda_handler(test_event, MockContext())
    print(json.dumps(result, indent=2))
