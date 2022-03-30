import configparser
import os

import requests


# Module information.
__author__ = 'Anthony Farina'
__copyright__ = 'Copyright (C) 2022 Computacenter Digital Innovation'
__credits__ = ['Anthony Farina']
__maintainer__ = 'Anthony Farina'
__email__ = 'farinaanthony96@gmail.com'
__license__ = 'MIT'
__version__ = '2.0.0'
__status__ = 'Released'


# Global variables from the config file for easy referencing.
CONFIG = configparser.ConfigParser()
CONFIG_PATH = '/../configs/PRTG-Offline-Sensor-Reporter-config.ini'
CONFIG.read(os.path.dirname(os.path.realpath(__file__)) + CONFIG_PATH)

# PRTG global variables.
PRTG_INST_URL = CONFIG['PRTG Info']['server-url']
PRTG_TABLE_URL = PRTG_INST_URL + '/api/table.xml?'
PRTG_USERNAME = CONFIG['PRTG Info']['username']
PRTG_PASSWORD = CONFIG['PRTG Info']['password']
PRTG_PROBE_FILTER = CONFIG['PRTG Info']['probe-substrings'].split(',')
PRTG_GROUP_FILTER = CONFIG['PRTG Info']['group-substrings'].split(',')
PRTG_DEVICE_FILTER = CONFIG['PRTG Info']['device-substrings'].split(',')
PRTG_SENSOR_FILTER = CONFIG['PRTG Info']['sensor-substrings'].split(',')

# Opsgenie global variables.
OG_BASE_API_URL = 'https://api.opsgenie.com/v2/'
OG_ALERTS_URL = OG_BASE_API_URL + 'alerts'
OG_API_KEY = CONFIG['Opsgenie Info']['api-key']
OG_ALERT_MESSAGE = CONFIG['Opsgenie Info']['message']
OG_ALERT_TAGS = CONFIG['Opsgenie Info']['tags'].split(',')
OG_TEAM_RESPONDERS = CONFIG['Opsgenie Info']['team-responders'].split(',')
OG_USER_RESPONDERS = CONFIG['Opsgenie Info']['user-responders'].split(',')


# This function will collect live sensor statuses from PRTG that are
# down, down (acknowledged), unknown, or partially down. It will then
# make an Opsgenie alert of the collected information.
def prtg_offline_sensor_reporter() -> None:
    # Prepare the PRTG API request parameters.
    sensor_params = {
        'content': 'sensors',
        'columns': 'probe,group,device,name,status,objid,parentid',
        'filter_status': [1, 5, 13, 14],
        'sortby': 'status',
        'output': 'json',
        'count': '50000',
        'username': PRTG_USERNAME,
        'password': PRTG_PASSWORD
    }

    # Filter certain probes, if configured.
    if PRTG_PROBE_FILTER[0] != '':
        probe_substrings = list()
        for substring in PRTG_PROBE_FILTER:
            probe_substrings.append('@sub(' + substring + ')')
        sensor_params['filter_probe'] = probe_substrings

    # Filter certain groups, if configured.
    if PRTG_GROUP_FILTER[0] != '':
        group_substrings = list()
        for substring in PRTG_GROUP_FILTER:
            group_substrings.append('@sub(' + substring + ')')
        sensor_params['filter_group'] = group_substrings

    # Filter certain devices, if configured.
    if PRTG_DEVICE_FILTER[0] != '':
        device_substrings = list()
        for substring in PRTG_DEVICE_FILTER:
            device_substrings.append('@sub(' + substring + ')')
        sensor_params['filter_device'] = device_substrings

    # Filter certain sensor names, if configured.
    if PRTG_SENSOR_FILTER[0] != '':
        sensor_substrings = list()
        for substring in PRTG_SENSOR_FILTER:
            sensor_substrings.append('@sub(' + substring + ')')
        sensor_params['filter_name'] = sensor_substrings

    # Prepare and send the PRTG API request and convert it to JSON.
    prtg_sensors_resp = requests.get(url=PRTG_TABLE_URL, params=sensor_params)
    prtg_sensors = prtg_sensors_resp.json()

    # Prepare lists for storing respective sensor statuses.
    unknown_list = list()
    down_list = list()
    down_ack_list = list()
    down_partial_list = list()

    # Go through all the retrieved sensors.
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
    all_sensors_list = \
        [unknown_list, down_list, down_ack_list, down_partial_list]
    report_str = '\n'
    list_count = 0

    # Iterate through each sensor status list.
    for sensor_list in all_sensors_list:
        # Check which status list we are on based on the order in
        # all_sensors_list.
        if list_count == 0:
            report_str += 'Current Unknown sensors in PRTG:\n'
        elif list_count == 1:
            report_str += '\nCurrent Down sensors in PRTG:\n'
        elif list_count == 2:
            report_str += '\nCurrent Down (Ack\'d) sensors in PRTG:\n'
        else:
            report_str += '\nCurrent Partially Down sensors in PRTG:\n'

        # Check if this list is empty.
        if len(sensor_list) == 0:
            report_str += 'No sensors to report!\n'

        # Go through each sensor in this list and add it to the report
        # string.
        for sensor in sensor_list:
            report_str += sensor['probe'] + ' > ' + sensor['group'] + ' > ' + \
                          sensor['device'] + ' > ' + sensor['name'] + ' is ' +\
                          sensor['status'] + '\n'

        # We are about to begin the next status list.
        report_str += '\n'
        list_count += 1

    # Fill responders list with teams and users from the config file.
    alert_responders = list()

    # Add teams.
    for team in OG_TEAM_RESPONDERS:
        alert_responders.append({'name': team, 'type': 'team'})

    # Add users.
    for user in OG_USER_RESPONDERS:
        alert_responders.append({'name': user, 'type': 'user'})

    # Prepare and send the API call to OpsGenie to make an alert.
    og_api_resp = requests.post(url=OG_ALERTS_URL,
                                headers={'Authorization': OG_API_KEY},
                                json={
                                    'message': OG_ALERT_MESSAGE,
                                    'description': report_str,
                                    'responders': alert_responders,
                                    'tags': OG_ALERT_TAGS
                                })
    print(og_api_resp.status_code)
    print(og_api_resp.text)


# The main method that runs the script. There are no input parameters.
if __name__ == '__main__':
    # Run the script.
    prtg_offline_sensor_reporter()
