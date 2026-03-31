#!/bin/bash
# =============================================================
#  Roblox Auto Rejoin - Termux Setup Script
#  Run once on a fresh Termux install (rooted Android required)
# =============================================================

set -e

echo ""
echo "======================================================"
echo "  Roblox Auto Rejoin Tool - Termux Setup"
echo "======================================================"
echo ""

# ── 1. Root check ─────────────────────────────────────────────
if ! su -c "echo test" 2>/dev/null | grep -q "test"; then
  echo "[ERROR] Root access is required."
  echo "        Install Magisk and grant Termux superuser permissions."
  exit 1
fi
echo "[OK] Root access confirmed"

# ── 2. Memory check ───────────────────────────────────────────
MEMORY=$(free -m 2>/dev/null | awk '/Mem:/{print $2}' || echo 0)
if [ "$MEMORY" -gt 0 ] && [ "$MEMORY" -lt 512 ]; then
  echo "[WARN] Only ${MEMORY}MB RAM detected. Recommend at least 512 MB."
fi

# ── 3. Storage setup ──────────────────────────────────────────
echo "[..] Setting up storage access…"
[ -L "/data/data/com.termux/files/home/storage" ] && \
  rm -f /data/data/com.termux/files/home/storage
termux-setup-storage
sleep 2
echo "[OK] Storage configured"

# ── 4. Mirror ─────────────────────────────────────
echo "[..] Selecting fastest mirror…"
if command -v termux-change-repo &>/dev/null; then
  termux-change-repo --select-mirror Grimler
else
  MIRROR_DIR="/data/data/com.termux/files/usr/etc/termux"
  mkdir -p "$MIRROR_DIR"
  echo "deb https://packages.termux.dev/apt/termux-main stable main" \
    > "$MIRROR_DIR/sources.list"
fi
echo "[OK] Mirror set"

# ── 5. Package update ─────────────────────────────────────────
echo "[..] Updating package lists…"
yes | pkg update -y 2>/dev/null || true
yes | pkg upgrade -y 2>/dev/null || true
echo "[OK] Packages updated"

# ── 6. Dependencies ───────────────────────────────────────────
echo "[..] Installing system packages…"
yes | pkg install -y python python-pip curl tsu android-tools 2>/dev/null
echo "[OK] System packages installed"

# ── 7. Python dependencies ────────────────────────────────────
echo "[..] Installing Python packages…"
pip install --quiet --upgrade pip
pip install --quiet requests psutil
echo "[OK] Python packages installed"

# ── 8. Download Rejoiner.py to /sdcard/Download ───────────────
DEST="/sdcard/Download/Rejoiner.py"
echo "[..] Downloading Rejoiner.py…"
curl -Ls "https://raw.githubusercontent.com/vthangsinkyi/setup-termux/refs/heads/main/Rejoiner.py" \
  -o "$DEST"
su -c "chmod 644 $DEST"
echo "[OK] Rejoiner.py saved to $DEST"

# ── 9. Global launcher ────────────────────────────────────────
LAUNCHER="/data/data/com.termux/files/usr/bin/rejoiner"
cat > "$LAUNCHER" <<'EOF'
#!/bin/bash
cd /sdcard/Download
python Rejoiner.py "$@"
EOF
chmod +x "$LAUNCHER"
echo "[OK] Launcher created: type 'rejoiner' to start"

# ── 10. Roblox check ──────────────────────────────────────────
if ! su -c "pm list packages com.roblox.client" 2>/dev/null | grep -q "com.roblox.client"; then
  echo ""
  echo "[WARN] Roblox (com.roblox.client) not found on this device."
  echo "       Install Roblox before running the tool."
fi

echo ""
echo "======================================================"
echo "  Setup complete!"
echo ""
echo "  To launch the tool:"
echo "    rejoiner"
echo "  Or directly:"
echo "    python /sdcard/Download/Rejoiner.py"
echo "======================================================"
echo ""
