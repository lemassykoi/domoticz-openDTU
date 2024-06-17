import requests
import time
import logging

# Replace with your OpenDTU device IP address
dtu_base_url      = "http://10.0.10.1"

# Replace with your Domoticz device IP address
domoticz_base_url = "http://127.0.0.1"

# Replace with your Telegram Values
TG_TOKEN                       = 'YOUR_TELEGRAM_TOKEN'
TG_CHATID                      = 'xxxxxxxxx'

daily_report_sent              = False
notif_all_started              = False
notif_all_stopped              = False
sleep_duration                 = 3
log_format                     = "%(asctime)s - %(name)s - %(levelname)s - %(message)s \t (%(filename)s:%(lineno)d)"

# Mapping between inverter serial numbers and their corresponding Domoticz IDX values
# Replace Serials by yours
idx_global                     = 1125
serial_to_datas = {
    '1125xxxxxxxx': {'idx': '1126', 'name': 'Panneau 1', 'max_power': 400},
    '1125xxxxxxxx': {'idx': '1128', 'name': 'Extension 1', 'max_power': 400},
    '1125xxxxxxxx': {'idx': '1127', 'name': 'Panneau 2', 'max_power': 400},
    '1125xxxxxxxx': {'idx': '1129', 'name': 'Extension 2', 'max_power': 400}
}

# Initialize the production state for each inverter
solar_production = {serial: False for serial in serial_to_datas.keys()}

# Initialize Logging
logging.basicConfig(
    format = log_format,
    level  = 'INFO'
)

logging.info('Start...')

def get_system_info():
    return fetch_data(f"{dtu_base_url}/api/system/status")

def get_live_data():
    return fetch_data(f"{dtu_base_url}/api/livedata/status")

def get_inverter_live_data(inverter):
    return fetch_data(f"{dtu_base_url}/api/livedata/status?inv={inverter}")

def fetch_data(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"HTTP Request failed: {e}")
        return None

def update_domoticz_solar(IDX, POWER, ENERGY):
    update_url = f"{domoticz_base_url}/json.htm?type=command&param=udevice&idx={IDX}&nvalue=0&svalue={str(POWER)};{str(ENERGY)}"
    response = requests.get(update_url)
    if response.status_code == 200:
        return response

def send_message_by_telegram(MESSAGE, TOKEN, CHATID):
    import requests
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHATID}&text={MESSAGE}"
    try:
        print(requests.get(url).json()) # this sends the message
        return True
    except Exception as e:
        logging.error(e)
        return False

while True:
    try:
        global_tic = time.perf_counter()
        tic = time.perf_counter()
        live_data = get_live_data()
        if live_data is not None:
            # Update Global Solar Datas
            current_power = (round(float(live_data.get('total')['Power'].get('v')), 1))
            yield_day = (float(live_data.get('total')['YieldDay'].get('v')))
            response = update_domoticz_solar(idx_global, current_power, yield_day)
            toc = time.perf_counter()
            logging.debug(f"1 - Duration : {toc - tic:0.4f} seconds. HTTP : {response.status_code}")
            
            # Update Individual Solar Panel Datas
            tic = time.perf_counter()
            # Get the list off all inverters serial numbers
            for serial, data in serial_to_datas.items():
                idx  = data['idx']
                name = data['name']
                # For each serial number, query to openDTU
                live_data = get_inverter_live_data(serial)
                if live_data is not None:
                    if live_data and 'inverters' in live_data:
                        inverter_data = live_data['inverters'][0]
                        # Check if the inverter is producing energy
                        if inverter_data['producing']:
                            # Check if it was NOT producing during previous run :
                            if not solar_production[serial]:
                                # If it was not, then this a production start from the morning
                                solar_production[serial] = True
                                send_message_by_telegram(f"Starting Solar Production for {name}", TG_TOKEN, TG_CHATID)
                            power = round(float(inverter_data['INV']['0']['Power DC']['v']), 1)
                            energy = int(inverter_data['INV']['0']['YieldDay']['v'])
                            response = update_domoticz_solar(idx, power, energy)
                            logging.debug(f"Inverter {serial} : HTTP {response.status_code}\n")
                        else:
                            # Check if it was producing during previous run :
                            if solar_production[serial]:
                                # If it was, then this is production end from the evening
                                solar_production[serial] = False
                                send_message_by_telegram(f"Ending Solar Production for {name}", TG_TOKEN, TG_CHATID)
                            logging.debug(f'Inverter {serial} is NOT producing energy')
                    else:
                        logging.warning('No inverters in live_data')
                else:
                    logging.warning(f'No data received for inverter {name} ({serial})')
            toc = time.perf_counter()
            logging.debug(f"2 - Duration : {toc - tic:0.4f} seconds.\n")

            # Check if ALL inverters have stopped or started producing
            all_inverters_stopped = all(not value for value in solar_production.values())
            all_inverters_started = all(value for value in solar_production.values())
            
            if all_inverters_stopped and not notif_all_stopped:
                logging.debug('All Inverters are NOT producing now')
                send_message_by_telegram("All inverters Stopped!", TG_TOKEN, TG_CHATID)
                notif_all_stopped = True
                notif_all_started = False
            elif all_inverters_started and not notif_all_started:
                logging.debug('All Inverters are producing now')
                send_message_by_telegram("All inverters Started!", TG_TOKEN, TG_CHATID)
                notif_all_started = True
                notif_all_stopped = False
                daily_report_sent = False
            
            # Send Daily Report
            if not daily_report_sent and notif_all_stopped:
                logging.info('Time to send Daily Production Message')
                yield_day = (float(live_data.get('total')['YieldDay'].get('v')))
                energy_in_kwh = yield_day / 1000
                message = (f"🌞 Production Solaire du Jour : {energy_in_kwh} kWh")
                send_message_by_telegram(message, TG_TOKEN, TG_CHATID)
                daily_report_sent = True

        else:
            logging.warning('No live_data received')
        global_toc = time.perf_counter()
        logging.debug(f"== Total Duration : {global_toc - global_tic:0.4f} seconds.\n")
        time.sleep(sleep_duration)
    except Exception as e:
        logging.debug(e)
        exit(-1)
