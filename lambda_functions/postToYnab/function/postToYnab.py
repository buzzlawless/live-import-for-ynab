import os
import sys
import json

import boto3
import botocore
import requests


s3client = boto3.client('s3')
BUCKET_NAME = os.getenv('bucket_name') # S3 bucket of transaction emails
ddbclient = boto3.client('dynamodb')
TABLE_NAME = os.getenv('table_name') # DynamoDB table of transactions

PERSONAL_ACCESS_TOKEN = os.getenv('personal_access_token') # YNAB Token
BUDGET_ID = os.getenv('budget_id') # YNAB Budget Id
TIMEOUT = 5 # Seconds to wait for YNAB API

def lambda_handler(event, context):
    for record in event['Records']:
        if record['eventName'] == 'INSERT':
            image = record['dynamodb']['NewImage']
            message_id = image['message_id']['S']
            if is_duplicate_invocation(message_id):
                continue
            cleanup(message_id)
            transaction_data = {'transaction': {
                'account_id': get_account_id(image['last_digits']['S']),
                'date': image['date']['S'],
                'amount': to_milliunits(image['amount']['S']),
                'payee_name': image['payee']['S'],
                'cleared': 'uncleared'}
            }
            post_transaction(transaction_data)


def is_duplicate_invocation(message_id):
    '''Checks if this lambda function has already been invoked for this
    transaction'''
    response = ddbclient.get_item(TableName=TABLE_NAME,
                                  Key={'message_id': {'S': message_id}},
                                  ConsistentRead=True)
    return 'Item' not in response


def get_account_id(last_digits):
    '''Get the account id for the transaction. YNAB account name must include
    last four digits of card number.'''
    accounts = get_accounts()
    for account in accounts:
        if account['note'] is not None and last_digits in account['note']:
            return account['id']
    # Could not find account id. Exit program.
    print('Could not find account name containing ' + last_digits)
    sys.exit(1)


def get_accounts():
    '''Query YNAB to get the list of accounts.'''
    headers = {'accept': 'application/json',
               'Authorization': 'Bearer {0}'.format(PERSONAL_ACCESS_TOKEN)}
    try:
        r = requests.get('https://api.youneedabudget.com/v1/budgets/{0}/'
                        'accounts'.format(BUDGET_ID), headers=headers,
                        timeout=TIMEOUT)
    except requests.exceptions.Timeout:
        # YNAB API unresponsive. Exit program
        print('Timed out waiting for YNAB API.')
        sys.exit(1)

    if r.status_code == 200:
        return r.json()['data']['accounts']
    # Error calling API. Exit program.
    print('YNAB API GET request error')
    print(r.json())
    sys.exit(1)


def to_milliunits(amount):
    return -int(float(amount) * 1000)


def post_transaction(data):
    headers = {'accept': 'application/json',
               'Content-Type': 'application/json',
               'Authorization': 'Bearer {0}'.format(PERSONAL_ACCESS_TOKEN)}
    try:
        r = requests.post('https://api.youneedabudget.com/v1/budgets/{0}/'
                          'transactions'.format(BUDGET_ID),
                          data=json.dumps(data), headers=headers,
                          timeout=TIMEOUT)
    except requests.exceptions.Timeout:
        # YNAB API unresponsive. Exit program
        print('Timed out waiting for YNAB API.')
        sys.exit(1)
    if r.status_code != 201:
        # Error calling API. Exit program.
        print('YNAB API POST request error')
        print(r.json())
        print('Attempted to post:\n' + json.dumps(data))
        sys.exit(1)


def cleanup(message_id):
    ddbclient.delete_item(TableName=TABLE_NAME,
                          Key={'message_id': {'S': message_id}})
    s3client.delete_object(Bucket=BUCKET_NAME, Key=message_id)
