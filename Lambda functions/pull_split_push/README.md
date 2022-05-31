## use the geopandas.zip and create a Lambda Layer from the archive as documented [here] and include this layer in your lambda function

## Add SNS 'image_metadata_filter' subscription to this lambda 
## Add environment variable -> 
1.  'ImageStatus' -> 'ImageStatus' / or the name of the dynamodb table created to track progress of images.

## Add DynamoDB and S3 full access to the execution role of the lambda function 