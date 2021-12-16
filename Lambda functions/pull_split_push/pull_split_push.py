# Lambda script to pull the filtered images, split them, add metadata and
# upload them to the unprocessed bucket

import time
from coordinate_grid import *
import os
import geopandas as gpd
import boto3
from shapely.geometry import Point, Polygon
import pandas as pd

# import matplotlib.pyplot as plt
from PIL import Image
import boto3
from botocore.exceptions import ClientError
import logging
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.info("Function imports loaded")

s3_cli = boto3.client("s3")
s3_res = boto3.resource("s3")
sns_cli = boto3.client("sns")
table = boto3.resource("dynamodb").Table("ImageStatus")


def upload_file(file_name, bucket, object_name=None, metadata={}):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = file_name

    # Upload the file
    try:
        response = s3_cli.upload_file(
            file_name, bucket, object_name, ExtraArgs={"Metadata": metadata}
        )
    except ClientError as e:
        logging.error(e)
        return False
    return True


def lambda_handler(lambda_event, context):
    logger.info(json.dumps(lambda_event))
    dl_start = time.time()

    records = lambda_event["Records"][0]
    sns = records["Sns"]
    event = json.loads(sns["Message"])

    job_id = event["job_id"]
    filtered_path = event["filtered_path"]
    data_path = event["data_path"]
    shapefile_bucket = event["shapefile_bucket"]
    shp_suffices = [".cpg", ".dbf", ".prj", ".shp", ".shx"]

    item = {
        "message": "{}, Starting the upload to the unprocessed bucket.".format(
            sns["Subject"]
        ),
        "job_id": job_id,
        "time": dl_start,
    }

    sns_cli.publish(
        TopicArn="arn:aws:sns:us-east-1:206513143549:EV-Process-Notifier",
        Message=json.dumps(item),
    )

    save_loc = "/tmp/"
    try:
        logger.info("Starting download from {}".format(shapefile_bucket))
        # download all filtered shp files
        for suffix in shp_suffices:
            logger.info(
                "downloading from {}, file {}, at {}".format(
                    shapefile_bucket,
                    filtered_path + suffix,
                    save_loc + "filtered" + suffix,
                )
            )
            s3_cli.download_file(
                shapefile_bucket, filtered_path + suffix, save_loc + "filtered" + suffix
            )
        # download all data shp files
        for suffix in shp_suffices:
            logger.info(
                "downloading from {}, file {}, at {}".format(
                    shapefile_bucket, data_path + suffix, save_loc + "data" + suffix
                )
            )
            s3_cli.download_file(
                shapefile_bucket, data_path + suffix, save_loc + "data" + suffix
            )
    except Exception as e:
        logger.info(e)
        msg = "Error downloading, {}".format(str(e))
        item = {"message": msg, "job_id": job_id, "hasError": True, "time": time.time()}

        sns_cli.publish(
            TopicArn="arn:aws:sns:us-east-1:206513143549:EV-Process-Notifier",
            Message=json.dumps(item),
        )
        raise ValueError(msg)

    logger.info("completed download in {} seconds".format(time.time() - dl_start))

    # to be read from the events
    filtered = gpd.read_file(save_loc + "filtered.shp")

    # to be read from the events
    # upload_bucket = "eagleview-unprocessed-images"
    upload_bucket = event["upload_bucket"]
    images_bucket = event["images_bucket"]
    dl_path = save_loc
    # + 'tiles/'
    prefix = event["image_prefix"]

    
   
    filenames = filtered.filename.values
    

    # TODO: read this from environment variables?
    split = 9

    logger.info("Starting processing of {} files".format(len(filenames)))
    proc_start = time.time()
    count_proc = 0
    try:
        for filename in filenames:
            # check if the file has already been processed
            s3_uri = 's3://{}/{}{}'.format(images_bucket, prefix, filename)
            response = table.get_item(Key={'s3_uri':s3_uri,})
            if 'Item' in response:
                logger.info("{} already processed, moving on".format(s3_uri))
                continue
            
            loop_start = time.time()

            # initialize variables for this loop
            filepath = os.path.join(dl_path, filename)
            file_prefix = filename.split(".")[0]
            
            logger.info(
                "downloading image {} from path {} to {}".format(
                    filename, prefix + filename, filepath
                )
            )
            # download the image
            s3_cli.download_file(images_bucket, prefix + filename, filepath)

            # split them in 'split' chunks
            tiles = image_slicer.slice(filepath, split, save=False)

            logger.info("splitting {} in {} parts".format(filename, split))
            # save them locally for processing
            tiles = image_slicer.save_tiles(
                tiles,
                prefix=file_prefix,
                # TODO: change the save directory to be S3 ?
                directory=dl_path,
            )  # get lat/long coordinates for each split
            gdf_part = get_tile_geodataframe(
                tiles, filename, split, save_loc + "data.shp"
            )
            count_proc += 1
            # upload each split
            for _, row in gdf_part.iterrows():
                split_filename = row.filename
                logger.info("processing {}".format(split_filename))
                path = os.path.join(dl_path, split_filename)
                img = Image.open(path)
                metadata = {
                    "top_right": row.top_right,
                    "top_left": row.top_left,
                    "bottom_right": row.bottom_right,
                    "bottom_left": row.bottom_left,
                    # Add image width and height to each
                    "width": str(img.width),
                    "height": str(img.height),
                }
                upload_file(path, upload_bucket, split_filename, metadata)
                # close the PIL image
                img.close()
                # delete the downloaded images
                if os.path.exists(path):
                    os.remove(path)
                else:
                    logger.info("The file at {} does not exist".format(path))
            
            item ={
                's3_uri':s3_uri,
                'uploaded': True,
                'processed':False
            }        
            logger.info('updating {} status in DynamoDB'.format(s3_uri))
            table.put_item(Item=item)
            
            logger.info(
                "processed {} splits of {} in {} seconds".format(
                    split, filename, time.time() - loop_start
                )
            )
            # TODO: Remove these breaks and process one image per request
            # USE DynamoDB to track progress??
            break
    except Exception as e:
        item = {
            "message": str(e),
            "job_id": job_id,
            "hasError": True,
            "time": time.time(),
        }

        sns_cli.publish(
            TopicArn="arn:aws:sns:us-east-1:206513143549:EV-Process-Notifier",
            Message=json.dumps(item),
        )
        raise e

    item = {"job_id": job_id, "split": split}

    response = sns_cli.publish(
        TopicArn="arn:aws:sns:us-east-1:206513143549:trigger_rekognition_eagleview",
        Message=json.dumps(item),
        Subject="Uploaded {} more images using {} splits in {:.3f} seconds".format(
            count_proc, count_proc*split, time.time() - proc_start
        ),
    )

    logger.info("SNS publish gave {}".format(response))
    return {
        "Status": "Success",
        "Body": "processed {} images in {:.3f} seconds".format(
            count_proc, time.time() - proc_start
        ),
    }
