import json
import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Key

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    # print("here")
    # print(event['queryStringParameters'])
    # lat_min=Decimal("33.29069358819772")
    # lat_max=Decimal("33.29238040364967")
    # lon_min=Decimal("-111.86183519049074")
    # lon_max=Decimal("-111.85797280950929")
    print(event)
    print('-'*100)
    print(event["queryStringParameters"])
    
    limit = 5000
    
    params = event.get("queryStringParameters",{})
    
    lat_min=Decimal(event["queryStringParameters"]['lat_min'])
    lat_max=Decimal(event["queryStringParameters"]['lat_max'])
    lon_min=Decimal(event["queryStringParameters"]['lon_min'])
    lon_max=Decimal(event["queryStringParameters"]['lon_max'])
    
    
    table = boto3.resource('dynamodb').Table('eagleview-sidewalk-features')
    
    if "last_key" in params:
        last_evaluated = json.loads(event["queryStringParameters"].get("last_key")) 
        print('last_key', last_evaluated)
        response = table.scan(
            FilterExpression='lat1 >= :lat_min and lat1 <= :lat_max and lng1 >= :lon_min and lng1 <= :lon_max',
            # FilterExpression=fe,
            ExpressionAttributeValues={
                ':lat_min': lat_min,
                ':lat_max': lat_max,
                ':lon_min': lon_min,
                ':lon_max': lon_max
            },
            Limit=limit,
            ExclusiveStartKey=last_evaluated,
        )
    else:
        response = table.scan(
            FilterExpression='lat1 >= :lat_min and lat1 <= :lat_max and lng1 >= :lon_min and lng1 <= :lon_max',
            # FilterExpression=fe,
            ExpressionAttributeValues={
                ':lat_min': lat_min,
                ':lat_max': lat_max,
                ':lon_min': lon_min,
                ':lon_max': lon_max
            },
            Limit=limit,
        )

    last_key = response.get('LastEvaluatedKey',{})

    print('last key', response.get('LastEvaluatedKey','Nothing'))
    print('len response', len(response['Items']))
    
    data=response['Items']  if len(response)!=0 else response
    
    return {
        'statusCode': 200,
        'headers': {
            "Access-Control-Allow-Origin": "*",
            "Last-Key": json.dumps(last_key)
        },
        'body': json.dumps(data, cls=DecimalEncoder)
    }