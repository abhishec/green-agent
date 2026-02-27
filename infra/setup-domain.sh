#!/bin/bash
set -e
AWS_ACCOUNT=848269696611
AWS_REGION=us-east-1
CLUSTER=nexusbrain-training
DOMAIN=benchmark.usebrainos.com

echo "=== Setting up $DOMAIN ==="

# Get default VPC info
VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text --region $AWS_REGION)
SUBNET_IDS_SPACE=$(aws ec2 describe-subnets --filters Name=vpc-id,Values=$VPC_ID --query 'Subnets[*].SubnetId' --output text --region $AWS_REGION)
SUBNET_IDS_COMMA=$(echo $SUBNET_IDS_SPACE | tr ' ' ',')

# Step 1: Create security group for ALB (ports 80+443)
ALB_SG_ID=$(aws ec2 describe-security-groups \
  --filters Name=group-name,Values=agentbench-alb-sg Name=vpc-id,Values=$VPC_ID \
  --query 'SecurityGroups[0].GroupId' --output text --region $AWS_REGION 2>/dev/null)

if [ "$ALB_SG_ID" = "None" ] || [ -z "$ALB_SG_ID" ]; then
  ALB_SG_ID=$(aws ec2 create-security-group \
    --group-name agentbench-alb-sg \
    --description "ALB security group for agentbench" \
    --vpc-id $VPC_ID \
    --region $AWS_REGION \
    --query 'GroupId' --output text)
  aws ec2 authorize-security-group-ingress --group-id $ALB_SG_ID --protocol tcp --port 80 --cidr 0.0.0.0/0 --region $AWS_REGION
  aws ec2 authorize-security-group-ingress --group-id $ALB_SG_ID --protocol tcp --port 443 --cidr 0.0.0.0/0 --region $AWS_REGION
  echo "Created ALB security group: $ALB_SG_ID"
else
  echo "ALB security group exists: $ALB_SG_ID"
fi

# Step 2: Create ALB
ALB_ARN=$(aws elbv2 describe-load-balancers --names agentbench-alb \
  --query 'LoadBalancers[0].LoadBalancerArn' --output text --region $AWS_REGION 2>/dev/null || echo "None")

if [ "$ALB_ARN" = "None" ] || [ -z "$ALB_ARN" ]; then
  ALB_ARN=$(aws elbv2 create-load-balancer \
    --name agentbench-alb \
    --subnets $SUBNET_IDS_SPACE \
    --security-groups $ALB_SG_ID \
    --scheme internet-facing \
    --type application \
    --region $AWS_REGION \
    --query 'LoadBalancers[0].LoadBalancerArn' --output text)
  echo "Created ALB: $ALB_ARN"
else
  echo "ALB exists: $ALB_ARN"
fi

ALB_DNS=$(aws elbv2 describe-load-balancers --load-balancer-arns $ALB_ARN \
  --query 'LoadBalancers[0].DNSName' --output text --region $AWS_REGION)
ALB_ZONE=$(aws elbv2 describe-load-balancers --load-balancer-arns $ALB_ARN \
  --query 'LoadBalancers[0].CanonicalHostedZoneId' --output text --region $AWS_REGION)
echo "ALB DNS: $ALB_DNS"

# Step 3: Create target group
TG_ARN=$(aws elbv2 describe-target-groups --names agentbench-green-tg \
  --query 'TargetGroups[0].TargetGroupArn' --output text --region $AWS_REGION 2>/dev/null || echo "None")

if [ "$TG_ARN" = "None" ] || [ -z "$TG_ARN" ]; then
  TG_ARN=$(aws elbv2 create-target-group \
    --name agentbench-green-tg \
    --protocol HTTP \
    --port 9009 \
    --vpc-id $VPC_ID \
    --target-type ip \
    --health-check-path /health \
    --health-check-interval-seconds 30 \
    --region $AWS_REGION \
    --query 'TargetGroups[0].TargetGroupArn' --output text)
  echo "Created target group: $TG_ARN"
else
  echo "Target group exists: $TG_ARN"
fi

# Step 4: Request ACM certificate
CERT_ARN=$(aws acm list-certificates \
  --query "CertificateSummaryList[?DomainName=='$DOMAIN'].CertificateArn" \
  --output text --region $AWS_REGION)

if [ -z "$CERT_ARN" ]; then
  CERT_ARN=$(aws acm request-certificate \
    --domain-name $DOMAIN \
    --validation-method DNS \
    --region $AWS_REGION \
    --query 'CertificateArn' --output text)
  echo "Requested certificate: $CERT_ARN"
  echo "IMPORTANT: Add the following DNS validation record to usebrainos.com:"
  aws acm describe-certificate --certificate-arn $CERT_ARN --region $AWS_REGION \
    --query 'Certificate.DomainValidationOptions[0].ResourceRecord'
else
  echo "Certificate exists: $CERT_ARN"
fi

# Step 5: Wait for certificate validation (will skip if already validated)
CERT_STATUS=$(aws acm describe-certificate --certificate-arn $CERT_ARN --region $AWS_REGION \
  --query 'Certificate.Status' --output text)
echo "Certificate status: $CERT_STATUS"

if [ "$CERT_STATUS" = "PENDING_VALIDATION" ]; then
  echo "Waiting for certificate validation... (add DNS record first)"
  aws acm wait certificate-validated --certificate-arn $CERT_ARN --region $AWS_REGION
fi

# Step 6: Create HTTPS listener (only if cert is ISSUED)
CERT_STATUS=$(aws acm describe-certificate --certificate-arn $CERT_ARN --region $AWS_REGION \
  --query 'Certificate.Status' --output text)

if [ "$CERT_STATUS" = "ISSUED" ]; then
  # Add HTTPS listener
  aws elbv2 create-listener \
    --load-balancer-arn $ALB_ARN \
    --protocol HTTPS \
    --port 443 \
    --certificates CertificateArn=$CERT_ARN \
    --default-actions Type=forward,TargetGroupArn=$TG_ARN \
    --region $AWS_REGION 2>/dev/null || echo "HTTPS listener exists"

  # Add HTTP->HTTPS redirect
  aws elbv2 create-listener \
    --load-balancer-arn $ALB_ARN \
    --protocol HTTP \
    --port 80 \
    --default-actions '[{"Type":"redirect","RedirectConfig":{"Protocol":"HTTPS","Port":"443","StatusCode":"HTTP_301"}}]' \
    --region $AWS_REGION 2>/dev/null || echo "HTTP redirect listener exists"

  echo "Listeners configured"
fi

# Step 7: Wire ECS service to ALB target group
# AWS does not allow adding a load balancer to an existing ECS service via update-service.
# We must delete and recreate the service with --load-balancers at create time.
EXISTING_LB=$(aws ecs describe-services \
  --cluster $CLUSTER \
  --services agentbench-green \
  --region $AWS_REGION \
  --query 'services[0].loadBalancers[0].targetGroupArn' \
  --output text 2>/dev/null || echo "None")

if [ "$EXISTING_LB" = "None" ] || [ -z "$EXISTING_LB" ]; then
  echo "Wiring ALB to ECS service (requires service recreation)..."

  # Get current service config
  VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true \
    --query 'Vpcs[0].VpcId' --output text --region $AWS_REGION)
  SUBNET_IDS=$(aws ec2 describe-subnets \
    --filters Name=vpc-id,Values=$VPC_ID \
    --query 'Subnets[*].SubnetId' --output text --region $AWS_REGION)
  SG_ID=$(aws ec2 describe-security-groups \
    --filters Name=vpc-id,Values=$VPC_ID Name=group-name,Values=default \
    --query 'SecurityGroups[0].GroupId' --output text --region $AWS_REGION)

  # Delete existing service (scale to 0 first to avoid drain wait)
  aws ecs update-service --cluster $CLUSTER --service agentbench-green \
    --desired-count 0 --region $AWS_REGION > /dev/null
  aws ecs delete-service --cluster $CLUSTER --service agentbench-green \
    --force --region $AWS_REGION > /dev/null
  echo "Deleted old agentbench-green service"

  # Recreate with ALB wired
  aws ecs create-service \
    --cluster $CLUSTER \
    --service-name agentbench-green \
    --task-definition agentbench-green \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
    --load-balancers "targetGroupArn=$TG_ARN,containerName=green-agent,containerPort=9009" \
    --health-check-grace-period-seconds 60 \
    --region $AWS_REGION > /dev/null
  echo "Recreated agentbench-green service with ALB target group wired"
else
  echo "ECS service already wired to target group: $EXISTING_LB"
fi

# Step 8: Route53 — create ALIAS record
HOSTED_ZONE_ID=$(aws route53 list-hosted-zones-by-name \
  --dns-name usebrainos.com \
  --query 'HostedZones[0].Id' \
  --output text | cut -d'/' -f3)

if [ -n "$HOSTED_ZONE_ID" ] && [ "$HOSTED_ZONE_ID" != "None" ]; then
  aws route53 change-resource-record-sets \
    --hosted-zone-id $HOSTED_ZONE_ID \
    --change-batch "{
      \"Changes\": [{
        \"Action\": \"UPSERT\",
        \"ResourceRecordSet\": {
          \"Name\": \"$DOMAIN\",
          \"Type\": \"A\",
          \"AliasTarget\": {
            \"HostedZoneId\": \"$ALB_ZONE\",
            \"DNSName\": \"$ALB_DNS\",
            \"EvaluateTargetHealth\": true
          }
        }
      }]
    }"
  echo "Route53 ALIAS record created: $DOMAIN -> $ALB_DNS"
else
  echo "Route53 hosted zone not found for usebrainos.com"
  echo "Manually add DNS record: $DOMAIN CNAME $ALB_DNS"
fi

echo ""
echo "=== Setup complete ==="
echo "ALB DNS: $ALB_DNS"
echo "Domain: https://$DOMAIN (after DNS propagation)"
echo "Test: curl https://$DOMAIN/health"
