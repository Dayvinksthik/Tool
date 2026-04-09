#!/bin/bash
# =============================================================
#  Roblox Auto Rejoin
# =============================================================

echo ""
echo "======================================================"
echo "  Roblox Auto Rejoin — UGPhone / Redfinger Setup"
echo "======================================================"
echo ""

# ── 1. Root check ─────────────────────────────────────────────
if ! su -c "echo test" 2>/dev/null | grep -q "test"; then
  echo "[ERROR] Root access required. Grant Termux superuser in Magisk."
  exit 1
fi
echo "[OK] Root access confirmed"

# ── 2. Storage ────────────────────────────────────────────────
echo "[..] Setting up storage…"
termux-setup-storage
sleep 2
echo "[OK] Storage ready"

# ── 3. Update & install essentials ────────────────────────────
echo "[..] Updating Termux…"
export DEBIAN_FRONTEND=noninteractive
pkg update -y
pkg upgrade -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold

echo "[..] Installing required packages…"
pkg install -y python
pkg install -y python-pip curl tsu android-tools

# Fix curl if broken
if ! curl --version >/dev/null 2>&1; then
  pkg reinstall -y curl openssl >/dev/null 2>&1
fi

echo "[OK] Packages installed"

# ── 4. Python dependencies ────────────────────────────────────
echo "[..] Installing Python packages…"
python -m pip install --upgrade pip
python -m pip install requests pyprotectorx

echo "[OK] Python packages installed"

# ── 5. Download the fixed Rejoiner.py ─────────────────────────
DEST="/sdcard/Download/Rejoiner.py"
URL="https://raw.githubusercontent.com/Dayvinksthik/Tool/refs/heads/main/Rejoiner.py"

echo "[..] Downloading Rejoiner.py (Cloud-optimized version)…"
curl -fL --retry 3 --retry-delay 2 "$URL" -o "$DEST" || {
  echo "[ERROR] Download failed. Check your internet."
  exit 1
}

su -c "chmod 644 $DEST"
echo "[OK] Rejoiner.py saved to /sdcard/Download/"

# ── 6. Create easy launcher ───────────────────────────────────
LAUNCHER="$PREFIX/bin/rejoiner"

cat > "$LAUNCHER" <<'EOF'
#!/bin/bash
echo "Starting KOALA Roblox Auto Rejoin (Cloud Mode)..."
cd /sdcard/Download
termux-wake-lock
python -u Rejoiner.py "$@"
EOF

chmod +x "$LAUNCHER"
echo "[OK] Launcher created. You can now type: rejoiner"

# ── 7. Final message ──────────────────────────────────────────
echo ""
echo "======================================================"
echo "  ✅ SETUP COMPLETE!"
echo ""
echo "  After running 'rejoiner', choose option 2 to start automation."
echo "======================================================"
echo ""