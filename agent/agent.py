from cloud_engineer import execute_custom_task
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload):
    """Handler for Bedrock agent invocation"""
    # Extract the prompt from the payload
    user_message = payload.get(
        "prompt",
        payload.get("inputText", "No prompt found in input")
    )

    logger.info(f"Bedrock agent invoked with prompt: {user_message}")

    # Execute the cloud engineer task directly
    result = execute_custom_task(user_message)

    logger.info(f"Task execution completed, result length: {len(result)}")

    # Return the result as plain text (Bedrock Agent Core expects string response)
    return result


if __name__ == "__main__":
    app.run()

