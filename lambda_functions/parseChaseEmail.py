import os
import sys
import re

import boto3
import botocore
from datetime import datetime

s3client = boto3.client('s3')
BUCKET_NAME = os.getenv('bucket_name') # S3 bucket of transaction emails

ddbclient = boto3.client('dynamodb')
TABLE_NAME = os.getenv('table_name') # DynamoDB table of transaction data

DATE_LEN = 10 # len('12/30/2015')
NUM_DIGITS = 4 # Last digits of credit card
WS = '(?:\s|&nbsp;)*' # Whitespace regex


def lambda_handler(event, context):
    '''Get the email describing the transaction, parse it for the transaction
    data, and write that data to DynamoDB.'''
    ses_notification = event['Records'][0]['ses']
    message_id = ses_notification['mail']['messageId']
    try:
        email = s3client.get_object(Bucket=BUCKET_NAME, Key=message_id)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            # Could not find email. Exit program.
            print('The object does not exist. Key: ' + message_id)
            sys.exit(1)
        else:
            raise
    contents = email['Body'].read().decode('utf-8')
    (last_digits, date, amount, payee) = parse(contents)
    save_to_db(message_id, last_digits, date, amount, payee)


def parse(contents):
    '''Parse the contents of the email for transaction data.'''
    if 'Your Single Transaction Alert from Chase' not in contents:
        sys.exit(0)
    remainder = re.split(r'ending{0}in{0}'.format(WS), contents, 1)[1]
    last_digits = remainder[:NUM_DIGITS]
    remainder = re.split(r'charge{0}of{0}\(\$USD\){0}'.format(WS),
                         remainder, 1)[1]
    remainder = re.split(r'{0}at{0}'.format(WS), remainder, 1)
    amount = remainder[0]
    remainder = re.split(r'{0}has{0}been{0}authorized{0}on{0}'.format(WS),
                         remainder[1], 1)
    payee = remainder[0]
    remainder = re.split(r'{0}at'.format(WS),remainder[1],1)
    date = remainder[0]
    return (last_digits, date, amount, payee)


def format_date(date):
    '''Convert dates to ISO 8601 (RFC 3339 "full-date") format.'''
    month_day_year = date.replace(',', '').split(' ')
    month_and_day = datetime.strptime(f'{month_day_year[0]} {month_day_year[1]}', '%b %d')
    year = month_day_year[2]
    month = (f'{month_and_day:%m}') #formats datetime.month object to 2 digit string
    day = (f'{month_and_day:%d}') #formats datetime.day object to 2 digit string
    return '{0}-{1}-{2}'.format(year, month, day)


def save_to_db(message_id, last_digits, date, amount, payee):
    ddbclient.put_item(TableName=TABLE_NAME,
                       Item={'message_id': {'S': message_id},
                             'last_digits': {'S': last_digits},
                             'amount': {'S': amount},
                             'payee': {'S': payee},
                             'date': {'S': date}
                            },
                       ConditionExpression='attribute_not_exists(message_id)')

