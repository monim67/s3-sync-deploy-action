# s3-sync-deploy-action

S3SyncDeployAction is a drop in replacement for [S3DeployAction][S3DeployAction] AWS CDK toolkit
Codepipeline Action to deploying artifacts to S3. S3SyncDeployAction deploys to S3 like `aws
sync --delete` does. It syncs with S3 deleting any old non-existent file in artifact directory.

## Installation

```
npm install @monim67/s3-sync-deploy-action
```

or

```
yarn add @monim67/s3-sync-deploy-action
```

## Usage

Usage is similar to S3DeployAction.

```ts
import { S3SyncDeployAction } from "@monim67/s3-sync-deploy-action";

const deployAction = new S3SyncDeployAction({
  actionName: 'S3Deploy',
  bucket: targetBucket,
  input: sourceOutput,
});
```

 [S3DeployAction]: https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_codepipeline_actions.S3DeployAction.html
