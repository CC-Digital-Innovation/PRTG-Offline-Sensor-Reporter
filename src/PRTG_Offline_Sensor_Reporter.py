from datetime import datetime,timezone
from logging.handlers import SysLogHandler
import os

import dotenv
from loguru import logger
import requests


# Module information.
__author__ = 'Anthony Farina'
__copyright__ = 'Copyright 2024, PRTG Offline Sensor Reporter'
__credits__ = ['Anthony Farina']
__license__ = 'MIT'
__version__ = '1.0.1'
__maintainer__ = 'Anthony Farina'
__email__ = 'farinaanthony96@gmail.com'
__status__ = 'Released'


# Set up the extraction of global constants from the environment variable file.
dotenv.load_dotenv()


# Opsgenie global variables.
OG_API_ALERTS_URI = os.getenv('OG_API_ALERTS_URI')
OG_API_TOKEN = os.getenv('OG_API_TOKEN')
OG_RESPONDER_TEAM_IDS = os.getenv('OG_RESPONDER_TEAM_IDS', default='').split(',')
OG_RESPONDER_USER_IDS = os.getenv('OG_RESPONDER_USER_IDS', default='').split(',')
OG_RESPONDER_ESCALATION_IDS = os.getenv('OG_RESPONDER_ESCALATION_IDS', default='').split(',')
OG_RESPONDER_SCHEDULE_IDS = os.getenv('OG_RESPONDER_SCHEDULE_IDS', default='').split(',')
OG_ALERT_TITLE = os.getenv('OG_ALERT_TITLE')
OG_ALERT_TAGS = os.getenv('OG_ALERT_TAGS', default='').split(',')

# PRTG global variables.
PRTG_INSTANCE_TABLE_URL = os.getenv('PRTG_INSTANCE_TABLE_URL')
PRTG_USERNAME = os.getenv('PRTG_USERNAME')
PRTG_PASSHASH = os.getenv('PRTG_PASSHASH')
PRTG_EXCLUDED_PROBE_NAMES = os.getenv('PRTG_EXCLUDED_PROBE_SUBSTRINGS', default='').split(',')
PRTG_EXCLUDED_GROUP_NAMES = os.getenv('PRTG_EXCLUDED_GROUP_SUBSTRINGS', default='').split(',')
PRTG_EXCLUDED_DEVICE_NAMES = os.getenv('PRTG_EXCLUDED_DEVICE_SUBSTRINGS', default='').split(',')
PRTG_EXCLUDED_SENSOR_NAMES = os.getenv('PRTG_EXCLUDED_SENSOR_SUBSTRINGS', default='').split(',')

# logger global variables.
LOGGER_NAME = os.getenv('LOGGER_NAME')
LOGGER_FILE_NAME = os.getenv('LOGGER_FILE_NAME')

# Papertrail global variables.
PAPERTRAIL_ADDRESS = os.getenv('PAPERTRAIL_ADDRESS')
PAPERTRAIL_PORT = os.getenv('PAPERTRAIL_PORT')

# Slack global variables.
SLACK_API_TOKEN = os.getenv('SLACK_API_TOKEN')
SLACK_CHANNEL_IDS = os.getenv('SLACK_CHANNEL_IDS').split(',')

# Other global variables.
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))


def prtg_offline_sensor_reporter() -> None:
    """
     This function will gather the sensors that are currently down or unknown in the
     configured PRTG instance. It will make an Opsgenie alert of the report from
     the status data of the sensors to the configured Opsgenie instance.
    """

    logger.info(f'Beginning {OG_ALERT_TITLE}')
    logger.info('Gathering PRTG sensors...')

    # Prepare PRTG API parameters to retrieve all sensors with a status of 1 (Unknown),
    # 5 (Down), 13 (Down Acknowledged), or 14 (Down Partial).
    prtg_api_params = {'content': 'sensors',
                       'columns': 'probe,group,device,name,status,objid,parentid',
                       'filter_status': [1, 5, 13, 14],
                       'sortby': 'status',
                       'output': 'json',
                       'count': '50000',
                       'username': PRTG_USERNAME,
                       'passhash': PRTG_PASSHASH}

    # Send the PRTG API request.
    prtg_sensors_resp = requests.get(url=PRTG_INSTANCE_TABLE_URL, params=prtg_api_params)

    # Check if the PRTG request failed. If so, send a Slack message to all the 
    # configured Slack channels and end the script.
    if not prtg_sensors_resp.ok:
        error_message = f"\"{OG_ALERT_TITLE}\" was unable to run because of a " \
                        f"PRTG API error.\n\n" \
                        f"Status Code: {prtg_sensors_resp.status_code}\n\n" \
                        f"Reason: {prtg_sensors_resp.reason}"
        logger.error(error_message)
        send_error_to_slack_channels(error_message)
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
        url=OG_API_ALERTS_URI,
        headers=
        {
            'Authorization': OG_API_TOKEN,
            'Content-Type': 'application/json'
        },
        json=
        {
            'message': OG_ALERT_TITLE,
            'description': alert_report_text,
            'responders': opsgenie_responder_list(),
            'tags': OG_ALERT_TAGS
        }
    )
    
    # Check if the Opsgenie alert was successfully created.
    if og_api_resp.ok:
        logger.info('Opsgenie alert sent!')
    else:
        # Send the error to all configured Slack channels.
        error_message = f'\"{OG_ALERT_TITLE}\" was unable to run because of an '\
                        f'Opsgenie API error.\n\n' \
                        f'Status code: {og_api_resp.status_code}\n\n' \
                        f'Reason: {og_api_resp.reason}'
        logger.error(error_message)
        send_error_to_slack_channels(error_message)
        return
    
    # Successfully end the script.
    logger.info(f'End of {OG_ALERT_TITLE}')


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
    for team_responder_id in OG_RESPONDER_TEAM_IDS:
        responder = {'id': team_responder_id, 'type': 'team'}
        responders.append(responder)

    # Add user responders.
    for user_responder_id in OG_RESPONDER_USER_IDS:
        responder = {'id': user_responder_id, 'type': 'user'}
        responders.append(responder)

    # Add escalation responders.
    for escalation_responder_id in OG_RESPONDER_ESCALATION_IDS:
        responder = {'id': escalation_responder_id, 'type': 'escalation'}
        responders.append(responder)

    # Add schedule responders.
    for schedule_responder_id in OG_RESPONDER_SCHEDULE_IDS:
        responder = {'id': schedule_responder_id, 'type': 'schedule'}
        responders.append(responder)

    return responders


def send_slack_message(message: str, channel_id: str) -> None:
    """
    Send the provided message to the provided Slack channel via its channel ID.

    Params:
        message (str): The message to send to Slack.
        channel (str): The channel to send the message to.
    """

    # Send message to Slack.
    logger.info(f'Sending message to Slack with channel ID "{channel_id}"')
    slack_response = requests.post(
        url='https://slack.com/api/chat.postMessage',
        headers=
        {
            'Authorization': 'Bearer ' + SLACK_API_TOKEN,
            'Content-Type': 'application/json; charset=utf-8'
        },
        json=
        {
            'channel': channel_id,
            'text': message
        }
    )

    # Check the status of the request.
    slack_response_message = slack_response.json()
    slack_response_is_ok = slack_response_message['ok']
    if slack_response_is_ok:
        logger.info('Slack message sent successfully!')
    else:
        logger.error(f'Slack message failed to send.')
        logger.error(f'Reason: {slack_response_message['error']}')


def send_error_to_slack_channels(error_message: str) -> None:
    """
    Sends the provided error message to all configured Slack channels based
    off their respective channel IDs.

    Params:
        error_message (str): The error message to send to the Slack channels.
    """

    # Send the error to all configured Slack channels.
    for slack_channel in SLACK_CHANNEL_IDS:
        send_slack_message(error_message, slack_channel)
    logger.info(f"End of {OG_ALERT_TITLE}")


def initialize_logger() -> None:
    """
    Initializes the global logger for this script. Logs will be generated for the
    console, a log file, Paper Trail, and Fastvue.
    """

    # Check if the "logs" folder exists. If not, create it.
    if not os.path.isdir(SCRIPT_PATH + '/../logs'):
        os.mkdir(SCRIPT_PATH + '/../logs')

    # Add the local log file to the logger.
    now_utc = datetime.now(timezone.utc)
    logger.add(f"{SCRIPT_PATH}'/../logs/{LOGGER_FILE_NAME}_log_" \
               f"{now_utc.strftime('%Y-%m-%d_%H-%M-%S-%Z')}.log")

    # Add Paper Trail to the logger.
    paper_trail_handle = SysLogHandler(address=('logs.papertrailapp.com',
                                                49638))
    logger.add(paper_trail_handle)

    # Add Fastvue to the logger.
    fastvue_handle = SysLogHandler(address=('dev-syslog.quokka.ninja', 51514))
    logger.add(fastvue_handle)


if __name__ == '__main__':
    # Initializes the global logger for this script.
    initialize_logger()

    # Run the script.
    prtg_offline_sensor_reporter()
