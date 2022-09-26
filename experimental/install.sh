#!/usr/bin/env bash
# NOTE You may need to change the above line to /bin/bash

# Install the clock code and update the preferences to
# deliver the current time to the clock's RTC.
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
        echo "Usage:"
        echo "  ./install.sh /path/to/device"
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

# Make sure the Feather is connected befo re proceeding
if [[ ! -e "$dev" ]]; then
    echo "[ERROR] Device is not connected to USB"
    exit 1
fi

chip="trinkey-rp2040"
dtype="segment"
echo "Copying \"clock-${dtype}-${chip}.py\" to device \"$dev\"..."

# Copy prefs.json if present if the current dir
if [[ -e prefs.json ]]; then
    epoch=$(date +%s)
    sed "s|@EPOCH|${epoch}|" prefs.json > uprefs.json
    pyboard -d $dev -f cp uprefs.json :prefs.json
    rm uprefs.json
fi

# Copy log file then zap the device's one
if pyboard -d $dev -f cp :log.txt log.txt > /dev/null; then
    pyboard -d $dev -f rm :log.txt
else
    echo "Could not copy log.txt from the device"
fi

# Copy the 'compiled' code
pyboard -d $dev -f cp "clock-${dtype}-${chip}.py" :main.py

echo "Code copied. Press RESET or power cycle, to run the code."
