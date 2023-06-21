#!/bin/bash

# To keep the package list up to date and install the 'jq' package, execute the following commands:
sudo apt-get update && sudo apt-get install -y jq

# Declare arrays and set variables
declare -a instances
declare -a ips
declare -a keys
role_name="ec2-queue-manager-role-updated"

roles=$(aws iam get-role --role-name $role_name 2>/dev/null)

if [ -z "$roles" ]; then
    # To create the IAM role and attach the required policies, follow these steps:
    aws iam create-role --role-name $role_name --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
    aws iam attach-role-policy --role-name $role_name --policy-arn arn:aws:iam::aws:policy/AmazonEC2FullAccess

    # Define the policy for IAM actions
    working_policy='{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "AllowAllIAMActions",
          "Effect": "Allow",
          "Action": "iam:*",
          "Resource": "*"
        }
      ]
    }'

    # To assign the policy to the role, follow these steps:
    aws iam put-role-policy --role-name $role_name --policy-name AllIamAccess --policy-document "$working_policy"
    aws iam put-role-policy --role-name $role_name --policy-name PassRolePolicy --policy-document '{"Version":"2012-10-17","Statement":[{"Sid":"AllowPassRole","Effect":"Allow","Action":"iam:PassRole","Resource":"*"}]}'
    aws iam create-instance-profile --instance-profile-name $role_name
    aws iam add-role-to-instance-profile --role-name $role_name --instance-profile-name $role_name

    sleep 180
fi

for ((i=0; i<2; i++)); do
    current_key="cloud-course-$(date +'%N')"
    k_pem="$current_key.pem"

    keys+=("$k_pem")
    echo "${keys[@]}"

    echo "Creating key pair"
    aws ec2 create-key-pair --key-name $current_key | jq -r ".KeyMaterial" > $k_pem

    chmod 400 $k_pem

    sec_grp="my-sg-$(date +'%N')"

    aws ec2 create-security-group --group-name $sec_grp --description "Access my instances"

    my_ip=$(curl ipinfo.io/ip)
    echo "The ip address is $my_ip"

    aws ec2 authorize-security-group-ingress --group-name $sec_grp --port 22 --protocol tcp --cidr 0.0.0.0/0

    aws ec2 authorize-security-group-ingress --group-name $sec_grp --port 5000 --protocol tcp --cidr 0.0.0.0/0

    ubuntu_20_04_ami="ami-042e8287309f5df03"
    run_instances=$(aws ec2 run-instances --image-id $ubuntu_20_04_ami --instance-type t2.micro --key-name $current_key --security-groups $sec_grp --iam-instance-profile Name=$role_name)

    instance_id=$(echo $run_instances | jq -r '.Instances[0].InstanceId')

    instances+=("$instance_id")
    echo "${instances[@]}"

    echo "Waiting for instance to be created"
    aws ec2 wait instance-running --instance-ids $instance_id

    public_ip=$(aws ec2 describe-instances --instance-ids $instance_id | jq -r '.Reservations[0].Instances[0].PublicIpAddress')

    ips+=("$public_ip")
    echo "${ips[@]}"

    echo "instance is created"
done


for ((i=0; i<2; i++)); do
    local_ip=${ips[$(($i)) % 2]}
    other_ip=${ips[$(($i+1)) % 2]}
    max_workers=$(($i+2))
    scp -i "${keys[$i]}" -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=60" app.py ubuntu@"${ips[$i]}":/home/ubuntu/
    scp -i "${keys[$i]}" -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=60" workerApp.py ubuntu@"${ips[$i]}":/home/ubuntu/
    scp -i "${keys[$i]}" -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=60" workerSetup.sh ubuntu@"${ips[$i]}":/home/ubuntu/

    ssh -i "${keys[$i]}" -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=10" ubuntu@"${ips[$i]}" <<EOF

    echo "localIP=$local_ip" > variables.txt
    echo "otherIP=$other_ip" >> variables.txt
    echo "maxWorkers=$max_workers" >> variables.txt

    sudo apt update 
    sudo apt-get install unzip
    sudo apt install python3-pip --yes
    sudo pip3 install flask
    
    curl "https://d1vvhvl2y92vvt.cloudfront.net/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip awscliv2.zip
    sudo ./aws/install

    nohup /usr/local/bin/flask run --host 0.0.0.0 &>/dev/null &
    echo "running"
    exit
EOF
done
