# AgentBench — Green/Purple Agent Competition Scaffold

Benchmark framework for evaluating AI agents across 15 business scenarios.

## Quick Start

```bash
# Copy env vars
cp .env.example .env
# Fill in BRAINOS_API_KEY, BRAINOS_ORG_ID, ANTHROPIC_API_KEY

# Start both agents
docker-compose up --build

# Run a benchmark task
python bench-runner/run_benchmark.py --task task_01

# Run all tasks
python bench-runner/pass_k_runner.py --all --k 3
```

## Architecture

- **Green Agent** (port 9009): Issues tasks, provides MCP tool server, scores results
- **Purple Agent** (port 9010): Solves tasks via BrainOS (falls back to direct Claude SDK)

## Scenarios

| Task | Name | Difficulty |
|------|------|------------|
| task_01 | Multi-Item Order Modification | medium |
| task_02 | Procurement Approval | medium |
| task_03 | Employee Offboarding | medium |
| task_04 | Insurance Claim | hard |
| task_05 | Invoice Reconciliation | hard |
| task_06 | SLA Breach Escalation | medium |
| task_07 | Travel Rebooking | medium |
| task_08 | Compliance Audit | hard |
| task_09 | Subscription Migration | medium |
| task_10 | Dispute Resolution | hard |
| task_11 | Month-End Close | hard |
| task_12 | Product Planning | medium |
| task_13 | AR Collections | medium |
| task_14 | Incident RCA | hard |
| task_15 | QBR Aggregation | medium |

## Infrastructure Setup (AWS ECS + benchmark.usebrainos.com)

Deploy order — each step depends on the previous being stable:

```bash
# Step 1: Push images to ECR
bash infra/setup-ecr.sh

# Step 2: Register ECS task definitions and create Fargate services
bash infra/setup-ecs.sh

# Step 3: Domain setup — run ONLY after ECS services are running and healthy
# Creates: ALB, ACM certificate, target group, Route53 ALIAS record
# DO NOT run until `aws ecs describe-services` shows RUNNING for agentbench-green
bash infra/setup-domain.sh
```

### Domain setup notes (infra/setup-domain.sh)

- Creates an internet-facing ALB (`agentbench-alb`) in the default VPC
- Creates a target group (`agentbench-green-tg`) pointing at port 9009 (Green Agent `/health`)
- Requests an ACM certificate for `benchmark.usebrainos.com` via DNS validation
- **Manual step required**: After the script prints the DNS validation CNAME, add it to the usebrainos.com hosted zone in Route53 before re-running, or the `aws acm wait` will block indefinitely
- Once the certificate status is `ISSUED`, the script creates HTTPS (443) and HTTP→HTTPS redirect (80) listeners
- Creates a Route53 ALIAS A record pointing `benchmark.usebrainos.com` at the ALB
- ECS load-balancer wiring (`update-service`) is attempted but may need to be done at service creation time in `setup-ecs.sh` if the service was already created without an ALB

### Verify domain is live

```bash
curl https://benchmark.usebrainos.com/health
```

## Scoring

7-dimension scoring (0-100 per dimension):
- **Functional** (30%): Correct tools called
- **Policy Compliance** (20%): No policy violations
- **Escalation** (15%): Correct escalation decisions
- **Sequence** (15%): Tools called in right order
- **Arithmetic** (10%): Correct calculations
- **Hallucination** (5%): No invented tool names
- **Communication** (5%): Key facts in answer
