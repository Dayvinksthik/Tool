#!/bin/bash
if [ -e "/data/data/com.termux/files/home/storage" ]; then
    rm -rf /data/data/com.termux/files/home/storage
fi
termux-setup-storage
yes | pkg update
. <(curl https://raw.githubusercontent.com/vthangsinkyi/setup-termux/refs/heads/main/termux-change-repo.sh)
yes | pkg upgrade
yes | pkg i python
yes | pkg i python-pip
pip install requests pytz pyjwt pycryptodome rich colorama flask psutil discord python-socketio
curl -Ls "https://raw.githubusercontent.com/vthangsinkyi/setup-termux/main/Rejoiner.py" -o /sdcard/Download/Rejoiner.py