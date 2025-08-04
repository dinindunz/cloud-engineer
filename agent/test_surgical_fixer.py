#!/usr/bin/env python3
"""
Test script for the Surgical Code Fixer
Demonstrates the Claude-like agentic precision approach
"""

import json
from surgical_code_fixer import SurgicalCodeFixer

# Mock Bedrock model for testing
class MockBedrockModel:
    def __call__(self, prompt):
        # Mock agent response that simulates the agentic workflow
        if "Please fix this CloudWatch error using surgical precision" in prompt:
            return """
I'll analyze this CloudWatch error and fix it using surgical precision.

Step 1: Analyzing the error location...
Based on the error log, I can identify:
- File: src/lambda_function.py
- Function: process_request
- Error Type: IAM_PERMISSION
- Issue: Lambda cannot access DynamoDB table

Step 2: Retrieving current function code...
Current function retrieved from GitHub.

Step 3: Generating surgical fix...
I've identified the minimal change needed: add DynamoDB access permission check.

Step 4: Creating pull request...
✅ Pull Request Created

**Title**: Fix: Added DynamoDB access permission check and error handling
**URL**: https://github.com/myorg/user-service/pull/123
**Branch**: surgical-fix/myorg-user-service-add

**Summary**: Surgical fix applied with minimal changes to resolve CloudWatch error.

## Summary
Successfully applied surgical fix to resolve IAM permission error. The fix adds only the necessary DynamoDB access check without modifying any other code.
"""
        return "Mock response"

def test_surgical_fixer():
    """Test the surgical code fixer with a mock CloudWatch error"""
    
    # Mock CloudWatch error log
    error_log = """
    [ERROR] 2025-01-04T17:00:00.000Z RequestId: abc-123 
    An error occurred (AccessDeniedException) when calling the GetItem operation: 
    User: arn:aws:sts::123456789012:assumed-role/lambda-execution-role/lambda-function 
    is not authorized to perform: dynamodb:GetItem on resource: 
    arn:aws:dynamodb:ap-southeast-2:123456789012:table/user-data
    """
    
    repo_name = "myorg/user-service"
    
    # Create surgical fixer with mock model
    mock_model = MockBedrockModel()
    surgical_fixer = SurgicalCodeFixer(mock_model, [])
    
    # Execute surgical fix
    result = surgical_fixer.fix_cloudwatch_error(error_log, repo_name)
    
    print("🔧 Surgical Code Fix Test Results:")
    print("=" * 50)
    
    if result.get("success"):
        print("✅ SUCCESS!")
        print(f"📋 PR URL: {result.get('pr_url', 'Not found')}")
        print(f"� Summary: {result.get('summary')}")
        print("\n🤖 Agent Response:")
        print(result.get('response', 'No response'))
    else:
        print(f"❌ FAILED: {result.get('error')}")
    
    print("\n🎯 Key Benefits Demonstrated:")
    print("- Precise error location identification")
    print("- Surgical function-level editing")
    print("- Minimal change approach")
    print("- Automated PR creation")
    print("- No unnecessary refactoring")

if __name__ == "__main__":
    test_surgical_fixer()
