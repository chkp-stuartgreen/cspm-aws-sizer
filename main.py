import boto3
import json
from math import ceil

def count_instances(client): # Gather EC2 instances
    filters = [{
        "Name": "instance-state-name",
        "Values": ["running"]
    }]
    response = client.describe_instances(Filters=filters, MaxResults=1000)
    billableInstanceCount = 0
    # Declare non-billable instance types
    nonBillableEC2Types = ['nano', 'micro']
    for r in response['Reservations']:
        for i in r['Instances']:
            if not any(nonBill in i['InstanceType'] for nonBill in nonBillableEC2Types):
                billableInstanceCount += 1
    
    return billableInstanceCount

def count_rds(client): # Gather EC2 instances
    response = client.describe_db_instances(MaxRecords=100)
    billableRDSCount = 0
    # Declare non-billable instance types
    nonBillableRDSTypes = ['nano', 'micro']
    for r in response['DBInstances']:
        if not any(nonBill in r['DBInstanceClass'] for nonBill in nonBillableRDSTypes):
            billableRDSCount += 1
    return billableRDSCount

def count_lambdas(client):
    # Lambdas are counted at 60:1
    lambdaFactor = 60
    response = client.get_account_settings()
    totalLambdas = response['AccountUsage']['FunctionCount']
    billableLambdas = ceil(totalLambdas / lambdaFactor)
    return billableLambdas

def get_regions(client):

    response = client.describe_regions()
    regions = list(map(lambda r: r['RegionName'], response['Regions']))
    return regions

def get_eks_clusters(client):
    response = client.list_clusters()
    return response['clusters']

def get_eks_nodegroups(client):
    # --cluster-name
    return None

client = boto3.client('ec2', region_name='eu-west-1')
regions = get_regions(client)
print(regions)

#client = boto3.client('ec2')
#billableEC2 = count_instances(client)
#print(billableEC2)

#client = boto3.client('rds')
#billableRDS = count_rds(client)
#print(billableRDS)

#client = boto3.client('lambda')
#billableLamb = count_lambdas(client)
#print(billableLamb)