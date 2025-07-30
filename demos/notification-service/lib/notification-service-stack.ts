import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import { LambdaDestination } from 'aws-cdk-lib/aws-logs-destinations';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export class NotificationServiceStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // GitHub repository name - change this to your actual repo
    const githubRepoName = 'my-company/notification-service';

    // 1. Create SNS Topic for notifications
    const notificationTopic = new sns.Topic(this, 'NotificationTopic', {
      topicName: 'user-notifications',
      displayName: 'User Notifications'
    });

    // 3. Get the log group for the notification lambda and add tags
    const notificationLogGroup = new logs.LogGroup(this, 'NotificationServiceLogGroup', {
      logGroupName: '/aws/lambda/notification-service',
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // 2. Create the notification service lambda
    // This lambda will have insufficient permissions intentionally
    const notificationLambda = new lambda.Function(this, 'NotificationService', {
      functionName: 'notification-service',
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: 'index.handler',
      logGroup: notificationLogGroup,
      timeout: cdk.Duration.seconds(30),
      code: lambda.Code.fromInline(`
const { SNSClient, PublishCommand } = require('@aws-sdk/client-sns');

exports.handler = async (event) => {
    const sns = new SNSClient({});
    
    // Extract message from event
    const message = event.message || 'Default notification message';
    const subject = event.subject || 'Notification';
    
    try {
        const command = new PublishCommand({
            TopicArn: '${notificationTopic.topicArn}',
            Subject: subject,
            Message: message
        });
        
        const response = await sns.send(command);
        console.log(\`Successfully sent notification with MessageId: \${response.MessageId}\`);
        
        return {
            statusCode: 200,
            body: JSON.stringify({ status: 'success', messageId: response.MessageId })
        };
    } catch (error) {
        console.error(\`Failed to send notification: \${error.message}\`);
        throw error;
    }
};
      `),
      // Intentionally NOT granting SNS permissions
    });

    // Add GitHub repo name as a tag to the log group
    cdk.Tags.of(notificationLambda).add('GitHubRepo', githubRepoName);
    cdk.Tags.of(notificationLambda).add('Service', 'NotificationService');

    // 4. Create the cloud_agent lambda (your existing strands lambda)
    const cloudAgentLambda = lambda.Function.fromFunctionArn(
      this,
      'ImportedLambda',
      'arn:aws:lambda:ap-southeast-2:722141136946:function:CloudEngineerStack-CloudEngineerFunction386E0CF3-3OVQmdnDF2BB'
    );

    new lambda.CfnPermission(this, 'AllowCWLogsInvokeLambda', {
      action: 'lambda:InvokeFunction',
      functionName: cloudAgentLambda.functionArn,
      principal: 'logs.amazonaws.com',
      sourceArn: notificationLogGroup.logGroupArn,
    });

    // 6. Create CloudWatch Logs Subscription Filter with explicit dependency
    const subscriptionFilter = new logs.SubscriptionFilter(this, 'ErrorSubscriptionFilter', {
      logGroup: notificationLogGroup,
      destination: new LambdaDestination(cloudAgentLambda),
      filterPattern: logs.FilterPattern.anyTerm('ERROR', 'Exception', 'Failed'),
      filterName: 'ErrorsToCloudAgent'
    });

    // Output information
    new cdk.CfnOutput(this, 'NotificationServiceArn', {
      value: notificationLambda.functionArn,
      description: 'ARN of the notification service lambda'
    });

    new cdk.CfnOutput(this, 'CloudAgentArn', {
      value: cloudAgentLambda.functionArn,
      description: 'ARN of the cloud agent lambda'
    });

    new cdk.CfnOutput(this, 'SNSTopicArn', {
      value: notificationTopic.topicArn,
      description: 'ARN of the SNS notification topic'
    });
  }
}