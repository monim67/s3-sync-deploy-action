import * as path from "path";

import { Duration } from "aws-cdk-lib";
import { ActionBindOptions, ActionCategory, ActionConfig, IStage } from "aws-cdk-lib/aws-codepipeline";
import { S3DeployActionProps, Action } from "aws-cdk-lib/aws-codepipeline-actions";
import { PolicyStatement } from "aws-cdk-lib/aws-iam";
import { Runtime, Code, Function as LambdaFunction } from "aws-cdk-lib/aws-lambda";
import { Construct } from "constructs";

export type S3SyncDeployActionProps = S3DeployActionProps;

export class S3SyncDeployAction extends Action {
  private readonly props: S3SyncDeployActionProps;

  constructor(props: S3SyncDeployActionProps) {
    super({
      ...props,
      resource: props.bucket,
      category: ActionCategory.INVOKE,
      provider: "Lambda",
      artifactBounds: {
        minInputs: 1,
        maxInputs: 1,
        minOutputs: 0,
        maxOutputs: 0,
      },
      inputs: [props.input],
    });

    this.props = props;
  }

  protected bound(_scope: Construct, _stage: IStage, options: ActionBindOptions): ActionConfig {
    const syncFn = new LambdaFunction(_scope, "SyncFn", {
      runtime: Runtime.PYTHON_3_9,
      memorySize: 1024,
      timeout: Duration.seconds(60),
      handler: "index.handler",
      code: Code.fromAsset(path.join(path.dirname(__dirname), "src")),
      environment: {
        BUCKET_NAME: this.props.bucket.bucketName,
        ...(this.props.objectKey ? { BUCKET_PREFIX: this.props.objectKey } : {}),
      },
    });

    if (syncFn.role) {
      // pipeline needs permissions to read & write to the S3 bucket
      this.props.bucket.grantReadWrite(syncFn.role);

      if (this.props.accessControl !== undefined) {
        // we need to modify the ACL settings of objects within the Bucket,
        // so grant the Action's Role permissions to do that
        this.props.bucket.grantPutAcl(syncFn.role);
      }
    }

    // allow pipeline to list functions
    options.role.addToPrincipalPolicy(
      new PolicyStatement({
        actions: ["lambda:ListFunctions"],
        resources: ["*"],
      })
    );

    // allow pipeline to invoke this lambda functionn
    syncFn.grantInvoke(options.role);

    // the Action Role also needs to read from the Pipeline's bucket
    options.bucket.grantRead(options.role);

    // allow lambda to put job results for this pipeline
    // CodePipeline requires this to be granted to '*'
    // (the Pipeline ARN will not be enough)
    syncFn.addToRolePolicy(
      new PolicyStatement({
        resources: ["*"],
        actions: ["codepipeline:PutJobSuccessResult", "codepipeline:PutJobFailureResult"],
      })
    );

    return {
      configuration: {
        FunctionName: syncFn.functionName,
      },
    };
  }
}
