# ynab-live-import
Automatically import transactions to YNAB [(You Need a Budget)](https://youneedabudget.com) in real-time!

YNAB is great, but manually entering your transactions is kind of a bummer.  Auto-import is great, but I'm not crazy about giving up my bank account username and password.  And having to wait a few days for transactions to clear before they can be imported also isn’t ideal. File-based import gets the job done but is quite the hassle.

Wouldn’t it be great – magical, even – if YNAB could automatically import all your transactions in real-time with no effort on your part?  Thanks to the fantabulous YNAB API, this is now possible!

After a quick one-time setup, any credit card transaction will automatically appear in YNAB mere seconds after the purchase.    

I’ve only programmed support for Chase and Discover credit cards for now but the YNAB developer community and I can add support for other cards to this open-source project. Automatically importing debit card transactions, ATM withdrawals and deposits, bank transfers, and direct deposits are all possible and support for these can be added in the future!

# Demo Video

Click the image to watch a demo purchase!

[![](https://s3.amazonaws.com/ynab-live-import-misc/DemoVideoPreview.jpg)](https://vimeo.com/285756273)

Music credits:

Happy Alley Kevin MacLeod (incompetech.com)

Licensed under Creative Commons: By Attribution 3.0

http://creativecommons.org/licenses/by/3.0/

## So how does it work?

The idea sprung into mind after reading this article on [the secret API of banks](http://gduverger.com/secret-api-banks). Banks, especially in the US,  are not as gracious as YNAB and do not provide an API for developers. But, there’s a workaround. We’re all familiar with the email letting us know when there’s been a charge greater than $100, for example, alerting us to possible credit card theft. It turns out you can set this threshold to $0 and receive an email about every transaction. All that’s left is to programmatically parse the email to find the relevant information and submit it to YNAB! And don’t worry, you’ll set up a separate email for these notifications so your inbox won’t be bombarded with notifications.

### For techies

The whole stack runs on Amazon Web Services. Simple Email Service receives a notification email, saves it to S3, and triggers a particular lambda function tailored to whichever bank the notification came from. The lambda function retrieves the email from S3, parses it for transaction data (account, payee, amount, date), and writes that data to a DynamoDB table. The table has a stream enabled, which triggers another lambda function when the table is updated.  The function reads the transaction data from the stream and posts the transaction to YNAB using their API. The function finally deletes the email from S3 and the transaction data from DynamoDB.

All of the above can be deployed from a CloudFormation template.

# Setup

After this one-time setup, all future imports are automatic.

## 1. Create a free Amazon Web Services account (~1 minute)
Go to https://aws.amazon.com/ and create an account if you don't already have one.
## 2. Register a domain name if you don’t already have one (~5 minutes)
Register a domain [using Amazon Route 53](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/domain-register.html) ($12/year for a .com domain) if you don’t already have one.  If you already have a domain name (with any domain registrar, not just Amazon Route 53), you can use that instead.  I recommend Amazon Route 53 if you’re registering a new domain because it makes the next step a bit easier.
## 3. Verify your domain with Amazon Simple Email Service (~5 minutes)
Follow [these instructions](https://docs.aws.amazon.com/ses/latest/DeveloperGuide/verify-domain-procedure.html).  No need for DKIM signing.
## 4. Set up email notifications with your bank (~5 minutes)
As of today, only Chase and Discover are supported.
### Chase
Login to your account at [Chase.com](https://www.chase.com/).

Click the hamburger menu in the upper-left corner.

![Chase1](https://s3.amazonaws.com/ynab-live-import-misc/Chase1.png)

Click “Profile & settings”

![Chase2](https://s3.amazonaws.com/ynab-live-import-misc/Chase2.png)

Click “Alerts delivery”

![Chase3](https://s3.amazonaws.com/ynab-live-import-misc/Chase3.png)

Click “Add”

![Chase4](https://s3.amazonaws.com/ynab-live-import-misc/Chase4.png)

Add “chaseynab@yourdomain.com”, but replace “yourdomain” with the domain name you verified with Simple Email Service.  The nickname can be whatever you’d like.  Select “Plain text” for the email format.

![Chase5](https://s3.amazonaws.com/ynab-live-import-misc/Chase5.png)

Click “Choose alerts”

![Chase6](https://s3.amazonaws.com/ynab-live-import-misc/Chase6.png)

Click “Protection and security”.  Add an email alert for the YNAB email for card transactions over $0

![Chase7](https://s3.amazonaws.com/ynab-live-import-misc/Chase7.png)

### Discover
Login to your account at Discover.com
Go to the Profile page, click “Edit contact info”, and change your email address to “discoverynab@yourdomain.com”, but replace “yourdomain” with the domain name you verified with Simple Email Service.

![Discover](https://s3.amazonaws.com/ynab-live-import-misc/Discover.png)

## 5. Add the last 4 digits of your credit card to your YNAB account’s note section (~1 minute)
Login to your [YNAB](https://app.youneedabudget.com/) account.  Add the last 4 digits of your card number to your YNAB account notes section.  E.g. if your last 4 digits are 1234, it should look like this:

![YNAB](https://s3.amazonaws.com/ynab-live-import-misc/YNAB.png)

It’s okay to have other information in the notes section, but the digits have to be in there somewhere.

## 6. Click "Launch Stack" (~1 minute)
[![](https://s3.amazonaws.com/ynab-live-import-misc/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/create/review?filter=active&templateURL=https%3A%2F%2Fs3.amazonaws.com%2Fynab-live-import-cloud-formation-templates%2FynabLiveImport.template&stackName=YnabLiveImport)

Fill in "BudgetId" with the ID of the budget you want to import to.  Your budget ID can be found in the URL when you're looking at that budget in YNAB.

![YNAB2](https://s3.amazonaws.com/ynab-live-import-misc/YNAB2.png)

Fill in "Domain" with the domain you verified with Amazon Simple Email Service.  Include the ".com", e.g. "example.com".

Fill in "Personal Access Token" with your YNAB personal access token.  [Click here](https://api.youneedabudget.com/#personal-access-tokens) to read instructions for finding your token.  Note that that page says, "You should not share this access token with anyone or ask for anyone else's access token. It should be treated with as much care as your main account password."  It's okay for you to submit your token here because the live import infrastructure you're setting up exists on your very own personal Amazon Web Services account that you alone have access to.  Everyone who follows these directions is setting up their own live import system that they control, there is no central live import system that stores people's tokens... that would be bad!

When the Status changes from "CREATE_IN_PROGRESS" to "CREATE_COMPLETE" (a couple minutes), you're almost done!

## 7. Activate live import! (~1 minute)

Go to your [Simple Email Service Rule Sets](https://console.aws.amazon.com/ses/home#receipt-rules:) and activate "ynab-live-import-rule-set"

![RuleSet](https://s3.amazonaws.com/ynab-live-import-misc/RuleSet.png)

That's it! Automatic credit card imports with no effort on your part are now setup.

# FAQs
## How much does this cost?
Other than the cost of a domain ($12/year with Amazon Route53), absolutely free up to 1,000 transactions/month!  I doubt anyone regularly uses their credit cards more than 33 times a day, but if you do, it’ll only cost a few cents.

## Can you read my transaction emails?
Nope! The beauty of this solution is that the entire infrastructure is hosted on your very own Amazon Web Services account that you alone have access to.

## What accounts/transactions are supported?
Right now Chase and Discover credit card transactions are supported.  I hope to add support for debit card transactions, ATM withdrawals and deposits, bank transfers, and direct deposits in the near future.
