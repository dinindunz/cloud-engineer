### Root Cause Analysis of AWS CloudFormation Deployment Failure

This document outlines the investigation and findings of a CloudFormation deployment failure, despite the presence of an Admin role. The analysis was performed by a "CloudAgent" and the process is documented in a series of screenshots.

#### Initial Problem Statement
The CloudAgent was tasked with investigating why a CloudFormation deployment was failing, even though the execution role had `Admin` permissions. The initial thought was to investigate CloudFormation service limits and permissions.

- **[Initial Problem and Analysis](01_cfn_api_access_issue.png)**
  - The agent begins by stating its intention to investigate the CloudFormation API deployment failure.
  - It plans to check service limits, permissions, and try a diagnostic approach.
  - It successfully finds credentials in environment variables and notes the CloudFormation limits appear fine.
  - The agent then proceeds to check the IAM permissions and policies attached to the Lambda execution role.

#### Discovering the Root Cause
As the investigation progressed, the agent discovered that the issue was not with the IAM role's permissions but with a higher-level organizational policy.

- **[Discovering SCP Restrictions](02_analysis.png)**
  - The agent notes a pattern where operations are being cancelled by the user, suggesting a policy is blocking CloudFormation stack creation.
  - It verifies that the account is part of an AWS Organization with Service Control Policies (SCPs) enabled.
  - The agent's attempts to create a stack with more verbose error handling lead to an `AccessDeniedException` and `ClientError`.

- **[Further Analysis and Read-only Operations](03_analysis.png)**
  - The agent continues its analysis by checking if any read-only CloudFormation operations work, which could help narrow down the specific restriction.
  - It attempts to create a change set instead of a stack, but this also fails.
  - The agent successfully performs read-only operations, confirming it has read access to CloudFormation, which provides a clearer picture of the issue.

#### Final Findings and Solution
The investigation concludes that AWS Organizations Service Control Policies (SCPs) are the root cause, overriding the IAM permissions granted to the Admin role.

- **[Investigation Results](04_analysis.png)**
  - The agent clearly states the root cause: AWS Organizations Service Control Policies (SCPs) are blocking CloudFormation stack creation operations.
  - Evidence includes:
    - The account is part of an AWS Organization with SCPs enabled.
    - CloudFormation `WRITE` operations (`create_stack`, `create_change_set`) are blocked.
    - The error pattern is typical for an SCP denial, where the operation is "canceled by user."
    - While the Lambda Execution Role has Admin permissions, the SCPs take precedence.

- **[Full Report and Solutions](05_investigation_results.png)**
  - The final report from the CloudAgent is provided.
  - It defines SCPs as "guardrails" that set the maximum permissions for accounts and can override IAM permissions.
  - The report explains why other operations, like basic EC2 actions, might still work, as SCPs are often used to enforce controlled deployment methods.
  - It proposes several solutions:
    - Contacting the AWS Organization Administrator to review and modify the SCPs.
    - Temporarily allowing CloudFormation operations.
    - Adding an exception for the specific use case.
    - Suggesting alternative deployment methods, such as using AWS CDK, if it's allowed.