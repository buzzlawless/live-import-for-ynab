import os
import sys
import quopri
from datetime import datetime
import time

import boto3
import botocore
from bs4 import BeautifulSoup

s3client = boto3.client('s3')
BUCKET_NAME = os.getenv('bucket_name') # S3 bucket of transaction emails

ddbclient = boto3.client('dynamodb')
TABLE_NAME = os.getenv('table_name') # DynamoDB table of transaction data

NUM_DIGITS = 4 # Last digits of credit card


def lambda_handler(event, context):
    '''Get the email describing the transaction, parse it for the transaction
    data, and write that data to DynamoDB.'''
    ses_notification = event['Records'][0]['ses']
    message_id = ses_notification['mail']['messageId']
    contents = get_email(BUCKET_NAME, message_id)
    (last_digits, date, amount, payee) = parse(contents)
    save_to_db(message_id, last_digits, date, amount, payee)


def get_email(bucket, message_id):
    try:
        email = s3client.get_object(Bucket=bucket, Key=message_id)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            # Could not find email. Exit program.
            print('The object does not exist. Key: ' + message_id)
            sys.exit(1)
        else:
            raise
    return email['Body'].read().decode('utf-8')


def parse(contents):
    '''Parse the contents of the email for transaction data.'''
    text = extract_text(contents)
    remainder = text.split('Account ending in ')[1]
    last_digits = remainder[:NUM_DIGITS]
    remainder = remainder.split('A transaction of $')[1]
    amount = remainder.split(' was made on your account')[0]
    remainder = remainder.split('Merchant')[1]
    payee = remainder.split('Date')[0]
    remainder = remainder.split('Date')[1]
    date = format_date(remainder.split('Time')[0])
    return (last_digits, date, amount, payee)


def extract_text(contents):
    '''Extract text from Quoted-printable HTML'''
    doctype_declaration = '<!DOCTYPE HTML'
    html_doc = quopri.decodestring(
        doctype_declaration + contents.split(doctype_declaration, 1)[1]
    )
    soup = BeautifulSoup(html_doc, 'html.parser')
    return soup.get_text()


def format_date(date_string):
    '''Convert date_string from format 01/02/2022 to 2022-01-02'''
    date = datetime.strptime(date_string, '%m/%d/%Y')
    return date.strftime('%Y-%m-%d')


def save_to_db(message_id, last_digits, date, amount, payee):
    days_before_expiration = 30
    seconds_per_day = 86400
    expiration_time = str(int(time.time()) + days_before_expiration * seconds_per_day)
    ddbclient.put_item(TableName=TABLE_NAME,
                       Item={'message_id': {'S': message_id},
                             'last_digits': {'S': last_digits},
                             'amount': {'S': amount},
                             'payee': {'S': payee},
                             'date': {'S': date},
                             'ttl': {'N': expiration_time}
                            },
                       ConditionExpression='attribute_not_exists(message_id)')
