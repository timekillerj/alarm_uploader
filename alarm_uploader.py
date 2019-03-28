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

log_level = os.environ['LOGGING']
if log_level == 'debug':
    logging.getLogger().setLevel(logging.DEBUG)
else:
    logging.getLogger().setLevel(logging.INFO)

isy_host = os.environ['ISY_HOST']
isy_user = os.environ['ISY_USER']
isy_pass = os.environ['ISY_PASS']
isy_vartype = os.environ['ISY_VARTYPE']
isy_varid = os.environ['ISY_VARID']
rclone_remote = os.environ['RCLONE_REMOTE']
watch_dir = os.environ['WATCH_DIR']

isy_url = isy_host + '/rest/vars/get/' + str(isy_vartype) + '/' + str(isy_varid)

# Rclone Settings
rclone_conf = '/config/rclone.conf'
with open(rclone_conf, 'r') as rclone_file:
    rconfig=rclone_file.read()


def simple_get(isy_url):
    logging.info('Fetching {}'.format(isy_url))
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
    root = ET.fromstring(xml_response)
    for child in root:
        if child.tag == 'val':
            if child.text == "1":
                return True
    return False


if __name__ == '__main__':
    alarm_logged = 0
    while True:
        if alarm_active():
            if not alarm_logged:
                logging.info('Alarm Active!')
                alarm_logged =1
            i = inotify.adapters.InotifyTree(watch_dir)
            events = i.event_gen(yield_nones=False, timeout_s=1)
            events = list(events)
            if events:
                for event in events:
                    (_, type_names, path, filename) = event
                    if 'IN_CLOSE_WRITE' in type_names:
                        source = path + '/' + filename
                        dest = rclone_remote + path

                        logging.info('Uploading: {}'.format(source))
                        result = rclone.with_config(rconfig).copy(source, dest)
                        if result.get('error'):
                            logging.error('OUTPUT: {}'.format(result.get('out')))
                            logging.error('CODE: {}'.format(result.get('code')))
                            logging.error('ERROR: {}'.format(result.get('error')))
        else:
            logging.debug("Inactive, sleeping")
            alarm_logged = 0
            sleep(5)
