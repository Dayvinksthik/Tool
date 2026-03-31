#!/usr/bin/env python3
"""
Roblox Auto Rejoin Tool
Multi-account headless watchdog for rooted Android / Termux.
"""

import os
import sys
import time
import json
import shutil
import threading
import subprocess
import requests
from datetime import datetime

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
DISPLAY_INTERVAL = 1.0

# ── GLOBALS ────────────────────────────────────────────────────────────────────
platform_info          = None
account_threads        = {}
account_running        = {}
account_status         = {}
account_last_focus     = {}
account_focus_count    = {}
roblox_username_cache  = {}
display_running        = False
display_fps            = 0.0
automation_enabled     = False
lock = threading.Lock()


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
#  PLATFORM DETECTION
# ══════════════════════════════════════════════════════════════════════════════
class PlatformDetector:
    def detect_platform(self):
        if self._check_root():
            return {"type": "rooted", "has_root": True}
        return {"type": "unrooted", "has_root": False}

    def _check_root(self):
        try:
            r = subprocess.run(["su", "-c", "echo test"],
                               capture_output=True, text=True, timeout=5)
            return "test" in r.stdout
        except Exception:
            return False


def run_cmd(command, timeout=10):
    try:
        if platform_info and platform_info.get("has_root"):
            full = f"su -c '{command}'"
        else:
            full = command
        r = subprocess.run(full, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════════════════════
#  ROBLOX USERNAME LOOKUP
# ══════════════════════════════════════════════════════════════════════════════
def fetch_roblox_username(user_id):
    """Fetch Roblox username for a given numeric user ID via the public API.
    Returns the username string, or None on failure."""
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
    """Fetch Roblox usernames for all accounts that have a roblox_user_id.
    Runs in a background thread so it doesn't block startup."""
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
    """Return the cached Roblox username, or the account name as fallback."""
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
    return run_cmd("dumpsys window | grep mCurrentFocus")


def is_in_game(package):
    focus = get_current_focus()
    return bool(focus) and package in focus and (
        "UnityPlayerActivity" in focus or "GameActivity" in focus
    )


def is_frozen(package, threshold):
    if not is_roblox_running(package):
        with lock:
            account_focus_count[package] = 0
            account_last_focus[package]  = None
        return False
    focus = get_current_focus()
    with lock:
        prev  = account_last_focus.get(package)
        count = account_focus_count.get(package, 0)
        if not focus or focus == prev:
            count += 1
        else:
            count = 0
            prev  = focus
        account_last_focus[package]  = prev
        account_focus_count[package] = count
        if count >= threshold and package in (focus or prev or ""):
            return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
#  ROBLOX CONTROL
# ══════════════════════════════════════════════════════════════════════════════
def force_stop(package):
    run_cmd(f"am force-stop {package}")
    run_cmd(f"pkill -f {package}")
    time.sleep(3)


def launch_roblox(package, game_id, private_server_link=""):
    url = private_server_link if private_server_link else \
          f"roblox://experiences/start?placeId={game_id}"
    run_cmd(f'am start -a android.intent.action.VIEW -d "{url}"')
    time.sleep(5)
    if is_roblox_running(package):
        return True
    time.sleep(3)
    run_cmd(f"monkey -p {package} 1")
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

    set_status(name, "Stopping...")
    force_stop(package)

    for attempt in range(cfg.get("retry_attempts", 3)):
        set_status(name, f"Rejoining ({attempt+1})")
        if launch_roblox(package, game_id, ps_link):
            set_status(name, "Loading...")
            time.sleep(15)
            if is_in_game(package):
                set_status(name, "In-Game")
                return True
            set_status(name, f"Not In-Game ({attempt+1})")
        time.sleep(cfg.get("retry_delay", 10))

    set_status(name, "Rejoin Failed")
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
    try:
        requests.post(url, json={"content": message}, timeout=5)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  AUTOMATION LOOP
# ══════════════════════════════════════════════════════════════════════════════
def set_status(name, status):
    with lock:
        account_status[name] = status


def automation_loop(cfg):
    name      = cfg["name"]
    package   = cfg["package"]
    interval  = cfg.get("check_interval", 60)
    threshold = cfg.get("freeze_threshold", 3)
    webhook   = cfg.get("webhook_url", "")

    set_status(name, "Initializing")
    time.sleep(2)

    while account_running.get(name, False):
        try:
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

            for _ in range(interval):
                if not account_running.get(name, False):
                    break
                time.sleep(1)

        except Exception as e:
            set_status(name, f"Error")
            time.sleep(10)

    set_status(name, "Stopped")


# ══════════════════════════════════════════════════════════════════════════════
#  LIVE DASHBOARD DISPLAY
# ══════════════════════════════════════════════════════════════════════════════
def get_ram_mb():
    """Return used RAM in MB from /proc/meminfo."""
    try:
        out = run_cmd("cat /proc/meminfo")
        total = used_m = free_m = 0
        for line in out.splitlines():
            if line.startswith("MemTotal:"):
                total = int(line.split()[1]) // 1024
            elif line.startswith("MemAvailable:"):
                free_m = int(line.split()[1]) // 1024
        used_m = total - free_m
        return used_m
    except Exception:
        return 0


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


def draw_dashboard(cfg_list):
    """Clear screen and print the live KOALA dashboard."""
    global display_fps

    cols = shutil.get_terminal_size((80, 24)).columns
    sep  = f"{DIM}" + "-" * cols + f"{R}"

    out = []

    # ── KOALA ASCII HEADER ─────────────────────────────────────────────
    out.append("")
    for line in KOALA_ART:
        out.append(f"{CY}{BO}{line}{R}")
    out.append("")

    # ── SETTINGS BLOCK ─────────────────────────────────────────────────
    any_custom = any(c.get("private_server_link") for c in cfg_list)
    auto_state = f"{GR}Enable{R}"  if automation_enabled else f"{DIM}Disable{R}"
    cust_state = f"{GR}Enable{R}"  if any_custom          else f"{DIM}Disable{R}"

    out.append(f"Check roblox")
    out.append(f"Change accounts: {auto_state}")
    out.append(f"Change accounts custom: {cust_state}")
    out.append(f"Check UI size: {cols}")
    out.append("")

    # ── STATS BAR ──────────────────────────────────────────────────────
    out.append(sep)
    ram = get_ram_mb()
    out.append(f"FPS: {display_fps:.2f} | RAM: {ram}MB")
    out.append(sep)

    # ── ACCOUNT TABLE ──────────────────────────────────────────────────
    W_PKG  = 22
    W_USER = 18
    W_STAT = 16

    hdr_pkg  = "Package".ljust(W_PKG)
    hdr_user = "Username".ljust(W_USER)
    hdr_stat = "Status"
    out.append(f"{BO}{hdr_pkg}{hdr_user}{hdr_stat}{R}")

    with lock:
        statuses = dict(account_status)

    for cfg in cfg_list:
        name   = cfg["name"]
        pkg    = cfg["package"]
        status = statuses.get(name, "Initializing")
        uname  = get_display_username(cfg)

        pkg_str  = pkg[:W_PKG-1].ljust(W_PKG)
        user_str = uname[:W_USER-1].ljust(W_USER)
        stat_str = status_color(status)

        out.append(f"{pkg_str}{user_str}{stat_str}")

    out.append("")
    out.append(f"{DIM}Ctrl+C → menu{R}")

    os.system("clear")
    print("\n".join(out))


def display_thread_fn(cfg_list):
    """Background thread — refreshes live dashboard every DISPLAY_INTERVAL."""
    global display_fps, display_running
    frame = 0
    t0    = time.time()

    while display_running:
        t_start = time.time()
        draw_dashboard(cfg_list)

        frame += 1
        elapsed = time.time() - t0
        if elapsed > 0:
            display_fps = frame / elapsed

        sleep_rem = DISPLAY_INTERVAL - (time.time() - t_start)
        if sleep_rem > 0:
            time.sleep(sleep_rem)


# ══════════════════════════════════════════════════════════════════════════════
#  AUTOMATION START / STOP
# ══════════════════════════════════════════════════════════════════════════════
def start_automation(account_name=None):
    global automation_enabled
    accounts = load_accounts()
    if not accounts:
        print(f"{YL}No accounts configured.{R}")
        return
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
        t.start()
        account_threads[name] = t
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
    os.system("clear")


def menu_header():
    clear()
    for line in KOALA_ART:
        print(f"{CY}{BO}{line}{R}")
    root_txt = f"{GR}YES{R}" if (platform_info and platform_info.get("has_root")) \
               else f"{RD}NO{R}"
    print(f"\n  Root: {root_txt}\n")


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
    """Start automation + live display. Ctrl+C returns to menu."""
    global display_running
    accounts = load_accounts()
    if not accounts:
        print(f"  {YL}No accounts. Add one first.{R}\n")
        input("  Press Enter…")
        return

    fetch_thread = threading.Thread(target=prefetch_usernames, args=(accounts,), daemon=True)
    fetch_thread.start()

    start_automation()
    if not automation_enabled:
        print(f"  {RD}No accounts could start. Check Game IDs.{R}\n")
        input("  Press Enter…")
        return

    display_running = True
    dt = threading.Thread(target=display_thread_fn, args=(accounts,), daemon=True)
    dt.start()

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
def main():
    global platform_info
    try:
        platform_info = PlatformDetector().detect_platform()

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
