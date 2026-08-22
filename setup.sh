echo "Updating and upgrading Termux..."
pkg update -y && pkg upgrade -y

echo "Changing repositories..."
termux-change-repo

echo "Installing Python and pip..."
pkg install python python-pip -y

if ! command -v python &> /dev/null
then
    echo "Error: Python is not installed. Retrying..."
    pkg install python -y
fi

echo "Installing other necessary packages..."
pkg install which tsu proot termux-tools git openssh procps tor -y

echo "Installing Python libraries..."
pip install colorama pystyle requests

echo "Setting up necessary access permissions..."
termux-setup-storage

echo "Installing screen..."
pkg install screen -y

echo "Creating autoexec directories if they don't exist..."
mkdir -p /storage/emulated/0/Delta/Autoexecute/
mkdir -p /storage/emulated/0/Delta/Workspace
mkdir -p /storage/emulated/0/RobloxClone001/Codex/Autoexec/

echo "Installation complete! -- Nexora Collective | https://discord.gg/dCMVzpBuTm"
