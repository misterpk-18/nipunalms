#!/usr/bin/env bash
# Creates the AWS side of the production LMS server (docs/DEVELOPMENT.md Part F): one t3.micro like the CRM's, in the CRM's VPC
# and subnet, with its own security group, key pair and an instance role that reaches only the uploads bucket. Run it once, from a
# laptop with the `nipuna` AWS profile. It creates paid resources, so read it first. Nothing here touches the CRM's instance.
set -euo pipefail
export AWS_PROFILE="${AWS_PROFILE:-nipuna}" AWS_PAGER=""
REGION=ap-south-1
VPC=vpc-0018ec1e656baab75          # the CRM's VPC
SUBNET=subnet-0e2612ee139b71abb    # the CRM's public subnet (ap-south-1b)
AMI=ami-007b1f3fdea0383d9          # Ubuntu 24.04 amd64, the image the CRM runs on
BUCKET=nipunalms-uploads-prod
NAME=nipunalms-prod
KEY="$HOME/.ssh/$NAME.pem"

[ -e "$KEY" ] && { echo "$KEY already exists; remove it or pick another name"; exit 1; }
MYIP=$(curl -s https://checkip.amazonaws.com)

echo "== role that can use only the uploads bucket"
aws iam create-role --role-name "$NAME" --description "Nipuna LMS production server: uploads bucket only" \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
aws iam put-role-policy --role-name "$NAME" --policy-name uploads-bucket --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[
 {\"Effect\":\"Allow\",\"Action\":[\"s3:ListBucket\"],\"Resource\":\"arn:aws:s3:::$BUCKET\"},
 {\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\",\"s3:PutObject\",\"s3:DeleteObject\"],\"Resource\":\"arn:aws:s3:::$BUCKET/*\"}]}"
aws iam create-instance-profile --instance-profile-name "$NAME" >/dev/null
aws iam add-role-to-instance-profile --instance-profile-name "$NAME" --role-name "$NAME"

echo "== security group: 80 and 443 open, 22 only from $MYIP"
SG=$(aws ec2 create-security-group --region $REGION --group-name "$NAME" --description "Nipuna LMS production" --vpc-id $VPC --query GroupId --output text)
aws ec2 authorize-security-group-ingress --region $REGION --group-id "$SG" --ip-permissions \
  "IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=0.0.0.0/0,Description=http}]" \
  "IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=0.0.0.0/0,Description=https}]" \
  "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=$MYIP/32,Description=admin ssh}]" >/dev/null

echo "== key pair (private key kept at $KEY)"
aws ec2 create-key-pair --region $REGION --key-name "$NAME" --query KeyMaterial --output text > "$KEY"
chmod 600 "$KEY"

echo "== instance (a new role takes a few seconds to be usable)"
sleep 12
ID=$(aws ec2 run-instances --region $REGION --image-id $AMI --instance-type t3.micro --key-name "$NAME" \
  --subnet-id $SUBNET --security-group-ids "$SG" --iam-instance-profile Name="$NAME" \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3,Encrypted=true}' \
  --metadata-options 'HttpTokens=required,HttpEndpoint=enabled' \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME}]" "ResourceType=volume,Tags=[{Key=Name,Value=$NAME}]" \
  --query 'Instances[0].InstanceId' --output text)
aws ec2 wait instance-running --region $REGION --instance-ids "$ID"

echo "== elastic IP, so the address survives a stop and start"
ALLOC=$(aws ec2 allocate-address --region $REGION --domain vpc --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=$NAME}]" --query AllocationId --output text)
aws ec2 associate-address --region $REGION --instance-id "$ID" --allocation-id "$ALLOC" >/dev/null
IP=$(aws ec2 describe-addresses --region $REGION --allocation-ids "$ALLOC" --query 'Addresses[0].PublicIp' --output text)

echo
echo "instance $ID  security group $SG  address $IP"
echo "next: ssh -i $KEY ubuntu@$IP   (then deploy/server-setup.sh, see docs/DEVELOPMENT.md Part F)"
