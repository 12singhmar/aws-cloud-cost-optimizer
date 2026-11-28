"""Clean-up actions. These are the only calls in the project that change the AWS account.

An action runs only when the user clicks it and confirms, and only for a resource
that the latest scan flagged with exactly that action (checked in main.py).
"""


def run_fix(session, region, action, resource_id):
    ec2 = session.client("ec2", region_name=region)

    if action == "stop":
        ec2.stop_instances(InstanceIds=[resource_id])
        return f"Stopping server {resource_id}."

    if action == "terminate":
        ec2.terminate_instances(InstanceIds=[resource_id])
        return f"Deleting server {resource_id}."

    if action == "delete_volume":
        # back it up first, wait for the backup to finish, then delete the disk
        snap = ec2.create_snapshot(
            VolumeId=resource_id, Description=f"Backup before deleting {resource_id}",
            TagSpecifications=[{"ResourceType": "snapshot",
                                "Tags": [{"Key": "created-by", "Value": "aws-cost-cleaner"}]}])
        ec2.get_waiter("snapshot_completed").wait(SnapshotIds=[snap["SnapshotId"]])
        ec2.delete_volume(VolumeId=resource_id)
        return f"Backed up as {snap['SnapshotId']}, then deleted disk {resource_id}."

    if action == "release_ip":
        ec2.release_address(AllocationId=resource_id)
        return f"Released IP {resource_id}."

    if action == "delete_snapshot":
        ec2.delete_snapshot(SnapshotId=resource_id)
        return f"Deleted backup {resource_id}."

    if action == "delete_nat":
        ec2.delete_nat_gateway(NatGatewayId=resource_id)
        return f"Deleting NAT gateway {resource_id}. Its IP address can be released after."

    if action == "delete_lb":
        session.client("elbv2", region_name=region).delete_load_balancer(LoadBalancerArn=resource_id)
        return "Deleted load balancer."

    raise ValueError(f"Unknown action {action}")
