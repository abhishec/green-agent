#!/bin/bash
AWS_REGION="${AWS_REGION:-us-east-1}"
CLUSTER="${ECS_CLUSTER:-nexusbrain-training}"

for SERVICE in agentbench-green agentbench-purple; do
  TASK_ARN=$(aws ecs list-tasks --cluster $CLUSTER --service-name $SERVICE --region $AWS_REGION --query 'taskArns[0]' --output text 2>/dev/null)
  if [ "$TASK_ARN" = "None" ] || [ -z "$TASK_ARN" ]; then
    echo "$SERVICE: no running tasks"
    continue
  fi
  ENI_ID=$(aws ecs describe-tasks --cluster $CLUSTER --tasks $TASK_ARN --region $AWS_REGION \
    --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text)
  if [ -z "$ENI_ID" ] || [ "$ENI_ID" = "None" ]; then
    echo "$SERVICE: task starting (no ENI yet)"
    continue
  fi
  PUBLIC_IP=$(aws ec2 describe-network-interfaces --network-interface-ids $ENI_ID --region $AWS_REGION \
    --query 'NetworkInterfaces[0].Association.PublicIp' --output text)
  PORT=$([ "$SERVICE" = "agentbench-green" ] && echo 9009 || echo 9010)
  echo "$SERVICE: http://$PUBLIC_IP:$PORT"
done
