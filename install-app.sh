#!/usr/bin/env bash
# NOTE You may need to change the above line to /bin/bash

# Install the clock code with the requested WiFi credentials
#
# Version 1.0.1

# Set the Feather's device record
dev=/dev/cu.SLAB_USBtoUART

# Check that ampy is installed
command -v ampy >/dev/null || { echo "ampy not installed (go to https://github.com/scientifichackers/ampy) -- quitting"; exit 1; }

# Make sure the Feather is connected before proceeding
if ! [ -e "$dev" ]; then
    echo "Feather is not connected to USB -- quitting"
    exit 1
fi

# Ask the use what they want to do
read -n 1 -s -p "Press [ENTER] to install a Pythomn app, or [Q] to quit" keypress
echo

if [[ $keypress == "q" || $keypress == "@" ]]; then
    exit 0
fi

read -p "Enter your WiFi SSID: " ssid
read -s -p "Enter your WiFi password: " pass

echo "Adding WiFi credentials to code..."
sed "s|@SSID|$ssid|; \
     s|@PASS|$pass|" \
     "$HOME/Documents/GitHub/featherclock/clock.py" > "$HOME/main.py"

echo "Copying code to device..."
ampy --port $dev put "$HOME/main.py"

echo "Code copied. Press RESET on the Feather, or power cycle, to run the code."

# Remove artifact
rm "$HOME/main.py"
