import json
import os
import urllib3
import hashlib
import time
import logging
import gzip
import base64
import boto3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Set
from cloud_engineer import execute_custom_task
from botocore.exceptions import ClientError

# Initialize DynamoDB client for duplicate detection
dynamodb = boto3.resource('dynamodb')
DUPLICATE_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'slack-message-deduplication')

# Configure logging for AWS Lambda
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Remove existing handlers to avoid duplicates
for handler in logger.handlers:
    logger.removeHandler(handler)

# Add console handler for CloudWatch
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# Initialize HTTP client
http = urllib3.PoolManager()

# In-memory cache for processed messages (for this Lambda execution)
processed_messages: Set[str] = set()

# Rate limiting
last_message_time = 0
MIN_MESSAGE_INTERVAL = 2  # seconds between messages


def generate_message_id(event_data: Dict[str, Any]) -> str:
    """Generate a unique ID for a message to prevent duplicates"""
    # Use timestamp, user, channel, and text hash to create unique ID
    content = f"{event_data.get('ts', '')}-{event_data.get('user', '')}-{event_data.get('channel', '')}-{event_data.get('text', '')}"
    return hashlib.md5(content.encode()).hexdigest()


def is_duplicate_message(message_id: str) -> bool:
    """Check if we've already processed this message using DynamoDB for cross-execution deduplication"""
    global processed_messages

    # First check in-memory cache for this execution
    if message_id in processed_messages:
        logger.info(f"Message {message_id} already processed in this execution")
        return True

    try:
        # Try to put the message ID in DynamoDB with a condition that it doesn't exist
        table = dynamodb.Table(DUPLICATE_TABLE_NAME)
        
        # Use conditional put to ensure atomicity
        table.put_item(
            Item={
                'message_id': message_id,
                'timestamp': int(time.time()),
                'ttl': int(time.time()) + 3600  # TTL of 1 hour
            },
            ConditionExpression='attribute_not_exists(message_id)'
        )
        
        # If we get here, the item was successfully added (not a duplicate)
        processed_messages.add(message_id)
        logger.info(f"Message {message_id} is new, processing...")
        return False
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            # Item already exists, this is a duplicate
            logger.info(f"Message {message_id} already processed by another execution")
            return True
        else:
            # Some other error occurred, log it but don't block processing
            logger.error(f"Error checking for duplicate message {message_id}: {e}")
            # Add to in-memory cache and allow processing to continue
            processed_messages.add(message_id)
            return False
    except Exception as e:
        # Any other exception, log and allow processing
        logger.error(f"Unexpected error in duplicate detection for {message_id}: {e}")
        processed_messages.add(message_id)
        return False


def should_rate_limit() -> bool:
    """Simple rate limiting to prevent spam"""
    global last_message_time
    current_time = time.time()

    if current_time - last_message_time < MIN_MESSAGE_INTERVAL:
        return True

    last_message_time = current_time
    return False


def is_bot_mentioned(text: str, bot_user_id: str) -> bool:
    """Check if message is directed at the bot - more precise detection"""
    if not text:
        return False

    # Direct mention
    if f"<@{bot_user_id}>" in text:
        return True


def get_user_info(user_id: str, bot_token: str) -> Dict[str, Any]:
    """Get user information from Slack API"""
    try:
        url = f"https://slack.com/api/users.info?user={user_id}"
        headers = {
            "Authorization": f"Bearer {bot_token}",
            "Content-Type": "application/json",
        }

        response = http.request("GET", url, headers=headers)
        return json.loads(response.data.decode("utf-8"))
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        return {}


def post_slack_message(
    channel: str, text: str, bot_token: str, thread_ts: str = None
) -> Dict[str, Any]:
    """Post message to Slack channel with optional threading"""
    try:
        url = "https://slack.com/api/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {bot_token}",
            "Content-Type": "application/json",
        }

        data = {
            "channel": channel,
            "text": text,
        }

        # Add thread support
        if thread_ts:
            data["thread_ts"] = thread_ts

        logger.info(f"Posting message to channel {channel}: {text[:100]}...")

        response = http.request(
            "POST", url, body=json.dumps(data).encode("utf-8"), headers=headers
        )
        result = json.loads(response.data.decode("utf-8"))

        logger.debug(f"Slack API response: {result}")
        return result
    except Exception as e:
        error_msg = f"Error posting message: {e}"
        logger.error(error_msg)
        return {"ok": False, "error": str(e)}


def execute_aws_agent(prompt: str) -> Dict[str, Any]:
    """Execute AWS Cloud Engineer agent with prompt"""
    try:
        logger.info(f"Executing AWS agent with prompt: {prompt}")

        # Execute the task using the fixed cloud_engineer module
        result = execute_custom_task(prompt)

        return {"success": True, "result": result, "prompt": prompt}
    except Exception as e:
        logger.error(f"Error executing AWS agent: {e}")
        return {"success": False, "error": str(e), "prompt": prompt}


def format_slack_response(agent_result: Dict[str, Any]) -> str:
    """Format agent response for Slack"""
    if not agent_result.get("success"):
        return f"❌ **AWS Cloud Engineer Error:** {agent_result.get('error', 'Unknown error')}"

    result = agent_result.get("result", "")

    # Truncate if too long (Slack has message limits)
    if len(result) > 3000:
        result = result[:2900] + "\n\n... (truncated for Slack)"

    return f"🤖 **AWS Cloud Engineer Response:**\n```\n{result}\n```"


def create_audit_log(
    event_data: Dict[str, Any],
    user_info: Dict[str, Any],
    aws_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create comprehensive audit log"""
    user_data = user_info.get("user", {})
    profile = user_data.get("profile", {})

    audit_log = {
        "timestamp": datetime.utcnow().isoformat(),
        "userId": event_data.get("user"),
        "userEmail": profile.get("email", "email-not-available"),
        "userName": user_data.get("real_name") or user_data.get("name", "unknown"),
        "channel": event_data.get("channel"),
        "messageType": event_data.get("type"),
        "messageText": event_data.get("text"),
        "messageLength": len(event_data.get("text", "")),
        "messageId": generate_message_id(event_data),
        "threadTs": event_data.get("thread_ts"),
    }

    # Add AWS-specific fields if applicable
    if aws_result:
        audit_log.update(
            {
                "awsAction": "custom_task",
                "awsSuccess": aws_result.get("success", False),
                "awsPrompt": aws_result.get("prompt"),
                "responseLength": (
                    len(aws_result.get("result", "")) if aws_result else 0
                ),
            }
        )

    return audit_log


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for Slack integration with AWS Cloud Engineer
    """
    logger.info("Slack event: %s", json.dumps(event, indent=2))

    try:
        # Parse the request body
        body = json.loads(event.get("body", "{}"))

        # Handle Slack URL verification challenge
        if "challenge" in body:
            return {"statusCode": 200, "body": body["challenge"]}

        # Get environment variables
        bot_token = os.environ.get("SLACK_BOT_TOKEN")
        bot_user_id = os.environ.get("SLACK_BOT_USER_ID")

        # Check if this is a CloudWatch Logs event
        if "awslogs" in event:
            # Decode CloudWatch Logs data
            compressed_payload = base64.b64decode(event["awslogs"]["data"])
            uncompressed_payload = gzip.decompress(compressed_payload)
            log_data = json.loads(uncompressed_payload)

            log_group = log_data["logGroup"]
            log_stream = log_data["logStream"]

            # Fetch GitHub repo from CloudWatch Log Group tags
            logs_client = boto3.client("logs")
            github_repo = "unknown"

            try:
                response = logs_client.list_tags_log_group(logGroupName=log_group)
                tags = response.get("tags", {})
                github_repo = tags.get("GitHubRepo", "unknown")
            except Exception as tag_error:
                logger.warning(
                    f"Could not fetch tags for {log_group}: {str(tag_error)}"
                )

            logger.info(f"Processing CloudWatch Logs from: {log_group}")
            logger.info(f"GitHub Repository: {github_repo}")

            # Process each log event
            for log_event in log_data["logEvents"]:
                message = log_event["message"]
                timestamp = log_event["timestamp"]

                if any(
                    error_keyword in message
                    for error_keyword in ["ERROR", "Exception", "Failed"]
                ):
                    logger.info(f"Error detected in {log_group}")
                    logger.info(f"Error Message: {message}")
                    logger.info(f"GitHub Repo: {github_repo}")

                    error_data = {
                        "source": "cloudwatch_logs",
                        "github_repo": github_repo,
                        "log_group": log_group,
                        "log_stream": log_stream,
                        "error_message": message,
                        "timestamp": timestamp,
                    }

                    error_data_json = json.dumps(error_data, indent=2)
                    logger.info(f"Strands processing: {error_data_json}")

            # Execute the AWS Cloud Engineer agent with context
            agent_result = execute_aws_agent(
                "Follow the system prompt exactly - apply ONLY the specific fix needed, no broader improvements. Remember: Your role is automated incident response with minimal, targeted fixes only. No improvements beyond fixing the specific error."
                + error_data_json
            )

            # Format and post response to Slack
            slack_response = format_slack_response(agent_result)
            post_result = post_slack_message("C02JWK1LN9X", slack_response, bot_token)

            return {
                "statusCode": 200,
                "body": json.dumps("Successfully processed CloudWatch Logs"),
            }

        # Handle actual Slack events
        if "event" in body:
            event_data = body["event"]
            event_type = event_data.get("type")
            text = event_data.get("text", "")
            user = event_data.get("user")
            channel = event_data.get("channel")
            bot_id = event_data.get("bot_id")
            thread_ts = event_data.get("thread_ts")

            # Ignore bot messages to prevent loops
            if bot_id:
                return {"statusCode": 200, "body": json.dumps({"message": "OK"})}

            # Check for duplicate messages
            message_id = generate_message_id(event_data)
            if is_duplicate_message(message_id):
                logger.info(f"Skipping duplicate message: {message_id}")
                return {
                    "statusCode": 200,
                    "body": json.dumps({"message": "Duplicate message ignored"}),
                }

            # Rate limiting
            if should_rate_limit():
                logger.warning("Rate limited - skipping message")
                return {
                    "statusCode": 200,
                    "body": json.dumps({"message": "Rate limited"}),
                }

            if not bot_token:
                logger.error(
                    "Error: SLACK_BOT_TOKEN not found in environment variables"
                )
                return {
                    "statusCode": 500,
                    "body": json.dumps({"error": "Missing bot token"}),
                }

            try:
                # Get user info
                user_info = get_user_info(user, bot_token)

                # Create basic audit log
                audit_log = create_audit_log(event_data, user_info)
                logger.info("AUDIT LOG: %s", json.dumps(audit_log, indent=2))

                # Check if this is an AWS-related message
                if text and is_bot_mentioned(text, bot_user_id):
                    logger.info(f"AWS bot mentioned by {audit_log['userEmail']}!")

                    # Respond to Slack immediately to prevent retries
                    immediate_response = {
                        "statusCode": 200,
                        "body": json.dumps({"message": "Processing your request..."})
                    }
                    
                    # Process the agent request asynchronously
                    try:
                        # Execute the AWS Cloud Engineer agent with context
                        agent_result = execute_aws_agent(text)

                        # Format and post response to Slack
                        slack_response = format_slack_response(agent_result)
                        post_result = post_slack_message(
                            channel, slack_response, bot_token, thread_ts
                        )

                        # Log the result
                        if post_result.get("ok"):
                            logger.info("AWS Cloud Engineer response posted successfully")
                        else:
                            logger.error(
                                f"Failed to post AWS Cloud Engineer response: {post_result.get('error', 'Unknown error')}"
                            )
                    except Exception as agent_error:
                        logger.error(f"Error in async agent processing: {agent_error}")
                        # Post error message to Slack
                        error_response = f"❌ **AWS Cloud Engineer Error:** {str(agent_error)}"
                        post_slack_message(channel, error_response, bot_token, thread_ts)
                    
                    # Return immediately to prevent Slack retries
                    return immediate_response

            except Exception as error:
                logger.error(f"Error processing message: {error}")

                # Fallback audit log
                fallback_audit_log = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "userId": user,
                    "userEmail": "error-fetching-email",
                    "channel": channel,
                    "messageType": event_type,
                    "messageText": text,
                    "messageId": message_id,
                    "error": str(error),
                }
                logger.warning(
                    "FALLBACK AUDIT LOG: %s", json.dumps(fallback_audit_log, indent=2)
                )

        return {"statusCode": 200, "body": json.dumps({"message": "OK"})}

    except Exception as e:
        logger.error(f"Lambda handler error: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


# Test function for local development
def test_lambda_handler():
    """Test function for local development"""
    test_event = {
        "body": json.dumps(
            {
                "event": {
                    "type": "message",
                    "text": "List CloudFormation stack names",
                    "user": "U123456789",
                    "channel": "C123456789",
                    "ts": "1234567890.123456",
                }
            }
        )
    }

    result = lambda_handler(test_event, None)
    logger.info("Test result: %s", json.dumps(result, indent=2))


if __name__ == "__main__":
    test_lambda_handler()
