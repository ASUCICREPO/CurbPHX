import numpy as np
import image_slicer
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon

def get_separate_lat_lons(lat_lons):
    lats = np.array([[x[0] for x in lat_lons]])
    lons = np.array([[y[1] for y in lat_lons]])
    # reshape from row vector to column vector
    lats = lats.T
    lons = lons.T
    return lats, lons


def get_logical_coefficients(lats, lons):
    # we convert the irregular quadrilateral to another axis where
    # they would become a square and it will be easier to interpolate
    # lat longs of points inside a square than a random quadlilateral
    # Reference --> https://www.particleincell.com/2012/quad-interpolation/
    A = np.array([[1, 0, 0, 0], [1, 1, 0, 0], [1, 1, 1, 1], [1, 0, 1, 0]])
    AI = np.linalg.inv(A)
    # print(AI)
    alphas = np.matmul(AI, lats)
    # alphas = AI * lats
    betas = np.matmul(AI, lons)
    # betas = AI * lons
    return alphas, betas


def from_logical(l, m, alphas, betas):
    # mult_matrix = np.array([1, l, m, l*m])
    lat = np.sum(alphas[0] + alphas[1] * l + alphas[2] * m + alphas[3] * l * m)
    lon = np.sum(betas[0] + betas[1] * l + betas[2] * m + betas[3] * l * m)
    return (lat, lon)


def transform_point(lat, lon, alphas, betas):
    # solving a traditional quadratic equation
    # ax**2 + bx + c = 0
    a = alphas[3] * betas[2] - alphas[2] * betas[3]
    # print(alphas[3],betas[2],alphas[2],betas[3])
    # print('A ->', a)

    b = (
        alphas[3] * betas[0]
        - alphas[0] * betas[3]
        + alphas[1] * betas[2]
        - alphas[2] * betas[1]
        + lat * betas[3]
        - lon * alphas[3]
    )
    c = alphas[1] * betas[0] - alphas[0] * betas[1] + lat * betas[1] - lon * alphas[1]

    # compute m = (-b + sqrt(b**2 - 4ac)) / 2a
    det = np.sqrt(b * b - 4 * a * c)
    # print('det -->', det)
    m = (-b + det) / (2 * a)
    # print(m)
    # compute l
    l = (lat - alphas[0] - alphas[2] * m) / (alphas[1] + alphas[3] * m)

    # l-m are our transformed coordinates in logical space
    return (l[0], m[0])


def get_jobs(base_x, base_y, x, y, dims):
    r = x / dims[0]
    s = y / dims[1]
    return {
        "TL": (r - base_x, s - base_y),
        "TR": (r, s - base_y),
        "BR": (r, s),
        "BL": (r - base_x, s),
    }


def extract_latlon_from_geodf(filename, shp_path):
    geodf = gpd.read_file(shp_path)
    item = geodf[geodf["filename"] == filename]
    geometry = item.iloc[0].geometry
    lon, lat = geometry.exterior.coords.xy
    lon = np.array([lon[:-1]]).T
    lat = np.array([lat[:-1]]).T
    # print(lat, '\n', lon)
    return lat, lon


def get_coords_from_lm(filename, l, m, shp_path):
    lats, lons = extract_latlon_from_geodf(filename, shp_path)
    alphas, betas = get_logical_coefficients(lats, lons)
    # print('alphas --> {}\nbetas--> {}'.format(alphas, betas))
    point = from_logical(l, m, alphas, betas)
    # print('point for l,m {},{} is {}'.format(l,m,point))
    return point


def get_coords_for_corners(filename, tile, split, shp_path):
    dims = image_slicer.main.calc_columns_rows(split)
    basename = tile.basename
    parts = basename.split("_")
    x = int(parts[2])
    y = int(parts[1])
    base_x = 1 / dims[0]
    base_y = 1 / dims[1]
    jobs = get_jobs(base_x, base_y, x, y, dims)
    coords = {}
    for job in jobs:
        coords[job] = get_coords_from_lm(filename, jobs[job][0], jobs[job][1], shp_path)
    return coords

def get_tile_geodataframe(tiles, filename, split, shp_path=r"shapefiles\rhode\rhode_polygon.shp"):
    data = {
        'filename':[],
        'top_right':[],
        'top_left':[],
        'bottom_left':[],
        'bottom_right':[],
        'geometry':[]
    }

    # adding lat lon for each sliced photo
    for tile in tiles:
        coords = get_coords_for_corners(filename, tile, split, shp_path)
        data['filename'].append("{}.png".format(tile.basename))    
        data['top_left'].append("{}".format(coords['TL']))    
        data['top_right'].append("{}".format(coords['TR']))    
        data['bottom_right'].append("{}".format(coords['BR']))    
        data['bottom_left'].append("{}".format(coords['BL'])) 
        data['geometry'].append(
            Polygon(
                [
                    coords['TL'],
                    coords['TR'],
                    coords['BR'],
                    coords['BL']
                ]
            )
        )   
    geodf = gpd.GeoDataFrame(data)
    geodf.crs = 'EPSG:4326'
    return geodf
        