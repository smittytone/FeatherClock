#!/usr/bin/env bash
# NOTE You may need to change the above line to /bin/bash

# Install the clock code with the requested WiFi credentials
#
# Version 1.3.0

# Set the Feather's device record using the argument
dev=$1

if [[ -z "$dev" ]]; then
    # No arg passed, so try the 'device' file
    if [[ -e device ]]; then
        dev=$(cat device)
    fi

    if [[ -z "$dev" ]]; then
        echo "Usage: ./install.sh /path/to/device"
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
if [[ ! -e "$dev" ]]; then
    echo "[ERROR] Feather or Pico W is not connected to USB"
    exit 1
fi

# FROM 1.0.10 -- Allow user to choose device type
read -n 1 -s -p "Press [3] to install on an ESP32, or any other key to install on a Pico W " keypress
echo

chip="pico-w"
if [[ ${keypress} == "3" ]]; then
    chip="esp32"
fi

dtype="segment"
if [[ ${chip} != "pico-w" ]]; then
    read -n 1 -s -p "Press [M] to use a matrix LED, or any other key for a segment LED " keypress
    echo

    keypress=${keypress^^}
    if [[ ${keypress} == "M" ]]; then
        dtype="matrix"
    fi
fi

read -p "Enter your WiFi SSID: " ssid
read -p "Enter your WiFi password: " pass

echo -e "\nAdding WiFi credentials to code..."
sed "s|\"@SSID\"|\"$ssid\"|; \
     s|\"@PASS\"|\"$pass\"|" \
     "$HOME/GitHub/featherclock/clock-${dtype}-${chip}.py" > "main.py"

echo "Copying \"clock-${dtype}-${chip}.py\" to device \"$dev\"..."

# Copy prefs.json if present if the current dir
if [[ -e prefs.json ]]; then
    pyboard -d $dev -f cp prefs.json :prefs.json
fi

# Copy log file then zap the device's one
if pyboard -d $dev -f cp :log.txt log.txt > /dev/null; then
    pyboard -d $dev -f rm :log.txt
else
    echo "Could not copy log.txt from the device"
fi

# Copy the 'compiled' code
pyboard -d $dev -f cp main.py :main.py

echo "Code copied. Press RESET on the Feather, or power cycle, to run the code."

# Remove artifact
rm "main.py"
