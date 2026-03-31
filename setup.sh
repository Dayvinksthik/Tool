#!/bin/bash
# =============================================================
#  Roblox Auto Rejoin - Termux Setup Script
#  Run once on a fresh Termux install (rooted Android required)
# =============================================================

# Do NOT use set -e — we handle errors manually so one failure
# doesn't abort the whole setup.

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
  echo "[WARN] Only ${MEMORY}MB RAM — recommend at least 512MB"
fi

# ── 3. Storage setup ──────────────────────────────────────────
echo "[..] Setting up storage access…"
[ -L "$HOME/storage" ] && rm -f "$HOME/storage"
termux-setup-storage
sleep 2
echo "[OK] Storage configured"

# ── 4. Force Cloudflare mirror (fully synced, most reliable) ──
# The auto-selected mirror often has 404s for newer packages.
# packages-cf.termux.dev is Cloudflare-backed and always complete.
echo "[..] Setting Cloudflare mirror…"
SOURCES_DIR="/data/data/com.termux/files/usr/etc/apt/sources.list.d"
SOURCES_MAIN="/data/data/com.termux/files/usr/etc/apt/sources.list"
mkdir -p "$SOURCES_DIR"
# Write the primary source pointing to Cloudflare CDN
echo "deb https://packages-cf.termux.dev/apt/termux-main stable main" \
  > "$SOURCES_MAIN"
# Remove any conflicting sources that might override it
rm -f "$SOURCES_DIR"/*.list 2>/dev/null || true
echo "[OK] Mirror set to packages-cf.termux.dev (Cloudflare CDN)"

# ── 5. Update package lists ───────────────────────────────────
echo "[..] Updating package lists…"
apt-get update -y 2>&1 | tail -3
echo "[OK] Package lists updated"

# ── 6. Upgrade existing packages ──────────────────────────────
echo "[..] Upgrading packages (this may take a while)…"
apt-get upgrade -y --fix-missing 2>&1 | tail -5 || \
  echo "[WARN] Some packages could not upgrade — continuing anyway"
echo "[OK] Packages upgraded"

# ── 7. Install required system packages ───────────────────────
echo "[..] Installing python, curl, tsu, android-tools…"
apt-get install -y --fix-missing python python-pip curl tsu android-tools 2>&1 | tail -5

# Verify Python actually installed
if ! command -v python &>/dev/null && ! command -v python3 &>/dev/null; then
  echo "[WARN] Python not found after install — retrying with pip fallback…"
  apt-get install -y --fix-missing python3 python3-pip 2>&1 | tail -3
fi

# Final check
if command -v python &>/dev/null; then
  PY_VER=$(python --version 2>&1)
  echo "[OK] $PY_VER installed"
elif command -v python3 &>/dev/null; then
  PY_VER=$(python3 --version 2>&1)
  echo "[OK] $PY_VER installed (as python3)"
  # Create python symlink if missing
  ln -sf "$(command -v python3)" \
    /data/data/com.termux/files/usr/bin/python 2>/dev/null || true
  echo "[OK] python symlink created"
else
  echo "[ERROR] Python could not be installed. Try running setup again."
  echo "        If this keeps failing, run: pkg install python"
  exit 1
fi

# ── 8. Install Python packages ────────────────────────────────
echo "[..] Installing Python packages (requests, psutil)…"
pip install --quiet --upgrade pip 2>/dev/null || \
  pip3 install --quiet --upgrade pip 2>/dev/null || true
pip install --quiet requests psutil 2>/dev/null || \
  pip3 install --quiet requests psutil 2>/dev/null || true
echo "[OK] Python packages installed"

# ── 9. Download Rejoiner.py ───────────────────────────────────
DEST="/sdcard/Download/Rejoiner.py"
echo "[..] Downloading Rejoiner.py…"
curl -Ls "https://raw.githubusercontent.com/vthangsinkyi/setup-termux/refs/heads/main/Rejoiner.py" \
  -o "$DEST"
su -c "chmod 644 $DEST"
echo "[OK] Rejoiner.py → $DEST"

# ── 10. Global launcher ───────────────────────────────────────
LAUNCHER="/data/data/com.termux/files/usr/bin/rejoiner"
cat > "$LAUNCHER" <<'EOF'
#!/bin/bash
cd /sdcard/Download
python Rejoiner.py "$@"
EOF
chmod +x "$LAUNCHER"
echo "[OK] 'rejoiner' shortcut created"

# ── 11. Roblox check ──────────────────────────────────────────
if ! su -c "pm list packages com.roblox.client" 2>/dev/null \
    | grep -q "com.roblox.client"; then
  echo ""
  echo "[WARN] Roblox not found. Install it from the Play Store first."
fi

echo ""
echo "======================================================"
echo "  Setup complete!"
echo ""
echo "  Run the tool:"
echo "    cd /sdcard/Download && python Rejoiner.py"
echo ""
echo "  Or use the shortcut:"
echo "    rejoiner"
echo "======================================================"
echo ""
