# Surgical Code Fix System

## Overview

The Surgical Code Fix system provides Claude-like precision for CloudWatch error fixes using Bedrock. It replaces the complex multi-agent workflow with a focused, surgical approach that only modifies the exact problematic function.

## Architecture

### Three-Step Bedrock Workflow

1. **Planner Agent** (Bedrock Call #1)
   - Analyzes CloudWatch error log
   - Identifies exact file, function, and line number
   - Determines error type and likely cause
   - Returns structured JSON with precise location

2. **Editor Agent** (Bedrock Call #2)
   - Takes current function code + error context
   - Makes ONLY surgical changes to fix the specific error
   - Cannot modify code outside the target function
   - Returns complete fixed function with change description

3. **PR Creator** (GitHub MCP Tools)
   - Creates targeted pull request with minimal changes
   - Includes detailed description linking error to fix
   - Uses structured branch naming and PR templates

## Key Benefits

### 🎯 Surgical Precision
- **Function-Level Scope**: Only modifies the exact problematic function
- **No Refactoring**: Cannot improve or optimize unrelated code
- **Minimal Changes**: Smallest possible fix for the specific error
- **Constraint-Based**: Each Bedrock prompt has very narrow scope

### ⚡ Speed & Efficiency
- **3 Focused Calls**: Planner → Editor → PR Creator
- **Single Tool**: `surgical_code_fix(error_log, repo_name)`
- **No Coordination**: Avoids complex multi-agent workflows
- **Immediate Results**: Get PR URL and analysis in one response

### 🔒 Safety & Reliability
- **Error Handling**: Comprehensive try/catch with fallbacks
- **Validation**: Clear change types (ADD/MODIFY/REMOVE) with line numbers
- **Traceability**: Direct link from CloudWatch error to GitHub PR
- **Rollback Ready**: Minimal changes make rollbacks safer

## Usage

### Primary Tool: `surgical_code_fix()`

```python
# Called by orchestrator for CloudWatch errors
result = surgical_code_fix(
    error_log="[ERROR] AccessDeniedException: dynamodb:GetItem...",
    repo_name="myorg/user-service"  # From CloudWatch log tags
)
```

### Expected Output

```
✅ Surgical Code Fix Complete

🔍 Error Analysis:
- File: src/lambda_function.py
- Function: process_request
- Error Type: IAM_PERMISSION
- Root Cause: Recent deployment missing DynamoDB read permission

🔧 Fix Applied:
- Change Type: ADD
- Description: Added DynamoDB access permission check and error handling
- Lines Changed: [47, 48, 49]

📋 Pull Request:
- PR URL: https://github.com/myorg/user-service/pull/123
- PR Number: #123

⚡ Next Steps:
- Review and merge PR to resolve error
- Monitor CloudWatch for error resolution
```

## Integration Points

### Orchestrator Priority
The orchestrator now prioritizes surgical fixes:
1. **PRIMARY**: `surgical_code_fix()` for CloudWatch errors
2. **FALLBACK**: Specialist agents for complex scenarios

### Bedrock Prompts
- **Planner Prompt**: Constrained to return only location JSON
- **Editor Prompt**: Constrained to modify only the target function
- **JSON Parsing**: Robust extraction with error handling

### GitHub Integration
- Uses existing GitHub MCP tools for PR creation
- Structured branch naming: `surgical-fix/{repo}-{change-type}`
- Detailed PR descriptions with error correlation

## Error Types Handled

### IAM Permission Errors
- **Detection**: AccessDeniedException patterns
- **Fix**: Add missing permissions or error handling
- **Example**: Lambda can't access DynamoDB → Add IAM permission

### Timeout Errors
- **Detection**: Task timeout patterns
- **Fix**: Increase timeout values or optimize code
- **Example**: Lambda timeout → Increase timeout configuration

### Resource Not Found
- **Detection**: ResourceNotFoundException patterns
- **Fix**: Correct resource references or create missing resources
- **Example**: S3 bucket not found → Fix bucket name reference

### Configuration Errors
- **Detection**: Configuration mismatch patterns
- **Fix**: Correct configuration values
- **Example**: Wrong environment variable → Fix variable name

## Fallback Strategy

If surgical fix fails:
1. Log detailed error information
2. Return error message to orchestrator
3. Orchestrator can use specialist agents as fallback
4. Maintain system reliability

## Testing

Use the test script to validate functionality:

```bash
cd agent
python test_surgical_fixer.py
```

This demonstrates the three-step workflow with mock responses.

## Monitoring

The system provides detailed logging:
- Planner step success/failure
- Editor step success/failure
- PR creation success/failure
- Overall surgical fix results

Monitor CloudWatch logs for system health and performance metrics.
