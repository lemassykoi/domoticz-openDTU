import requests
import time
import logging
import datetime

# Replace with your OpenDTU device IP address
dtu_base_url      = "http://10.0.10.1"
# Replace with your Domoticz device IP address
domoticz_base_url = "http://10.0.20.1"
# Define the time to run the send_daily_to_telegram function (e.g., 10 PM)
daily_report_scheduled_hour    = 22
daily_report_scheduled_minute  = 0
# Define the loop duration (time between each update)
sleep_duration                 = 3
# Domoticz IDX for Global Sensor (not individual)
idx_global                     = 1125
# Define your Telegram Settings
TG_TOKEN                       = '1234567890:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
TG_CHATID                      = 'xxxxxxxxx'
report_send                    = False
solar_production               = False
log_format                     = "%(asctime)s - %(name)s - %(levelname)s - %(message)s \t (%(filename)s:%(lineno)d)"
# Mapping between inverter serial numbers and their corresponding Domoticz IDX values
serial_to_idx                  = {
    '11259203xxxx': '1126',    # panneau 1
    '11259214xxxx': '1128',    # extension 1
    '11259203xxxx': '1127',    # panneau 2
    '11259203xxxx': '1129'     # extension 2
}

logging.basicConfig(
    format = log_format,
    level  = 'INFO'
)

logging.info('Start...')

def get_system_info():
    """Fetch system info from OpenDTU."""
    url = f"{dtu_base_url}/api/system/status"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        logging.info(f"Error: {response.status_code}")
        return None

def get_live_data():
    """Fetch global live data from OpenDTU."""
    url = f"{dtu_base_url}/api/livedata/status"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        logging.info(f"Error: {response.status_code}")
        return None

def get_inverter_live_data(inverter):
    """Fetch inverter detailed live data from OpenDTU."""
    url = f"{dtu_base_url}/api/livedata/status?inv={inverter}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        logging.info(f"Error: {response.status_code}")
        return None

def update_domoticz_solar(IDX, POWER, ENERGY):
    update_url = f"{domoticz_base_url}/json.htm?type=command&param=udevice&idx={IDX}&nvalue=0&svalue={str(POWER)};{str(ENERGY)}"
    response = requests.get(update_url)
    if response.status_code == 200:
        return response
    else:
      return False

def send_message_by_telegram(MESSAGE, TOKEN, CHATID):
    import requests
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHATID}&text={MESSAGE}"
    try:
        print(requests.get(url).json()) # this sends the message
        return True
    except Exception as e:
        logging.error(e)

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
            if not response:
                logging.error("Error updating Domoticz Global Sensor")
            else:
                toc = time.perf_counter()
                logging.debug(f"1 - Duration : {toc - tic:0.4f} seconds. HTTP : {response.status_code}")
            # Update Individual Solar Panel Datas - start counter
            tic = time.perf_counter()
            # Get the list off all inverters serial numbers
            for serial, idx in serial_to_idx.items():
                # For each serial number, query to openDTU
                live_data = get_inverter_live_data(serial)
                if live_data is not None:
                    if live_data and 'inverters' in live_data:
                        inverter_data = live_data['inverters'][0]
                        # Check if the inverter is producing energy
                        if inverter_data['producing']:
                            # Check if it was producing during previous run :
                            if not solar_production:
                                # If it was not, then this a production start from the morning
                                solar_production = True
                                report_send = False
                                send_message_by_telegram("Starting Solar Production !", TG_TOKEN, TG_CHATID)
                            power = round(float(inverter_data['INV']['0']['Power DC']['v']), 1)
                            energy = int(inverter_data['INV']['0']['YieldDay']['v'])
                            response = update_domoticz_solar(idx, power, energy)
                            logging.debug(f"Inverter {serial} : HTTP {response.status_code}\n")
                        else:
                            # Check if it was producing during previous run :
                            if solar_production:
                                # If it was, then this is production end from the evening
                                solar_production = False
                                send_message_by_telegram("Ending Solar Production !", TG_TOKEN, TG_CHATID)
                            logging.debug(f'Inverter {serial} is NOT producing energy')
                    else:
                        logging.warning('no inverters in live_data')
                else:
                    logging.debug(f'no data received for inverter {serial}')
            toc = time.perf_counter()
            logging.debug(f"2 - Duration : {toc - tic:0.4f} seconds.\n")
            # Check the current time and execute the new function if it's the scheduled time
            current_time = datetime.datetime.now()
            if current_time.hour == daily_report_scheduled_hour and current_time.minute == daily_report_scheduled_minute and not report_send:
                # Get daily produced value in Wh
                logging.info('Time to send Daily Production Message')
                yield_day = (float(live_data.get('total')['YieldDay'].get('v')))
                energy_in_kwh = yield_day / 1000
                message = (f"🌞 Production Solaire du Jour : {energy_in_kwh} kWh")
                if send_message_by_telegram(message, TG_TOKEN, TG_CHATID):
                    report_send = True
        else:
            logging.info('no data received')
        global_toc = time.perf_counter()
        logging.debug(f"== Total Duration : {global_toc - global_tic:0.4f} seconds.\n")
        time.sleep(sleep_duration)
    except Exception as e:
        logging.error("Exiting Try Loop !)
        logging.error(e)
        exit(-1)
