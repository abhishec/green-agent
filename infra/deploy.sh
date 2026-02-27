#!/usr/bin/env bash
set -euo pipefail

AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-848269696611}"
AWS_REGION="${AWS_REGION:-us-east-1}"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECS_CLUSTER="${ECS_CLUSTER:-nexusbrain-training}"
TAG="${TAG:-latest}"

echo "Logging in to ECR..."
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo "Building and pushing green-agent..."
docker buildx build \
  --platform linux/amd64 \
  -t "${ECR_REGISTRY}/agentbench-green:${TAG}" \
  --push \
  ./green-agent

echo "Building and pushing purple-agent..."
docker buildx build \
  --platform linux/amd64 \
  -t "${ECR_REGISTRY}/agentbench-purple:${TAG}" \
  --push \
  ./purple-agent

echo "Forcing ECS redeployment..."
aws ecs update-service \
  --cluster "$ECS_CLUSTER" \
  --service agentbench-green \
  --force-new-deployment \
  --region "$AWS_REGION"

aws ecs update-service \
  --cluster "$ECS_CLUSTER" \
  --service agentbench-purple \
  --force-new-deployment \
  --region "$AWS_REGION"

echo "Deploy complete. Monitor at:"
echo "  https://console.aws.amazon.com/ecs/home?region=${AWS_REGION}#/clusters/${ECS_CLUSTER}"
