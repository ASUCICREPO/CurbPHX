## use the following ARN to import the Lambda layer to this Lambda function for importing the dependencies

- arn:aws:lambda:us-east-1:668099181075:layer:AWSLambda-Python38-SciPy1x:29

## Add SNS 'trigger_rekognition_eagleview' subscription to this lambda 

## Add environment variable => 
1. 'UnprocessedBucket' -> 'eagleview-unprocessed-images' or the name of the bucket created for storing unprocessed images
2. 'ProcessedBucket' -> 'eagleview-processed-images' or the name of the bucket created for storing processed images

## Add DynamoDB, SNS, Rekognition and S3 full access to the execution role of the lambda function 