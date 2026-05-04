if ! su -c "echo test" 2>/dev/null | grep -q "test"; then
  echo "[ERROR] Root access required."
  echo "        Grant Termux superuser in Magisk, then retry."
  exit 1
fi
echo "[OK] Root access confirmed"

echo "[..] Setting up storage…"
[ -L "$HOME/storage" ] && rm -f "$HOME/storage"
termux-setup-storage
sleep 2
echo "[OK] Storage ready"

echo "[..] Setting mirror to Cloudflare CDN…"
SOURCES="/data/data/com.termux/files/usr/etc/apt/sources.list"
SOURCES_D="/data/data/com.termux/files/usr/etc/apt/sources.list.d"
mkdir -p "$SOURCES_D"
echo "deb https://packages-cf.termux.dev/apt/termux-main stable main" \
  > "$SOURCES"
rm -f "$SOURCES_D"/*.list 2>/dev/null || true
echo "[OK] Mirror: packages-cf.termux.dev"

echo "[..] Updating package lists…"
apt-get update -y 2>&1 | grep -E "^(Err|Get|Hit|Reading|Done)" || true
echo "[OK] Package lists updated"

echo "[..] Installing Python…"
apt-get install -y --fix-missing python python-pip 2>&1 | tail -3

if ! command -v python &>/dev/null; then
  echo "[..] Trying python3…"
  apt-get install -y --fix-missing python3 python3-pip 2>&1 | tail -3
  if command -v python3 &>/dev/null; then
    ln -sf "$(command -v python3)" \
      /data/data/com.termux/files/usr/bin/python 2>/dev/null || true
  fi
fi

if ! command -v python &>/dev/null; then
  echo "[ERROR] Python could not be installed."
  echo "        Run manually: pkg install python"
  exit 1
fi
echo "[OK] $(python --version 2>&1)"

echo "[..] Ensuring pip is available…"
python -m ensurepip --upgrade 2>/dev/null || true
python -m pip install --quiet --upgrade pip 2>/dev/null || true

echo "[..] Installing requests…"

python -m pip install --quiet requests && REQUESTS_OK=1 || REQUESTS_OK=0

if [ "$REQUESTS_OK" -eq 0 ]; then
  echo "[..] pip failed — trying apt fallback…"
  apt-get install -y python-requests 2>/dev/null && REQUESTS_OK=1 || true
fi

if [ "$REQUESTS_OK" -eq 0 ]; then
  echo "[..] Trying pip directly…"
  pip install requests && REQUESTS_OK=1 || true
fi

if python -c "import requests" 2>/dev/null; then
  echo "[OK] requests installed and importable"
else
  echo "[ERROR] requests could not be installed."
  echo "        Run manually: python -m pip install requests"
  exit 1
fi

echo "[..] Installing tsu, android-tools…"
apt-get install -y --fix-missing tsu android-tools 2>&1 | tail -3
echo "[OK] System tools installed"

echo "[..] Verifying Rejoiner.py can start…"
python -c "
import os, sys, time, json, shutil, threading, subprocess, requests
from datetime import datetime
print('[OK] All imports OK')
"

LAUNCHER="/data/data/com.termux/files/usr/bin/rejoiner"
cat > "$LAUNCHER" <<'EOF'
#!/bin/bash
cd /sdcard/Download
python Rejoiner.py "$@"
EOF
chmod +x "$LAUNCHER"
echo "[OK] Shortcut 'rejoiner' created"

if ! su -c "pm list packages com.roblox.client" 2>/dev/null \
    | grep -q "com.roblox.client"; then
  echo "[WARN] Roblox not found — install Roblox before running"
fi
