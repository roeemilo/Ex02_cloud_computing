#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

#install 'jq' package
sudo apt-get update && sudo apt-get install -y jq

worker_role_name="ec2-instance-create-role-worker"

####
if aws iam get-role --role-name $worker_role_name >/dev/null 2>&1; then
    echo "Role $worker_role_name already exists. Using the existing role."
else
    echo "Role $worker_role_name does not exist. Creating the role..."

    # Create the IAM role and attach necessary policies
    aws iam create-role --role-name $worker_role_name --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
    aws iam attach-role-policy --role-name $worker_role_name --policy-arn arn:aws:iam::aws:policy/AmazonEC2FullAccess
    aws iam create-instance-profile --instance-profile-name $worker_role_name
    aws iam add-role-to-instance-profile --role-name $worker_role_name --instance-profile-name $worker_role_name

    echo "Role $worker_role_name created successfully."
fi
####

# Create new key pair
current_key="cloud-course-$(date +'%N')"
key_file="$current_key.pem"

echo "Creating key pair"
aws ec2 create-key-pair --key-name $current_key | jq -r ".KeyMaterial" > $key_file

chmod 400 $key_file

security_group="my-sg-$(date +'%N')"
aws ec2 create-security-group --group-name $security_group --description "Access my instances"

my_ip=$(curl ipinfo.io/ip)
echo "My IP: $my_ip"

echo "Setting up rules"
aws ec2 authorize-security-group-ingress --group-name $security_group --port 22 --protocol tcp --cidr "$my_ip/32"

aws ec2 authorize-security-group-ingress --group-name $security_group --port 5000 --protocol tcp --cidr "$my_ip/32"

ubuntu_20_04_ami="ami-042e8287309f5df03"
echo "Creating new instance"
run_instances=$(aws ec2 run-instances --image-id $ubuntu_20_04_ami --instance-type t2.micro --key-name $current_key --security-groups $security_group --iam-instance-profile Name=$worker_role_name)
instance_id=$(echo $run_instances | jq -r '.Instances[0].InstanceId')

echo "Waiting for instance to be created"
aws ec2 wait instance-running --instance-ids $instance_id

public_ip=$(aws ec2 describe-instances --instance-ids $instance_id | jq -r '.Reservations[0].Instances[0].PublicIpAddress')

scp -i $key_file -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=60" workerApp.py ubuntu@$public_ip:/home/ubuntu/app.py

ssh -i $key_file -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=10" ubuntu@$public_ip <<EOF
    sudo apt update
    sudo apt-get install unzip
    sudo apt install python3-pip --yes
    sudo pip3 install flask

    echo "instanceID=$instance_id" > workerVariables.txt
    echo "primaryIP=$my_ip" >> workerVariables.txt

    curl "https://d1vvhvl2y92vvt.cloudfront.net/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip awscliv2.zip
    sudo ./aws/install

    # Run the app
    nohup /usr/local/bin/flask run --host 0.0.0.0 > flask_output.log 2>&1 &
    exit
EOF