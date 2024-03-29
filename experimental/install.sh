#!/usr/bin/env bash
# NOTE You may need to change the above line to /bin/bash

# Install the clock code and update the preferences to
# deliver the current time to the clock's RTC.
#
# Version 1.3.1c

# Set the Feather's display type using the argument
display_type=$1

# Set the target volume
platform=$(uname)
if [[ ${platform} == Darwin ]]; then
    device=/Volumes/CIRCUITPY
else
    device="/media/$USER/CIRCUITPY"
fi

quirk=" "
if [[ ${platform} == Darwin ]]; then
    quirk="-X"
fi

if [[ -z "${display_type}" ]]; then
    echo 'Usage: ./install.sh {display type}'
    echo 'The supported display types are `segment` or `oled`.'
    exit 1
fi

if [[ ! ${display_type} == "segment" && ! ${display_type} == "segment" ]]; then
    echo "[ERROR] Unsupported display type: ${display_type}"
    exit 1
fi

# Make sure the Feather is connected befo re proceeding
if [[ ! -d "${device}" ]]; then
    echo "[ERROR] Device is not connected to USB"
    exit 1
fi

chip="trinkey-rp2040"
echo "Copying \"clock-${display_type}-${chip}.py\" to device \"${device}\"..."

# Copy prefs.json if present if the current dir
if [[ -e prefs.json ]]; then
    epoch=$(date +%s)
    sed "s|@EPOCH|${epoch}|" prefs.json > uprefs.json
    cp ${quirk} uprefs.json "${device}/prefs.json"
    rm uprefs.json
fi

# Copy log file then zap the device's one
cp ${quirk} "${device}/log.txt" log.txt 2>/dev/null || echo "Could not copy log.txt from the device"
[[ -e "${device}/log.txt" ]] && rm -f "${device}/log.txt"

# Copy the 'compiled' code
cp ${quirk} "clock-${display_type}-${chip}.py" "${device}/code.py"
cp ${quirk} boot.py "${device}/boot.py"

echo "Code copied. Press RESET or power cycle, to run the code."
