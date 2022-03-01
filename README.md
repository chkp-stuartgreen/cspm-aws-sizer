# CloudGuard CSPM - AWS Asset Counter

### A tool to count billable assets in single AWS accounts or across AWS Ogranizations.

This tool requires the AWS CLI to be installed and configured with access to the account you wish to scan. 
The commands used by Boto3 are:
- STS Assume role
- STS get-caller-identity
- EC2 describe-instances
- EC2 describe-regions
- RDS describe-db-instances
- Lambda list-tags
- Lambda list-functions
- Organizations list-accounts

When using organizations mode (`--org-mode`) - it will use the suggested AWS role of OrganizationAccountAccessRole. If you use a different role name, please provide it using `--org-role-name`

### Usage

Single account mode: `python3 main.py`
Organization mode, default cross-account role: `python3 main.py --org-mode`
Organization mode, custom role name: `python3 main.py --org-mode --org-role-name MyCustomRoleName`

Sample output:

