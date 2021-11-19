# Imports
import geopandas as gpd
import pandas as pd
from coordinate_grid import *
from metadata_filter_helper import *
import math
import boto3
import os
import logging
import json
from datetime import datetime
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.info("Function imports loaded")

sns = boto3.client("sns")

import uuid
import time


def lambda_handler(lambda_event, context):
    start = time.time()

    logger.info("Received an Event at {} seconds!".format(start))
    logger.info(json.dumps(lambda_event))

    try:
        records = lambda_event["Records"][0]
        sns_rec = records["Sns"]
        event = json.loads(sns_rec["Message"])
        
        job_id = event["job_id"]
        xml_file = event["xml"]
        image_s3 = event["s3"]
    
        item = {
            "message": "Generated job {} for: \n {}\n {} ".format(
                job_id, xml_file, image_s3
            ),
            "job_id": job_id,
            "time": start,
        }
    
        logger.info("xml_file received {}".format(xml_file))
        logger.info("s3 path received {}".format(image_s3))
    
        sns.publish(
            TopicArn="arn:aws:sns:us-east-1:206513143549:EV-Process-Notifier",
            Message=json.dumps(item),
        )
    
        logger.info("process status updated")
        photo_dict, images_bucket, images_path = read_xml_get_nodes(xml_file, image_s3)
    except ValueError as ve:
        item = {
            "message": str(ve),
            "job_id": job_id,
            "hasError": True,
            "time": time.time(),
        }

        sns.publish(
            TopicArn="arn:aws:sns:us-east-1:206513143549:EV-Process-Notifier",
            Message=json.dumps(item),
        )
        return {"status": "FAIL", "message": str(ve), "body": "Custom Error: No Output"}
    logger.info("{}, {}".format(images_bucket, images_path))
    logger.info("XML loaded and photo dict created {}".format(len(photo_dict)))
    # exit()

    # covnert from ECEF to WGS84
    photo_data_dict = parse_xml_get_data(photo_dict, 4978, 4326)
    logger.info("photo_data_dict created after parsing {}".format(len(photo_data_dict)))

    gdf, poly_gdf = create_geodataframe(photo_data_dict)
    logger.info("geodataframe created {}".format(len(poly_gdf)))

    today = datetime.today()

    # save file to /tmp and upload to s3 marked with timestamp
    timestamp = today.strftime("%m-%d-%y/%H:%M:%S/")
    path_prefix = "/tmp"
    shapefile = "metadata_poly"
    shp_suffix = ".shp"
    filepath = os.path.join(path_prefix, shapefile + shp_suffix)
    poly_gdf.to_file(filepath)

    export_bucket = "export-data-phx-cic"

    shapefile_prefix = "shapefiles/"
    # upload to s3
    shp_suffices = [".cpg", ".dbf", ".prj", ".shp", ".shx"]
    for suffix in shp_suffices:
        upload_file(
            os.path.join(path_prefix, shapefile + suffix),
            export_bucket,
            os.path.join(shapefile_prefix, timestamp, shapefile + suffix)
            #  shapefile_prefix + timestamp + shapefile + suffix
        )
    logger.info("uploading shapefile to s3")

    # filtering out images according to cell sizes
    # adding bounds to the poly_gdf
    bdf = poly_gdf.bounds
    data = pd.concat([poly_gdf, bdf], axis=1)

    # getting the bounds for all the image sets provided
    minmax_bbox = (data.minx.min(), data.miny.min(), data.maxx.max(), data.maxy.max())
    mean_bbox = (data.minx.mean(), data.miny.mean(), data.maxx.mean(), data.maxy.mean())

    # can change the bounding box definition here
    bbox = minmax_bbox

    # area of the main bounding box
    bbox_area = abs(bbox[0] - bbox[2]) * abs(bbox[1] - bbox[3])
    grid_area = data.area.mean() / bbox_area
    ratio = math.sqrt(grid_area)

    cells = create_grid_cells(ratio, bbox)
    logger.info("grid cells created")
    # cells.head()

    # Creating a Dataframe of filtered image bounds w.r.t the cells
    strtree, fdf = create_index_filter_image_bounds(data, cells)

    logger.info("images filtered using strtree index")
    poly_map = {}
    for index, row in data.iterrows():
        poly_map[row["geometry"].wkt] = row

    f_data = gpd.GeoDataFrame()

    logger.info("fdf len {}".format(len(fdf)))
    logger.info("poly_map len {}".format(len(poly_map)))

    for _, row in fdf.iterrows():
        try:
            match = poly_map[row["geometry"].wkt]
        except Exception as e:
            logger.info(row.geometry)
        f_data = pd.concat([f_data, match], axis=1)
    f_data = f_data.transpose()
    # f_data.head()
    logger.info("length of filtered dataframe {}".format(len(f_data)))

    export = f_data[["geometry", "filename"]]
    export.crs = "epsg:4326"

    # TODO: save this result to dynamodb or s3 or somewhere!!
    filtered_shapefilename = "filtered_poly"
    filtered_filepath = os.path.join(path_prefix, filtered_shapefilename + shp_suffix)
    export.to_file(filtered_filepath)
    for suffix in shp_suffices:
        # upload to s3
        upload_file(
            os.path.join(path_prefix, filtered_shapefilename + suffix),
            export_bucket,
            os.path.join(shapefile_prefix, timestamp, filtered_shapefilename + suffix),
            # shapefile_prefix + timestamp + filtered_shapefilename,
        )

    output = {
        "data_path": os.path.join(shapefile_prefix, timestamp, shapefile),
        "filtered_path": os.path.join(
            shapefile_prefix, timestamp, filtered_shapefilename
        ),
        "shapefile_bucket": export_bucket,
        "images_bucket": images_bucket,
        # TODO: Read these from DynamoDB
        "upload_bucket": "eagleview-unprocessed-images",
        #   "image_prefix": "image_sets/frames/images/"
        "image_prefix": images_path,
        "job_id": job_id,
    }

    logger.info(output)

    response = sns.publish(
        TopicArn="arn:aws:sns:us-east-1:206513143549:image_metadata_filter",
        Message=json.dumps(output),
        Subject="Filtered {} images down to {} in {:.3f} secs".format(
            len(data), len(export), time.time() - start
        ),
    )

    logger.info("SNS publish gave {}".format(response))

    return {
        'statusCode': 200,
        "body": "Filtered {} images down to {} in {} secs".format(
            len(data), len(export), time.time() - start
        )
    }
