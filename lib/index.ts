// import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
// import * as sqs from 'aws-cdk-lib/aws-sqs';

export interface S3SyncDeployActionProps {
  // Define construct properties here
}

export class S3SyncDeployAction extends Construct {

  constructor(scope: Construct, id: string, props: S3SyncDeployActionProps = {}) {
    super(scope, id);

    // Define construct contents here

    // example resource
    // const queue = new sqs.Queue(this, 'S3SyncDeployActionQueue', {
    //   visibilityTimeout: cdk.Duration.seconds(300)
    // });
  }
}
