# #####################################################################################################################
#  Copyright 2020-2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.                                       #
#                                                                                                                     #
#  Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance     #
#  with the License. A copy of the License is located at                                                              #
#                                                                                                                     #
#  http://www.apache.org/licenses/LICENSE-2.0                                                                         #
#                                                                                                                     #
#  or in the 'license' file accompanying this file. This file is distributed on an 'AS IS' BASIS, WITHOUT WARRANTIES  #
#  OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions     #
#  and limitations under the License.                                                                                 #
# #####################################################################################################################
from aws_cdk import (
    aws_s3 as s3,
    core,
)
from lib.blueprints.byom.pipeline_definitions.deploy_actions import (
    batch_transform,
    sagemaker_layer,
    create_invoke_lambda_custom_resource,
)
from lib.blueprints.byom.pipeline_definitions.sagemaker_role import create_sagemaker_role
from lib.blueprints.byom.pipeline_definitions.sagemaker_model import create_sagemaker_model
from lib.blueprints.byom.pipeline_definitions.templates_parameters import (
    create_blueprint_bucket_name_parameter,
    create_assets_bucket_name_parameter,
    create_algorithm_image_uri_parameter,
    create_batch_input_bucket_name_parameter,
    create_batch_inference_data_parameter,
    create_batch_job_output_location_parameter,
    create_custom_algorithms_ecr_repo_arn_parameter,
    create_inference_instance_parameter,
    create_kms_key_arn_parameter,
    create_model_artifact_location_parameter,
    create_model_name_parameter,
    create_custom_algorithms_ecr_repo_arn_provided_condition,
    create_kms_key_arn_provided_condition,
)


class BYOMBatchStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Parameteres #
        blueprint_bucket_name = create_blueprint_bucket_name_parameter(self)
        assets_bucket_name = create_assets_bucket_name_parameter(self)
        custom_algorithms_ecr_repo_arn = create_custom_algorithms_ecr_repo_arn_parameter(self)
        kms_key_arn = create_kms_key_arn_parameter(self)
        algorithm_image_uri = create_algorithm_image_uri_parameter(self)
        model_name = create_model_name_parameter(self)
        model_artifact_location = create_model_artifact_location_parameter(self)
        inference_instance = create_inference_instance_parameter(self)
        batch_input_bucket = create_batch_input_bucket_name_parameter(self)
        batch_inference_data = create_batch_inference_data_parameter(self)
        batch_job_output_location = create_batch_job_output_location_parameter(self)

        # Conditions
        custom_algorithms_ecr_repo_arn_provided = create_custom_algorithms_ecr_repo_arn_provided_condition(
            self, custom_algorithms_ecr_repo_arn
        )
        kms_key_arn_provided = create_kms_key_arn_provided_condition(self, kms_key_arn)

        # Resources #
        assets_bucket = s3.Bucket.from_bucket_name(self, "AssetsBucket", assets_bucket_name.value_as_string)
        # getting blueprint bucket object from its name - will be used later in the stack
        blueprint_bucket = s3.Bucket.from_bucket_name(self, "BlueprintBucket", blueprint_bucket_name.value_as_string)

        sm_layer = sagemaker_layer(self, blueprint_bucket)
        # creating a sagemaker model
        # create Sagemaker role
        sagemaker_role = create_sagemaker_role(
            self,
            "MLOpsSagemakerBatchRole",
            custom_algorithms_ecr_arn=custom_algorithms_ecr_repo_arn.value_as_string,
            kms_key_arn=kms_key_arn.value_as_string,
            assets_bucket_name=assets_bucket_name.value_as_string,
            input_bucket_name=batch_input_bucket.value_as_string,
            input_s3_location=batch_inference_data.value_as_string,
            output_s3_location=batch_job_output_location.value_as_string,
            ecr_repo_arn_provided_condition=custom_algorithms_ecr_repo_arn_provided,
            kms_key_arn_provided_condition=kms_key_arn_provided,
        )

        # create sagemaker model
        sagemaker_model = create_sagemaker_model(
            self,
            "MLOpsSagemakerModel",
            execution_role=sagemaker_role,
            primary_container={
                "image": algorithm_image_uri.value_as_string,
                "modelDataUrl": f"s3://{assets_bucket_name.value_as_string}/{model_artifact_location.value_as_string}",
            },
            tags=[{"key": "model_name", "value": model_name.value_as_string}],
        )

        # create batch tranform lambda
        batch_transform_lambda = batch_transform(
            self,
            "BatchTranformLambda",
            blueprint_bucket,
            assets_bucket,
            sagemaker_model.attr_model_name,
            inference_instance.value_as_string,
            batch_input_bucket.value_as_string,
            batch_inference_data.value_as_string,
            batch_job_output_location.value_as_string,
            core.Fn.condition_if(
                kms_key_arn_provided.logical_id, kms_key_arn.value_as_string, core.Aws.NO_VALUE
            ).to_string(),
            sm_layer,
        )

        # create custom resource to invoke the batch transform lambda
        invoke_lambda_custom_resource = create_invoke_lambda_custom_resource(
            self,
            "InvokeBatchLambda",
            batch_transform_lambda.function_arn,
            batch_transform_lambda.function_name,
            blueprint_bucket,
            {
                "Resource": "InvokeLambda",
                "function_name": batch_transform_lambda.function_name,
                "sagemaker_model_name": sagemaker_model.attr_model_name,
                "model_name": model_name.value_as_string,
                "inference_instance": inference_instance.value_as_string,
                "algorithm_image": algorithm_image_uri.value_as_string,
                "model_artifact": model_artifact_location.value_as_string,
                "assets_bucket": assets_bucket.bucket_name,
                "batch_inference_data": batch_inference_data.value_as_string,
                "batch_job_output_location": batch_job_output_location.value_as_string,
                "custom_algorithms_ecr_arn": custom_algorithms_ecr_repo_arn.value_as_string,
                "kms_key_arn": kms_key_arn.value_as_string,
            },
        )

        invoke_lambda_custom_resource.node.add_dependency(batch_transform_lambda)

        core.CfnOutput(
            self,
            id="ModelName",
            value=sagemaker_model.attr_model_name,
            description="The name of the SageMaker model used by the batch transform job",
        )

        core.CfnOutput(
            self,
            id="BatchTransformJobName",
            value=f"{sagemaker_model.attr_model_name}-batch-transform-*",
            description="The name of the SageMaker batch transform job",
        )

        core.CfnOutput(
            self,
            id="BatchTransformOutputLocation",
            value=f"https://s3.console.aws.amazon.com/s3/buckets/{batch_job_output_location.value_as_string}/",
            description="Output location of the batch transform. Our will be saved under the job name",
        )
