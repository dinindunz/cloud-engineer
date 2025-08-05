# Root Cause Analysis Demo

This demo showcases the Cloud Engineer Agent's systematic approach to investigating and diagnosing complex AWS infrastructure issues, specifically a CloudFormation deployment failure caused by organizational policies.

## Investigation Overview

The Cloud Engineer Agent methodically investigates a CloudFormation deployment failure by:
1. Analyzing the initial problem and checking service limits
2. Examining IAM permissions and policies
3. Testing different CloudFormation operations to isolate the issue
4. Identifying AWS Organizations Service Control Policies as the root cause
5. Providing comprehensive findings and actionable solutions

## Demo Screenshots

### 1. Initial Problem and Analysis
![Initial Problem and Analysis](01_cfn_api_access_issue.png)
*Agent begins investigation of CloudFormation API deployment failure, checking service limits and IAM permissions*

### 2. Discovering SCP Restrictions
![Discovering SCP Restrictions](02_analysis.png)
*Agent identifies pattern of operations being cancelled and discovers AWS Organization with Service Control Policies*

### 3. Further Analysis and Read-only Operations
![Further Analysis and Read-only Operations](03_analysis.png)
*Agent tests read-only CloudFormation operations to narrow down specific restrictions and confirm access patterns*

### 4. Investigation Results
![Investigation Results](04_analysis.png)
*Agent clearly identifies AWS Organizations Service Control Policies as the root cause blocking CloudFormation operations*

### 5. Full Report and Solutions
![Full Report and Solutions](05_investigation_results.png)
*Comprehensive final report with detailed explanation of SCPs and multiple solution approaches*

## Key Features Demonstrated

- **Systematic Investigation**: Methodical approach to diagnosing complex infrastructure issues
- **Multi-layer Analysis**: Examination of service limits, IAM permissions, and organizational policies
- **Pattern Recognition**: Identification of specific error patterns indicating SCP restrictions
- **Root Cause Identification**: Clear determination that SCPs override IAM Admin permissions
- **Solution-Oriented Reporting**: Comprehensive recommendations including alternative deployment methods
- **Evidence-Based Conclusions**: Detailed documentation of findings with supporting evidence
- **Operational Context**: Understanding of AWS Organizations hierarchy and policy precedence
