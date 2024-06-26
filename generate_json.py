## Read Devices from OpenDTU
## Create Domoticz dummy devices and get IDX
## Generate data.json with the required infos
## Then you can use run_v2.py

import requests
import logging
import json
import os

# Base URLs and configuration
domoticz_base_url  = "http://192.168.15.100"       ## MODIFY THE VALUE, add user/pass if needed
json_filename      = 'data.json'
sensor_name_P1     = 'Solar P1 Meter'              ## MODIFY THE VALUE
sensor_name_global = 'Solar'                       ## MODIFY THE VALUE
dummy_HW_IDX       = 11                            ## MODIFY THE VALUE : this is the Hardware IDX of the Dummy Hardware, from Domoticz Settings, Hardware
telegram_token     = "1234567890:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  ## MODIFY THE VALUE
telegram_chat_id   = "xxxxxxxxx"                   ## MODIFY THE VALUE
dtu_base_IP        = '192.168.5.5'                 ## MODIFY THE VALUE
dtu_base_login     = 'admin'
dtu_base_password  = 'password'                    ## MODIFY THE VALUE
dtu_base_url       = f"http://{dtu_base_login}:{dtu_base_password}@{dtu_base_IP}"
sleep_duration     = 3                             ## MODIFY THE VALUE IF NEEDED
log_format         = "%(asctime)s - %(name)s - %(levelname)s - %(message)s\n(%(filename)s:%(lineno)d)"
logging.basicConfig(format=log_format)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Fetch inverter details
inverters_list = requests.get(f'{dtu_base_url}/api/inverter/list', timeout=1)
inverters_data = inverters_list.json()

def create_dummy_device(sensor_name, device_type, device_subtype, options=None):
    """Create a dummy device in Domoticz and return its IDX."""
    update_url = f"{domoticz_base_url}/json.htm?type=command&param=createdevice&idx={dummy_HW_IDX}&sensorname={sensor_name}&devicetype={device_type}&devicesubtype={device_subtype}&Switchtype=4"
    if options:
        #options_str = json.dumps(options).replace(" ", "")
        options_str = json.dumps(options)
        update_url += f"&Options={options_str}"
    print(update_url)
    response = requests.get(update_url)
    if response.status_code == 200:
        result = response.json()
        if result.get('status') == 'OK':
            new_idx = result['idx']
            logger.info(f'Device {sensor_name} created : IDX {new_idx}')
            return new_idx
        else:
            logger.error(f"Status not OK : {result.get('status')}")
            return None
    else:
        logger.error(f"Failed to create device {sensor_name}: {response.status_code}")
        return None

def generate_data_json(devices_info, global_solar_idx, global_solar_historic_idx):
    logger.info('Generate JSON File')
    """Generate the data.json file with the required format."""
    solar_units = {device['serial']: {
        "idx": device['idx'],
        "name": device['name'],
        "max_power": 400,
        "failures": 0
    } for device in devices_info}
    
    data = {
        "solar_units": solar_units,
        "telegram": {
            "token": telegram_token,
            "chat_id": telegram_chat_id
        },
        "global_solar": {
            "idx": global_solar_idx,
            "name": sensor_name_global,
            "failures": 0
        },
        "global_solar_historic": {
            "idx": global_solar_historic_idx,
            "name": sensor_name_P1,
            "failures": 0
        },
        "global_config": {
            "dtu_base_url": f'http://{dtu_base_IP}',
            "domoticz_base_url": domoticz_base_url,
            "sleep_duration": sleep_duration
        }
    }
    
    with open(json_filename, 'w') as json_file:
        json.dump(data, json_file, indent=4)

def main():
    devices_info = []
    # If json_filename already exists, ask if user wants to overwrite it
    if os.path.exists(json_filename):
        logger.warning('File already exists!')
        answer = input('Do you want to overwrite it? [Y/n]').strip() or "Y"
        #answer = input()
        if not (answer == 'Y' or answer == 'y'):
            logger.info('Aborting')
            exit(0)
        else:
            logger.info('Overwriting existing file')
            os.remove(json_filename)

    # Create Individual Inverters from OpenDTU
    for inverter in inverters_data['inverter']:
        sensor_name = inverter['name']
        serial_number = inverter['serial']
        logger.info(f'Discovered OpenDTU Inverter : {sensor_name}')
        idx = create_dummy_device(sensor_name, 243, 29, {"EnergyMeterMode": "1"})
        if idx is not None:
            devices_info.append({'name': sensor_name, 'serial': serial_number, 'idx': idx})

    # Create P1 Meter for history
    global_solar_historic_idx = create_dummy_device(sensor_name_P1, 250, 1)
    
    # Create Global Solar Dummy for Instant Value
    global_solar_idx = create_dummy_device(sensor_name_global, 243, 29, {"EnergyMeterMode": "1"})
    
    # Generate the data.json file
    generate_data_json(devices_info, global_solar_idx, global_solar_historic_idx)

    # Output the devices info list
    logger.info(f"Devices Info: {devices_info}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
