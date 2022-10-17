#!/bin/bash
set -eo pipefail

Help()
{
    echo "Syntax: deploy -b budgetId -t personalAccessToken -d domain"
}

# Process input arguments

BUDGET_ID=""
PERSONAL_ACCESS_TOKEN=""
DOMAIN=""
while getopts ":hb:t:d:" option; do
   case "$option" in
      h) 
         Help
         exit 0;;
      b) 
         BUDGET_ID="$OPTARG";;
      t) 
         PERSONAL_ACCESS_TOKEN="$OPTARG";;
      d)
         DOMAIN="$OPTARG";; 
     \?)
         echo "Invalid argument: -$OPTARG"
         Help
         exit 1;;
   esac
done

# Validate arguments

if [ -z "$BUDGET_ID" ]; then
    echo "Missing budgetId"
    Help
    exit 1;
fi
if [ -z "$PERSONAL_ACCESS_TOKEN" ]; then
    echo "Missing personalAccessToken"
    Help
    exit 1;
fi
if [ -z "$DOMAIN" ]; then
    echo "Missing domain"
    Help
    exit 1;
fi

# Create AWS resources

BUCKET_NAME=ynab-lambda-artifacts-"$BUDGET_ID"
s3_bucket_exists() {   
    aws s3api head-bucket --bucket $BUCKET_NAME
}
if ! s3_bucket_exists; then
    aws s3 mb s3://"$BUCKET_NAME"
    echo "Created S3 bucket for lambda artifacts: $BUCKET_NAME"
fi

cd lambda_functions
for f in *; do
    cd "$f"
    if [ -d dependencies ]; then
        rm -r dependencies
    fi
    if [ -f requirements.txt ]; then
        echo "Installing dependencies for $f lambda function"
        python3 -m pip install --target dependencies/python/ -r requirements.txt
    fi
    cd ..
done

echo "Packaging CloudFormation template"
cd ..
aws cloudformation package \
    --template-file live_import_for_ynab_template.json \
    --s3-bucket "$BUCKET_NAME" \
    --output-template-file live_import_for_ynab_template_packaged.json \
    --use-json

echo "Deploying CloudFormation stack"
aws cloudformation deploy \
    --template-file live_import_for_ynab_template_packaged.json \
    --stack-name LiveImportForYnab \
    --parameter-overrides BudgetId="$BUDGET_ID" PersonalAccessToken="$PERSONAL_ACCESS_TOKEN" Domain="$DOMAIN" \
    --capabilities CAPABILITY_NAMED_IAM

echo "Setting live-import-for-ynab-rule-set as Simple Email Service active receipt rule set"
aws ses set-active-receipt-rule-set --rule-set-name live-import-for-ynab-rule-set

