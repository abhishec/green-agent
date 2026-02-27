#!/usr/bin/env bash
set -euo pipefail

AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-848269696611}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "Creating ECR repositories..."

aws ecr create-repository \
  --repository-name agentbench-green \
  --region "$AWS_REGION" \
  --image-scanning-configuration scanOnPush=true \
  2>/dev/null || echo "agentbench-green already exists"

aws ecr create-repository \
  --repository-name agentbench-purple \
  --region "$AWS_REGION" \
  --image-scanning-configuration scanOnPush=true \
  2>/dev/null || echo "agentbench-purple already exists"

echo "ECR repositories ready:"
echo "  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/agentbench-green"
echo "  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/agentbench-purple"
