#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { AgentCoreStack } from '../lib/agent-core-stack';

const app = new cdk.App();
new AgentCoreStack(app, 'AgentCoreStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});