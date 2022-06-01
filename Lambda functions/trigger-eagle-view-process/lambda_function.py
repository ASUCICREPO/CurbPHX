import json
import boto3
import logging
import time

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.info("Function imports loaded")

def lambda_handler(event, context):
    
    sns = boto3.client('sns')
    
    # start the process
    try:
        logger.info(json.dumps(event))
        
        # get the query parameters
        if "queryStringParameters" not in event:
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {"error": "job_id, s3, xml should be passed as a query parameter!"}
                ),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods":"GET",
                },
            }
    
        params = event["queryStringParameters"]
    
        if "job_id" not in params or "s3" not in params or "xml" not in params:
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {"error": "job_id, s3 and xml should be passed as a query parameter!"}
                ),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods":"GET",
                },
            }
    
        job_id = params["job_id"]
        
        sns.publish(
            TopicArn="arn:aws:sns:us-east-1:206513143549:trigger-ev-process",
            Message=json.dumps(params),
        )
        logger.info("process started")
    except Exception as e:
        if job_id:
            item = {
                "message": str(e),
                "job_id": job_id,
                "hasError": True,
                "time": time.time(),
            }
            sns.publish(
                TopicArn="arn:aws:sns:us-east-1:206513143549:EV-Process-Notifier",
                Message=json.dumps(item),
            )
        return {
            "status": "FAIL", 
            "message": str(e), 
            "body": "Custom Error: No Output",
            "headers": {
                "Content-Type": "application/text",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods":"GET",
            }
        }

    return {
        'statusCode': 200,
        'body': json.dumps({'message':'Succesfully started the process.'}),
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods":"GET",
        }
    }
