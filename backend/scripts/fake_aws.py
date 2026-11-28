"""Test mode: run a FAKE AWS on this computer (moto) with some waste in it.

Use this only when no real AWS account is available. The app shows "Test mode"
on every page while it is connected to the fake AWS.

1. In one terminal:   python scripts/fake_aws.py
2. In another terminal start the backend pointed at it (Windows):
     set AWS_ENDPOINT_URL=http://127.0.0.1:5000
     set AWS_ACCESS_KEY_ID=test
     set AWS_SECRET_ACCESS_KEY=test
     python -m uvicorn app.main:app
"""

import time

import boto3
from moto.server import ThreadedMotoServer

URL = "http://127.0.0.1:5000"


def client(service, region):
    return boto3.client(service, region_name=region, endpoint_url=URL,
                        aws_access_key_id="test", aws_secret_access_key="test")


def tag(name, kind):
    return [{"ResourceType": kind, "Tags": [{"Key": "Name", "Value": name}]}]


def fill():
    # Mumbai: one server in use, one stopped server, a backup of a deleted disk
    ec2 = client("ec2", "ap-south-1")
    ami = ec2.describe_images()["Images"][0]["ImageId"]
    ec2.run_instances(ImageId=ami, InstanceType="t3.micro", MinCount=1, MaxCount=1,
                      TagSpecifications=tag("college-website", "instance"))
    old = ec2.run_instances(ImageId=ami, InstanceType="t3.small", MinCount=1, MaxCount=1,
                            TagSpecifications=tag("old-project", "instance"))["Instances"][0]["InstanceId"]
    ec2.stop_instances(InstanceIds=[old])
    temp = ec2.create_volume(AvailabilityZone="ap-south-1a", Size=20, VolumeType="gp2")["VolumeId"]
    ec2.create_snapshot(VolumeId=temp, Description="before upgrade")
    ec2.delete_volume(VolumeId=temp)

    # Oregon: a spare 50 GB disk someone forgot
    client("ec2", "us-west-2").create_volume(AvailabilityZone="us-west-2a", Size=50, VolumeType="gp3",
                                             TagSpecifications=tag("db-backup-disk", "volume"))

    # Singapore: an IP address nobody uses
    client("ec2", "ap-southeast-1").allocate_address(Domain="vpc")

    # Frankfurt: a NAT gateway that sends no data
    ec2 = client("ec2", "eu-central-1")
    subnet = ec2.describe_subnets()["Subnets"][0]["SubnetId"]
    ip = ec2.allocate_address(Domain="vpc")["AllocationId"]
    ec2.create_nat_gateway(SubnetId=subnet, AllocationId=ip)

    # N. Virginia: a load balancer with no servers behind it
    ec2 = client("ec2", "us-east-1")
    subnets = [s["SubnetId"] for s in ec2.describe_subnets()["Subnets"][:2]]
    client("elbv2", "us-east-1").create_load_balancer(Name="test-app-lb", Subnets=subnets)


if __name__ == "__main__":
    server = ThreadedMotoServer(port=5000)
    server.start()
    fill()
    print(f"Fake AWS running at {URL} with test waste in 5 regions. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
