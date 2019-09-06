#!/usr/local/bin/bash
# NOTE You may need to change the above line to /bin/bash

# Install the clock code with the requested WiFi credentials
#
# Version 1.0.0

dev=/dev/cu.SLAB_USBtoUART

if ! [ -e "$dev" ]; then
    echo "Feather is not connected -- quitting"
    exit 1
fi

read -n 1 -s -p "Press [ENTER] to install code, or [Q] to quit" keypress
echo

if [[ $keypress == "q" || $keypress == "@" ]]; then
    exit 0
fi

read -p "Enter your WiFi SSID: " ssid
read -s -p "Enter your WiFi password: " pass

echo "Adding WiFi credentials to code..."
sed "s|@AGENT|https://agent.electricimp.com/TbVXb2WIEZMy|; \
    s|@SSID|$ssid|; \
    s|@PASS|$pass|" \
    "$HOME/documents/github/featherclock/clock.py" > "$HOME/desktop/main.py"

echo "Copying code to device..."
ampy --port $dev put "$HOME/desktop/main.py"

echo "Code copied. Press RESET on the Feather, or power cycle, to run the code."