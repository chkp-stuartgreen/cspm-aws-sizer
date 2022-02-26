import boto3
import json
from math import ceil

default_region = 'eu-west-1'


def count_instances_and_nodes(region, session=None):  # Gather EC2 instances and EKS nodes
    #filters = []
    if session:
        client = session.client('ec2', region_name=region)
    else:
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


def count_rds(region, session=None):  # Gather EC2 instances
    if session:
        client = session.client('rds', region_name=region)
    else:
        client = boto3.client('rds', region_name=region)
    response = client.describe_db_instances(MaxRecords=100)
    billableRDSCount = 0
    # Declare non-billable instance types
    nonBillableRDSTypes = ['nano', 'micro']
    for r in response['DBInstances']:
        if not any(nonBill in r['DBInstanceClass'] for nonBill in nonBillableRDSTypes):
            billableRDSCount += 1
    return billableRDSCount


def count_lambdas(region, session=None):
    if session:
        client = session.client('lambda', region_name=region)
    else:    
        client = boto3.client('lambda', region_name=region)
    response = client.list_functions()


    totalLambdas = 0
    for l in response['Functions']:
        funcTags = client.list_tags(Resource=l['FunctionArn'])
        if not ('Owner' in funcTags['Tags'] and funcTags['Tags']['Owner'] == 'Cloudguard Serverless Security'):
            totalLambdas += 1
    
    return totalLambdas


def get_regions(region):
    client = boto3.client('ec2', region_name=region)
    response = client.describe_regions()
    regions = list(map(lambda r: r['RegionName'], response['Regions']))
    return regions


def all_regions_check(session=None):
    regions = get_regions(default_region)
    billableEC2 = 0
    billableLamb = 0
    billableRDS = 0
    billableNode = 0
    lambdaFactor = 60

    for reg in regions:
        print(f"[INFO] Checking region {reg}")
        ec2_and_nodes = count_instances_and_nodes(reg, session)
        billableEC2 += ec2_and_nodes['instances']
        billableNode += ec2_and_nodes['nodes']
        billableLamb += count_lambdas(reg, session)
        billableRDS += count_rds(reg, session)

    
    return {"totalEC2": billableEC2, "totalLambda": ceil(billableLamb / lambdaFactor), "totalK8sNodes": billableNode, "totalRDS": billableRDS}

def org_mode():
    # Assume role, get token, list accounts, assume to each account
    # run commands
    
    orgClient = boto3.client('organizations')
    resp = orgClient.list_accounts()
    accountNumbers = list(map(lambda a: a['Id'], resp['Accounts']))
    stsClient = boto3.client('sts')
    currentAccount = stsClient.get_caller_identity()['Account']
    
    for account in accountNumbers:
        # Don't assume into account if it's the current account for user

        # Assume into each account
        if account != currentAccount:
            org_account_arn = 'arn:aws:iam::' + account + ':role/OrganizationAccountAccessRole'
        
        
            stsResp = stsClient.assume_role(
                RoleArn=org_account_arn,
                RoleSessionName='CloudGuard_AssetCounter',
                DurationSeconds=1800
                )
            stsSes = boto3.Session(
                aws_access_key_id=stsResp['Credentials']['AccessKeyId'],
                aws_secret_access_key=stsResp['Credentials']['SecretAccessKey'],
                aws_session_token=stsResp['Credentials']['SessionToken']
            )
            # Pass the session to region handler, then iterate entity types
            print(all_regions_check(stsSes))
        else:
            print(all_regions_check())


def print_results(results):
    print(f"[INFO] *** Asset count complete ***")
    print(
        f"[INFO] Total EC2 instances (exluding Micro and Nano) : {results['totalEC2']}")
    print(f"[INFO] Total billable RDS Instances / databases : {results['totalRDS']}")
    print(f"[INFO] Total billable Lambda functions (60:1): {results['totalLambda']}")
    print(f"[INFO] Total billable EKS nodes: {results['totalK8sNodes']}")


#allRegionsCount = all_regions_check()
#print_results(allRegionsCount)

org_mode()