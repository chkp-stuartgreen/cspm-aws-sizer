import boto3
from math import ceil
from botocore.exceptions import ClientError
import argparse

default_region = 'eu-west-1'
errorsEncountered = 0


# Gather EC2 instances and EKS nodes
def count_instances_and_nodes(region, session=None):
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

    for reg in regions:
        print(f"[INFO] Checking region {reg}")
        ec2_and_nodes = count_instances_and_nodes(reg, session)
        billableEC2 += ec2_and_nodes['instances']
        billableNode += ec2_and_nodes['nodes']
        billableLamb += count_lambdas(reg, session)
        billableRDS += count_rds(reg, session)

    return {"totalEC2": billableEC2, "totalLambda": billableLamb, "totalK8sNodes": billableNode, "totalRDS": billableRDS}


def org_mode(orgRoleName='OrganizationAccountAccessRole'):
    # Assume role, get token, list accounts, assume to each account
    # run commands

    orgClient = boto3.client('organizations')
    resp = orgClient.list_accounts()
    accountNumbers = list(map(lambda a: a['Id'], resp['Accounts']))
    stsClient = boto3.client('sts')
    currentAccount = stsClient.get_caller_identity()['Account']

    orgTotalEC2 = 0
    orgTotalLambda = 0
    orgTotalK8sNodes = 0
    orgTotalRDS = 0

    for account in accountNumbers:
        # Assume into each account
        # (Don't assume into account if it's the current account for user)
        if account != currentAccount:
            org_account_arn = 'arn:aws:iam::' + account + \
                ':role/' + orgRoleName
            print(f"[INFO] Checking account: {account}")
            print(f"[INFO] Using role {org_account_arn} for STS Assume Role")

            try:
                stsResp = stsClient.assume_role(
                    RoleArn=org_account_arn,
                    RoleSessionName='CloudGuard_AssetCounter',
                    DurationSeconds=1800
                )
            except ClientError as e:
                global errorsEncountered
                errorsEncountered = 1
                print(f"[ERROR] Could not assume into account {account}")
                print(f"[ERROR] Message: {e}")
                continue
            stsSes = boto3.Session(
                aws_access_key_id=stsResp['Credentials']['AccessKeyId'],
                aws_secret_access_key=stsResp['Credentials']['SecretAccessKey'],
                aws_session_token=stsResp['Credentials']['SessionToken']
            )
            # Pass the session to region handler, then iterate entity types
            results = all_regions_check(stsSes)

        else:
            results = all_regions_check()

        orgTotalEC2 += results['totalEC2']
        orgTotalLambda += results['totalLambda']
        orgTotalK8sNodes += results['totalK8sNodes']
        orgTotalRDS += results['totalRDS']

    return {"totalEC2": orgTotalEC2, "totalLambda": orgTotalLambda, "totalK8sNodes": orgTotalK8sNodes, "totalRDS": orgTotalRDS}


def print_results(results):
    print(f"[INFO] *** Asset count complete ***")
    print(
        f"[INFO] Total EC2 instances (exluding Micro and Nano) : {results['totalEC2']}")
    print(f"[INFO] Total RDS Instances / databases : {results['totalRDS']}")
    print(f"[INFO] Total Lambda functions : {results['totalLambda']}")
    print(f"[INFO] Total EKS nodes: {int(results['totalK8sNodes']) * 3}")
    grandTotal = results['totalEC2'] + results['totalRDS'] + \
        (results['totalK8sNodes'] * 3) + (ceil(results['totalLambda'] / 60))
    print(
        f"[INFO] Total billable assets (including above plus 60:1 Lambda, 1:3 EKS Nodes): {grandTotal}")
    if errorsEncountered:
        print(
            f"[WARNING] Errors were encountered - please see above output. Results may not be accurate.")


def main():
    #args = dict([arg.split('=') for arg in sys.argv[1:]])
    #if '--help' in args:
    #    print_help()
    #    exit()
    #if '--org-mode' and '--org-role-name' in args:
    #    print(f"[INFO] Running in Organizations mode")
    #    print(f"[INFO] Using custom role name '{args['--org-role-name']}'")
    #    results = org_mode(args['--org-role-name'])
    #elif '--org-mode' in args:
    #    print("[INFO] Running in Organizations mode, default role name...")
    #    results = org_mode()
    #else:
    #    print("[INFO] Running in single account mode...")
    #    results = all_regions_check()
    #
    #print_results(results)
    parser = argparse.ArgumentParser(description = "CSPM billable asset counter for AWS. \
        A tool to scan single accounts or AWS Organizations to count billable assets for CloudGuard CSPM.\
        This tool uses the AWS CLI credentials to connect with your AWS accounts.\
        If you plan to use it with an AWS Organization, please make sure your AWS CLI user has cross-account\
        permissions in each child account.")
    parser.add_argument("--org-mode", help="Scan all accounts in an organisation. Requires cross-account permissions on AWS CLI user.", action="store_true")
    parser.add_argument("--org-role-name", help="Specify a role to assume in child accounts (default is OrganizationAccountAccessRole)")
    args = parser.parse_args()
    if args.org_mode and args.org_role_name:
        print(f"[INFO] Running in org mode with custom role name {args.org_role_name}...")
        results = org_mode(args.org_role_name)
    elif args.org_role_name and not args.org_mode:
        print(f"[INFO] Assuming org mode (role name provided without --org-mode) with custom role name {args.org_role_name}...")
        results = org_mode(args.org_role_name)
    elif args.org_mode:
        print("[INFO] Running in org mode, default assume role")
        results = org_mode()
    else:
        print("[INFO] Running in single account mode...")
        results = all_regions_check()
    
    print_results(results)

if __name__ == "__main__":
    main()