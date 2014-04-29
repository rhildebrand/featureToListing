import os
import csv
import json
import weoXML
import argparse
import HILDEBRAND
import WeoGeoAPI_admin as WeoGeoAPI

def dataset_updater(HOSTN, UNAME, PWORD, F, **kwargs):
    input = open((F), 'r')
    content = csv.reader(input, delimiter=',')

    session = WeoGeoAPI.weoSession_admin(HOSTN, UNAME, PWORD)
    if session.connect() == False:
        print 'Could not connect.'
        exit(0)
    
    for token,geoid in content:
        geoid = geoid.strip()
        token = token.strip()
        status, record = session.getDataset(token, WeoGeoAPI.formats.JSON)
        if status != 200:
            print 'Could not retrieve listing record for ' + str(token) + '. Status: ' + str(status)
            continue
        if kwargs['BASE'] is not None:
            HILDEBRAND.update_preview_base(session, token, kwargs['TILE_TOKEN'], kwargs['BASE'], record)
        if kwargs['VECTOR'] is not None:
            HILDEBRAND.add_preview_vector(session, token, 'highlight', kwargs['VECTOR'] + geoid + '.json', record)
        if kwargs['OVERLAY'] is not None:
            add_preview_tile_layer(session, token, OVERLAY, 'png')
        if kwargs['NAME'] is not None:
            record['name'] = kwargs['NAME'] + record['name']
        if kwargs['LAYERS'] is not None:
            record['layers'] = kwargs['LAYERS']
    
        status, message = session.updateDataset(token, record, WeoGeoAPI.formats.JSON)
        if status != 204:
            print 'Update FAILED: ' + token
            continue
    
        print 'UPDATES are complete for: ' + token
    
    input.close()
    return

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Tool to update listing content via the WeoGeoAPI.')
    parser.add_argument('-H', '--HOSTNAME', required=True, 
                        help='Enter Library URL.')
    parser.add_argument('-U', '--USERNAME', required=True, 
                        help='Enter Library Administrator.')
    parser.add_argument('-P', '--PASSWORD', required=True, 
                        help='Enter Administrator Password.')
    parser.add_argument('-F', '--TOKENS-FILE', required=True, 
                        help='Enter path to file containing Tokens.')
    parser.add_argument('-T', '--TILE-TOKEN', required=False, 
                        help='Enter Tile Token.')
    parser.add_argument('-N', '--NAME', required=False, default='', 
                        help='Enter the desired Base Name for the listing.')
    parser.add_argument('-L', '--LAYERS', nargs='+', required=False, 
                        help='Enter a comma delimited list of layer names.')
    parser.add_argument('-B', '--BASE', required=False, type=int,
                        help='Enter the maximum zoom level of the base tiles token. Used with \'-T\'')
    parser.add_argument('-V', '--VECTOR', required=False, 
                        help='Enter the base path to be used for a Vector Overlay.')
    parser.add_argument('-O', '--OVERLAY', required=False, 
                        help='Enter the token to be used as a Tile Overlay.')
    args = parser.parse_args()
    dataset_updater(args.HOSTNAME, args.USERNAME, args.PASSWORD, args.TOKENS_FILE, 
                    TILE_TOKEN=args.TILE_TOKEN, NAME=args.NAME, LAYERS=args.LAYERS, 
                    BASE=args.BASE, VECTOR=args.VECTOR, OVERLAY=args.OVERLAY)