# Star Wars Unlimited Database

An application that provides a website and an API for users to search for cards from the Star Wars Unlimited collectible card game from Fantasy Flight Games.

This application is deployed on AWS and makes use of numerous AWS services.

# Route 53

Route 53 provides both domain registration and DNS routing. There are two Type A Records of note:<br/><br/>

www.swu-db.com routes requests to an Application Load Balancer<br/>
api.swu-db.com routes requests to API Gateway<br/>

# API Gateway

A REST API within API Gatway provides two resources to users:<br/>

/Cards/Search - GET is a way for users to submit the same search query string that is used when performing a search through the website.<br/>
For example, the following retrieves all cards with a Cost equal to 3 in a human readable JSON format:<br/>
https://api.swu-db.com/cards/search?q=c=3&pretty=true <br>

/Cards/{Set}/{Card} - GET allows to users to retrieve a single card using the three letter set identifier and card number.<br/>
For example, the following returns the card Darth Vader - Dark Lord of the Sith:<br/>
https://api.swu-db.com/cards/sor/010

# DynamoDB

All card data is stored in a Cards table in DynamoDB. Additionally, a DynamoDB Stream is configured on that table so that anytime a change is made a lambda function is invoked. This function retrieves all unique traits, leaders, bases, and card types and stores the results in a memcached cluster for quick retrieval.

# Lambda

The application uses three lambda functions:<br/>
## swudb-get-leader-base-traits

This is the function mentioned above that is triggered by the DynamoDB stream. When a user performs a search, theree fields are prepopulated with potential choices: leader, bases, and traits. This lambda function retrieves those values from the DynamoDB table and stores them in an ElastiCache memcached cluster for faster retrieval.

## swudb-search
## swudb-get-card

These are the backing lambda functions for the two API methods mentioned above

# Elastic Load Balancer

An application load balancer acts as the target for www requests and passes those requests to a target group. This target group is associated with an auto-scaling group. This auto-scaling group spans multiple AZs for high availability.

# EC2

The application itself runs on EC2 instances

# SNS

Users can submit feature requests/bugs/comments through the website. These requests are sent to an SNS Topic. I'm a subscriber to this topic and the requests are sent to me via e-mail.

# ElastiCache

A memcached cluster stores data that is needed by the search page.

# CloudFront /  S3

The card images are stored in an S3 bucket and retrieved by the users via a CloudFront distribution

# CI/CD

The code is stored in a CodeCommit repository and deployed using CodeDeploy. A pipeline is configured using CodePipeline that kicks off the deploy process when code is pushed to the main branch of the repo.
