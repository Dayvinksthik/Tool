#!/usr/bin/env python3
"""
Roblox Auto Rejoin Tool — KOALA
"""

import os
import sys
import time
import json
import shutil
import threading
import subprocess
import requests
import re
from datetime import datetime, timedelta

# ── ANSI COLORS ────────────────────────────────────────────────────────────────
R   = "\033[0m"
CY  = "\033[96m"
GR  = "\033[92m"
YL  = "\033[93m"
RD  = "\033[91m"
BL  = "\033[94m"
DIM = "\033[2m"
BO  = "\033[1m"

# ── CONSTANTS ──────────────────────────────────────────────────────────────────
ACCOUNTS_FILE    = "/sdcard/roblox_accounts.json"
DEFAULT_PACKAGE  = "com.roblox.client"
COOLDOWN_SECONDS = 30
WEBHOOK_COOLDOWN = 15
_ram_cache       = (0, 0)

# ── GLOBALS ────────────────────────────────────────────────────────────────────
platform_info          = None
account_threads        = {}
account_running        = {}
account_status         = {}
account_last_focus     = {}
account_focus_count    = {}
account_in_game_since  = {}
roblox_username_cache  = {}
display_running        = False
display_fps            = 0.0
automation_enabled     = False
lock = threading.Lock()
USE_ROOT = False

# ── TIMINGS ────────────────────────────────────────────────────────────────────
DISPLAY_INTERVAL = 60
CHECK_INTERVAL   = 60
_dumpsys_ttl     = 30

# ── SHARED DUMPSYS CACHE ───────────────────────────────────────────────────────
_dumpsys_cache     = ("", 0.0)
_dumpsys_lock      = threading.Lock()


# ══════════════════════════════════════════════════════════════════════════════
#  ASCII ART — KOALA
# ══════════════════════════════════════════════════════════════════════════════
KOALA_ART = [
    "██╗  ██╗ ██████╗  █████╗ ██╗      █████╗ ",
    "██║ ██╔╝██╔═══██╗██╔══██╗██║     ██╔══██╗",
    "█████╔╝ ██║   ██║███████║██║     ███████║",
    "██╔═██╗ ██║   ██║██╔══██║██║     ██╔══██║",
    "██║  ██╗╚██████╔╝██║  ██║███████╗██║  ██║",
    "╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝",
]


# ══════════════════════════════════════════════════════════════════════════════
#  LOADING SCREEN
# ══════════════════════════════════════════════════════════════════════════════
def loading_screen(duration=2.0):
    """Simple loading screen with minimal ANSI."""
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    for line in KOALA_ART:
        print(f"{CY}{BO}{line}{R}")
    print("\n")
    time.sleep(duration)
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


# ══════════════════════════════════════════════════════════════════════════════
#  PLATFORM DETECTION
# ══════════════════════════════════════════════════════════════════════════════
class PlatformDetector:
    def detect_platform(self):
        has_su = False
        try:
            r = subprocess.run(["which", "su"], capture_output=True, timeout=2)
            has_su = r.returncode == 0
        except:
            pass
        
        if not has_su:
            return {"type": "unrooted", "has_root": False}
        
        global USE_ROOT
        try:
            r = subprocess.run(
                ["su", "-c", "echo test"],
                capture_output=True, text=True, timeout=3,
                stdin=subprocess.DEVNULL
            )
            if "test" in r.stdout and r.returncode == 0:
                USE_ROOT = True
                return {"type": "rooted", "has_root": True}
            else:
                USE_ROOT = False
                return {"type": "unrooted", "has_root": False}
        except (subprocess.TimeoutExpired, Exception):
            USE_ROOT = False
            return {"type": "unrooted", "has_root": False}


def run_cmd(command, timeout=10, force_no_root=False):
    """Safe command runner (non-blocking, root-safe)."""
    try:
        if force_no_root or not USE_ROOT:
            r = subprocess.run(
                command, shell=True,
                capture_output=True, text=True,
                timeout=timeout,
                stdin=subprocess.DEVNULL
            )
            return r.stdout.strip()

        r = subprocess.run(
            ["su", "-c", command],
            capture_output=True, text=True,
            timeout=3,
            stdin=subprocess.DEVNULL
        )

        if r.returncode == 0:
            return r.stdout.strip()

        r = subprocess.run(
            command, shell=True,
            capture_output=True, text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL
        )
        return r.stdout.strip()

    except:
        return ""


# ══════════════════════════════════════════════════════════════════════════════
#  QUICK SETUP WIZARD
# ══════════════════════════════════════════════════════════════════════════════
def quick_setup_wizard():
    clear()
    print(f"{CY}{BO}Welcome to KOALA Setup Wizard!{R}\n")
    print("Let's configure your first Roblox account.\n")

    name = input("Account name: ").strip()
    if not name:
        name = "Account1"

    pkg = input(f"Package name [{DEFAULT_PACKAGE}]: ").strip()
    if not pkg:
        pkg = DEFAULT_PACKAGE

    uid = input("Roblox User ID: ").strip()

    gid = input("Game ID (Place ID): ").strip()
    if not gid:
        print(f"{RD}Game ID is required!{R}")
        time.sleep(2)
        return

    ps = input("Private server link (optional): ").strip()
    wh = input("Discord webhook URL (optional): ").strip()

    iv = input("Check interval in seconds [60]: ").strip()
    check_interval = int(iv) if iv.isdigit() else 60

    rd_input = input("Retry delay in seconds [10]: ").strip()
    retry_delay = int(rd_input) if rd_input.isdigit() else 10

    ft = input("Freeze threshold (checks) [3]: ").strip()
    freeze_threshold = int(ft) if ft.isdigit() else 3

    ok = add_account(
        name=name, package=pkg, game_id=gid,
        private_server_link=ps, webhook_url=wh,
        check_interval=check_interval, retry_delay=retry_delay,
        freeze_threshold=freeze_threshold, roblox_user_id=uid
    )

    if ok:
        print(f"\n{GR}Account '{name}' created successfully!{R}")
        if uid:
            uname = fetch_roblox_username(uid)
            if uname:
                with lock:
                    roblox_username_cache[name] = uname
                print(f"Roblox username: {uname}")
    else:
        print(f"\n{RD}Failed to create account (name may already exist).{R}")

    print("\nPress Enter to continue...")
    input()
    clear()


# ══════════════════════════════════════════════════════════════════════════════
#  BATTERY OPTIMIZATION WARNING
# ══════════════════════════════════════════════════════════════════════════════
def check_battery_optimization():
    """Warn if Termux is not exempt from battery optimization."""
    try:
        whitelist = run_cmd("dumpsys deviceidle whitelist", force_no_root=True)
        if "com.termux" not in whitelist:
            print(f"{YL}⚠ Battery optimization may kill Termux in background.{R}")
            print(f"   Run: {CY}adb shell dumpsys deviceidle whitelist +com.termux{R}")
            print(f"   Or disable battery optimization for Termux in Settings.\n")
            time.sleep(2)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  ROBLOX USERNAME LOOKUP
# ══════════════════════════════════════════════════════════════════════════════
def fetch_roblox_username(user_id):
    if not user_id:
        return None
    try:
        resp = requests.get(
            f"https://users.roblox.com/v1/users/{user_id}",
            timeout=8
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("name")
    except Exception:
        pass
    return None


def prefetch_usernames(accounts):
    for acc in accounts:
        name    = acc["name"]
        user_id = acc.get("roblox_user_id", "").strip()
        if user_id and name not in roblox_username_cache:
            uname = fetch_roblox_username(user_id)
            with lock:
                roblox_username_cache[name] = uname or acc["name"]
        elif not user_id:
            with lock:
                roblox_username_cache[name] = acc["name"]


def get_display_username(acc):
    with lock:
        return roblox_username_cache.get(acc["name"], acc["name"])


# ══════════════════════════════════════════════════════════════════════════════
#  ACCOUNT MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════
def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    try:
        with open(ACCOUNTS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_accounts(accounts):
    try:
        with open(ACCOUNTS_FILE, "w") as f:
            json.dump(accounts, f, indent=4)
        run_cmd(f"chmod 644 {ACCOUNTS_FILE}")
        return True
    except Exception:
        return False


def add_account(name, package=DEFAULT_PACKAGE, game_id="",
                private_server_link="", webhook_url="",
                check_interval=60, retry_attempts=3,
                retry_delay=10, freeze_threshold=3, roblox_user_id=""):
    accounts = load_accounts()
    if any(a["name"] == name for a in accounts):
        return False
    accounts.append({
        "name": name, "package": package,
        "game_id": game_id, "private_server_link": private_server_link,
        "webhook_url": webhook_url, "check_interval": check_interval,
        "retry_attempts": retry_attempts, "retry_delay": retry_delay,
        "freeze_threshold": freeze_threshold, "roblox_user_id": roblox_user_id,
    })
    save_accounts(accounts)
    return True


def remove_account(name):
    save_accounts([a for a in load_accounts() if a["name"] != name])


def update_account(name, updates):
    accounts = load_accounts()
    for i, a in enumerate(accounts):
        if a["name"] == name:
            accounts[i].update(updates)
            save_accounts(accounts)
            return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
#  ROBLOX STATE
# ══════════════════════════════════════════════════════════════════════════════
def is_roblox_running(package):
    if run_cmd(f"pidof {package}").strip():
        return True
    return bool(run_cmd(f"ps | grep {package} | grep -v grep").strip())


def get_current_focus():
    return run_cmd("dumpsys window | grep mCurrentFocus", force_no_root=True)


GAME_ACTIVITIES = [
    "UnityPlayerActivity",
    "GameActivity",
    "NativeActivity",
    "ActivityNativeMain",
    "com.roblox.client.ActivityNativeMain",
    "com.roblox.client.GameActivity",
    "com.roblox.client.UnityPlayerActivity",
    "com.roblox.client/.ActivityNativeMain",
]

MENU_ACTIVITIES = [
    "ActivitySplash", "SplashActivity",
    "ActivityLogin",  "LoginActivity",
    "LaunchActivity", "MainActivity",
    "ActivitySocialSlot",
]

def _dumpsys_activity(timeout=20):
    global _dumpsys_cache
    with _dumpsys_lock:
        out, ts = _dumpsys_cache
        if time.time() - ts < _dumpsys_ttl:
            return out

    grep_pat = (
        "mResumedActivity|mFocusedActivity|mLastPausedActivity|"
        "mCurrentFocus|UnityPlayerActivity|GameActivity|"
        "NativeActivity|ActivityNativeMain|ActivitySplash|"
        "ActivityLogin|com\\.roblox"
    )
    out = run_cmd(
        f"dumpsys activity | grep -E '{grep_pat}'",
        timeout=timeout,
        force_no_root=True
    ) or ""

    with _dumpsys_lock:
        _dumpsys_cache = (out, time.time())
    return out


def _invalidate_dumpsys_cache():
    global _dumpsys_cache
    with _dumpsys_lock:
        _dumpsys_cache = ("", 0.0)


def is_in_game(package):
    if not is_roblox_running(package):
        return False

    dump = _dumpsys_activity()

    for keyword in ("mResumedActivity", "mFocusedActivity", "mLastPausedActivity"):
        for line in dump.splitlines():
            if keyword in line and package in line:
                if any(a in line for a in GAME_ACTIVITIES):
                    return True
                if any(a in line for a in MENU_ACTIVITIES):
                    return False

    focus = get_current_focus()
    if focus and package in focus:
        if any(a in focus for a in GAME_ACTIVITIES):
            return True
        if any(a in focus for a in MENU_ACTIVITIES):
            return False

    window_dump = run_cmd("dumpsys window windows | grep -E 'mCurrentFocus|Window #'", force_no_root=True)
    if f"{package}" in window_dump and "Roblox" in window_dump:
        return True

    in_pkg_task = False
    for line in dump.splitlines():
        if package in line:
            in_pkg_task = True
        if in_pkg_task:
            if any(a in line for a in GAME_ACTIVITIES):
                return True
            if any(a in line for a in MENU_ACTIVITIES):
                return False
        if in_pkg_task and ("* Task{" in line or "* TaskRecord" in line) and package not in line:
            in_pkg_task = False

    return True


def _get_pid(package):
    out = run_cmd(f"pidof {package}") or run_cmd(f"ps -A | grep {package}")
    if out:
        for token in out.split():
            if token.isdigit():
                return token
    return None


def _read_cpu_jiffies(pid):
    try:
        with open(f"/proc/{pid}/stat") as f:
            fields = f.read().split()
        return int(fields[13]) + int(fields[14])
    except Exception:
        return None


def is_frozen(package, threshold):
    if not is_roblox_running(package):
        with lock:
            account_focus_count[package] = 0
            account_last_focus[package]  = None
        return False

    pid = _get_pid(package)
    jiffies = _read_cpu_jiffies(pid) if pid else None

    with lock:
        prev_jiffies = account_last_focus.get(package)
        count        = account_focus_count.get(package, 0)

        if jiffies is None:
            focus = get_current_focus()
            if focus and package in focus:
                if focus == prev_jiffies:
                    count += 1
                else:
                    count = 0
            account_last_focus[package]  = focus
            account_focus_count[package] = count
            return count >= threshold

        if prev_jiffies is not None and jiffies == prev_jiffies:
            count += 1
        else:
            count = 0

        account_last_focus[package]  = jiffies
        account_focus_count[package] = count
        return count >= threshold


# ══════════════════════════════════════════════════════════════════════════════
#  ROBLOX CONTROL
# ══════════════════════════════════════════════════════════════════════════════
def force_stop(package):
    run_cmd(f"am force-stop {package}")
    run_cmd(f"pkill -f {package}")
    time.sleep(3)


def parse_private_server_link(url, game_id=""):
    """
    Extract place ID and private server code from a Roblox private server link.
    Returns (place_id, code) or (None, None) if parsing fails.
    """
    if not url:
        return None, None
    
    place_id = None
    code = None
    
    match = re.search(r'[?&]code=([^&]+)', url)
    if match:
        code = match.group(1)
    
    match = re.search(r'/games/(\d+)', url)
    if match:
        place_id = match.group(1)
    
    if code and not place_id and game_id:
        place_id = game_id
    
    return place_id, code


def launch_roblox(package, game_id, private_server_link=""):
    place_id, code = parse_private_server_link(private_server_link, game_id)

    if code and place_id:
        url = f"roblox://experiences/start?placeId={place_id}&privateServerCode={code}"
    else:
        url = f"roblox://experiences/start?placeId={game_id}"

    run_cmd(
        f'am start -a android.intent.action.VIEW -d "{url}"',
        force_no_root=True
    )

    time.sleep(5)

    if is_roblox_running(package):
        return True

    run_cmd(f"monkey -p {package} 1", force_no_root=True)
    time.sleep(5)

    return is_roblox_running(package)


def rejoin_game(cfg, name):
    package = cfg["package"]
    game_id = cfg.get("game_id", "")
    ps_link = cfg.get("private_server_link", "")

    if not game_id and not ps_link:
        set_status(name, "No Game ID")
        return False

    cooldown_key = f"__rejoin_{package}"
    now = time.time()
    with lock:
        last = account_last_focus.get(cooldown_key, 0)
        if now - last < COOLDOWN_SECONDS:
            return False
        account_last_focus[cooldown_key] = now

    retry_delay = cfg.get("retry_delay", 10)
    attempt = 0

    while account_running.get(name, False):
        attempt += 1
        set_status(name, f"Killing... ({attempt})")
        force_stop(package)
        time.sleep(3)

        set_status(name, f"Rejoining ({attempt})")
        if launch_roblox(package, game_id, ps_link):
            set_status(name, f"Loading... ({attempt})")
            time.sleep(18)

            _invalidate_dumpsys_cache()
            if is_in_game(package):
                set_status(name, "In-Game")
                with lock:
                    account_in_game_since[name] = time.time()
                return True

        set_status(name, f"Retrying... ({attempt})")
        _invalidate_dumpsys_cache()
        time.sleep(retry_delay)

    return False


def send_webhook(url, message, name=None):
    if not url:
        return

    key = f"__wh_{name or 'g'}"
    with lock:
        last = account_last_focus.get(key, 0)
        if time.time() - last < WEBHOOK_COOLDOWN:
            return
        account_last_focus[key] = time.time()

    color = 0x2b2d31
    if "crashed" in message or "failed" in message:
        color = 0xed4245
    elif "kicked" in message or "frozen" in message:
        color = 0xfaa81a 
    elif "rejoined" in message:
        color = 0x57f287
    elif "rejoining" in message:
        color = 0xfee75c

    embed = {
        "title": "Koala Hub",
        "description": message,
        "color": color,
        "footer": {"text": "discord.gg/KoalaHub"},
        "timestamp": datetime.utcnow().isoformat()
    }

    payload = {"embeds": [embed]}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  AUTO-THROTTLE UTILS
# ══════════════════════════════════════════════════════════════════════════════
def get_load_average():
    try:
        with open("/proc/loadavg") as f:
            return float(f.read().split()[0])
    except Exception:
        return None


def get_cpu_core_count():
    try:
        return os.cpu_count() or 4
    except Exception:
        return 4


# ══════════════════════════════════════════════════════════════════════════════
#  AUTOMATION LOOP (per account)
# ══════════════════════════════════════════════════════════════════════════════
def set_status(name, status):
    with lock:
        account_status[name] = status
        if status != "In-Game":
            account_in_game_since.pop(name, None)


def automation_loop(cfg):
    name      = cfg["name"]
    package   = cfg["package"]
    base_interval = cfg.get("check_interval", CHECK_INTERVAL)
    threshold = cfg.get("freeze_threshold", 3)
    webhook   = cfg.get("webhook_url", "")

    set_status(name, "Initializing")
    time.sleep(2)

    cores = get_cpu_core_count()

    while account_running.get(name, False):
        try:
            interval = base_interval
            load = get_load_average()
            cpu_pct = get_cpu_usage_percent()
            if load and load > cores * 1.5:
                interval = min(base_interval * 3, 300)
            elif cpu_pct > 80:
                interval = min(base_interval * 2, 180)

            running = is_roblox_running(package)
            ingame  = is_in_game(package)

            if not running:
                set_status(name, "Not Running")
                send_webhook(webhook, f"❌ {name}: crashed – rejoining…", name)
                ok = rejoin_game(cfg, name)
                send_webhook(webhook,
                             f"✅ {name}: rejoined" if ok else f"❌ {name}: failed",
                             name)
            elif not ingame:
                set_status(name, "Kicked/Disc.")
                send_webhook(webhook, f"⚠️ {name}: kicked – rejoining…", name)
                ok = rejoin_game(cfg, name)
                send_webhook(webhook,
                             f"✅ {name}: rejoined" if ok else f"❌ {name}: failed",
                             name)
            elif is_frozen(package, threshold):
                set_status(name, "Frozen")
                send_webhook(webhook, f"❄️ {name}: frozen – rejoining…", name)
                ok = rejoin_game(cfg, name)
                send_webhook(webhook,
                             f"✅ {name}: rejoined" if ok else f"❌ {name}: failed",
                             name)
            else:
                set_status(name, "In-Game")
                with lock:
                    if name not in account_in_game_since:
                        account_in_game_since[name] = time.time()

            for _ in range(interval):
                if not account_running.get(name, False):
                    break
                time.sleep(1)

            time.sleep(0.5)

        except Exception as e:
            set_status(name, f"Error")
            time.sleep(10)

    set_status(name, "Stopped")


# ══════════════════════════════════════════════════════════════════════════════
#  LIVE DASHBOARD DISPLAY
# ══════════════════════════════════════════════════════════════════════════════
def get_ram_mb():
    global _ram_cache
    val, last_read = _ram_cache
    if time.time() - last_read < 5:
        return val
    try:
        with open("/proc/meminfo") as f:
            data = f.read()
        total = free_m = 0
        for line in data.splitlines():
            if line.startswith("MemTotal:"):
                total = int(line.split()[1]) // 1024
            elif line.startswith("MemAvailable:"):
                free_m = int(line.split()[1]) // 1024
        val = total - free_m
    except Exception:
        val = 0
    _ram_cache = (val, time.time())
    return val


def get_total_mem_mb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 0


def get_uptime_str():
    try:
        with open("/proc/uptime") as f:
            uptime_sec = float(f.read().split()[0])
        days = int(uptime_sec // 86400)
        hours = int((uptime_sec % 86400) // 3600)
        minutes = int((uptime_sec % 3600) // 60)
        seconds = int(uptime_sec % 60)
        if days:
            return f"{days}d {hours}h {minutes}m {seconds}s"
        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        return f"{minutes}m {seconds}s"
    except Exception:
        return "N/A"


def get_cpu_usage_percent():
    try:
        def read_cpu():
            with open("/proc/stat") as f:
                parts = f.readline().split()
            vals = [int(x) for x in parts[1:]]
            idle = vals[3] + vals[4]
            total = sum(vals)
            return idle, total

        idle1, total1 = read_cpu()
        time.sleep(0.1)
        idle2, total2 = read_cpu()
        total_delta = total2 - total1
        idle_delta = idle2 - idle1
        if total_delta <= 0:
            return 0.0
        usage = 100.0 * (1.0 - idle_delta / total_delta)
        return max(0.0, min(100.0, usage))
    except Exception:
        return 0.0


def get_tool_memory_mb():
    try:
        pid = os.getpid()
        out = run_cmd(f"ps -p {pid} -o rss=")
        if out:
            return int(out.strip()) // 1024
    except Exception:
        pass
    return 0


def get_roblox_process_count(cfg_list):
    pids = set()
    for cfg in cfg_list:
        pid = _get_pid(cfg["package"])
        if pid:
            pids.add(pid)
    return len(pids)


def status_color(s):
    s = s or "?"
    if "In-Game" in s:
        return f"{GR}{s}{R}"
    if any(w in s for w in ["Rejoin", "Loading", "Stopping", "Kick", "Frozen"]):
        return f"{YL}{s}{R}"
    if any(w in s for w in ["Failed", "Error", "Not"]):
        return f"{RD}{s}{R}"
    if "Stopped" in s:
        return f"{DIM}{s}{R}"
    return f"{CY}{s}{R}"


def format_duration(seconds):
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds//60)}m {int(seconds%60)}s"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h {m}m"


def draw_dashboard(cfg_list):
    global display_fps

    cols = shutil.get_terminal_size((80, 24)).columns
    sep  = f"{DIM}" + "-" * cols + f"{R}"

    out = []

    for line in KOALA_ART:
        out.append(f"{CY}{BO}{line}{R}")
    out.append("")

    any_custom = any(c.get("private_server_link") for c in cfg_list)
    auto_state = f"{GR}Enable{R}"  if automation_enabled else f"{DIM}Disable{R}"
    cust_state = f"{GR}Enable{R}"  if any_custom          else f"{DIM}Disable{R}"

    out.append(f"Check roblox")
    out.append(f"Change accounts: {auto_state}")
    out.append(f"Change accounts custom: {cust_state}")
    out.append(f"Check UI size: {cols}")
    out.append("")

    cpu_pct = get_cpu_usage_percent()
    used_ram = get_ram_mb()
    total_ram = get_total_mem_mb()
    tool_ram = get_tool_memory_mb()
    uptime = get_uptime_str()
    roblox_count = get_roblox_process_count(cfg_list)

    out.append(f"{BO}System Info for Day{R}")
    out.append(sep)
    out.append(f"CPU Usage: {cpu_pct:5.1f}%   Memory Used: {used_ram / 1024:.2f} GB   Total Memory: {total_ram / 1024:.1f} GB")
    out.append(f"Tool Memory Used: {tool_ram:.2f} MB   Uptime: {uptime}   Total Roblox Processes: {roblox_count}")
    out.append("")
    out.append(f"Details:")

    with lock:
        statuses = dict(account_status)
        ingame_times = dict(account_in_game_since)

    for cfg in cfg_list:
        name   = cfg["name"]
        pkg    = cfg["package"]
        status = statuses.get(name, "Initializing")
        uname  = get_display_username(cfg)
        stat_str = status_color(status)
        pid = _get_pid(pkg) or "-"

        duration_str = ""
        if status == "In-Game" and name in ingame_times:
            elapsed = time.time() - ingame_times[name]
            duration_str = f" [{format_duration(elapsed)}]"

        out.append(f"  {pkg} (PID: {pid}) — {uname} — {stat_str}{duration_str}")

    out.append("")
    out.append(sep)
    out.append(f"{DIM}Ctrl+C → menu{R}")

    print("\n" * 2)
    sys.stdout.write("\n".join(out) + "\n")
    sys.stdout.flush()


def display_thread_fn(cfg_list):
    global display_running

    while display_running:
        try:
            draw_dashboard(cfg_list)
            time.sleep(2)
        except:
            time.sleep(2)


# ══════════════════════════════════════════════════════════════════════════════
#  AUTOMATION START / STOP
# ══════════════════════════════════════════════════════════════════════════════
def start_automation(account_name=None):
    global automation_enabled
    accounts = load_accounts()
    if not accounts:
        print(f"{YL}No accounts configured.{R}")
        return

    stagger = 3
    started = 0

    for acc in accounts:
        name = acc["name"]
        if account_name and name != account_name:
            continue
        if account_running.get(name):
            continue
        if not acc.get("game_id") and not acc.get("private_server_link"):
            print(f"{RD}No Game ID for {name}, skipping.{R}")
            continue
        account_running[name] = True
        t = threading.Thread(target=automation_loop, args=(acc,), daemon=True)
        t.name = f"watcher-{name}"
        t.start()
        account_threads[name] = t
        started += 1
        if started > 1:
            time.sleep(stagger)

    automation_enabled = any(account_running.values())


def stop_automation(account_name=None):
    global automation_enabled
    if account_name:
        account_running[account_name] = False
        if account_name in account_threads:
            account_threads[account_name].join(timeout=5)
            del account_threads[account_name]
    else:
        for n in list(account_running):
            account_running[n] = False
        for t in account_threads.values():
            t.join(timeout=5)
        account_threads.clear()
    automation_enabled = any(account_running.values())


# ══════════════════════════════════════════════════════════════════════════════
#  MENU SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
def clear():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def menu_header():
    clear()
    for line in KOALA_ART:
        print(f"{CY}{BO}{line}{R}")
    root_status = f"{GR}YES{R}" if USE_ROOT else f"{RD}NO{R}"
    print(f"\n  Root: {root_status}\n")


def _ask(prompt, default=""):
    val = input(f"  {prompt} [{default}]: ").strip()
    return val if val else default


def manage_accounts():
    while True:
        accounts = load_accounts()
        menu_header()
        print(f"{CY}  ── MANAGE ACCOUNTS ──{R}\n")
        for i, a in enumerate(accounts, 1):
            st = f"{GR}RUN{R}" if account_running.get(a["name"]) else f"{DIM}STOP{R}"
            print(f"  {i}. {a['name']}  ({a['package']})  [{st}]")
        n = len(accounts)
        print(f"\n  {n+1}. Add account")
        print(f"  {n+2}. Remove account")
        print(f"  {n+3}. Back\n")
        choice = input(f"  {CY}Choice: {R}").strip()
        if not choice.isdigit():
            continue
        idx = int(choice)
        if 1 <= idx <= n:
            edit_account(accounts[idx - 1])
        elif idx == n + 1:
            add_account_interactive()
        elif idx == n + 2:
            remove_account_interactive()
        elif idx == n + 3:
            break


def edit_account(acc):
    menu_header()
    print(f"{CY}  ── EDIT: {acc['name']} ──{R}\n")
    acc["package"]             = _ask("Package",             acc.get("package", DEFAULT_PACKAGE))
    acc["roblox_user_id"]      = _ask("Roblox User ID",     acc.get("roblox_user_id", ""))
    acc["game_id"]             = _ask("Game ID",             acc.get("game_id", ""))
    acc["private_server_link"] = _ask("Private server link", acc.get("private_server_link", ""))
    acc["webhook_url"]         = _ask("Discord webhook",     acc.get("webhook_url", ""))
    v = _ask("Check interval (s)", str(acc.get("check_interval", 60)))
    acc["check_interval"]      = int(v) if v.isdigit() else acc.get("check_interval", 60)
    v = _ask("Retry attempts",     str(acc.get("retry_attempts", 3)))
    acc["retry_attempts"]      = int(v) if v.isdigit() else acc.get("retry_attempts", 3)
    v = _ask("Retry delay (s)",    str(acc.get("retry_delay", 10)))
    acc["retry_delay"]         = int(v) if v.isdigit() else acc.get("retry_delay", 10)
    v = _ask("Freeze threshold",   str(acc.get("freeze_threshold", 3)))
    acc["freeze_threshold"]    = int(v) if v.isdigit() else acc.get("freeze_threshold", 3)
    update_account(acc["name"], acc)
    uid = acc.get("roblox_user_id", "").strip()
    if uid:
        print(f"  {BL}Fetching Roblox username…{R}")
        uname = fetch_roblox_username(uid)
        with lock:
            roblox_username_cache[acc["name"]] = uname or acc["name"]
        print(f"  {GR}Username: {roblox_username_cache[acc['name']]}{R}")
    print(f"\n  {GR}Saved!{R}")
    time.sleep(1.5)


def add_account_interactive():
    menu_header()
    print(f"{CY}  ── ADD ACCOUNT ──{R}\n")
    name = input("  Account name (label): ").strip()
    if not name:
        return
    uid = input("  Roblox User ID (numbers only): ").strip()
    pkg = _ask("Package", DEFAULT_PACKAGE)
    gid = input("  Game ID: ").strip()
    ps  = input("  Private server link (optional): ").strip()
    wh  = input("  Discord webhook URL (optional): ").strip()
    iv  = _ask("Check interval (s)", "60")
    ra  = _ask("Retry attempts",     "3")
    rd  = _ask("Retry delay (s)",    "10")
    ft  = _ask("Freeze threshold",   "3")
    ok  = add_account(name, pkg, gid, ps, wh,
                      int(iv) if iv.isdigit() else 60,
                      int(ra) if ra.isdigit() else 3,
                      int(rd) if rd.isdigit() else 10,
                      int(ft) if ft.isdigit() else 3,
                      roblox_user_id=uid)
    if ok and uid:
        print(f"  {BL}Fetching Roblox username…{R}")
        uname = fetch_roblox_username(uid)
        with lock:
            roblox_username_cache[name] = uname or name
        fetched = roblox_username_cache[name]
        print(f"  {GR}Username: {fetched}{R}")
    print(f"\n  {GR if ok else RD}{'Added!' if ok else 'Already exists.'}{R}")
    time.sleep(1.5)


def remove_account_interactive():
    accounts = load_accounts()
    if not accounts:
        return
    menu_header()
    print(f"{CY}  ── REMOVE ACCOUNT ──{R}\n")
    for i, a in enumerate(accounts, 1):
        print(f"  {i}. {a['name']}")
    c = input("\n  Remove #: ").strip()
    if c.isdigit():
        idx = int(c) - 1
        if 0 <= idx < len(accounts):
            n = accounts[idx]["name"]
            stop_automation(n)
            remove_account(n)
            print(f"\n  {GR}Removed.{R}")
            time.sleep(1)


def run_dashboard():
    global display_running
    accounts = load_accounts()
    if not accounts:
        print(f"  {YL}No accounts. Add one first.{R}\n")
        input("  Press Enter…")
        return

    prefetch_usernames(accounts)

    start_automation()
    if not automation_enabled:
        print(f"  {RD}No accounts could start. Check Game IDs.{R}\n")
        input("  Press Enter…")
        return

    display_running = True
    dt = threading.Thread(target=display_thread_fn, args=(accounts,), daemon=True)
    dt.start()

    threading.Thread(target=input_listener, daemon=True).start()

    try:
        while display_running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        display_running = False
        dt.join(timeout=3)
        stop_automation()


def display_menu():
    menu_header()
    print(f"  {CY}1.{R} Manage accounts")
    print(f"  {CY}2.{R} Start automation  (live dashboard)")
    print(f"  {CY}3.{R} Stop all")
    print(f"  {CY}4.{R} Toggle single account")
    print(f"  {CY}5.{R} Exit")
    print()


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
def input_listener():
    global display_running
    while display_running:
        try:
            cmd = input()
            if cmd.lower() in ["exit", "stop", "q"]:
                display_running = False
        except:
            break


def main():
    global platform_info, USE_ROOT
    try:
        detector = PlatformDetector()
        platform_info = detector.detect_platform()
        
        if USE_ROOT:
            print(f"{GR}✓ Root access available and will be used{R}")
        else:
            print(f"{DIM}✗ Running without root (safer for cloud phones){R}")
        
        loading_screen(duration=1.5)
        check_battery_optimization()

        if not load_accounts():
            quick_setup_wizard()
            if not load_accounts():
                add_account("Account1", DEFAULT_PACKAGE)

        while True:
            display_menu()
            choice = input(f"  {CY}Choice (1-5): {R}").strip()

            if choice == "1":
                manage_accounts()
            elif choice == "2":
                run_dashboard()
            elif choice == "3":
                stop_automation()
                print(f"  {GR}All stopped.{R}\n")
                time.sleep(1)
            elif choice == "4":
                accounts = load_accounts()
                if not accounts:
                    continue
                menu_header()
                print(f"{CY}  ── TOGGLE ACCOUNT ──{R}\n")
                for i, a in enumerate(accounts, 1):
                    st = f"{GR}Running{R}" if account_running.get(a["name"]) else "Stopped"
                    print(f"  {i}. {a['name']}  [{st}]")
                print(f"  {len(accounts)+1}. Back\n")
                c = input(f"  {CY}Choice: {R}").strip()
                if c.isdigit():
                    idx = int(c)
                    if 1 <= idx <= len(accounts):
                        n = accounts[idx-1]["name"]
                        if account_running.get(n):
                            stop_automation(n)
                        else:
                            start_automation(n)
            elif choice == "5":
                stop_automation()
                clear()
                print(f"{CY}Goodbye!{R}\n")
                break

    except KeyboardInterrupt:
        print()
        stop_automation()
        clear()
        print(f"{CY}Bye!{R}\n")
    except Exception as e:
        print(f"{RD}Fatal: {e}{R}")
        sys.exit(1)


if __name__ == "__main__":
    main()