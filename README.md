# Solar Production Monitoring Script
# From OpenDTU - NO MQTT
# (v2 is also available, with JSON file for settings)

This repository contains a Python script designed to monitor solar production data from an OpenDTU device and update a Domoticz server with the collected data. Additionally, the script sends daily production reports via Telegram, after all inverters are not producing (at the end of the day).

## Prerequisites

Before running the script, ensure you have the following:

- Python 3.x installed
- A DomoticZ instance running
- Some dummy devices `Electric (Instant + Counter)`, set in Return, and Computed (see picture below)
![image](https://github.com/lemassykoi/domoticz-openDTU/assets/16377344/64968239-1e42-4799-89a4-fc16ead7862e)
- Required Python packages (`requests`, `logging`)

## Setup

1. Clone this repository:
    ```sh
    git clone https://github.com/lemassykoi/domoticz-openDTU.git
    cd domoticz-openDTU
    ```

2. Install the required Python packages:
    ```sh
    pip install requests
    ```

3. Update the script with your device IP addresses and other configuration details:
    - Replace `dtu_base_url` with the IP address of your OpenDTU device.
    - Replace `domoticz_base_url` with the IP address of your Domoticz device.
    - Set the `TG_TOKEN` and `TG_CHATID` with your Telegram bot token and chat ID respectively.

## Script Overview

The script performs the following functions:

- Fetches system info and live data from the OpenDTU device.
- Updates the Domoticz server with the collected solar power data.
- Sends a start and end message for solar production via Telegram.
- Sends a daily production report via Telegram at the specified time.

### Key Variables

- `dtu_base_url`: Base URL for the OpenDTU device.
- `domoticz_base_url`: Base URL for the Domoticz server.
- `sleep_duration`: Time between each data update.
- `idx_global`: Domoticz IDX for global solar data.
- `TG_TOKEN`, `TG_CHATID`: Telegram bot token and chat ID for sending messages.
- `serial_to_idx`: Mapping between inverter serial numbers and their corresponding Domoticz IDX values.

### Main Functions

- `get_system_info()`: Fetches system info from OpenDTU.
- `get_live_data()`: Fetches global live data from OpenDTU.
- `get_inverter_live_data(inverter)`: Fetches detailed live data for a specific inverter.
- `update_domoticz_solar(IDX, POWER, ENERGY)`: Updates Domoticz with the solar data.
- `send_message_by_telegram(MESSAGE, TOKEN, CHATID)`: Sends a message via Telegram.

### Usage

To run the script, simply execute:

```sh
python domoticz-openDTU.py
```

### Logging

The script uses Python's logging module to log messages with the following format:

```
%(asctime)s - %(name)s - %(levelname)s - %(message)s \t (%(filename)s:%(lineno)d)
```

Logging levels can be adjusted as needed by modifying the `logging.basicConfig` call.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

Feel free to open an issue if you encounter any problems or have questions. Contributions are welcome!
