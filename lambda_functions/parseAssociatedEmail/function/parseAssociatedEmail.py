import os
import sys
import re
import datetime
import quopri
import io

import boto3
import botocore


s3client = boto3.client('s3')
BUCKET_NAME = os.getenv('bucket_name') # S3 bucket of transaction emails

ddbclient = boto3.client('dynamodb')
TABLE_NAME = os.getenv('table_name') # DynamoDB table of transaction data

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

# helpers (the quopri module only supports file-to-file conversion)
def encodestring(instring, tabs=0):
    outfile = io.BytesIO()
    quopri.encode(io.BytesIO(instring.encode()), outfile, tabs)
    return outfile.getvalue().decode("utf-8", "ignore")

# helpers (the quopri module only supports file-to-file conversion)
def decodestring(instring):
    outfile = io.BytesIO()
    quopri.decode(io.BytesIO(instring.encode()), outfile)
    return outfile.getvalue().decode("utf-8", "ignore")

def parse(contents):
    '''Parse the contents of the email for transaction data.'''
    contents = decodestring(contents)
    if 'Your account had a transaction' not in contents:
        sys.exit(0)
    last_digits_regex = "Account Number ending \*(\d+)"
    last_digits_all = re.search(last_digits_regex, contents)
    last_digits = last_digits_all.group(1)
    #last_digits = '1234'
    
    amount_regex = "Transaction Amount \- \$(((\d+)|,+|\.)+)"
    amount_all = re.search(amount_regex, contents)
    amount = amount_all.group(1)
    #amount = '1.99'
                         
    payee = 'Not Found' #Associated does not send the payee in the email
    
    now = datetime.datetime.now()
    date = '{0}-{1}-{2}'.format(now.year, '{:02d}'.format(now.month), now.day)
    
    return (last_digits, date, amount, payee)

def save_to_db(message_id, last_digits, date, amount, payee):
    ddbclient.put_item(TableName=TABLE_NAME,
                       Item={'message_id': {'S': message_id},
                             'last_digits': {'S': last_digits},
                             'amount': {'S': amount},
                             'payee': {'S': payee},
                             'date': {'S': date}
                            },
                       ConditionExpression='attribute_not_exists(message_id)')
