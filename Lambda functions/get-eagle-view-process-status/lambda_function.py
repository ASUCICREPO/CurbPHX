import json
import boto3


def lambda_handler(event, context):
    print(json.dumps(event))

    # get the query parameters

    if "queryStringParameters" not in event:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {"error": "job_id should be passed as a query parameter!"}
            ),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods":"GET",
            },
        }

    params = event["queryStringParameters"]

    if "job_id" not in params:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {"error": "job_id should be passed as a query parameter!"}
            ),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods":"GET",
            },
        }

    job_id = params["job_id"]

    table = boto3.resource("dynamodb").Table("EagleView_Process_Status")

    response = table.get_item(Key={"job_id": job_id})

    if "Item" not in response:
        item = {"job_id": job_id}
    else:
        item = response["Item"]

    return {
        "statusCode": 200,
        "body": json.dumps(item),
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods":"GET",
        },
    }
