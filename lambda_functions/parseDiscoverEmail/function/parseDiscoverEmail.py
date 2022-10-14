import os
import sys
import re
import datetime
import calendar
import time

import boto3
import botocore


s3client = boto3.client('s3')
BUCKET_NAME = os.getenv('bucket_name') # S3 bucket of transaction emails

ddbclient = boto3.client('dynamodb')
TABLE_NAME = os.getenv('table_name') # DynamoDB table of transaction data

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
    if 'Your purchase exceeds the amount you set' not in contents:
        sys.exit(0)
    last_digits = re.split(r'account{0}number{0}ending{0}with{0}'.format(WS),
                           contents, 1)[1][:NUM_DIGITS]
    remainder = re.split(r'Merchant:{0}'.format(WS), contents, 1)[1]
    remainder = re.split(r'{0}Amount:{0}\$'.format(WS), remainder, 1)
    payee = remainder[0]
    remainder = re.split(r'{0}Date:{0}'.format(WS), remainder[1], 1)
    amount = remainder[0]
    remainder = re.split(r'{0}Wasn\'t'.format(WS), remainder[1], 1)[0]
    date = format_date(remainder)
    return (last_digits, date, amount, payee)


def format_date(date):
    '''Convert dates to ISO 8601 (RFC 3339 "full-date") format.'''
    remainder = re.split('(?:\s|&nbsp;)+'.format(WS), date, 1)
    month_name = remainder[0]
    remainder = re.split(',{0}'.format(WS), remainder[1], 1)
    day = remainder[0]
    year = remainder[1]
    month = datetime.date.month # Fallback
    for i in range(12):
        if month_name == calendar.month_name[i]:
            month = i
            break
    return '{0}-{1}-{2}'.format(year, month, day)


def save_to_db(message_id, last_digits, date, amount, payee):
    days_before_expiration = 30
    seconds_per_day = 86400
    expiration_time = int(time.time()) + days_before_expiration * seconds_per_day
    ddbclient.put_item(TableName=TABLE_NAME,
                       Item={'message_id': {'S': message_id},
                             'last_digits': {'S': last_digits},
                             'amount': {'S': amount},
                             'payee': {'S': payee},
                             'date': {'S': date},
                             'ttl': {'N': expiration_time}
                            },
                       ConditionExpression='attribute_not_exists(message_id)')
