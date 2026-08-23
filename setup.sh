#!/data/data/com.termux/files/usr/bin/bash

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Nexora | Rooted Setup"
echo "  discord.gg/dCMVzpBuTm"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "[1/8] Updating Termux packages..."
pkg update -y && pkg upgrade -y

echo "[2/8] Changing repositories..."
termux-change-repo

echo "[3/8] Installing Python and pip..."
pkg install python python-pip -y

if ! command -v python &> /dev/null; then
    echo "Error: Python not installed. Retrying..."
    pkg install python -y
fi

echo "[4/8] Installing Termux tools..."
pkg install termux-tools git openssh procps screen tsu -y

echo "[5/8] Installing Python libraries..."
pip install colorama pystyle requests

echo "[6/8] Setting up storage permissions..."
termux-setup-storage

echo "[7/8] Creating Delta directories (requires root)..."
su -c "mkdir -p /storage/emulated/0/Delta/Autoexecute"
su -c "mkdir -p /storage/emulated/0/Delta/Workspace"
su -c "chmod -R 777 /storage/emulated/0/Delta"

echo "[8/8] Creating clone client directories..."
CLIENTS="clienb clienc cliend cliene clienf clieng clienh clieni clienj clienk clienl clienm clienn clieno clienu clienv clienw clienx clieny clienz clienp clienq clienr cliens"
for CLIENT in $CLIENTS; do
    su -c "mkdir -p /storage/emulated/0/Android/data/com.roblox.${CLIENT}/files/delta/autoexec"
    su -c "mkdir -p /storage/emulated/0/Android/data/com.roblox.${CLIENT}/files/delta/workspace"
    su -c "chmod -R 777 /storage/emulated/0/Android/data/com.roblox.${CLIENT}/files/delta" 2>/dev/null
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Setup complete!"
echo "  Run: python Rejoin.py"
echo "  Nexora | discord.gg/dCMVzpBuTm"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
