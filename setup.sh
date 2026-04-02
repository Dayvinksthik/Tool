#!/bin/bash
# =============================================================
#  Roblox Auto Rejoin — Termux Setup Script
# =============================================================

echo ""
echo "======================================================"
echo "  Roblox Auto Rejoin — Termux Setup"
echo "======================================================"
echo ""

# ── 1. Root check ─────────────────────────────────────────────
if ! su -c "echo test" 2>/dev/null | grep -q "test"; then
  echo "[ERROR] Root access required."
  echo "        Grant Termux superuser in Magisk, then retry."
  exit 1
fi
echo "[OK] Root access confirmed"

# ── 2. Storage ────────────────────────────────────────────────
echo "[..] Setting up storage…"
[ -L "$HOME/storage" ] && rm -f "$HOME/storage"
termux-setup-storage
sleep 2
echo "[OK] Storage ready"

# ── 3. Force Cloudflare mirror ────────────────────────────────
echo "[..] Setting mirror to Cloudflare CDN…"
SOURCES="/data/data/com.termux/files/usr/etc/apt/sources.list"
SOURCES_D="/data/data/com.termux/files/usr/etc/apt/sources.list.d"
mkdir -p "$SOURCES_D"
echo "deb https://packages-cf.termux.dev/apt/termux-main stable main" > "$SOURCES"
rm -f "$SOURCES_D"/*.list 2>/dev/null || true
echo "[OK] Mirror set"

# ── 4. FULL SYSTEM UPDATE ──────────────
echo "[..] Updating system (fix broken packages)…"
pkg update -y && pkg upgrade -y
echo "[OK] System fully updated"

# ── 5. Install Python ─────────────────────────────────────────
echo "[..] Installing Python…"
pkg install -y python python-pip

if ! command -v python &>/dev/null; then
  pkg install -y python3 python3-pip
  ln -sf "$(command -v python3)" $PREFIX/bin/python 2>/dev/null || true
fi

if ! command -v python &>/dev/null; then
  echo "[ERROR] Python install failed"
  exit 1
fi
echo "[OK] $(python --version)"

# ── 6. pip + requests ─────────────────────────────────────────
echo "[..] Installing pip + requests…"
python -m ensurepip --upgrade 2>/dev/null || true
python -m pip install --upgrade pip >/dev/null 2>&1

python -m pip install requests >/dev/null 2>&1 || \
pkg install -y python-requests

python -c "import requests" 2>/dev/null || {
  echo "[ERROR] requests install failed"
  exit 1
}
echo "[OK] requests ready"

# ── 7. Install system tools ───────────────────────────────────
echo "[..] Installing system tools…"
pkg install -y curl tsu android-tools
echo "[OK] Tools installed"

echo "[..] Checking curl health..."

if ! curl --version >/dev/null 2>&1; then
  echo "[WARN] curl broken — repairing..."

  pkg reinstall -y curl openssl >/dev/null 2>&1 || true

  if ! curl --version >/dev/null 2>&1; then
    echo "[WARN] forcing clean reinstall..."
    pkg uninstall -y curl openssl >/dev/null 2>&1 || true
    pkg install -y curl openssl >/dev/null 2>&1 || true
  fi
fi

if ! curl --version >/dev/null 2>&1; then
  echo "[FATAL] curl still broken"
  echo "Run: rm -rf \$PREFIX then reopen Termux"
  exit 1
fi

echo "[OK] curl working"

# ── 9. Download Rejoiner.py ─────────────
DEST="/sdcard/Download/Rejoiner.py"
URL="https://raw.githubusercontent.com/Dayvinksthik/Tool/refs/heads/main/Rejoiner.py"

echo "[..] Downloading Rejoiner.py…"

curl -fL --retry 3 --retry-delay 2 "$URL" -o "$DEST" || {
  echo "[WARN] curl failed — trying wget..."
  pkg install -y wget >/dev/null 2>&1
  wget -O "$DEST" "$URL" || {
    echo "[ERROR] Download failed"
    exit 1
  }
}

su -c "chmod 644 $DEST"
echo "[OK] Saved to $DEST"

# ── 10. Import test ───────────────────────────────────────────
echo "[..] Testing Python imports…"
python - <<EOF
import requests, os, sys, time, subprocess
print("[OK] All imports OK")
EOF

# ── 11. Create launcher ───────────────────────────────────────
LAUNCHER="$PREFIX/bin/rejoiner"

cat > "$LAUNCHER" <<'EOF'
#!/bin/bash
cd /sdcard/Download
python Rejoiner.py "$@"
EOF

chmod +x "$LAUNCHER"
echo "[OK] Command 'rejoiner' created"

# ── 12. Check Roblox ──────────────────────────────────────────
if ! su -c "pm list packages com.roblox.client" | grep -q "com.roblox.client"; then
  echo "[WARN] Roblox not installed"
fi

echo ""
echo "======================================================"
echo "  ✅ Setup COMPLETE"
echo ""
echo "  Run:"
echo "    rejoiner"
echo ""
echo "======================================================"
echo ""