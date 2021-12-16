import xml.etree.ElementTree as ET
from pyproj import Transformer, CRS
import geopandas as gpd
from shapely.geometry import Polygon, Point
import re
from coordinate_grid import *
import boto3
import logging
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_cli = boto3.client("s3")
s3_res = boto3.resource("s3")


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
        s3_cli.upload_file(
            file_name, bucket, object_name, ExtraArgs={"Metadata": metadata}
        )
    except ClientError as e:
        logging.error(e)
        return False
    return True


def read_xml_get_nodes(xml_file, image_s3):
    # Path to the s3 bucket

    # e.g. s3://eagle-view-images/image_sets/frames/photos.xml
    
    # match for the bucket name
    image_bucket_name = re.search("(?<=s3://)(.*?)(?=/)", image_s3)
    if not image_bucket_name:
        raise ValueError(
            "Invalid S3 URI for images, must be in format 's3://bucket_name/path_to_images_folder/'"
        )
    # get the texts
    image_bucket_name = image_bucket_name.group()
    logger.info('bucket name images - {}'.format(image_bucket_name))

    # get everything after bucket name
    image_path = re.search("(?<={}/)(.*)".format(image_bucket_name), image_s3)
    if not image_path:
        raise ValueError(
            "Invalid S3 URI, must be in format 's3://bucket_name/path_to_images_folder/'"
        )
    # get the texts
    image_path = image_path.group()
    logger.info('image path s3 - {}'.format(image_path))

    # match for the bucket name
    xml_bucket_name = re.search("(?<=s3://)(.*?)(?=/)", xml_file)
    if not xml_bucket_name:
        raise ValueError(
            "Invalid S3 URI, must be in format 's3://bucket_name/path_to_xml'"
        )
    # get the texts
    xml_bucket_name = xml_bucket_name.group()
    logger.info('bucket name xml - {}'.format(xml_bucket_name))
    
    # get everything after bucket name
    xml_path = re.search("(?<={}/)(.*)".format(xml_bucket_name), xml_file)
    if not xml_path:
        raise ValueError(
            "Invalid S3 URI, must be in format 's3://bucket_name/path_to_xml'"
        )
    # get the texts
    xml_path = xml_path.group()
    logger.info('path xml - {}'.format(xml_path))
    
    # fetch filename
    xml_filename = xml_path.split('/')[-1]
    save_loc = "/tmp/"
    # download from s3
    # with tempfile.TemporaryFile() as f:
    f = save_loc + xml_filename
    try:
        logger.info("Starting download from {} for {} at {} ".format(xml_bucket_name, xml_path, f))
        s3_cli.download_file(xml_bucket_name, xml_path, f)
    except Exception as e:
        logger.info(e)
        raise ValueError("Error downloading, The S3 bucket is not public or doesn't have necessary rights")

    logger.info("Finished download from {} for {}".format(xml_bucket_name, xml_path))
    # xml = content.read()
    xml = f
    tree = ET.parse(xml)
    root = tree.getroot()

    # getting sub elements from the xml file
    block = root.find("Block")

    # mapping children to their parent elements
    parent_map = {c: p for p in tree.iter() for c in p}

    # creating a dict to store parent and node using filename as the key
    photo_dict = {}

    # populating the dictionary
    for photo in block.iter("Photo"):
        imagepath = photo.find("ImagePath")
        key = imagepath.text.split("/")[-1]
        parent = parent_map[photo]
        # logger.info(imagepath.tag, key, parent)
        photo_dict[key] = {"parent": parent, "node": photo}
    return photo_dict, image_bucket_name, image_path


def parse_xml_get_data(photo_dict, _from=4978, _to=4326):
    # ECEF (x,y,z w.r.t earth's center)
    ecef = CRS.from_epsg(_from)
    # WGS84 (lat long)
    wgs84 = CRS.from_epsg(_to)
    transformer = Transformer.from_crs(ecef, wgs84)

    # extracting metadata information and linking them to filenames
    photo_data_dict = {}
    for filename in photo_dict.keys():
        obj = photo_dict[filename]
        elem = obj["node"]
        # extract the 4 corners of the image boundaries
        proj_corners_text = elem.find("ProjectedCorners").text
        projected_corners = proj_corners_text.split(" ")
        projected_corners = [x.split(",") for x in projected_corners]
        lat_lon_corners = [
            transformer.transform(x[0], x[1], x[2]) for x in projected_corners
        ]
        lat_lon_corners = [(x[1], x[0], x[2]) for x in lat_lon_corners]
        # extract the center of the image
        center = elem.find("Pose").find("Center")
        projected_center = (
            float(center.find("x").text),
            float(center.find("y").text),
            float(center.find("z").text),
        )
        lat_lon_center = transformer.transform(
            projected_center[0], projected_center[1], projected_center[2]
        )
        lat_lon_center = (lat_lon_center[1], lat_lon_center[0], lat_lon_center[2])
        data = {
            "id": elem.find("Id").text,
            "image_path": elem.find("ImagePath").text,
            "mask_path": elem.find("MaskPath").text,
            "frame_number": elem.find("FrameNumber").text,
            "projected_corners": projected_corners,
            "lat_lon_corners": lat_lon_corners,
            "ground_x": elem.find("GroundX").text,
            "ground_y": elem.find("GroundY").text,
            "lat_lon_center": lat_lon_center,
            "pose": elem.find("Pose"),
            "filename": filename,
        }
        photo_data_dict[filename] = data
    return photo_data_dict


def create_geodataframe(photo_data_dict):
    datapoints = {
        "id": [],
        "filename": [],
        "corner_1": [],
        "corner_2": [],
        "corner_3": [],
        "corner_4": [],
        "center": [],
        "polygon": [],
    }

    for key in photo_data_dict.keys():
        element = photo_data_dict[key]
        datapoints["id"].append(element["id"])
        datapoints["filename"].append(element["filename"])
        # logger.info(element['lat_lon_center'][:2][::-1])
        # logger.info(element['lat_lon_center'][:2])
        datapoints["corner_1"].append(Point(element["lat_lon_corners"][0]))
        datapoints["corner_2"].append(Point(element["lat_lon_corners"][1]))
        datapoints["corner_3"].append(Point(element["lat_lon_corners"][2]))
        datapoints["corner_4"].append(Point(element["lat_lon_corners"][3]))
        datapoints["center"].append(Point(element["lat_lon_center"]))
        datapoints["polygon"].append(Polygon(element["lat_lon_corners"]))

    # creating a dataframe of points and polygons
    gdf = gpd.GeoDataFrame(datapoints, crs="EPSG:4326")

    # creating a dataframe containing just filename and the polygons
    poly_gdf = gpd.GeoDataFrame(gdf[["filename", "polygon"]], crs="EPSG:4326")
    poly_gdf.crs = {
        "proj": "latlong",
        "ellps": "WGS84",
        "datum": "WGS84",
        "no_defs": True,
    }
    poly_gdf.columns = ["filename", "geometry"]
    return gdf, poly_gdf


def create_grid_cells(ratio, bbox):
    def process_jobs(l, m):
        # get 4 points of the polygon
        jobs = {
            "TL": (l, m),
            "TR": (l, m + m_iter),
            "BR": (l + l_iter, m + m_iter),
            "BL": (l + l_iter, m),
        }
        points = []

        # convert them from logical
        for job in jobs:
            (lat, lon) = from_logical(jobs[job][0], jobs[job][1], alphas, betas)
            point = (lon, lat)
            grid_dict[job].append(point)
            points.append(point)

        # create a polygon using these coordinates
        poly = Polygon(points)
        grid_dict["geometry"].append(poly)
        # x,y = poly.exterior.xy
        # plt.plot(x,y, color='red')

    # as the photo polygons are usually vertical rectangles, we can assume l:m = 2:1 (if m is the length)
    # trial 2 -> equal ratios
    l_iter = ratio
    m_iter = ratio
    logger.info("total jobs possible --> {}".format(1 / l_iter * 1 / m_iter))

    lat_lons = [
        (bbox[1], bbox[0]),
        (bbox[1], bbox[2]),
        (bbox[3], bbox[2]),
        (bbox[3], bbox[0]),
    ]

    grid_dict = {
        "TL": [],
        "TR": [],
        "BR": [],
        "BL": [],
        "geometry": [],
    }

    lats, lons = get_separate_lat_lons(lat_lons)
    alphas, betas = get_logical_coefficients(lats, lons)
    l = 0
    m = 0

    logger.info("iterators for x and y are {} and {}".format(l_iter, m_iter))

    while l <= (1 - l_iter):
        while m <= (1 - m_iter):
            # grid_dict is updated in place as its passed by reference
            process_jobs(l, m)
            m += m_iter
        l += l_iter
        m = 0

    cells = gpd.GeoDataFrame(grid_dict)
    logger.info("we created {} cells ".format(len(cells)))
    cells["area"] = cells.geometry.area

    return cells


def create_index_filter_image_bounds(data, cells):
    # creating a index of geometries to find overlaps
    from shapely.strtree import STRtree

    strtree = STRtree(data.geometry.to_list())
    idx_fil = gpd.GeoDataFrame()
    fil = []
    for _, cell in cells.iterrows():
        polys = [poly for poly in strtree.query(cell.geometry)]
        area_max = float("-inf")
        fil_row = None
        for poly in polys:
            area = poly.overlaps(cell.geometry)
            if area >= area_max and poly not in fil:
                area_max = area
                fil_row = poly
        fil.append(fil_row)

    fdf = gpd.GeoDataFrame(fil, columns=["geometry"])
    fdf.name = "geometry"
    # ax = fdf.plot(figsize=(12, 12), alpha=0.5)
    # cells.geometry.boundary.plot(ax=ax, color='grey')
    # plt.title('filtered from {} to {}'.format(len(data), len(fdf)))

    return strtree, fdf