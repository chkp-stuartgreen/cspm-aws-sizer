import boto3
import json
from math import ceil

default_region = 'eu-west-1'


def count_instances_and_nodes(region):  # Gather EC2 instances and EKS nodes
    #filters = []
    client = boto3.client('ec2', region_name=region)
    filters = [{
        "Name": "instance-state-name",
        "Values": ["running"]
    }]
    response = client.describe_instances(Filters=filters, MaxResults=1000)
    billableNodeCount = 0
    billableInstanceCount = 0
    # Declare non-billable instance types
    nonBillableEC2Types = ['nano', 'micro']
    markedAsNode = False
    for r in response['Reservations']:
        for i in r['Instances']:
            if ('Tags' in i):
                for t in i['Tags']:
                    if t['Key'] == 'eks:cluster-name':
                        billableNodeCount += 1
                        markedAsNode = True
                        break

            if not any(nonBill in i['InstanceType'] for nonBill in nonBillableEC2Types) and not markedAsNode:
                billableInstanceCount += 1

    return {"instances": billableInstanceCount, "nodes": billableNodeCount}


def count_rds(region):  # Gather EC2 instances
    client = boto3.client('rds', region_name=region)
    response = client.describe_db_instances(MaxRecords=100)
    billableRDSCount = 0
    # Declare non-billable instance types
    nonBillableRDSTypes = ['nano', 'micro']
    for r in response['DBInstances']:
        if not any(nonBill in r['DBInstanceClass'] for nonBill in nonBillableRDSTypes):
            billableRDSCount += 1
    return billableRDSCount


def count_lambdas(region):
    # Lambdas are counted at 60:1
    client = boto3.client('lambda', region_name=region)
    lambdaFactor = 60
    response = client.get_account_settings()
    totalLambdas = response['AccountUsage']['FunctionCount']
    billableLambdas = ceil(totalLambdas / lambdaFactor)
    return billableLambdas


def get_regions(region):
    client = boto3.client('ec2', region_name=region)
    response = client.describe_regions()
    regions = list(map(lambda r: r['RegionName'], response['Regions']))
    return regions


def all_regions_check():
    regions = get_regions(default_region)
    billableEC2 = 0
    billableLamb = 0
    billableRDS = 0
    billableNode = 0

    for reg in regions:
        print(f"[INFO] Checking region {reg}")
        ec2_and_nodes = count_instances_and_nodes(reg)
        billableEC2 += ec2_and_nodes['instances']
        billableNode += ec2_and_nodes['nodes']
        billableLamb += count_lambdas(reg)
        billableRDS += count_rds(reg)

    return {"totalEC2": billableEC2, "totalLambda": billableLamb, "totalK8sNodes": billableNode, "totalRDS": billableRDS}


def print_results(results):
    print(f"[INFO] *** Asset count complete ***")
    print(
        f"[INFO] Total EC2 instances (exluding Micro and Nano) : {results['totalEC2']}")
    print(f"[INFO] Total RDS Instances / databases : {results['totalRDS']}")
    print(f"[INFO] Total Lambda functions (60:1): {results['totalLambda']}")
    print(f"[INFO] Total EKS nodes: {results['totalK8sNodes']}")


allRegionsCount = all_regions_check()
print_results(allRegionsCount)
