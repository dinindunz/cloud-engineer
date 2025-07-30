#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { CloudEngineerStack } from "../lib/cloud-engineer-stack";

const app = new cdk.App();
new CloudEngineerStack(app, "CloudEngineerStack", {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});
