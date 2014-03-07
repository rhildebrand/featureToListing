import os
import csv
import ogr
import osr
import json
import math
import subprocess
import WeoGeoAPI_admin

def get_geom(feat):
    geom = feat.GetGeometryRef().GetEnvelope()
    n = geom[3]
    s = geom[2]
    e = geom[1]
    w = geom[0]
    return n,s,e,w

def reproject_geom(feat, inRef, outRef):
    inSpatialRef = osr.SpatialReference()
    inSpatialRef.ImportFromEPSG(inRef)
    outSpatialRef = osr.SpatialReference()
    outSpatialRef.ImportFromEPSG(outRef)
    coordTransform = osr.CoordinateTransformation(inSpatialRef, outSpatialRef)
    geom = feat.GetGeometryRef()
    geom.Transform(coordTransform)
    geom = geom.GetEnvelope()
    n = geom[3]
    s = geom[2]
    e = geom[1]
    w = geom[0]
    return n,s,e,w

def mk_tldr_call(n,s,e,w,gid,hostname,username,password,token,based):
    try:
        subprocess.check_call(['python', 'tldr.py', 
                            '--bounding-box', str(n) + ',' + str(s) + ',' + str(e) + ',' + str(w), 
                            '--hostname',     hostname, 
                            '--username',     username, 
                            '--password',     password, 
                            '--token',        token, 
                            '--mask',         based + 'raster\\' + gid + '.tif',
                            '--work-dir',     based + 'temp', 
                            '--output-file',  based + gid + '\\' + gid], 
                            shell=True)
    except:
        pass
    return

def mk_listing_dir(gid):
    try:
        subprocess.check_call(['mkdir', gid], shell=True)
    except subprocess.CalledProcessError:
        pass
    return

def identifiers(feat):
    geoid = feat.GetField('GEOID')
    name = feat.GetField('NAME').split(',')
    namelsad = feat.GetField('NAMELSAD')
    town = name[0].split('-')[0]
    state = name[1].split('-')[0]
    listing_name = str(town) + ',' + str(state) + ' Metro Region'
    return geoid, listing_name, namelsad

def get_file_names(gid):
    for path,dirs,files in os.walk(gid):
        for afile in files:
            if 'base' in afile:
                base = afile
            elif 'thumb' in afile:
                thumb = afile
            elif afile.endswith('kml.png'):
                k = afile
    return base,thumb,k

def mk_weofile(based, gid):
    input_boundaries = based + str(gid) + '/' + str(gid) + '-boundaries.txt'
    boundaries_file = open(input_boundaries, 'r')
    output_weofile_path = based + str(gid) + '/' + str(gid) + '-upload.weo'
    output_weofile = open(output_weofile_path, 'w')
    for line in boundaries_file:
        head,tail = line.strip().split('=')
        coords = tail.strip('(').strip(')').split(',')
        if 'baseImage' in head:
            base_feat = assemble_coords(coords)
        elif 'kmlBoundary' in head:
            geo_feat = assemble_coords(coords)
        else:
            pass
    boundaries_file.close()
    return output_weofile, base_feat, geo_feat

def assemble_coords(coords):
    n = coords[0]
    s = coords[1]
    e = coords[2]
    w = coords[3]
    bounds = """<north>{n}</north><south>{s}</south><east>{e}</east><west>{w}</west>""".format(n=n,s=s,e=e,w=w)
    return bounds

###############################################################################################################
############################################ MODIFY scale ELEMENTS ############################################
###############################################################################################################

# Find optimum start scale for spherical mercator tiles
def startScaleSM (tilesNorth, tilesSouth, tilesEast, tilesWest):
    longSide = max(tilesNorth - tilesSouth , tilesEast - tilesWest)
    longSidePixels = longSide / 256
    C = 156543 / longSidePixels  # max resolution / longSidePixels
    D = math.trunc(math.log10( C ) / 0.30103)
    return D
    
# Find optimum start scale for geo tiles
def startScaleGeo (tilesNorth, tilesSouth, tilesEast, tilesWest):
    longSide = max(tilesNorth - tilesSouth , tilesEast - tilesWest)
    longSidePixels = longSide / 256
    C = 0.703125 / longSidePixels
    D = math.trunc(math.log10( C ) / 0.30103)
    return D

###############################################################################################################
######################################## MODIFY preview_layer ELEMENTS ########################################
###############################################################################################################

# Modify 'base' in preview_layers.
def update_preview_base(weos, token, layer_id, update_token, record):
    '''Begin by creating the indice to slice out the layer_id from the api_url. Then 
       parse through preview_layers to find the base entity and apply the parameters.'''

    start,stop = layer_id.split(':')
    preview_layer_info = record['preview_layers']
    for layer in preview_layer_info:
        if layer['layer_name'] == 'base':
            status, message = weos.updateTileLayer(token, layer['api_url'][slice(int(start), int(stop))], update_token, layer['image_format'], layer['start_zoom'], layer['num_zooms'])
            if status != 200:
                print 'FAILED for: ' + token, message
            else:
                print 'SUCCESS for: ' + token
    return

# Modify preview_layers by adding new feature.
def add_preview_vector(weos, token, layer_type, url, record):
    tags_content = record['tag_list']
    for tag in tags_content:
        status, message = weos.addVectorLayer(token, layer_type, url)
###        status, message = weos.addVectorLayer(token, 'highlight', ('http://vectors.weogeo.net.s3.amazonaws.com/vectors/digitalglobe/europe/' + tag + '.json'))
        if status != 200:
            print 'FAILED for: ' + token, message
        else:
            print 'SUCCESS for: ' + token
    return

# Add the OSM Transparent Roads tile overlay
def add_preview_tile_layer(weos, dataset_token, update_token, file_format):
    status, message = weos.addTileLayer(dataset_token, update_token, file_format)
    if status != 200:
        print 'FAILED for: ' + dataset_token, message
    else:
        print 'SUCCESS for: ' + dataset_token
    return

###############################################################################################################
############################################### WEOFILE CREATION ##############################################
###############################################################################################################

def mk_update_weo(t, fips, df, dfm, subdomain):
    weo = """<?xml version='1.0' encoding='UTF-8'?>
<dataset>
    <token>{t}</token>
    <hosted>true</hosted>
    <data_upload_template>weodata2.weogeo.com/dataset_tiles/{t}/data/</data_upload_template>
    <misc_upload_template>weodata2.weogeo.com/dataset_tiles/{t}/misc/</misc_upload_template>
    <public_upload_template>weodata2.weogeo.com/dataset_tiles/{t}/public/</public_upload_template>
    <kml_upload_template>weodata2.weogeo.com/dataset_tiles/{t}/kml/</kml_upload_template>
    <tile_upload_template>weotiles.weogeo.com/dataset_tiles/${{hash}}/{t}/xyz/</tile_upload_template>
    <thumbnail_upload_template>weodata2.weogeo.com/dataset_tiles/{t}/thumbnail/</thumbnail_upload_template>
    <baseimage_upload_template>weodata2.weogeo.com/dataset_tiles/{t}/baseimage/</baseimage_upload_template>
    <weo_upload_template>weodata2.weogeo.com/dataset_tiles/{t}/weo/</weo_upload_template>
    <weogeo_mode>library</weogeo_mode>
    <weogeo_host>{subdomain}.weogeo.com</weogeo_host>
    <weocatch>
        <host>process.weogeo.com</host>
        <port>80</port>
    </weocatch>
    <modify>
        <add>
            <data_files>{df}</data_files>
            <data_files_map>{dfm}</data_files_map>
        </add>
        <delete>
            <tilepack_file>false</tilepack_file>
        </delete>
    </modify>
</dataset>""".format(t=t, fips=fips, df=df, dfm=dfm, subdomain=subdomain)
    return weo

def mk_upload_weo(HOSTN, LICENSE, GEOID, BASED, BASEIMAGE, THUMBNAIL, BASE_TITLE, LISTING_NAME, NAMELSAD, base_bounds, geo_bounds, north, south, east, west):
    weo = """<?xml version="1.0" encoding="UTF-8"?>
<dataset>
  <token></token>
  <hosted>true</hosted>
  <tile_order>yx</tile_order>
  <data_upload_template>weodata2.weogeo.com/${{token}}/data/</data_upload_template>
  <misc_upload_template>weodata2.weogeo.com/${{token}}/misc/</misc_upload_template>
  <public_upload_template>weodata2.weogeo.com/${{token}}/public/</public_upload_template>
  <kml_upload_template>weodata2.weogeo.com/${{token}}/kml/</kml_upload_template>
  <tile_upload_template>weotiles.weogeo.com/${{hash}}/${{token}}/</tile_upload_template>
  <thumbnail_upload_template>weodata2.weogeo.com/${{token}}/thumbnail/</thumbnail_upload_template>
  <baseimage_upload_template>weodata2.weogeo.com/${{token}}/baseimage/</baseimage_upload_template>
  <weo_upload_template>weodata2.weogeo.com/${{token}}/weo/</weo_upload_template>
  <job_upload_template>weojobs.weogeo.com/${{token}}/</job_upload_template>
  <weogeo_mode>library</weogeo_mode>
  <weogeo_host>{HOSTN}</weogeo_host>
  <weocatch>
    <host>process.weogeo.com</host>
    <port>80</port>
  </weocatch>
  <name>{BASE_TITLE} {LISTING_NAME}</name>
  <tags>{GEOID}</tags>
  <description><![CDATA[{NAMELSAD}]]></description>
  <data_created_on/>
  <content_license_id>{LICENSE}</content_license_id>
  <boundaries>
    <baseimage>
      {base_bounds}
      <proj4>+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +no_defs</proj4>
      <number_of_lines>256</number_of_lines>
      <number_of_samples>256</number_of_samples>
    </baseimage>
    <tiles>
      <north>{north}</north>
      <south>{south}</south>
      <east>{east}</east>
      <west>{west}</west>
      <proj4>+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +no_defs</proj4>
    </tiles>
    <geo>
      {geo_bounds}
      <sample_pixel_size>0.0000000000</sample_pixel_size>
      <line_pixel_size>0.0000000000</line_pixel_size>
      <number_of_samples>100000</number_of_samples>
      <number_of_lines>100000</number_of_lines>
      <proj4>+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs </proj4>
    </geo>
  </boundaries>
  <tile_file_format>png</tile_file_format>
  <thumbnail_file>{BASED}{GEOID}/{THUMBNAIL}</thumbnail_file>
  <small_preview_file>{BASED}{GEOID}/{BASEIMAGE}</small_preview_file>
  <data_files/>
  <data_files_map/>
  <public_files/>
  <meta>
    <weoapp>
      <version>3.5.0</version>
      <platform>Windows</platform>
    </weoapp>
  </meta>
</dataset>""".format(HOSTN=HOSTN, LICENSE=LICENSE, GEOID=GEOID, BASED=BASED, BASEIMAGE=BASEIMAGE, THUMBNAIL=THUMBNAIL, BASE_TITLE=BASE_TITLE, LISTING_NAME=LISTING_NAME, NAMELSAD=NAMELSAD, base_bounds=base_bounds, geo_bounds=geo_bounds, north=north, south=south, east=east, west=west)
    return weo

###############################################################################################################
################################################# MAKE GEOJSON ################################################
###############################################################################################################
def mk_json_feature(north, south, east, west, file):
    north = float(north)
    south = float(south)
    east = float(east)
    west = float(west)

    properties = dict()
    properties['PATH'] = './' + file.split('.')[0]
    properties['EXTS'] = 'dbf;prj;shp;shx'
    properties['LAYERS'] = '0'
    properties['WEO_TYPE'] = 'WEO_FEATURE'
    properties['WEO_MISCELLANEOUS_FILE'] = 'No'

    geometry = dict()
    geometry['type'] = 'Polygon'
    geometry['coordinates'] = [((west,north), (east,north), (east,south), (west,south), (west,north))]

    feature = dict()
    feature['geometry'] = geometry
    feature['type'] = 'Feature'
    feature['properties'] = properties

    return feature
    
def mk_json_feature_misc(north, south, east, west, file):
    north = float(north)
    south = float(south)
    east = float(east)
    west = float(west)

    properties = dict()
    properties['PATH'] = './' + file.split('.')[0]
    properties['EXTS'] = 'TEST'
    properties['LAYERS'] = '0'
    properties['WEO_TYPE'] = 'WEO_FEATURE'
    properties['WEO_MISCELLANEOUS_FILE'] = 'Yes'

    geometry = dict()
    geometry['type'] = 'Polygon'
    geometry['coordinates'] = [((west,north), (east,north), (east,south), (west,south), (west,north))]

    feature = dict()
    feature['geometry'] = geometry
    feature['type'] = 'Feature'
    feature['properties'] = properties

    return feature