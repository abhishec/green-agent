# Agent Bench — AWS Deployment

## Architecture

- **green-agent**: Port 9009 — baseline benchmark agent (no BrainOS)
- **purple-agent**: Port 9010 — BrainOS-powered agent (with Brain context mesh + RL)
- **Cluster**: nexusbrain-training (us-east-1)
- **ECR**: 848269696611.dkr.ecr.us-east-1.amazonaws.com

## Prerequisites

1. AWS CLI configured with access to account 848269696611
2. Docker with buildx support
3. SSM parameters set (see below)

## SSM Parameters (set before first deploy)

```bash
aws ssm put-parameter --name /agentbench/brainos-api-key \
  --value "YOUR_API_KEY" --type SecureString --region us-east-1

aws ssm put-parameter --name /agentbench/brainos-org-id \
  --value "YOUR_ORG_ID" --type SecureString --region us-east-1

aws ssm put-parameter --name /agentbench/anthropic-api-key \
  --value "YOUR_ANTHROPIC_KEY" --type SecureString --region us-east-1
```

## One-time setup

```bash
cd infra

# 1. Create ECR repositories
bash setup-ecr.sh

# 2. Register task definitions + create ECS services
bash setup-ecs.sh
```

## Deploy (after code changes)

```bash
cd agent-bench
bash infra/deploy.sh
```

## Get service URLs

```bash
cd infra && bash get-ips.sh
```

## Run benchmark

```bash
GREEN_URL=$(bash infra/get-ips.sh | grep green | awk '{print $2}')
PURPLE_URL=$(bash infra/get-ips.sh | grep purple | awk '{print $2}')
python run_benchmark.py --task task_01 --green-url $GREEN_URL --purple-url $PURPLE_URL
```

## Monitor

- ECS console: https://console.aws.amazon.com/ecs/home?region=us-east-1#/clusters/nexusbrain-training
- CloudWatch logs: /ecs/agentbench-green and /ecs/agentbench-purple
