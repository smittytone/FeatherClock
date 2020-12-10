#!/usr/bin/env bash
# NOTE You may need to change the above line to /bin/bash

# Install the clock code with the requested WiFi credentials
#
# Version 1.1.1

# Set the Feather's device record using the argument
dev=$1

if [[ -z "$dev" ]]; then
    # No arg passed, so try the 'device' file
    if [[ -e device ]]; then
        dev=$(cat device)
    fi

    if [[ -z "$dev" ]]; then
        echo "Error -- Device path not specified as an argument or in the file \"device\""
        exit 1
    fi
fi

# Check that ampy is installed
command -v ampy >/dev/null || { echo "Error -- ampy not installed (see https://github.com/scientifichackers/ampy)"; exit 1; }

# Make sure the Feather is connected befo re proceeding
if [[ ! -e "$dev" ]]; then
    echo "Error -- Feather is not connected to USB"
    exit 1
fi

# FROM 1.0.10 -- Allow user to choose device type
read -n 1 -s -p "Press [3] to install on an ESP32, or any other key for ESP8266 " keypress
echo

chip="-esp8266"
if [[ $keypress == "3" ]]; then
    chip="-esp32"
fi

# FROM 1.1.0 -- Allow user to choose display type
read -n 1 -s -p "Press [M] to use a matrix LED, or any other key for a segment LED" keypress
echo

type="-segment"
keypress=${keypress^^}
if [[ $keypress == "M" ]]; then
    type="-matrix"
fi

read -p "Enter your WiFi SSID: " ssid
read -p "Enter your WiFi password: " pass

echo -e "\nAdding WiFi credentials to code..."
sed "s|\"@SSID\"|\"$ssid\"|; \
     s|\"@PASS\"|\"$pass\"|" \
     "$HOME/GitHub/featherclock/clock${type}${chip}.py" > "$HOME/main.py"

echo "Copying \"clock${type}${chip}.py\" to device \"$dev\"..."
ampy --port $dev put "$HOME/main.py"

echo "Code copied. Press RESET on the Feather, or power cycle, to run the code."

# Remove artifact
rm "$HOME/main.py"
