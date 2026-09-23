import os

import dotenv
import requests
from loguru import logger


# ====================== Environment / Global Variables =======================
dotenv.load_dotenv(override=True)

# Opsgenie global environment variables.
OPSGENIE_API_ALERTS_URI = os.getenv('OPSGENIE_API_ALERTS_URI')
OPSGENIE_API_TOKEN = os.getenv('OPSGENIE_API_TOKEN')
OPSGENIE_RESPONDER_TEAM_IDS = os.getenv('OPSGENIE_RESPONDER_TEAM_IDS', default='').split(',')
OPSGENIE_RESPONDER_USER_IDS = os.getenv('OPSGENIE_RESPONDER_USER_IDS', default='').split(',')
OPSGENIE_RESPONDER_ESCALATION_IDS = os.getenv('OPSGENIE_RESPONDER_ESCALATION_IDS', default='').split(',')
OPSGENIE_RESPONDER_SCHEDULE_IDS = os.getenv('OPSGENIE_RESPONDER_SCHEDULE_IDS', default='').split(',')
OPSGENIE_ALERT_TITLE = os.getenv('OPSGENIE_ALERT_TITLE')
OPSGENIE_ALERT_TAGS = os.getenv('OPSGENIE_ALERT_TAGS', default='').split(',')

# PRTG global environment variables.
PRTG_INSTANCE_TABLE_URL = os.getenv('PRTG_INSTANCE_TABLE_URL')
PRTG_USERNAME = os.getenv('PRTG_USERNAME')
PRTG_PASSHASH = os.getenv('PRTG_PASSHASH')
PRTG_EXCLUDED_PROBE_NAMES = os.getenv('PRTG_EXCLUDED_PROBE_SUBSTRINGS', default='').split(',')
PRTG_EXCLUDED_GROUP_NAMES = os.getenv('PRTG_EXCLUDED_GROUP_SUBSTRINGS', default='').split(',')
PRTG_EXCLUDED_DEVICE_NAMES = os.getenv('PRTG_EXCLUDED_DEVICE_SUBSTRINGS', default='').split(',')
PRTG_EXCLUDED_SENSOR_NAMES = os.getenv('PRTG_EXCLUDED_SENSOR_SUBSTRINGS', default='').split(',')


def filter_out(prtg_sensor: dict) -> bool:
    """
    This function will take a PRTG sensor in the form of a dictionary
    and return whether the sensor should be filtered out of the report or not.

    Params:
        prtg_sensor (dict): The PRTG sensor dictionary to filter out. It must
        have the probe, group, device, and name attributes from the API.

    Returns:
        (bool): True if this sensor should be excluded from the report, false
        otherwise.
    """

    return any(excluded_probe_name for excluded_probe_name in PRTG_EXCLUDED_PROBE_NAMES 
               if excluded_probe_name in prtg_sensor['probe']) or \
           any(excluded_group_name for excluded_group_name in PRTG_EXCLUDED_GROUP_NAMES 
               if excluded_group_name in prtg_sensor['group']) or \
           any(excluded_device_name for excluded_device_name in PRTG_EXCLUDED_DEVICE_NAMES 
               if excluded_device_name in prtg_sensor['device']) or \
           any(excluded_sensor_name for excluded_sensor_name in PRTG_EXCLUDED_SENSOR_NAMES 
               if excluded_sensor_name in prtg_sensor['name'])


def opsgenie_responder_list() -> list[dict]:
    """
    This function will format and return a list of opsgenie responder objects
    for an Opsgenie API alerts request.

    Returns:
        (list[dict]): A list of responder dictionaries for an Opsgenie API alert
        request.
    """

    responders = list()

    # Add team responders.
    for team_responder_id in OPSGENIE_RESPONDER_TEAM_IDS:
        responder = {'id': team_responder_id, 'type': 'team'}
        responders.append(responder)

    # Add user responders.
    for user_responder_id in OPSGENIE_RESPONDER_USER_IDS:
        responder = {'id': user_responder_id, 'type': 'user'}
        responders.append(responder)

    # Add escalation responders.
    for escalation_responder_id in OPSGENIE_RESPONDER_ESCALATION_IDS:
        responder = {'id': escalation_responder_id, 'type': 'escalation'}
        responders.append(responder)

    # Add schedule responders.
    for schedule_responder_id in OPSGENIE_RESPONDER_SCHEDULE_IDS:
        responder = {'id': schedule_responder_id, 'type': 'schedule'}
        responders.append(responder)

    return responders


def run() -> None:
    """
     This function will gather the sensors that are currently down or unknown in the
     configured PRTG instance. It will make an Opsgenie alert of the report from
     the status data of the sensors to the configured Opsgenie instance.
    """

    logger.info(f'Beginning {OPSGENIE_ALERT_TITLE}')
    logger.info('Gathering PRTG sensors...')

    # Prepare PRTG API parameters to retrieve all sensors with a status of 1 (Unknown),
    # 5 (Down), 13 (Down Acknowledged), or 14 (Down Partial).
    prtg_api_params = {
        'content': 'sensors',
        'columns': 'probe,group,device,name,status,objid,parentid',
        'filter_status': [1, 5, 13, 14],
        'sortby': 'status',
        'output': 'json',
        'count': '50000',
        'username': PRTG_USERNAME,
        'passhash': PRTG_PASSHASH
    }

    # Send the PRTG API request.
    prtg_sensors_resp = requests.get(url=PRTG_INSTANCE_TABLE_URL, params=prtg_api_params)

    # Check if the PRTG request failed. If so, send a Slack message to all the 
    # configured Slack channels and end the script.
    if not prtg_sensors_resp.ok:
        error_message = f"\"{OPSGENIE_ALERT_TITLE}\" was unable to run because of a " \
                        f"PRTG API error.\n\n" \
                        f"Status Code: {prtg_sensors_resp.status_code}\n\n" \
                        f"Reason: {prtg_sensors_resp.reason}"
        logger.error(error_message)
        return

    # Since the response was successful, convert the response's text to JSON.
    logger.info('Sensors gathered!')
    prtg_sensors = prtg_sensors_resp.json()

    # Prepare lists for storing respective sensor statuses.
    unknown_list = list()
    down_list = list()
    down_ack_list = list()
    down_partial_list = list()

    # Go through all the sensors from the PRTG API request.
    logger.info('Filtering sensors...')
    for sensor in prtg_sensors['sensors']:
        # Filter out excluded sensors.
        if filter_out(sensor):
            continue

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

    logger.info('Sensors filtered!')

    # Make an iterable list of the sensor status lists.
    all_sensor_status_lists = [unknown_list, down_list, down_ack_list, down_partial_list]
    alert_report_text = ''
    list_count = 0

    # Iterate through each sensor status list.
    logger.info('Creating Opsgenie report...')
    for sensor_list in all_sensor_status_lists:
        # Check which status list we are on. Based on the order in all_sensors_list.
        if list_count == 0:
            alert_report_text += '\nCurrent Unknown sensors in PRTG:\n'
        elif list_count == 1:
            alert_report_text += '\nCurrent Down sensors in PRTG:\n'
        elif list_count == 2:
            alert_report_text += '\nCurrent Down (Ack\'d) sensors in PRTG:\n'
        else:
            alert_report_text += '\nCurrent Partially Down sensors in PRTG:\n'

        # Check if this list is empty.
        if len(sensor_list) == 0:
            alert_report_text += 'No sensors to report!\n'

        # Go through each sensor in this list and add it to the description string.
        # This for loop will not run if this list is empty.
        for sensor in sensor_list:
            alert_report_text += sensor['probe'] + ' > ' + sensor['group'] + ' > ' + sensor['device'] + ' > ' + \
                         sensor['name'] + ' is ' + sensor['status'] + '\n'

        # We are about to begin the next status list.
        alert_report_text += '\n'
        list_count += 1

    logger.info('Opsgenie report created!')

    # Prepare and send the API call to OpsGenie.
    logger.info('Sending alert to Opsgenie...')
    og_api_resp = requests.post(
        url=OPSGENIE_API_ALERTS_URI,
        headers={
            'Authorization': OPSGENIE_API_TOKEN,
            'Content-Type': 'application/json'
        },
        json={
            'message': OPSGENIE_ALERT_TITLE,
            'description': alert_report_text,
            'responders': opsgenie_responder_list(),
            'tags': OPSGENIE_ALERT_TAGS
        }
    )
    
    # Check if the Opsgenie alert was successfully created.
    if og_api_resp.ok:
        logger.info('Opsgenie alert sent!')
    else:
        # Send the error to all configured Slack channels.
        error_message = f'\"{OPSGENIE_ALERT_TITLE}\" was unable to run because of an '\
                        f'Opsgenie API error.\n\n' \
                        f'Status code: {og_api_resp.status_code}\n\n' \
                        f'Reason: {og_api_resp.reason}'
        logger.error(error_message)
        return
    
    # Successfully end the script.
    logger.info(f'End of {OPSGENIE_ALERT_TITLE}')


if __name__ == '__main__':
    run()
