import os
import ogr
import osr
import argparse
import subprocess
from HILDEBRAND import *

def feature_to_listing(HOSTN, UNAME, PWORD, TOKN, BASED, SOURC, TITLE, LICN):
    # Set the input vector file. In this case, the
    # input is EPSG:4326 and if a different projection
    # is to be used, some changes will need to be made. 
    driver = ogr.GetDriverByName('ESRI Shapefile')
    input_features_datasource = driver.Open(BASED + SOURC)
    if input_features_datasource is None:
        print 'Could not open ' + SOURC
        exit
    input_layer = input_features_datasource.GetLayer()

    # Make working directory for the TLDR program if it doesn't exist. 
    try:
        subprocess.check_call(['mkdir', (BASED + 'temp')], shell=True)
    except subprocess.CalledProcessError:
        pass

    # Initializes getting the first feature
    feature = input_layer.GetNextFeature()
    while feature:
        # Get NSEW of a feature
        north, south, east, west = get_geom(feature)

        # Get NSEW of a feature in SPHERICAL MERCATOR
        # This bbox will be used for boundaries.tiles 
        # when the input tile source is a SMERC token. 
        smerc_n, smerc_s, smerc_e, smerc_w = reproject_geom(feature, 4326, 3857)

        # Get attribute values to be used later
        # THIS IS A VARIABLE AREA - SPECIFY YOUR ATTRIBUTES FOR NAMING
        # Close the feature - it is no longer needed
        geoid, listing_name, namelsad = identifiers(feature)

        feature.Destroy()

        # Make a directory to store the preview image files
        # that are created by TLDR & the Upload Weofile.
        mk_listing_dir(BASED + geoid)

        # Call TLDR to make the preview image files.
        mk_tldr_call(north, south, east, west, geoid, 
                     HOSTN, UNAME, PWORD, TOKN, BASED)

        # Get file names for the Upload Weofile.
        baseimage, thumbnail, kml = get_file_names(BASED + geoid)

        # Open tldr.py-generated boundaries file and 
        # create location for new Weofile output.
        output_weofile, base_feat, geo_feat = mk_weofile(BASED, geoid)

        # Create the structure for an Upload Weofile 
        weo_contents = mk_upload_weo(HOSTN, LICN, geoid, BASED, baseimage, thumbnail,
                                     TITLE, listing_name, namelsad, base_feat, 
                                     geo_feat, smerc_n, smerc_s, smerc_e, smerc_w)

        output_weofile.write(weo_contents)
        output_weofile.close()

        # Call Weoapp on the Upload Weofile that was created
        # Store the token that Weoapp creates for the upload
        call_weoapp = subprocess.Popen(['weoapp', '--continue', '--GUI', '--no-delete', 
                                        BASED + geoid + '/' + geoid + '-upload.weo'], -1, 
                                        None, stdout=subprocess.PIPE)
        weo_out, weo_err = call_weoapp.communicate()
        for aline in weo_out.split('\n'):
            if ':weoapp-token' in aline:
                output_tokens_file.write(aline.split(':')[2] + ',' + geoid + '\n')

        print '--------------------------------------------------------------------------'
#        exit()
        feature = input_layer.GetNextFeature()
    else:
        feature = input_layer.GetNextFeature()

    output_tokens_file.close()
    return

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create WeoGeo Listings from features in input vector file')
    parser.add_argument('-H', '--HOSTNAME', required=True, 
                        help='Enter Library URL.')
    parser.add_argument('-U', '--USERNAME', required=True, 
                        help='Enter Library Administrator.')
    parser.add_argument('-P', '--PASSWORD', required=True, 
                        help='Enter Administrator Password.')
    parser.add_argument('-T', '--TOKEN', required=True, 
                        help='Enter Tile Token.')
    parser.add_argument('-B', '--BASEDIR', required=True, 
                        help='Enter Abs. path to base directory. EX: C:\\Users\\Project\\Sublistings\\')
    parser.add_argument('-V', '--VECTOR', required=True, 
                        help='Enter path to input file. EX: vectors\\file.shp')
    parser.add_argument('-N', '--NAME', required=False, default='', 
                        help='Enter the desired Base Name for the listing.')
    parser.add_argument('-L', '--LICENSE', required=False, default=1, type=int, 
                        help='Enter the integer value of the License ID you want to use.')
    args = parser.parse_args()

    output_tokens_file = open((args.BASEDIR + 'tokens.csv'), 'w')

    feature_to_listing(args.HOSTNAME, args.USERNAME, args.PASSWORD, args.TOKEN, 
                       args.BASEDIR, args.VECTOR, args.NAME, args.LICENSE)