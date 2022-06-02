## use the geopandas.zip and create a Lambda Layer from the archive as documented [here] and include this layer in your lambda function

## Add SNS 'trigger-ev-process' lambda subscription to this lambda 

## Add environment variable => 
1.  'UnprocessedBucket' -> 'eagleview-unprocessed-images' or the name of the bucket created for storing unprocessed images

## Add SNS and S3 full access to the execution role of the lambda function 