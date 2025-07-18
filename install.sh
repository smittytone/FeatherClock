#!/usr/bin/env bash
# NOTE You may need to change the above line to /bin/bash

# Install the clock code with the requested WiFi credentials
#
# Version 1.4.0

# Set the Feather's device record using the argument
dev=$1
platform=$(uname)

if [[ -z "${dev}" ]]; then
    # No arg passed, so try the 'device' file
    if [[ -e device ]]; then
        dev=$(cat device)
    fi

    if [[ -z "${dev}" ]]; then
        echo "Usage: ./install.sh /path/to/device"
        echo "Important: run this script from the featherclock directory"
        echo "Optional: place /path/to/device in the file 'device' in this directory"
        exit 1
    fi
fi

# Check that pyboard is installed
if ! which pyboard.py > /dev/null; then
    if ! which pyboard > /dev/null; then
        echo "[ERROR] pyboard.py not installed (see https://docs.micropython.org/en/latest/reference/pyboard.py.html)"
        exit 1
    fi
fi

# Make sure the Feather is connected before proceeding
[ ! -e "${dev}" ] && { echo "[ERROR] No Feather or Pico W is connected via USB" ; exit 1; }

# FROM 1.0.10 -- Allow user to choose device type
# FROM 1.4.0  -- Change keys
read -n 1 -s -p "Press [E] to install on an ESP32, or [P] to install on a Pico W " key
echo

chip="NONE"
device="NONE"

key=${key^^}
[ ${key} == "E" ] && chip="esp32"
[ ${key} == "P" ] && chip="pico_w" && device="segment"
[ ${chip} != "NONE" ] || exit 1

# Select display type for ESP32 builds
if [[ ${chip} != "pico_w" ]]; then
    read -n 1 -s -p "Press [M] to use a matrix LED, or [S] for a segment LED " key
    echo

    key=${key^^}
    [ ${key} == "M" ] && device="matrix"
    [ ${key} == "S" ] && device="segment"
    [ ${device} != "NONE" ] || exit 1
fi

# Get WiFi details
read -p "Enter your WiFi SSID: " ssid
read -p "Enter your WiFi password: " pass

# Build the code
# NOTE Change path in third SED line if you store this repo in a different location
echo -e "\nAdding WiFi credentials to code..."
sed "s|\"@SSID\"|\"${ssid}\"|; \
     s|\"@PASS\"|\"${pass}\"|" \
    "${PWD}/clock_${device}_${chip}.py" > "main.py"

# Code transfer
echo "Copying application and data files to device \"${dev}\"..."

# Copy prefs.json if present if the current dir
[ -e prefs.json ] && pyboard -d ${dev} -f cp prefs.json :prefs.json

# Copy log file then zap the device's one
if pyboard -d ${dev} -f cp :log.txt log.txt > /dev/null; then
    pyboard -d ${dev} -f rm :log.txt
else
    echo "Could not copy log.txt from the device"
fi

# Copy the 'compiled' code
pyboard -d ${dev} -f cp main.py :main.py

echo "Code copied. Press RESET on the Feather, or power cycle, to run the code."

# Remove artifact
rm "main.py"
