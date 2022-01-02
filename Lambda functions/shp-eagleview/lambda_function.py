from pytz import timezone
from datetime import datetime
import tempfile
import os
import simplekml
import boto3
import json
import hashlib
import time
from decimal import Decimal
from shapely.geometry import LineString
import geopandas as gpd
import glob
import shutil

sns_cli = boto3.client('sns')

def updateStatus(process, status):
    table = boto3.resource('dynamodb').Table('ProcessStatus')
    response = table.update_item(
        Key={
            'process': process
        },
        UpdateExpression="set proc_status = :s",
        ExpressionAttributeValues={
            ':s': Decimal(status)
        },
        ReturnValues="UPDATED_NEW"
    )
    return response

def lambda_handler(lambda_event, context):
    records = lambda_event['Records'][0]
    sns = records['Sns']
    event = json.loads(sns['Message'])
    job_id = event['job_id']
    start = time.time()
    
    item = {
        'message': 'Generating shp/kml files...',
        'job_id':job_id,
        'time': time.time()
    }
    
    sns_cli.publish(
        TopicArn="arn:aws:sns:us-east-1:206513143549:EV-Process-Notifier",
        Message=json.dumps(item),
    )
    

    try:
        print("Received event: " + json.dumps(event, indent=2))
        print('starting KML processing')
        kml = simplekml.Kml()
    
        # scanning all items
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('eagleview-sidewalk-features')
        response = table.scan()
        items = response['Items']
        print(len(items))
        # while 'LastEvaluatedKey' in response:
        #     print(response['LastEvaluatedKey'])
        #     response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        #     items.extend(response['Items'])
    
        print('dtype of items is {}'.format(type(items)))
    
        Detached_Sidewalk = 'Detached Sidewalk'
        Sidewalk = 'Sidewalk'
        No_Sidewalk = 'No Sidewalk'
        # Advance_By = 0.0001
    
        sidewalkColorMap = {}
        sidewalkColorMap[Sidewalk] = simplekml.Color.orange
        sidewalkColorMap[Detached_Sidewalk] = simplekml.Color.green
        sidewalkColorMap[No_Sidewalk] = simplekml.Color.red
    
        datapoints = {
            'id':[],
            'label':[],
            'color':[],
            'geometry':[]
        }
    
        for item in items:
            feature = item['label']
            coords = [(item['lat1'], item['lng1']), (item['lat2'], item['lng2'])]
            # print(coords)
            lns = kml.newlinestring(
                name=feature,
                coords=coords
            )
            lns.extrude = 5
            lns.altitudemode = simplekml.AltitudeMode.relativetoground
            lns.style.linestyle.color = sidewalkColorMap[feature]
            coords_shp = [(item['lng1'], item['lat1']), (item['lng2'], item['lat2'])]
            datapoints['id'].append(item['PlaceID'])
            datapoints['label'].append(item['label'])
            datapoints['geometry'].append(LineString(coords_shp))
            datapoints['color'].append(sidewalkColorMap[feature])
    
        gdf = gpd.GeoDataFrame(datapoints,crs="EPSG:4326")
    
        # processing done, now move to S3 bucket
        print('loading s3')
        s3_client = boto3.client('s3')
        s3_res = boto3.resource('s3')
    
        # add to bucket
    
        def upload_file(file_name, bucket_name, object_name):
            # If S3 object_name was not specified, use file_name
            import logging
            if object_name is None:
                object_name = file_name
            # Upload the file
            try:
                response = s3_client.upload_file(
                    file_name, bucket_name, object_name)
                print(response)
            except Exception as e:
                logging.error(e)
            # return success status
                return False
            return True
    
        # create bucket (if it doesn't exist)
    
        def create_bucket(bucket_name, region=None):
            import logging
            try:
                if region is None:
                    s3_client.create_bucket(Bucket=bucket_name)
                    print("bucket created", bucket_name)
                else:
                    location = {'LocationConstraint': region}
                    s3_client.create_bucket(Bucket=bucket_name,
                                            CreateBucketConfiguration=location)
            except Exception as e:
                logging.error(e)
            # return success status
                return False
            return True
    
        # function to get the time at export of data
    
        def get_export_time():
            tz = timezone('MST')
            now = datetime.now(tz)
            return now.strftime("%m-%d-%Y/%H:%M:%S")
    
        print('creating a temporary directory for the export')
        # save the processed information and export to s3
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            filename = os.environ['kml_file_name']
            shpfilename = os.environ['shp_file_name']
            bucket_name = os.environ['bucket_name']
            print('saving {} at {} bucket'.format(filename, bucket_name))
            kml.save(filename)
            # create bucket if doesn't exist
            create_bucket(bucket_name)
            # set to MST
            # time_str=get_export_time()
            
            # use job id s s3 path directory
            filepath = '{}/{}'.format(job_id, filename)
            # pushLog("Done! KML created. Starting upload to s3.")
            upload_file(filename, bucket_name, filepath)
    
            poly_gdf = gpd.GeoDataFrame(gdf[['id','label','geometry']], crs="EPSG:4326")
            poly_gdf.crs = {'proj': 'latlong', 'ellps': 'WGS84', 'datum': 'WGS84', 'no_defs': True}
            poly_gdf.columns = ['id','label','geometry']
            
            # poly_gdf.to_file(shpfilename)
            
            zipfilename = '{}'.format(shpfilename.split('.')[0])
            
            poly_gdf.to_file(filename=zipfilename, driver='ESRI Shapefile')
            
            # Compress folder into 'filename.zip'
            shutil.make_archive(zipfilename, 'zip', root_dir = zipfilename)
            print('zipped file name {}.zip'.format(zipfilename))
            
            # Clean up
            shutil.rmtree(zipfilename)
            
            shpPackFiles = glob.glob(shpfilename.split(".")[0]+'.*')
            print(shpPackFiles)
            
            shpFilePaths = []
            
            for shpName in shpPackFiles:
                # use job id s s3 path directory
                shpfilepath = '{}/{}/{}'.format(job_id, "shp", shpName)
                shpFilePaths.append(shpfilepath)
                upload_file(shpName, bucket_name, shpfilepath)
            # pushLog("Done! Uploaded KML to s3 at "+filepath)
            print('upload done at path', filepath)
            
            presigned = []
            # generating pre-signed URI's for download
            # KML
            response = s3_client.generate_presigned_url('get_object',
                                          Params={'Bucket': bucket_name,'Key': filepath},
                                          ExpiresIn=3600)
            presigned.append(response)
            
            # print(response)
            
            # SHP
            for file in shpFilePaths:
                response = s3_client.generate_presigned_url('get_object',
                                              Params={'Bucket': bucket_name,'Key': file},
                                              ExpiresIn=3600)
                presigned.append(response)
                # print(response)
            
            print(presigned)
            
            item = {
                'message': 'Processed kml and shp files in {:.3f} seconds. Process Ended!'.format(time.time() - start),
                'shpfilepaths': presigned,
                'job_id':job_id,
                'time': time.time(),
            }
            
            sns_cli.publish(
                TopicArn="arn:aws:sns:us-east-1:206513143549:EV-Process-Notifier",
                Message=json.dumps(item),
            )

        return None
    except Exception as e:
            item = {
                'message': str(e),
                'job_id':job_id,
                'hasError':True,
                'time': time.time()
            }
            
            sns_cli.publish(
                TopicArn="arn:aws:sns:us-east-1:206513143549:EV-Process-Notifier",
                Message=json.dumps(item),
            )
            return {"status": "FAIL", "message": str(e), "body": "Custom Error: No Output"}
