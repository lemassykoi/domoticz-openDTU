import requests
import time
import logging
import json
json_path = 'data.json'

class CustomFormatter(logging.Formatter):

    grey     = "\x1b[38;20m"
    yellow   = "\x1b[33;20m"
    red      = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset    = "\x1b[0m"
    OKBLUE   = '\033[94m'
    OKCYAN   = '\033[96m'
    OKGREEN  = '\033[92m'
    format   = "%(asctime)s - %(name)s - %(levelname)s - %(message)s\t(%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: OKBLUE + format + reset,
        logging.INFO: OKCYAN + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# create logger with 'spam_application'
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)

# Mapping between inverter serial numbers and their corresponding Domoticz IDX values
def load_serial_data(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

# Fonction pour sauvegarder les données dans le fichier JSON
def save_serial_data(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

# Load Datas from Json
config_data = load_serial_data(json_path)

# Extraire les unités solaires et les configurations Telegram
serial_to_datas   = config_data.get('solar_units', {})
telegram_config   = config_data.get('telegram', {})
global_solar      = config_data.get('global_solar', {})
global_solar_P1   = config_data.get('global_solar_historic', {})
global_config     = config_data.get('global_config', {})

# Define some Vars
TG_TOKEN          = telegram_config.get('token')
TG_CHATID         = telegram_config.get('chat_id')
dtu_base_url      = global_config.get('dtu_base_url')
domoticz_base_url = global_config.get('domoticz_base_url')
sleep_duration    = global_config.get('sleep_duration')
idx_global        = global_solar.get('idx')
name_global       = global_solar.get('name')
idx_global_P1     = global_solar_P1.get('idx')
name_global_P1    = global_solar_P1.get('name')
timeout_requests  = 1
daily_report_sent = False
notif_all_started = False
notif_all_stopped = False

# Initialize production state for each inverter
solar_production = {serial: False for serial in serial_to_datas.keys()}

logger.info('Start...')

def get_system_info():
    return fetch_data(f"{dtu_base_url}/api/system/status")

def get_live_data():
    return fetch_data(f"{dtu_base_url}/api/livedata/status")

def get_inverter_live_data(inverter: str):
    return fetch_data(f"{dtu_base_url}/api/livedata/status?inv={inverter}")

def fetch_data(url: str):
    try:
        response = requests.get(url=url, timeout=timeout_requests)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectTimeout:
        logger.error('Connect Timeout error')  # Erreur de délai d'attente
        return None
    except requests.exceptions.Timeout as timeout_err:
        logger.error(f'Timeout error: {timeout_err}')  # Erreur de délai d'attente
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP Request failed: {e}")
        return None

def update_domoticz_solar(IDX: str, POWER: int, ENERGY: int):
    update_url = f"{domoticz_base_url}/json.htm?type=command&param=udevice&idx={IDX}&nvalue=0&svalue={POWER};{ENERGY}"
    try:
        response = requests.get(update_url)
        response.raise_for_status()  # Lève une exception pour les codes d'état HTTP 4xx/5xx
        return response
    except requests.exceptions.HTTPError as http_err:
        logger.error(f'HTTP error occurred: {http_err}')  # Erreur HTTP (4xx ou 5xx)
        return False
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f'Connection error occurred: {conn_err}')  # Erreur de connexion
        return False
    except requests.exceptions.Timeout as timeout_err:
        logger.error(f'Timeout error occurred: {timeout_err}')  # Erreur de délai d'attente
        return False
    except requests.exceptions.RequestException as req_err:
        logger.error(f'An error occurred: {req_err}')  # Erreur générique pour toutes les autres exceptions
        return False

# used for total production of openDTU
def update_domoticz_P1_meter(IDX: str, PROD: int, RETURN1: int):
    update_url = f"{domoticz_base_url}/json.htm?type=command&param=udevice&idx={IDX}&nvalue=0&svalue=0;0;{RETURN1};0;0;{PROD}"
    try:
        response = requests.get(update_url)
        response.raise_for_status()  # Lève une exception pour les codes d'état HTTP 4xx/5xx
        return response
    except requests.exceptions.HTTPError as http_err:
        logger.error(f'HTTP error occurred: {http_err}')  # Erreur HTTP (4xx ou 5xx)
        return False
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f'Connection error occurred: {conn_err}')  # Erreur de connexion
        return False
    except requests.exceptions.Timeout as timeout_err:
        logger.error(f'Timeout error occurred: {timeout_err}')  # Erreur de délai d'attente
        return False
    except requests.exceptions.RequestException as req_err:
        logger.error(f'An error occurred: {req_err}')  # Erreur générique pour toutes les autres exceptions
        return False

def send_message_by_telegram(MESSAGE: str, TOKEN, CHATID):
    import requests
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHATID}&text={MESSAGE}&parse_mode=HTML"
    try:
        print(requests.get(url).json()) # this sends the message
        return True
    except Exception as e:
        logger.error(e)
        return False

# Fonction pour générer le résumé des échecs
def generate_failure_summary(serial_to_datas):
    summary_lines = []
    for serial, info in serial_to_datas.items():
        name = info['name']
        failures = info['failures']
        summary_lines.append(f"<b>{name}</b>  ({serial})  :\n{failures} échecs de communication")
    return "\n".join(summary_lines)

while True:
    try:
        global_tic = time.perf_counter()
        tic = time.perf_counter()
        # Query Global Live Datas
        live_data = get_live_data()
        if live_data is not None:
            # Update Global Solar Datas
            current_power     = (round(float(live_data.get('total')['Power'].get('v')), 1))
            yield_day         = int(live_data.get('total')['YieldDay'].get('v'))
            yield_total       = int((live_data.get('total')['YieldTotal'].get('v'))*1000)
            solar_response    = update_domoticz_solar(idx_global, current_power, yield_day)
            p1_meter_response = update_domoticz_P1_meter(idx_global_P1, current_power, yield_total)
            
            if not solar_response:
                logger.warning(f"Update of {name_global} Failed. Response is None")
            elif solar_response.status_code != 200:
                logger.error(f"1.1 - KO : HTTP : {solar_response.status_code}")
            else:
                logger.info(f"1.1 - OK : HTTP {solar_response.status_code}")
            
            if not p1_meter_response:
                logger.warning(f"Update of {name_global_P1} Failed. Response is None.")
            elif p1_meter_response.status_code != 200:
                logger.error(f"1.2 - KO : HTTP : {p1_meter_response.status_code}")
            else:
                logger.info(f"1.2 - OK : HTTP {p1_meter_response.status_code}")
        else:
            logger.warning('No live_data received')
        toc = time.perf_counter()
        logger.info(f"1 - Duration : {toc - tic:0.4f} seconds.\n")
        # Update Individual Solar Panel Datas
        tic = time.perf_counter()
        # Get the list off all inverters serial numbers
        for serial, data in serial_to_datas.items():
            idx  = data['idx']
            name = data['name']
            # For each serial number, query to openDTU
            inverter_live_data = get_inverter_live_data(serial)
            if inverter_live_data is not None:
                if inverter_live_data and 'inverters' in inverter_live_data:
                    inverter_data = inverter_live_data['inverters'][0]
                    # Check if the inverter is producing energy
                    if inverter_data['producing']:
                        # Check if it was NOT producing during previous run :
                        if not solar_production[serial]:
                            # If it was not, then this a production start from the morning
                            solar_production[serial] = True
                            send_message_by_telegram(f"Starting Solar Production for {name}", TG_TOKEN, TG_CHATID)
                        power = round(float(inverter_data['INV']['0']['Power DC']['v']), 1)
                        energy = int(inverter_data['INV']['0']['YieldDay']['v'])
                        logger.debug(f'Inverter {name} is producing energy, sending values to Domoticz')
                        response = update_domoticz_solar(idx, power, energy)
                        logger.info(f"Inverter {name} ({serial}) : HTTP {response.status_code}\n")
                    else:
                        # Check if it was producing during previous run :
                        if solar_production[serial]:
                            # If it was, then this is production end from the evening
                            solar_production[serial] = False
                            send_message_by_telegram(f"Ending Solar Production for {name}", TG_TOKEN, TG_CHATID)
                        logger.warning(f'Inverter {name} is NOT producing energy')
                        # Send Zero Values
                        response = update_domoticz_solar(idx, 0, 0)
                else:
                    logger.warning('No inverters in live_data')
            else:
                logger.warning(f'No data received for inverter {name} ({serial})')
                data['failures'] += 1
                logger.warning(f'Incrementing Failure Count for {name}')
                save_serial_data(json_path, config_data)
        toc = time.perf_counter()
        logger.info(f"2 - Duration : {toc - tic:0.4f} seconds.\n")

        # Check if ALL inverters have stopped or started producing
        all_inverters_stopped = all(not value for value in solar_production.values())
        all_inverters_started = all(value for value in solar_production.values())
        if all_inverters_stopped and not notif_all_stopped:
            logger.info('All Inverters are NOT producing now')
            send_message_by_telegram("🌜 All inverters Stopped!", TG_TOKEN, TG_CHATID)
            notif_all_stopped = True
            notif_all_started = False
        elif all_inverters_started and not notif_all_started:
            logger.info('All Inverters are producing now')
            send_message_by_telegram("🔆 All inverters Started!", TG_TOKEN, TG_CHATID)
            notif_all_started = True
            notif_all_stopped = False
            daily_report_sent = False
            # Optionally, reset the failure counts for today (clear night events)
            logger.info('Reset Failure counter for each inverter')
            for serial in serial_to_datas:
                serial_to_datas[serial]['failures'] = 0
            save_serial_data(json_path, config_data)

        # Send Daily Report
        if not daily_report_sent and notif_all_stopped:
            logger.info('Time to send Daily Production Message')
            yield_day = (float(live_data.get('total')['YieldDay'].get('v')))
            energy_in_kwh = yield_day / 1000
            message = (f"🌞 Production Solaire du Jour : {energy_in_kwh} kWh")
            send_message_by_telegram(message, TG_TOKEN, TG_CHATID)
            daily_report_sent = True
            ## Get all failures
            failure_summary = generate_failure_summary(serial_to_datas)
            logger.info("Summary of failures for today:")
            logger.info(failure_summary)
            logger.info("Sending Failures for today with Telegram...")
            send_message_by_telegram(failure_summary, TG_TOKEN, TG_CHATID)
            # Optionally, reset the failure counts for the next day
            logger.info('Reset Failure counter for each inverter')
            for serial in serial_to_datas:
                serial_to_datas[serial]['failures'] = 0
            save_serial_data(json_path, config_data)

        global_toc = time.perf_counter()
        logger.info(f"== Total Duration : {global_toc - global_tic:0.4f} seconds.\n")
        logger.debug(f"Sleep for {sleep_duration} seconds...")
        time.sleep(sleep_duration)
    except Exception as e:
        logger.critical(e)
