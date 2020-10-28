#!/usr/bin/env bash
# NOTE You may need to change the above line to /bin/bash

# Install the clock code with the requested WiFi credentials
#
# Version 1.0.10

# Set the Feather's device record
dev=""

if [[ -e device ]]; then
    dev=$(cat device)
fi

dev=$1

if [[ -z "$dev" ]]; then
    echo "Device path not specified as an argument or in the file \'device\'"
    exit 1
fi

# Check that ampy is installed
command -v ampy >/dev/null || { echo "ampy not installed (see https://github.com/scientifichackers/ampy) -- quitting"; exit 1; }

# Make sure the Feather is connected befo re proceeding
if [[ ! -e "$dev" ]]; then
    echo "Feather is not connected to USB -- quitting"
    exit 1
fi

# Ask the use what they want to do
read -n 1 -s -p "Press [ENTER] to install a µPython app on your Feather, or [Q] to quit " keypress
echo

if [[ $keypress == "q" || $keypress == "@" ]]; then
    exit 0
fi

# FROM 1.0.10 -- Allow user to choose device type
# Ask the use what they want to do
read -n 1 -s -p "Press [3] to install on an ESP32, or any other key for ESP8266 " keypress
echo

chip="-esp8266"
if [[ $keypress == "3" ]]; then
    chip="-esp32"
fi

read -p "Enter your WiFi SSID: " ssid
read -s -p "Enter your WiFi password: " pass

echo -e "\nAdding WiFi credentials to code..."
sed "s|\"@SSID\"|\"$ssid\"|; \
     s|\"@PASS\"|\"$pass\"|" \
     "$HOME/GitHub/featherclock/clock$chip.py" > "$HOME/main.py"

echo "Copying code to device..."
ampy --port $dev put "$HOME/main.py"

echo "Code copied. Press RESET on the Feather, or power cycle, to run the code."

# Remove artifact
rm "$HOME/main.py"
