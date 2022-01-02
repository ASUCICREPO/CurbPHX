import json
import boto3
import uuid
import logging
import time

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.info("Function imports loaded")

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('EagleView_Process_Status')

def lambda_handler(lambda_event, context):
    # logger.info(json.dumps(lambda_event))
    
    records = lambda_event['Records'][0]
    event = json.loads(records['Sns']['Message'])

    logger.info("event triggered in {} seconds".format(time.time() - event['time']))
    logger.info(event)
    
    process_status = event['message']
    job_id = event['job_id'] if 'job_id' in event else str(uuid.uuid4())
    # check if an entry for the job id already exists
    response = table.get_item(Key = {
        'job_id':job_id
    })
    if 'Item' in response:
        # add the new status and update the item
        item = response['Item']
        logger.info(item)
    else:
        # create a new item for this job
        item = {
            'job_id': job_id,
            'messages': [],
        }
    
    item['messages'].append(process_status)
    item['hasError'] = item['hasError'] if 'hasError' in item else False
    event['hasError'] = event['hasError'] if 'hasError' in event else False
    item['hasError'] = item['hasError'] or event['hasError']
    if 'shpfilepaths' in event:
        item['shpfilepaths'] = event['shpfilepaths']
    logger.info(item)
    x = table.put_item(Item=item)
    logger.info(x)
    return {
        'statusCode': 200,
        'body': json.dumps('Updated process status {} for job id {}!'.format(process_status, job_id))
    }
