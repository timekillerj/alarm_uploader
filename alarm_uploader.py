#!/usr/bin/env python

import os
import logging
import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException
from time import sleep
import xml.etree.ElementTree as ET
import inotify.adapters
import rclone
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log_level = os.environ['log_level']
if log_level == 'debug':
    logging_level = logging.DEBUG
else:
    logging_level = logging.INFO

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging_level,
    datefmt='%Y-%m-%d %H:%M:%S')

isy_host = os.environ['isy_host']
isy_user = os.environ['isy_user']
isy_pass = os.environ['isy_pass']
isy_vartype = os.environ['isy_vartype']
isy_varid = os.environ['isy_varid']
rclone_remote = os.environ['rclone_remote']
watch_dir = os.environ['watch_dir']

isy_url = 'https://' + isy_host + '/rest/vars/get/' + str(isy_vartype) + '/' + str(isy_varid)
logging.debug('ISY url: {}'.format(isy_url))
logging.debug('RCLONE remote: {}'.format(rclone_remote))
logging.debug('watch_dir: {}'.format(watch_dir))

# Rclone Settings
rclone_conf = '/rclone.conf'
with open(rclone_conf, 'r') as rclone_file:
    rconfig=rclone_file.read()


def simple_get(isy_url):
    logging.debug('Fetching {}'.format(isy_url))
    try:
        resp = requests.get(isy_url, auth=HTTPBasicAuth(isy_user, isy_pass), verify=False)
        if is_good_response(resp):
            return resp.content
        else:
            return None

    except RequestException as e:
        logging.error('Error during requests to {}: {}'.format(isy_url, str(e)))

def is_good_response(resp):
    content_type = resp.headers['Content-Type'].lower()
    return(resp.status_code == 200
            and content_type is not None
            and content_type.find('xml') > -1)

def alarm_active():
    xml_response = simple_get(isy_url)
    if not xml_response:
        return False
    root = ET.fromstring(xml_response)
    for child in root:
        if child.tag == 'val':
            if child.text == "1":
                return True
    return False


if __name__ == '__main__':
    alarm_logged = 0
    logging.info('Setting up inotify watch_dir {}'.format(watch_dir))
    i = inotify.adapters.InotifyTree(watch_dir)
    logging.info('inotify watch complete')
    uploaded_files = 0
    while True:
        if alarm_active():
            if not alarm_logged:
                logging.info('Alarm Active!')
                alarm_logged =1
            events = i.event_gen(yield_nones=False, timeout_s=1)
            events = list(events)
            if events:
                for event in events:
                    (_, type_names, path, filename) = event
                    if 'IN_CLOSE_WRITE' in type_names:
                        source = path + '/' + filename
                        dest = rclone_remote + path
                        
                        logging.debug('Uploading: {}'.format(source))
                        logging.debug('    to {}'.format(dest))
                        result = rclone.with_config(rconfig).copy(source, dest)
                        if result.get('error'):
                            logging.error('OUTPUT: {}'.format(result.get('out')))
                            logging.error('CODE: {}'.format(result.get('code')))
                            logging.error('ERROR: {}'.format(result.get('error')))
                        else:
                            uploaded_files += 1
        else:
            if alarm_logged:
                logging.info("Alarm resolved, uploaded {} files".format(uploaded_files))
                alarm_logged = 0
                uploaded_files = 0

            logging.debug("Inactive, sleeping")
            sleep(5)
