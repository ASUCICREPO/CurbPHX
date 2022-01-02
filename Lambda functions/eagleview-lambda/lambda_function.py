import boto3
from decimal import Decimal
import json
import os
import logging
import ast
import time
# import urllib.request
# import urllib.parse
# import urllib.error
logger = logging.getLogger()
logger.setLevel(logging.INFO)
import numpy as np
from scipy.spatial import distance

print('Loading function')

table = boto3.resource('dynamodb').Table('eagleview-sidewalk-features')

def getRatio(w, h, x, y):
    return (x/float(w), y/float(h))
    
def from_logical(l, m, alphas, betas):
    # mult_matrix = np.array([1, l, m, l*m])
    lat = np.sum(alphas[0] + alphas[1] * l + alphas[2] * m + alphas[3] * l * m)
    lon = np.sum(betas[0] + betas[1] * l + betas[2] * m + betas[3] * l * m)
    return (lat, lon)
    

def get_logical_coefficients(lats, lons):
    A = np.array([
        [1, 0, 0, 0],
        [1, 1, 0, 0],
        [1, 1, 1, 1],
        [1, 0, 1, 0]
    ])
    AI = np.linalg.inv(A)
    alphas = np.matmul(AI, lats)
    betas = np.matmul(AI, lons)
    return alphas, betas

def get_separate_lat_lons(tl, tr, br, bl):
    tl=ast.literal_eval(tl)
    tr=ast.literal_eval(tr)
    br=ast.literal_eval(br)
    bl=ast.literal_eval(bl)
    lats = np.array([[tl[0], tr[0], br[0], bl[0]]])
    # print(lats)
    lons = np.array([[tl[1], tr[1], br[1], bl[1]]])
    # print(lons)
    lats = lats.T
    lons = lons.T
    return lats, lons

def getConvertedLatLngs(line_points, tl, tr, br, bl, imgWidth, imgHeight):
    # print(tl, tr)
    # print(type(ast.literal_eval(tl)))
    # return line_points
    lats, lons = get_separate_lat_lons(tl, tr, br, bl)
    # print(lats)
    # print(lons)
    alphas, betas = get_logical_coefficients(lats, lons)
    from_x, from_y = getRatio(imgWidth, imgHeight, line_points[0], line_points[1])
    to_x, to_y = getRatio(imgWidth, imgHeight, line_points[2], line_points[3])
    from_lat, from_lng = from_logical(from_x, from_y, alphas, betas)
    to_lat, to_lng = from_logical(to_x, to_y, alphas, betas)
    return [from_lat, from_lng, to_lat, to_lng]

def convertAndInsertDB(key, tl, tr, bl, br, line_arr, imgWidth, imgHeight):
    with table.batch_writer() as batch:
        for idx, line_points in enumerate(line_arr):
            data={}
            # print(key)
            data['PlaceID'] = str(key)+"-"+str(idx)
            coords=getConvertedLatLngs(line_points, tl, tr, br, bl, imgWidth, imgHeight)
            # print(str(key))
            # print(line_points)
            data['lat1'] = Decimal(str(coords[0]))
            data['lng1'] = Decimal(str(coords[1]))
            data['lat2'] = Decimal(str(coords[2]))
            data['lng2'] = Decimal(str(coords[3]))
            data['label'] = line_points[4]
            # print(data)
            batch.put_item(Item=data)
    

def closest_node(node, nodes):
    node=np.asarray(node)
    nodes_np=np.asarray(nodes)
    dist_matrix = distance.cdist(node[np.newaxis, :-1], nodes_np[:,:-1])
    ind=dist_matrix.argmin()
    dist=dist_matrix[0][ind]
    return (nodes[ind][:], dist)

s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')
sns_cli = boto3.client('sns')

def getMetaData(bucket, key):
    try:
        response = s3.head_object(Bucket=bucket, Key=key)
        if "Metadata" in response:
            width=float(response['Metadata']['width'])
            height=float(response['Metadata']['height'])
            tl=response['Metadata']['top_left']
            tr=response['Metadata']['top_right']
            bl=response['Metadata']['bottom_left']
            br=response['Metadata']['bottom_right']
            return (tl, tr, bl, br, width, height)
        else:
            raise Exception("No key in meta")
    except Exception as e:
        print(e)
    return None

def modify_label(lins, l, r, ind, sample_window):
    threshold=0.8
    #check continuity and labels
    det=0
    sw=0
    nsw=0
    for i in range(l,r+1):
        if(lins[i][5]=="Detached Sidewalk"):
            det+=1
        elif(lins[i][5]=="Sidewalk"):
            sw+=1
        elif(lins[i][5]=="No Sidewalk"):
            nsw+=1
    # print("det:"+str(det))
    # print("sw:"+str(sw))
    continuous=True
    for i in range(l+1,r+1):
        if(lins[i-1][2]!=lins[i][0] and lins[i-1][3]!=lins[i][1] ):
            continuous=False
    
    if(nsw>=threshold*sample_window):
        return (True, "No Sidewalk", continuous)
    if(sw>=threshold*sample_window):
        return (True, "Sidewalk", continuous)
    if(det>=threshold*sample_window):
        return (True, "Detached Sidewalk", continuous)
    return (False, "",False)

def move_object_between_buckets(to_bucket, from_bucket, object_key):
    logger.info("moving object {} from {} to {} ".format(object_key, from_bucket, to_bucket))
    copy_source = {
        'Bucket': from_bucket,
        'Key': object_key
    }
    s3.copy(copy_source, to_bucket, object_key)
    s3.delete_object( Bucket=from_bucket, Key=object_key)

def get_labels_and_imgdata(bucket, key):
    st_time = time.time()
    lat = lon = 0.0
    min_confidence = 0
    # model = 'arn:aws:rekognition:us-east-1:206513143549:project/eagle-view-test/version/eagle-view-test.2021-09-03T15.03.12/1630706591691'
    model='arn:aws:rekognition:us-east-1:206513143549:project/eagle-view-test/version/eagle-view-test.2021-10-20T11.29.33/1634754573606'
    data = labels = {}
    tl, tr, bl, br, imgWidth, imgHeight =getMetaData(bucket, key)
    # print(tl, tr, bl, br)
    # uncomment this
    
    response = rekognition.detect_custom_labels(Image={'S3Object': {'Bucket': bucket, 'Name': key}}, MinConfidence=min_confidence, ProjectVersionArn=model)
    print(response)
    points_arr=[]
    for customLabel in response["CustomLabels"]:
        if "Geometry" in customLabel:
            box = customLabel["Geometry"]["BoundingBox"]
            left = imgWidth * box["Left"]
            top = imgHeight * box["Top"]
            width = imgWidth * box["Width"]
            height = imgHeight * box["Height"]
    
            points = [[left,top],
                [left + width, top],
                [left + width, top + height],
                [left , top + height]]
            average = [sum(x)/len(x) for x in zip(*points)]
            if(customLabel["Name"]=="Detached Sidewalk"):
                points_arr.append([average[0], average[1], "Detached Sidewalk"])
            elif(customLabel["Name"]=="No Sidewalk"):
                points_arr.append([average[0], average[1], "No Sidewalk"])
            else:
                points_arr.append([average[0], average[1], "Sidewalk"])
    # print(len(points_arr))
    lines_list=[]
    new_node=list(points_arr[0])
    
    while 0<len(points_arr)-1:
        prev_node=new_node
        points_arr.remove(prev_node)
        new_node, dist=closest_node(prev_node, points_arr)
        lines_list.append([prev_node, new_node, dist])
        
    # line_arr=[]
    # for line in lines_list:
    #     line_points=[line[0][0], line[0][1], line[1][0], line[1][1], line[0][2]]
    #     if line[2]>100:
    #         continue
    #     line_arr.append(line_points)
    # test=line_arr
            
    line_arr=[]
    for line in lines_list:
        line_points=[line[0][0], line[0][1], line[1][0], line[1][1], line[2], line[0][2]]
        if line[2]>100:
            continue
        line_arr.append(line_points)
        
    
    new_arr=[]    
    sample_window=5
    for ind,x in enumerate(line_arr):
        if ind<sample_window or ind>len(line_arr)-sample_window-1:
            continue
        left_check, left_label, left_continuous = modify_label(line_arr, ind-sample_window, ind-1, ind, sample_window)
        right_check, right_label, right_continuous = modify_label(line_arr, ind+1, ind+sample_window, ind, sample_window)
        if(left_check and right_check):
            if(left_label==right_label and left_continuous and right_continuous):
                new_arr.append([x[0], x[1], x[2], x[3], x[4], left_label])
                continue
        new_arr.append(x)  
    
    new_arr=line_arr[0:5]+new_arr[:]+line_arr[-5:]
    
    test=[]
    start=(new_arr[0][0], new_arr[0][1])
    end=(new_arr[0][2],new_arr[0][3])
    dist=new_arr[0][4]
    label=new_arr[0][5]
    for t in new_arr[1:]:
        curr_start=(t[0], t[1])
        curr_end=(t[2], t[3])
        curr_dist=t[4]
        curr_label=t[5]
        if end!=curr_start or dist+curr_dist>1000 or curr_label!=label:
            # count>5
            # count=0
            test.append([start[0], start[1], end[0], end[1], label])
            start=curr_start
            end=curr_end
            dist=curr_dist
            label=curr_label
        elif end==curr_start:
            # count+=1
            dist+=curr_dist
            end=curr_end
    test.append([start[0], start[1], end[0], end[1], label])
    
    batch_size = 100
    total_len = len(test)
    print(
        "total length of insert array is {} anad batch size is {}, so total batches -> {}".format(
            total_len, batch_size, total_len // batch_size + 1
        )
    )
    
    for i in range(total_len // batch_size + 1):
        convertAndInsertDB(
            key,
            tl,
            tr,
            bl,
            br,
            test[i * batch_size : (i + 1) * batch_size],
            imgWidth,
            imgHeight,
        )
        
    processed_bucket = os.environ['ProcessedBucket']
    move_object_between_buckets(processed_bucket, bucket, key)



def lambda_handler(lambda_event, context):
    logger.info("Received event: " + json.dumps(lambda_event, indent=2))
    
    records = lambda_event['Records'][0]
    sns = records['Sns']
    event = json.loads(sns['Message'])
    job_id = event['job_id']
    split = event['split']
    subject = sns['Subject']
    
    start = time.time()
    
    item = {
        'message': '{}, Starting sidewalk detection using AWS Rekognition.'.format(sns['Subject']),
        'job_id':job_id,
        'time': start
    }
    
    sns_cli.publish(
        TopicArn="arn:aws:sns:us-east-1:206513143549:EV-Process-Notifier",
        Message=json.dumps(item),
    )
    
    num=0
    update = split // 2
    bucket = os.environ['UnprocessedBucket']
    # bucket = 'eagleview-unprocessed-images'
    st_time = time.time()
    content = s3.list_objects(Bucket=bucket)['Contents']
    for key in content:
        try:
            filename = key['Key']
            logger.info("#### filename below ####")
            extension = os.path.splitext(filename)[1]
            if extension != ".png" and extension != ".jpg":
                continue
            logger.info(filename)
            response = get_labels_and_imgdata(bucket, filename)
            num+=1
            
            if num < len(content) and num % update == 0:
                item = {
                    'message': 'Processed {}/{} in {:.3f} seconds. On to the remaining...'.format(num, len(content), time.time() - st_time),
                    'job_id':job_id,
                    'time': time.time()
                }
                sns_cli.publish(
                    TopicArn="arn:aws:sns:us-east-1:206513143549:EV-Process-Notifier",
                    Message=json.dumps(item),
                )
                st_time = time.time()
            
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
            print(e)
            raise e
    
    item = {
        'message': 'Processed {} images using {} image-splits in {:.3f} seconds. Starting generation of shp/kml files.'.format(num//split, num, time.time() - start),
        'job_id':job_id,
        'time': time.time()
    }
    
    sns_cli.publish(
        TopicArn="arn:aws:sns:us-east-1:206513143549:EV-Process-Notifier",
        Message=json.dumps(item),
    )

    item = {"job_id": job_id}
    print(json.dumps(item))

    response = sns_cli.publish(
        TopicArn="arn:aws:sns:us-east-1:206513143549:trigger-shp",
        Message=json.dumps(item),
    
    )

    
    return None