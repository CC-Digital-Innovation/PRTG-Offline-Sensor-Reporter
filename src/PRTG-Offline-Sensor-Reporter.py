import configparser
import json
import os

import requests


# Module information.
__author__ = 'Anthony Farina'
__copyright__ = 'Copyright 2021, PRTG Offline Sensor Reporter'
__credits__ = ['Anthony Farina']
__license__ = 'MIT'
__version__ = '1.0.0'
__maintainer__ = 'Anthony Farina'
__email__ = 'farinaanthony96@gmail.com'
__status__ = 'Released'


# Global variables from the config file for easy referencing.
CONFIG = configparser.ConfigParser()
CONFIG_PATH = '/../configs/PRTG-Offline-Sensor-Reporter-config.ini'
CONFIG.read(os.path.dirname(os.path.realpath(__file__)) + CONFIG_PATH)
PRTG_API_URL = CONFIG['PRTG Info']['server-url'] + '/api/table.xml?'
PRTG_USERNAME = CONFIG['PRTG Info']['username']
PRTG_PASSWORD = CONFIG['PRTG Info']['password']
PRTG_PASSHASH = CONFIG['PRTG Info']['passhash']
OG_API_KEY = CONFIG['Opsgenie API Info']['API-Key']


# This function will report the sensors that are currently down or unknown in PRTG. It will
# make an Opsgenie alert of the report.
def prtg_offline_sensor_reporter() -> None:
    # Prepare PRTG API parameters to retrieve all sensors with a status of 1 (Unknown),
    # 5 (Down), 13 (Down Acknowledged), or 14 (Down Partial).
    prtg_api_params = {'content': 'sensors',
                       'columns': 'probe,group,device,name,status,objid,parentid',
                       'filter_status': [1, 5, 13, 14],
                       'sortby': 'status',
                       'output': 'json',
                       'count': '50000',
                       'username': PRTG_USERNAME}

    # Add password or passhash to the end of the parameter list for authorization to the PRTG API.
    add_auth(prtg_api_params)

    # Send the PRTG API request and convert it to JSON.
    prtg_sensors_resp = requests.get(url=PRTG_API_URL, params=prtg_api_params)
    prtg_sensors = json.loads(prtg_sensors_resp.text)

    # Prepare lists for storing respective sensor status.
    unknown_list = list()
    down_list = list()
    down_ack_list = list()
    down_partial_list = list()

    # Go through all the sensors from the PRTG API request.
    for sensor in prtg_sensors['sensors']:
        # Add this sensor to its respective status list.
        if sensor['status_raw'] == 1:
            unknown_list.append(sensor)
        elif sensor['status_raw'] == 5:
            down_list.append(sensor)
        elif sensor['status_raw'] == 13:
            down_ack_list.append(sensor)
        elif sensor['status_raw'] == 14:
            down_partial_list.append(sensor)
        # Add any anomalous sensors to the unknown sensor list.
        else:
            unknown_list.append(sensor)

    # Make an iterable list of the sensor status lists.
    all_sensors_list = [unknown_list, down_list, down_ack_list, down_partial_list]
    descr_str = ''
    list_count = 0

    # Iterate through each sensor status list.
    for sensor_list in all_sensors_list:
        # Check which status list we are on. Based on the order in all_sensors_list.
        if list_count == 0:
            descr_str += 'Current Unknown sensors in PRTG:\n'
        elif list_count == 1:
            descr_str += '\nCurrent Down sensors in PRTG:\n'
        elif list_count == 2:
            descr_str += '\nCurrent Down (Ack\'d) sensors in PRTG:\n'
        else:
            descr_str += '\n Current Partially Down sensors in PRTG:\n'

        # Check if this list is empty.
        if len(sensor_list) == 0:
            descr_str += 'No sensors to report!\n'

        # Go through each sensor in this list and add it to the description string.
        # This for loop will not run if this list is empty.
        for sensor in sensor_list:
            descr_str += sensor['probe'] + ' > ' + sensor['group'] + ' > ' + sensor['device'] + ' > ' + \
                         sensor['name'] + ' is ' + sensor['status'] + '\n'

        # We are about to begin the next list iteration.
        descr_str += '\n'
        list_count += 1

    # Prepare and send the API call to OpsGenie.
    og_api_url = 'https://api.opsgenie.com/v2/alerts'
    og_api_resp = requests.post(url=og_api_url,
                                headers={'Authorization': OG_API_KEY, 'Content-Type': 'application/json'},
                                json={'message': 'Current Offline PRTG Sensors',
                                      'description': descr_str,
                                      'responders': [
                                          {'id': 'test-team-id', 'type': 'team'},
                                          {'id': 'test-user-id', 'type': 'user'}
                                      ],
                                      'tags': ['PRTG', 'test-tag']
                                      })


# This function (short for "add authorization") appends the authorization method to the given params
# parameter to authenticate a PRTG API call. Based on which field is filled inside the config file,
# we will append either the password or passhash. Passhash has priority over password.
def add_auth(params) -> None:
    # If the passhash field is empty in the config file, use the password field.
    if PRTG_PASSHASH == '':
        params.update({'password': PRTG_PASSWORD})
    # The passhash field is not empty. Use this field.
    else:
        params.update({'passhash': PRTG_PASSHASH})


# The main method that runs the script. There are no input parameters.
if __name__ == '__main__':
    # Run the script.
    prtg_offline_sensor_reporter()
