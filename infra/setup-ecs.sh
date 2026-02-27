#!/usr/bin/env bash
set -euo pipefail

AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-848269696611}"
AWS_REGION="${AWS_REGION:-us-east-1}"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECS_CLUSTER="${ECS_CLUSTER:-nexusbrain-training}"

# Create CloudWatch log groups
echo "Creating CloudWatch log groups..."
aws logs create-log-group --log-group-name /ecs/agentbench-green --region "$AWS_REGION" 2>/dev/null || echo "/ecs/agentbench-green already exists"
aws logs create-log-group --log-group-name /ecs/agentbench-purple --region "$AWS_REGION" 2>/dev/null || echo "/ecs/agentbench-purple already exists"

echo "Registering ECS task definitions..."

# Green Agent task definition
aws ecs register-task-definition --cli-input-json "{
  \"family\": \"agentbench-green\",
  \"networkMode\": \"awsvpc\",
  \"requiresCompatibilities\": [\"FARGATE\"],
  \"cpu\": \"512\",
  \"memory\": \"1024\",
  \"executionRoleArn\": \"arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole\",
  \"containerDefinitions\": [{
    \"name\": \"green-agent\",
    \"image\": \"${ECR_REGISTRY}/agentbench-green:latest\",
    \"portMappings\": [{\"containerPort\": 9009, \"protocol\": \"tcp\"}],
    \"essential\": true,
    \"environment\": [
      {\"name\": \"PORT\", \"value\": \"9009\"}
    ],
    \"logConfiguration\": {
      \"logDriver\": \"awslogs\",
      \"options\": {
        \"awslogs-group\": \"/ecs/agentbench-green\",
        \"awslogs-region\": \"${AWS_REGION}\",
        \"awslogs-stream-prefix\": \"ecs\"
      }
    }
  }]
}" --region "$AWS_REGION"

# Purple Agent task definition (with SSM secrets)
aws ecs register-task-definition --cli-input-json "{
  \"family\": \"agentbench-purple\",
  \"networkMode\": \"awsvpc\",
  \"requiresCompatibilities\": [\"FARGATE\"],
  \"cpu\": \"512\",
  \"memory\": \"1024\",
  \"executionRoleArn\": \"arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole\",
  \"containerDefinitions\": [{
    \"name\": \"purple-agent\",
    \"image\": \"${ECR_REGISTRY}/agentbench-purple:latest\",
    \"portMappings\": [{\"containerPort\": 9010, \"protocol\": \"tcp\"}],
    \"essential\": true,
    \"environment\": [
      {\"name\": \"BRAINOS_API_URL\", \"value\": \"https://platform.usebrainos.com\"},
      {\"name\": \"PORT\", \"value\": \"9010\"}
    ],
    \"secrets\": [
      {\"name\": \"BRAINOS_API_KEY\", \"valueFrom\": \"arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/agentbench/brainos-api-key\"},
      {\"name\": \"BRAINOS_ORG_ID\", \"valueFrom\": \"arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/agentbench/brainos-org-id\"},
      {\"name\": \"ANTHROPIC_API_KEY\", \"valueFrom\": \"arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/agentbench/anthropic-api-key\"}
    ],
    \"logConfiguration\": {
      \"logDriver\": \"awslogs\",
      \"options\": {
        \"awslogs-group\": \"/ecs/agentbench-purple\",
        \"awslogs-region\": \"${AWS_REGION}\",
        \"awslogs-stream-prefix\": \"ecs\"
      }
    }
  }]
}" --region "$AWS_REGION"

echo "ECS task definitions registered."

# Get default VPC network config
VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true \
  --query 'Vpcs[0].VpcId' --output text --region "$AWS_REGION")
SUBNET_IDS=$(aws ec2 describe-subnets --filters Name=vpc-id,Values="$VPC_ID" \
  --query 'Subnets[*].SubnetId' --output text --region "$AWS_REGION" | tr '\t' ',')
SG_ID=$(aws ec2 describe-security-groups \
  --filters Name=vpc-id,Values="$VPC_ID" Name=group-name,Values=default \
  --query 'SecurityGroups[0].GroupId' --output text --region "$AWS_REGION")

echo "Network: VPC=$VPC_ID SG=$SG_ID"
echo "Subnets: $SUBNET_IDS"

# Create or update green service
echo "Creating/updating agentbench-green service..."
aws ecs create-service \
  --cluster "$ECS_CLUSTER" \
  --service-name agentbench-green \
  --task-definition agentbench-green \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
  --region "$AWS_REGION" 2>/dev/null || \
  aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service agentbench-green \
    --task-definition agentbench-green \
    --region "$AWS_REGION"

# Create or update purple service
echo "Creating/updating agentbench-purple service..."
aws ecs create-service \
  --cluster "$ECS_CLUSTER" \
  --service-name agentbench-purple \
  --task-definition agentbench-purple \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
  --region "$AWS_REGION" 2>/dev/null || \
  aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service agentbench-purple \
    --task-definition agentbench-purple \
    --region "$AWS_REGION"

echo ""
echo "ECS services created/updated on cluster: ${ECS_CLUSTER}"
echo "Monitor: https://console.aws.amazon.com/ecs/home?region=${AWS_REGION}#/clusters/${ECS_CLUSTER}"
