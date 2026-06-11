import re
import json
import importlib
import socket
import ctypes
import shutil
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox, simpledialog
import subprocess
from datetime import date
from ctypes import wintypes
from pathlib import Path
import sqlite3

try:
    _tkinterdnd2 = importlib.import_module("tkinterdnd2")
    DND_FILES = _tkinterdnd2.DND_FILES
    TkinterDnD = _tkinterdnd2.TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

default_server_name = r"\\applemango"
default_drive_letter = "Z"
allowed_mapping_letters = list("ABDEFHIJKLMNOPQRSTUVWXYZ")
session_logged_in = False
session_username = ""
session_password = ""
session_account_name = ""
active_workspace = ""
credential_store_path = Path.home() / ".applemango_archiver_credentials.json"

def get_drive_target():
    return f"{default_drive_letter.strip().upper().rstrip(':')}:"

def run_net_command(command):
    return subprocess.run(
        ["cmd", "/d", "/c", f"chcp 949>nul & {command}"],
        capture_output=True,
        text=True,
        encoding="cp949",
        errors="replace"
    )

def get_mapped_drives_text():
    entries = get_mapped_network_drives()

    if entries is None:
        return "Current Mapped Drives: unavailable"

    drives = []
    for drive, remote in entries:
        folder_name = remote.rstrip("\\/").split("\\")[-1]
        drives.append(f"{drive.rstrip(':')}:{folder_name}")

    if not drives:
        return "Current Mapped Drives: none"

    return "Current Mapped Drives: " + ", ".join(drives)

def format_drive_summary(entries):
    if entries is None:
        return "Current Mapped Drives: unavailable"
    if not entries:
        return "Current Mapped Drives: none"

    pairs = []
    for drive, remote in entries:
        folder_name = remote.rstrip("\\/").split("\\")[-1]
        pairs.append(f"{drive.rstrip(':')}:{folder_name}")

    if len(pairs) <= 3:
        return "Current Mapped Drives: " + " ".join(pairs)

    return "Current Mapped Drives: " + " ".join(pairs[:3]) + " ..."

def normalize_drive_letter(raw):
    letter = raw.strip().upper().rstrip(":")
    if len(letter) != 1 or not letter.isalpha():
        return None
    return f"{letter}:"

def get_mapped_network_drives():
    result = run_net_command("net use")

    if result.returncode != 0:
        return None

    entries = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("Status") or line.startswith("---") or line.startswith("The command completed"):
            continue

        cols = re.split(r"\s{2,}", line)
        drive = ""
        remote = ""

        if len(cols) >= 3 and cols[1].endswith(":"):
            drive = cols[1].upper()
            remote = cols[2]
        elif len(cols) >= 2 and cols[0].endswith(":"):
            drive = cols[0].upper()
            remote = cols[1]
        else:
            continue

        if remote.startswith("\\\\"):
            entries.append((drive, remote))

    return entries

def get_current_mapped_letters():
    entries = get_mapped_network_drives()
    if entries is None:
        return set()
    return {drive for drive, _ in entries}

def get_available_mapping_letters():
    used_letters = {drive.rstrip(":") for drive in get_current_mapped_letters()}
    return [letter for letter in allowed_mapping_letters if letter not in used_letters]

def extract_account_name(raw_username):
    cleaned = raw_username.strip()
    if "\\" in cleaned:
        cleaned = cleaned.split("\\")[-1]
    if "@" in cleaned:
        cleaned = cleaned.split("@")[0]
    return cleaned

def get_network_info_text():
    ip_addr = "Unavailable"
    ssid = "Unavailable"

    ip_result = subprocess.run(["ipconfig"], capture_output=True, text=True)
    if ip_result.returncode == 0:
        ip_match = re.search(r"IPv4 Address[.\s]*:\s*([0-9.]+)", ip_result.stdout)
        if ip_match:
            ip_addr = ip_match.group(1)

    ssid_result = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True)
    if ssid_result.returncode == 0:
        ssid_match = re.search(r"^\s*SSID\s*:\s*(.+)$", ssid_result.stdout, flags=re.MULTILINE)
        if ssid_match:
            found_ssid = ssid_match.group(1).strip()
            if found_ssid:
                ssid = found_ssid

    return f"IP: {ip_addr}    SSID: {ssid}"

def get_server_ip(server_name):
    normalized_server = server_name.strip().lstrip("\\")
    if not normalized_server:
        return "Unavailable"

    try:
        return socket.gethostbyname(normalized_server)
    except OSError:
        return "Unavailable"

def check_server_availability(server_name):
    normalized_server = server_name.strip().lstrip("\\")
    if not normalized_server:
        return False, "Unavailable"

    ip_addr = get_server_ip(server_name)
    ping_result = subprocess.run(
        ["ping", "-n", "1", normalized_server],
        capture_output=True,
        text=True
    )

    is_available = ping_result.returncode == 0
    return is_available, ip_addr

def load_saved_credentials():
    if not credential_store_path.exists():
        return None

    try:
        payload = json.loads(credential_store_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if not username or not password:
        return None

    return {"username": username, "password": password}

def save_credentials(username, password):
    payload = {"username": username.strip(), "password": password}
    credential_store_path.write_text(json.dumps(payload), encoding="utf-8")

def clear_saved_credentials():
    if credential_store_path.exists():
        try:
            credential_store_path.unlink()
        except OSError:
            pass

def authenticate_to_server(username, password):
    subprocess.run(
        ["net", "use", fr"{default_server_name}\IPC$", "/delete", "/y"],
        capture_output=True,
        text=True
    )

    login_cmd = [
        "net", "use",
        fr"{default_server_name}\IPC$",
        password,
        f"/user:{username}",
        "/persistent:no"
    ]
    login_result = subprocess.run(login_cmd, capture_output=True, text=True)
    if login_result.returncode == 0:
        return True, ""

    err = login_result.stderr.strip() or login_result.stdout.strip() or "Unknown error"
    return False, err

def update_session_login(username, password):
    global session_logged_in, session_username, session_password, session_account_name

    session_logged_in = True
    session_username = username.strip()
    session_password = password
    session_account_name = extract_account_name(username)

def clear_session_login():
    global session_logged_in, session_username, session_password, session_account_name

    session_logged_in = False
    session_username = ""
    session_password = ""
    session_account_name = ""

def get_server_share_names(server_name):
    normalized_server = server_name.strip().lstrip("\\")
    if not normalized_server:
        return None

    class SHARE_INFO_1(ctypes.Structure):
        _fields_ = [
            ("shi1_netname", wintypes.LPWSTR),
            ("shi1_type", wintypes.DWORD),
            ("shi1_remark", wintypes.LPWSTR)
        ]

    netapi32 = ctypes.WinDLL("Netapi32.dll")
    net_share_enum = netapi32.NetShareEnum
    net_share_enum.argtypes = [
        wintypes.LPWSTR,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD)
    ]
    net_share_enum.restype = wintypes.DWORD

    net_api_buffer_free = netapi32.NetApiBufferFree
    net_api_buffer_free.argtypes = [ctypes.c_void_p]
    net_api_buffer_free.restype = wintypes.DWORD

    shares = []
    resume_handle = wintypes.DWORD(0)
    server_unc = f"\\\\{normalized_server}"

    while True:
        buffer = ctypes.c_void_p()
        entries_read = wintypes.DWORD(0)
        total_entries = wintypes.DWORD(0)

        status = net_share_enum(
            server_unc,
            1,
            ctypes.byref(buffer),
            0xFFFFFFFF,
            ctypes.byref(entries_read),
            ctypes.byref(total_entries),
            ctypes.byref(resume_handle)
        )

        if status not in (0, 234):
            if buffer:
                net_api_buffer_free(buffer)
            return None

        if entries_read.value and buffer:
            share_array = ctypes.cast(buffer, ctypes.POINTER(SHARE_INFO_1))
            for index in range(entries_read.value):
                share_name = share_array[index].shi1_netname
                if share_name and not share_name.endswith("$"):
                    shares.append(share_name)

        if buffer:
            net_api_buffer_free(buffer)

        if status == 0:
            break

    return list(dict.fromkeys(shares))

def login_to_server(root, on_ui_refresh, on_auth_refresh, on_login_status_refresh):
    global session_logged_in, session_username, session_password, session_account_name

    username = simpledialog.askstring("Server Login", "Username:", parent=root)
    if not username:
        return

    password = simpledialog.askstring("Server Login", "Password:", parent=root, show="*")
    if password is None:
        return

    subprocess.run(
        ["net", "use", fr"{default_server_name}\IPC$", "/delete", "/y"],
        capture_output=True,
        text=True
    )

    login_cmd = [
        "net", "use",
        fr"{default_server_name}\IPC$",
        password,
        f"/user:{username}",
        "/persistent:no"
    ]
    login_result = subprocess.run(login_cmd, capture_output=True, text=True)

    if login_result.returncode == 0:
        session_logged_in = True
        session_username = username.strip()
        session_password = password
        session_account_name = extract_account_name(username)
        on_login_status_refresh()
        on_ui_refresh()
        on_auth_refresh()
        messagebox.showinfo(
            "Login Success",
            f"Authenticated to {default_server_name} as {session_account_name}",
            parent=root
        )
    else:
        session_logged_in = False
        session_username = ""
        session_password = ""
        session_account_name = ""
        on_login_status_refresh()
        on_auth_refresh()
        err = login_result.stderr.strip() or login_result.stdout.strip() or "Unknown error"
        messagebox.showerror("Login Failed", err, parent=root)

def logout_from_server(root, on_ui_refresh, on_auth_refresh, on_login_status_refresh):
    global session_logged_in, session_username, session_password, session_account_name

    subprocess.run(
        ["net", "use", fr"{default_server_name}\IPC$", "/delete", "/y"],
        capture_output=True,
        text=True,
        encoding = "mbcs",
        errors = "replace"
    )

    session_logged_in = False
    session_username = ""
    session_password = ""
    session_account_name = ""

    on_login_status_refresh()
    on_ui_refresh()
    on_auth_refresh()
    messagebox.showinfo("Logged Out", "You have been logged out.", parent=root)

def show_all_mapped_drives(root):
    mapped_entries = get_mapped_network_drives()
    if mapped_entries is None:
        messagebox.showerror("Mapped Drives", "Unable to read mapped drives.", parent=root)
        return

    if not mapped_entries:
        messagebox.showinfo("Mapped Drives", "No mapped drives found.", parent=root)
        return

    win = tk.Toplevel(root)
    win.title("All Mapped Drives")
    win.geometry("420x360")
    win.configure(bg="white")
    win.transient(root)

    tk.Label(
        win,
        text="All Mapped Drives",
        font=("Segoe UI", 10, "bold"),
        bg="white"
    ).pack(pady=(10, 8))

    list_frame = tk.Frame(win, bg="white")
    list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

    for drive, remote in mapped_entries:
        folder_name = remote.rstrip("\\/").split("\\")[-1]
        tk.Label(
            list_frame,
            text=f"{drive.rstrip(':')}:{folder_name}",
            font=("Segoe UI", 10),
            bg="white",
            anchor="w",
            justify="left"
        ).pack(fill="x", pady=2)

    tk.Button(
        win,
        text="Close",
        width=12,
        command=win.destroy,
        bg="#d9d9d9",
        activebackground="#c0c0c0",
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2"
    ).pack(pady=(0, 12))

def show_mapped_drives_window(root):
    mapped_entries = get_mapped_network_drives()
    if mapped_entries is None:
        messagebox.showerror("Mapped Drives", "Unable to read mapped drives.", parent=root)
        return

    if not mapped_entries:
        messagebox.showinfo("Mapped Drives", "No mapped drives found.", parent=root)
        return

    win = tk.Toplevel(root)
    win.title("Mapped Network Drives")
    win.geometry("420x360")
    win.configure(bg="white")
    win.transient(root)
    win.grab_set()

    tk.Label(
        win,
        text="Mapped Network Drives",
        font=("Segoe UI", 10, "bold"),
        bg="white"
    ).pack(pady=(10, 8))

    list_frame = tk.Frame(win, bg="white")
    list_frame.pack(fill="both", expand=True, padx=12, pady=(8, 8))

    for drive, remote in mapped_entries:
        tk.Label(
            list_frame,
            text=f"{drive} -> {remote}",
            font=("Segoe UI", 10),
            bg="white",
            anchor="w",
            justify="left",
            wraplength=370
        ).pack(fill="x", pady=2)

    status_var = tk.StringVar(value="Showing currently mapped drives.")
    tk.Label(win, textvariable=status_var, bg="white", fg="#aa0000", anchor="w", justify="left").pack(fill="x", padx=12, pady=(0, 6))

    button_row = tk.Frame(win, bg="white")
    button_row.pack(fill="x", padx=12, pady=(0, 12))

    tk.Button(
        button_row,
        text="Close",
        width=12,
        command=win.destroy,
        bg="#d9d9d9",
        activebackground="#c0c0c0",
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2"
    ).pack(side="left")

def discover_server_shares(server_name):
    shares = get_server_share_names(server_name) or []

    if not shares:
        try:
            server_root = Path(server_name)
            for child in server_root.iterdir():
                name = child.name
                if name and not name.endswith("$"):
                    shares.append(name)
        except OSError:
            shares = []

    if not shares:
        shares_result = run_net_command(f"net view {server_name}")

        if shares_result.returncode == 0:
            in_table = False
            header_skipped = False
            for raw_line in shares_result.stdout.splitlines():
                line = raw_line.rstrip()
                stripped = line.strip()

                if not stripped:
                    continue

                if not in_table:
                    if set(stripped) == {"-"}:
                        in_table = True
                        header_skipped = False
                    continue

                if stripped.lower().startswith("the command completed"):
                    break

                if not header_skipped:
                    header_skipped = True
                    continue

                cols = re.split(r"\s{2,}", stripped)
                if cols:
                    shares.append(cols[0])

    return list(dict.fromkeys(shares))

def map_network_drive(root, on_drive_changed):
    global session_logged_in, session_username, session_password

    if not session_logged_in:
        messagebox.showerror("Login Required", "Please log in first.")
        return

    shares = discover_server_shares(default_server_name)

    mapped_entries = get_mapped_network_drives() or []
    mapped_share_names = set()
    current_server = default_server_name.lstrip("\\").lower()

    for _, remote in mapped_entries:
        parts = remote.strip("\\").split("\\")
        if len(parts) >= 2 and parts[0].lower() == current_server:
            mapped_share_names.add(parts[1].lower())

    shares = [share for share in shares if share.lower() not in mapped_share_names]

    if not shares:
        messagebox.showinfo("No Shares Found", f"No unmapped disk shares found on {default_server_name}.")
        return

    # 2) Build selection window
    win = tk.Toplevel(root)
    win.title("Map Network Drives")
    win.geometry("420x440")
    win.configure(bg="white")
    win.transient(root)
    win.grab_set()

    tk.Label(
        win,
        text=f"Server: {default_server_name}",
        font=("Segoe UI", 10, "bold"),
        bg="white"
    ).pack(pady=(10, 8))

    list_frame = tk.Frame(win, bg="white")
    list_frame.pack(fill="both", expand=True, padx=12, pady=(8, 8))

    table_frame = tk.Frame(list_frame, bg="white")
    table_frame.pack(anchor="center")

    tk.Label(table_frame, text="Select Drive Letter", bg="white", font=("Segoe UI", 10, "bold"), justify="center").grid(row=0, column=0, sticky="n", padx=(0, 12), pady=(0, 6))
    tk.Label(table_frame, text="Select Shared Folders to Map", bg="white", font=("Segoe UI", 10, "bold"), justify="center").grid(row=0, column=1, sticky="n", padx=(12, 0), pady=(0, 6))

    table_frame.grid_columnconfigure(0, weight=0)
    table_frame.grid_columnconfigure(1, weight=1)

    available_letters = get_available_mapping_letters()
    if not available_letters:
        messagebox.showerror(
            "No Drive Letters Available",
            "No available drive letters to map. Please unmap an existing drive first.",
            parent=win
        )
        win.destroy()
        return

    row_models = []
    for idx, share in enumerate(shares, start=1):
        drive_var = tk.StringVar()
        selected_var = tk.BooleanVar(value=False)

        drive_combo = ttk.Combobox(
            table_frame,
            textvariable=drive_var,
            width=3,
            state="readonly",
            values=available_letters
        )
        drive_combo.grid(row=idx, column=0, sticky="n", pady=2, padx=(0, 12))
        drive_combo.set(available_letters[0])

        cb = tk.Checkbutton(
            table_frame,
            text=share,
            variable=selected_var,
            bg="white",
            activebackground="white",
            anchor="w",
            justify="left",
            wraplength=240
        )
        cb.grid(row=idx, column=1, sticky="w", padx=(12, 0), pady=2)

        row_models.append((share, selected_var, drive_var, drive_combo))

    status_var = tk.StringVar(value="Select one or more shares and enter drive letters.")
    status_label = tk.Label(win, textvariable=status_var, bg="white", fg="#aa0000", anchor="w", justify="left")
    status_label.pack(fill="x", padx=12, pady=(0, 6))

    button_row = tk.Frame(win, bg="white")
    button_row.pack(fill="x", padx=12, pady=(0, 12))

    map_btn = tk.Button(
        button_row,
        text="Map",
        state="disabled",
        width=16,
        bg="#d9d9d9",
        activebackground="#c0c0c0",
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2"
    )
    map_btn.pack(side="left")

    tk.Button(
        button_row,
        text="Cancel",
        width=12,
        command=win.destroy,
        bg="#d9d9d9",
        activebackground="#c0c0c0",
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2"
    ).pack(side="left", padx=(8, 0))

    def validate_selection(*_):
        selected_rows = [(s, sv, dv) for (s, sv, dv, _) in row_models if sv.get()]
        if not selected_rows:
            status_var.set("Select at least one shared folder.")
            map_btn.config(state="disabled", bg="#d9d9d9", activebackground="#c0c0c0", fg="black")
            return

        used_letters = get_current_mapped_letters()
        typed_letters = set()

        for share_name, _, drive_var_ref in selected_rows:
            drive = normalize_drive_letter(drive_var_ref.get())
            if not drive:
                status_var.set(f"Enter a valid drive letter for '{share_name}' (example: Z)")
                map_btn.config(state="disabled", bg="#d9d9d9", activebackground="#c0c0c0", fg="black")
                return
            if drive in used_letters or Path(f"{drive}\\").exists():
                status_var.set(f"{drive} is already in use. Choose another letter.")
                map_btn.config(state="disabled", bg="#d9d9d9", activebackground="#c0c0c0", fg="black")
                return
            if drive in typed_letters:
                status_var.set(f"{drive} is duplicated in your selections.")
                map_btn.config(state="disabled", bg="#d9d9d9", activebackground="#c0c0c0", fg="black")
                return
            typed_letters.add(drive)

        status_var.set("Ready to map.")
        map_btn.config(state="normal", bg="#4caf50", activebackground="#43a047", fg="white")

    for _, selected_var, drive_var, drive_combo in row_models:
        selected_var.trace_add("write", validate_selection)
        drive_var.trace_add("write", validate_selection)
        drive_combo.bind("<<ComboboxSelected>>", validate_selection)

    def do_map():
        validate_selection()
        if str(map_btn["state"]) == "disabled":
            return

        username = session_username
        password = session_password
        success_drive_letters = []
        failed_results = []

        for share_name, selected_var, drive_var, _ in row_models:
            if not selected_var.get():
                continue

            drive = normalize_drive_letter(drive_var.get())
            remote_path = fr"{default_server_name}\{share_name}"

            cmd = [
                "net", "use",
                drive,
                remote_path,
                password,
                f"/user:{username}",
                "/persistent:yes"
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)

            if r.returncode == 0:
                success_drive_letters.append(drive.rstrip(':'))
            else:
                err = r.stderr.strip() or r.stdout.strip() or "Unknown error"
                failed_results.append(f"{share_name} -> {drive.rstrip(':')}: {err}")

        on_drive_changed()
        if success_drive_letters and not failed_results:
            messagebox.showinfo(
                "Mapping Results",
                "Successfully mapped drives: " + " ".join(success_drive_letters),
                parent=win
            )
        elif success_drive_letters and failed_results:
            messagebox.showwarning(
                "Mapping Results",
                "Successfully mapped drives: "
                + " ".join(success_drive_letters)
                + "\n\nFailed to map\n"
                + "\n".join(failed_results),
                parent=win
            )
        else:
            messagebox.showerror(
                "Mapping Results",
                "Failed to map\n" + "\n".join(failed_results),
                parent=win
            )
        win.destroy()

    map_btn.config(command=do_map)
    validate_selection()

def unmap_network_drive(root, on_drive_changed):
    mapped_entries = get_mapped_network_drives()
    if mapped_entries is None:
        messagebox.showerror("Unmapping Failed", "Unable to read mapped drives.")
        return

    if not mapped_entries:
        messagebox.showinfo("No Mapped Drives", "There are no mapped network drives to unmap.")
        return

    win = tk.Toplevel(root)
    win.title("Unmap Network Drives")
    win.geometry("420x420")
    win.configure(bg="white")
    win.transient(root)
    win.grab_set()

    tk.Label(
        win,
        text="Select Mapped Drives to Unmap",
        font=("Segoe UI", 10, "bold"),
        bg="white"
    ).pack(pady=(10, 8))

    list_frame = tk.Frame(win, bg="white")
    list_frame.pack(fill="both", expand=True, padx=12, pady=(8, 8))

    row_models = []
    for drive, remote in mapped_entries:
        selected_var = tk.BooleanVar(value=False)
        cb = tk.Checkbutton(
            list_frame,
            text=f"{drive} -> {remote}",
            variable=selected_var,
            bg="white",
            activebackground="white",
            anchor="w",
            justify="left",
            wraplength=370
        )
        cb.pack(fill="x", pady=2, anchor="w")
        row_models.append((drive, selected_var))

    status_var = tk.StringVar(value="Select one or more mapped drives.")
    status_label = tk.Label(win, textvariable=status_var, bg="white", fg="#aa0000", anchor="w", justify="left")
    status_label.pack(fill="x", padx=12, pady=(0, 6))

    button_row = tk.Frame(win, bg="white")
    button_row.pack(fill="x", padx=12, pady=(0, 12))

    unmap_btn = tk.Button(
        button_row,
        text="Unmap",
        state="disabled",
        width=16,
        bg="#d9d9d9",
        activebackground="#c0c0c0",
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2"
    )
    unmap_btn.pack(side="left")

    tk.Button(
        button_row,
        text="Cancel",
        width=12,
        command=win.destroy,
        bg="#d9d9d9",
        activebackground="#c0c0c0",
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2"
    ).pack(side="left", padx=(8, 0))

    def validate_unmap_selection(*_):
        selected = [drive for drive, selected_var in row_models if selected_var.get()]
        if not selected:
            status_var.set("Select at least one mapped drive.")
            unmap_btn.config(state="disabled", bg="#d9d9d9", activebackground="#c0c0c0", fg="black")
            return

        status_var.set("Ready to unmap.")
        unmap_btn.config(state="normal", bg="#4caf50", activebackground="#43a047", fg="white")

    for _, selected_var in row_models:
        selected_var.trace_add("write", validate_unmap_selection)

    def do_unmap():
        validate_unmap_selection()
        if str(unmap_btn["state"]) == "disabled":
            return

        selected = [drive for drive, selected_var in row_models if selected_var.get()]
        success_results = []
        failed_results = []

        for drive in selected:
            cmd = ["net", "use", drive, "/delete", "/y"]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                success_results.append(drive.rstrip(':'))
            else:
                err = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                failed_results.append(f"{drive.rstrip(':')}: {err}")

        on_drive_changed()

        if success_results and not failed_results:
            messagebox.showinfo(
                "Unmapping Results",
                "Successfully unmapped drives: " + " ".join(success_results),
                parent=win
            )
        elif success_results and failed_results:
            messagebox.showwarning(
                "Unmapping Results",
                "Successfully unmapped drives: "
                + " ".join(success_results)
                + "\n\nFailed to unmap\n"
                + "\n".join(failed_results),
                parent=win
            )
        else:
            messagebox.showerror(
                "Unmapping Results",
                "Failed to unmap\n" + "\n".join(failed_results),
                parent=win
            )

        win.destroy()

    unmap_btn.config(command=do_unmap)
    validate_unmap_selection()

def run_archiver(root):
    if not session_logged_in:
        messagebox.showerror("Login Required", "Please log in first.", parent = root)
        return

    archiver_window = tk.Toplevel(root)
    archiver_window.title("Run Archiver")
    archiver_window.geometry("560x680")
    archiver_window.configure(bg = "white")
    archiver_window.transient(root)
    archiver_window.grab_set()

    selected_files = []
    top_directories = discover_server_shares(default_server_name)
    selected_directory_var = tk.StringVar(value = "")
    selected_subdirectory_var = tk.StringVar(value = "")
    destination_preview_var = tk.StringVar()
    status_var = tk.StringVar(value = "0 files ready")

    container = tk.Frame(archiver_window, bg = "white", padx = 18, pady = 16)
    container.pack(fill = "both", expand = True)

    button_row = tk.Frame(container, bg = "white")
    button_row.pack(fill = "x", pady = (0, 10))

    selected_files_list = tk.Frame(container, bg = "white")

    def update_preview_and_status(*_):
        topdir = selected_directory_var.get().strip()
        subdir = selected_subdirectory_var.get().strip()
        preview_parts = [get_drive_target(), "Archive"]
        if topdir:
            preview_parts.append(topdir)
        if subdir:
            preview_parts.append(subdir)
        preview_parts.append(str(date.today().year))
        destination_preview_var.set("/".join(preview_parts) + "/")
        status_var.set(f"{len(selected_files)} files ready")

    def get_share_subdirectories(share_name):
        cleaned_share = share_name.strip()
        if not cleaned_share:
            return []

        share_root = Path(fr"{default_server_name}\{cleaned_share}")
        try:
            subdirs = [child.name for child in share_root.iterdir() if child.is_dir()]
        except OSError:
            return []

        return sorted(subdirs, key = str.casefold)

    def refresh_subdirectory_options(*_):
        selected_share = selected_directory_var.get().strip()
        selected_subdirectory_var.set("")

        if not selected_share:
            subdirectory_combo.config(values = [], state = "disabled")
            update_preview_and_status()
            return

        subdirs = get_share_subdirectories(selected_share)
        subdirectory_combo.config(values = subdirs, state = "readonly")
        update_preview_and_status()

    def remove_selected_file(file_path):
        if file_path in selected_files:
            selected_files.remove(file_path)
            refresh_selected_files_view()

    def refresh_selected_files_view():
        for child in selected_files_list.winfo_children():
            child.destroy()

        for file_path in selected_files:
            row = tk.Frame(selected_files_list, bg = "white")
            row.pack(fill = "x", pady = 1)

            tk.Label(
                row,
                text = f"- {Path(file_path).name}",
                font = ("Segoe UI", 9),
                bg = "white",
                fg = "#333333",
                anchor = "w",
                justify = "left"
            ).pack(side = "left", fill = "x", expand = True)

            tk.Button(
                row,
                text = "x",
                width = 2,
                bg = "white",
                activebackground = "#efefef",
                fg = "#666666",
                relief = "flat",
                bd = 0,
                highlightthickness = 0,
                cursor = "hand2",
                command = lambda p = file_path: remove_selected_file(p)
            ).pack(side = "right")

        update_preview_and_status()

    def add_file_paths(paths):
        normalized_paths = []
        for raw_path in paths:
            candidate = str(raw_path).strip().strip("{}")
            if candidate and Path(candidate).is_file():
                normalized_paths.append(str(Path(candidate)))

        if not normalized_paths:
            return

        seen = set(selected_files)
        for file_path in normalized_paths:
            if file_path not in seen:
                selected_files.append(file_path)
                seen.add(file_path)

        refresh_selected_files_view()

    def add_folder_paths(folder_paths):
        discovered_files = []
        for raw_folder in folder_paths:
            folder_candidate = str(raw_folder).strip().strip("{}")
            folder_path = Path(folder_candidate)
            if folder_candidate and folder_path.is_dir():
                discovered_files.extend(str(p) for p in folder_path.rglob("*") if p.is_file())

        add_file_paths(discovered_files)

    def pick_files():
        files = filedialog.askopenfilenames(parent = archiver_window, title = "Add files")
        if files:
            add_file_paths(files)

    def pick_folder():
        folder = filedialog.askdirectory(parent = archiver_window, title = "Add folder")
        if folder:
            add_folder_paths([folder])

    def handle_drop(event):
        dropped_items = archiver_window.tk.splitlist(event.data)
        file_items = []
        folder_items = []

        for item in dropped_items:
            normalized_item = str(item).strip().strip("{}")
            if not normalized_item:
                continue
            path_obj = Path(normalized_item)
            if path_obj.is_file():
                file_items.append(normalized_item)
            elif path_obj.is_dir():
                folder_items.append(normalized_item)

        if file_items:
            add_file_paths(file_items)
        if folder_items:
            add_folder_paths(folder_items)

        return event.action if hasattr(event, "action") else None

    tk.Button(
        button_row,
        text = "Add Files",
        width = 16,
        bg = "#d9d9d9",
        activebackground = "#c0c0c0",
        fg = "black",
        activeforeground = "black",
        relief = "flat",
        bd = 0,
        highlightthickness = 0,
        cursor = "hand2",
        command = pick_files
    ).pack(side = "left")

    tk.Button(
        button_row,
        text = "Add Folder",
        width = 16,
        bg = "#d9d9d9",
        activebackground = "#c0c0c0",
        fg = "black",
        activeforeground = "black",
        relief = "flat",
        bd = 0,
        highlightthickness = 0,
        cursor = "hand2",
        command = pick_folder
    ).pack(side = "left", padx = (8, 0))

    attachment_canvas = tk.Canvas(
        container,
        height = 94,
        bg = "white",
        highlightthickness = 0,
        bd = 0,
        cursor = "hand2"
    )
    attachment_canvas.pack(fill = "x", pady = (0, 12))

    attachment_canvas.create_rectangle(
        8,
        8,
        508,
        86,
        dash = (3, 3),
        outline = "#9a9a9a",
        width = 1
    )
    attachment_canvas.create_text(
        258,
        47,
        text = "Click to add or drop files",
        fill = "#666666",
        font = ("Segoe UI", 10)
    )
    attachment_canvas.bind("<Button-1>", lambda _event: pick_files())

    if TkinterDnD is not None and hasattr(attachment_canvas, "drop_target_register"):
        attachment_canvas.drop_target_register(DND_FILES)
        attachment_canvas.dnd_bind("<<Drop>>", handle_drop)

    tk.Label(
        container,
        text = "Selected files:",
        font = ("Segoe UI", 10, "bold"),
        bg = "white",
        anchor = "w"
    ).pack(fill = "x", pady = (0, 4))

    selected_files_list.pack(fill = "x", pady = (0, 12))

    top_directory_row = tk.Frame(container, bg = "white")
    top_directory_row.pack(fill = "x", pady = (0, 10))

    tk.Label(
        top_directory_row,
        text = "Top Directory:",
        font = ("Segoe UI", 10),
        bg = "white",
        width = 15,
        anchor = "w"
    ).pack(side = "left")

    top_directory_combo = ttk.Combobox(
        top_directory_row,
        textvariable = selected_directory_var,
        width = 34,
        state = "readonly",
        values = top_directories
    )
    top_directory_combo.pack(side = "left", fill = "x", expand = True)

    subdirectory_row = tk.Frame(container, bg = "white")
    subdirectory_row.pack(fill = "x", pady = (0, 10))

    tk.Label(
        subdirectory_row,
        text = "Subdirectory:",
        font = ("Segoe UI", 10),
        bg = "white",
        width = 15,
        anchor = "w"
    ).pack(side = "left")

    subdirectory_combo = ttk.Combobox(
        subdirectory_row,
        textvariable = selected_subdirectory_var,
        width = 22,
        values = [],
        state = "disabled"
    )
    subdirectory_combo.pack(side = "left")

    tk.Label(
        subdirectory_row,
        text = "or type new subfolder",
        font = ("Segoe UI", 9),
        bg = "white",
        fg = "#666666"
    ).pack(side = "left", padx = (8, 0))

    preview_frame = tk.Frame(container, bg = "white")
    preview_frame.pack(fill = "x", pady = (0, 10))

    tk.Label(
        preview_frame,
        text = "Destination Preview:",
        font = ("Segoe UI", 10),
        bg = "white",
        anchor = "w"
    ).pack(fill = "x")

    tk.Label(
        preview_frame,
        textvariable = destination_preview_var,
        font = ("Segoe UI", 10),
        bg = "white",
        fg = "#333333",
        anchor = "w"
    ).pack(fill = "x", pady = (2, 0))

    tk.Button(
        container,
        text = "Archive Files",
        width = 24,
        bg = "#d9d9d9",
        activebackground = "#c0c0c0",
        fg = "black",
        activeforeground = "black",
        relief = "flat",
        bd = 0,
        highlightthickness = 0,
        cursor = "hand2",
        command = lambda: None
    ).pack(pady = (6, 10))

    tk.Label(
        container,
        text = "Status:",
        font = ("Segoe UI", 10),
        bg = "white",
        anchor = "w"
    ).pack(fill = "x")

    tk.Label(
        container,
        textvariable = status_var,
        font = ("Segoe UI", 10),
        bg = "white",
        fg = "#666666",
        anchor = "w"
    ).pack(fill = "x", pady = (2, 0))

    selected_directory_var.trace_add("write", refresh_subdirectory_options)
    selected_subdirectory_var.trace_add("write", update_preview_and_status)
    top_directory_combo.bind("<<ComboboxSelected>>", refresh_subdirectory_options)
    subdirectory_combo.bind("<<ComboboxSelected>>", update_preview_and_status)
    refresh_subdirectory_options()
    update_preview_and_status()

def admin(root, on_path_changed):

    admin_window = tk.Toplevel(root)
    admin_window.title("Admin Settings")
    admin_window.geometry("300x100")
    admin_window.configure(bg = "white")
    admin_window.resizable(False, False)
    admin_window.transient(root)
    admin_window.grab_set()

    def change_server_name():
        global default_server_name

        current_name = default_server_name.lstrip("\\")

        new_name = simpledialog.askstring(
            "Change Server Name",
            "Enter new server name:",
            parent = admin_window,
            initialvalue = current_name
        )
        if not new_name:
            return
        
        cleaned_name = new_name.strip().lstrip("\\")
        if not cleaned_name:
            return
        default_server_name = f"\\\\{cleaned_name}"

        on_path_changed()
        messagebox.showinfo(
            "Server Name Updated",
            f"New server name set to:\n{default_server_name}",
            parent = admin_window
        )

    tk.Button(
        admin_window,
        text = "Change Server Name",
        width = 24,
        height = 2,
        bg = "#d9d9d9",
        activebackground = "#c0c0c0",
        fg = "black",
        activeforeground = "black",
        relief = "flat",
        bd = 0,
        highlightthickness = 0,
        cursor = "hand2",
        command = change_server_name
    ).pack(pady = 6)

    tk.Button(
        admin_window,
        text = "Map Network Drive",
        width = 24,
        height = 2,
        bg = "#d9d9d9",
        activebackground = "#c0c0c0",
        fg = "black",
        activeforeground = "black",
        relief = "flat",
        bd = 0,
        highlightthickness = 0,
        cursor = "hand2",
        command = lambda: map_network_drive(admin_window)
    ).pack(pady = 6)

    tk.Button(
        admin_window,
        text = "Unmap Network Drive",
        width = 24,
        height = 2,
        bg = "#d9d9d9",
        activebackground = "#c0c0c0",
        fg = "black",
        activeforeground = "black",
        relief = "flat",
        bd = 0,
        highlightthickness = 0,
        cursor = "hand2",
        command = lambda: unmap_network_drive(admin_window)
    ).pack(pady = 6)

    tk.Button(
        admin_window,
        text = "Show Mapped Drive(s)",
        width = 24,
        height = 2,
        bg = "#d9d9d9",
        activebackground = "#c0c0c0",
        fg = "black",
        activeforeground = "black",
        relief = "flat",
        bd = 0,
        highlightthickness = 0,
        cursor = "hand2",
        command = lambda: show_mapped_drives_window(admin_window)
    ).pack(pady = 6)

class SequenceArchiverApp:
    def __init__(self):
        self.root = TkinterDnD.Tk() if TkinterDnD is not None else tk.Tk()
        self.root.geometry("620x740")
        self.root.configure(bg="white")
        self.root.resizable(False, False)

    def clear_screen(self):
        for child in self.root.winfo_children():
            child.destroy()

    def get_connection_snapshot(self):
        is_connected, ip_addr = check_server_availability(default_server_name)
        status_text = "Connected" if is_connected else "Unavailable"
        return is_connected, ip_addr, status_text

    def logout_and_return_to_login(self):
        global active_workspace

        subprocess.run(
            ["net", "use", fr"{default_server_name}\IPC$", "/delete", "/y"],
            capture_output=True,
            text=True
        )
        clear_session_login()
        active_workspace = ""
        self.show_login_screen()

    def leave_workspace(self):
        global active_workspace
        active_workspace = ""
        self.show_main_archiver_screen()

    def show_startup_screen(self):
        self.root.title("APPLEMANGO ARCHIVER")
        self.route_from_startup()

    def route_from_startup(self):
        saved = load_saved_credentials()
        if not saved:
            self.show_login_screen()
            return

        ok, _ = authenticate_to_server(saved["username"], saved["password"])
        if ok:
            update_session_login(saved["username"], saved["password"])
            self.show_main_archiver_screen()
            return

        clear_saved_credentials()
        clear_session_login()
        self.show_login_screen()

    def show_login_screen(self):
        self.root.title("APPLEMANGO ARCHIVER - Login")
        self.clear_screen()

        container = tk.Frame(self.root, padx=24, pady=28, bg="white")
        container.pack(fill="both", expand=True)

        tk.Label(container, text="APPLEMANGO ARCHIVER", font=("Segoe UI", 16, "bold"), bg="white").pack(pady=(0, 18))
        tk.Label(container, text="Login", font=("Segoe UI", 12, "bold"), bg="white").pack(anchor="w", pady=(0, 8))

        username_var = tk.StringVar(value=session_username)
        password_var = tk.StringVar()
        remember_var = tk.BooleanVar(value=load_saved_credentials() is not None)

        tk.Label(container, text="Username", font=("Segoe UI", 10), bg="white", anchor="w").pack(fill="x", pady=(8, 2))
        tk.Entry(container, textvariable=username_var, font=("Segoe UI", 10)).pack(fill="x")

        tk.Label(container, text="Password", font=("Segoe UI", 10), bg="white", anchor="w").pack(fill="x", pady=(10, 2))
        tk.Entry(container, textvariable=password_var, show="*", font=("Segoe UI", 10)).pack(fill="x")

        tk.Checkbutton(
            container,
            text="Remember Credentials",
            variable=remember_var,
            bg="white",
            activebackground="white"
        ).pack(anchor="w", pady=(10, 12))

        button_row = tk.Frame(container, bg="white")
        button_row.pack(fill="x")

        def submit_login():
            username = username_var.get().strip()
            password = password_var.get()
            if not username or not password:
                messagebox.showerror("Login", "Username and password are required.", parent=self.root)
                return

            ok, err = authenticate_to_server(username, password)
            if not ok:
                clear_session_login()
                messagebox.showerror("Login Failed", err, parent=self.root)
                return

            update_session_login(username, password)
            if remember_var.get():
                save_credentials(username, password)
            else:
                clear_saved_credentials()

            self.show_main_archiver_screen()

        tk.Button(
            button_row,
            text="Login",
            width=18,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=submit_login
        ).pack(side="left")

        tk.Button(
            button_row,
            text="Exit",
            width=18,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self.root.destroy
        ).pack(side="left", padx=(8, 0))

    def show_workspace_selection_screen(self):
        global active_workspace

        self.root.title("APPLEMANGO ARCHIVER - Workspace Selection")
        self.clear_screen()

        _, ip_addr, status_text = self.get_connection_snapshot()
        shares = discover_server_shares(default_server_name)

        container = tk.Frame(self.root, padx=24, pady=28, bg="white")
        container.pack(fill="both", expand=True)

        tk.Label(container, text="Workspace Selection", font=("Segoe UI", 14, "bold"), bg="white").pack(anchor="w", pady=(0, 12))
        tk.Label(container, text=f"Server: {default_server_name}", font=("Segoe UI", 10), bg="white", anchor="w").pack(fill="x")
        tk.Label(container, text=f"IP Address: {ip_addr}", font=("Segoe UI", 10), bg="white", anchor="w").pack(fill="x")
        tk.Label(container, text=f"Connection Status: {status_text}", font=("Segoe UI", 10), bg="white", anchor="w").pack(fill="x", pady=(0, 12))

        workspace_var = tk.StringVar(value=active_workspace if active_workspace in shares else "")

        tk.Label(container, text="Select Workspace", font=("Segoe UI", 10), bg="white", anchor="w").pack(fill="x", pady=(10, 4))
        workspace_combo = ttk.Combobox(container, textvariable=workspace_var, values=shares, state="readonly", width=48)
        workspace_combo.pack(fill="x")

        if shares and not workspace_var.get():
            workspace_combo.current(0)

        button_row = tk.Frame(container, bg="white")
        button_row.pack(fill="x", pady=(16, 0))

        def enter_workspace():
            global active_workspace

            selected = workspace_var.get().strip()
            if not selected:
                messagebox.showerror("Workspace", "Please select a workspace.", parent=self.root)
                return

            active_workspace = selected
            self.show_workspace_archiver_screen()

        tk.Button(
            button_row,
            text="Enter Workspace",
            width=20,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=enter_workspace
        ).pack(side="left")

        tk.Button(
            button_row,
            text="Logout",
            width=20,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self.logout_and_return_to_login
        ).pack(side="left", padx=(8, 0))

        tk.Button(
            button_row,
            text="Back",
            width=20,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self.show_main_archiver_screen
        ).pack(side="left", padx=(8, 0))

    def get_share_root_path(self, share_name, mapped_drive=None):
        if mapped_drive:
            return Path(f"{mapped_drive}\\")
        return Path(fr"{default_server_name}\{share_name}")

    def find_mapped_drive_for_share(self, share_name):
        target_remote = fr"{default_server_name}\{share_name}".lower().rstrip("\\/")
        entries = get_mapped_network_drives() or []
        for drive, remote in entries:
            if remote.lower().rstrip("\\/") == target_remote:
                return drive
        return None

    def map_share_with_next_available_letter(self, share_name):
        if not session_logged_in:
            return None, "Please log in first."

        existing = self.find_mapped_drive_for_share(share_name)
        if existing:
            return existing, ""

        available_letters = get_available_mapping_letters()
        if not available_letters:
            return None, "No available drive letters to map this shared folder."

        drive = f"{available_letters[0]}:"
        remote_path = fr"{default_server_name}\{share_name}"

        cmd = [
            "net", "use",
            drive,
            remote_path,
            session_password,
            f"/user:{session_username}",
            "/persistent:yes"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            return drive, ""

        err = result.stderr.strip() or result.stdout.strip() or "Unknown error"
        return None, err

    def unmap_drive_letter(self, drive_letter):
        drive = normalize_drive_letter(drive_letter or "")
        if not drive:
            return False, "Invalid drive letter."

        result = subprocess.run(
            ["net", "use", drive, "/delete", "/y"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return True, ""

        err = result.stderr.strip() or result.stdout.strip() or "Unknown error"
        return False, err

    def show_archive_architecture_screen(self):
        self.root.title("APPLEMANGO ARCHIVER - Archive Architecture")
        self.clear_screen()

        _, ip_addr, status_text = self.get_connection_snapshot()
        shares = discover_server_shares(default_server_name)

        container = tk.Frame(self.root, padx=24, pady=28, bg="white")
        container.pack(fill="both", expand=True)

        tk.Label(container, text="Archive Architecture", font=("Segoe UI", 14, "bold"), bg="white").pack(anchor="w", pady=(0, 12))
        tk.Label(container, text=f"Server: {default_server_name}", font=("Segoe UI", 10), bg="white", anchor="w").pack(fill="x")
        tk.Label(container, text=f"IP Address: {ip_addr}", font=("Segoe UI", 10), bg="white", anchor="w").pack(fill="x")
        tk.Label(container, text=f"Connection Status: {status_text}", font=("Segoe UI", 10), bg="white", anchor="w").pack(fill="x", pady=(0, 12))

        share_var = tk.StringVar(value=shares[0] if shares else "")

        tk.Label(container, text="Select Shared Folder", font=("Segoe UI", 10), bg="white", anchor="w").pack(fill="x", pady=(10, 4))
        share_combo = ttk.Combobox(container, textvariable=share_var, values=shares, state="readonly", width=48)
        share_combo.pack(fill="x")

        button_row = tk.Frame(container, bg="white")
        button_row.pack(fill="x", pady=(16, 0))

        def open_share_tree():
            selected_share = share_var.get().strip()
            if not selected_share:
                messagebox.showerror("Archive Architecture", "Please select a shared folder.", parent=self.root)
                return
            self.show_share_tree_screen(selected_share)

        tk.Button(
            button_row,
            text="View Tree",
            width=20,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=open_share_tree
        ).pack(side="left")

        tk.Button(
            button_row,
            text="Back",
            width=20,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self.show_main_archiver_screen
        ).pack(side="left", padx=(8, 0))

        tk.Button(
            button_row,
            text="Logout",
            width=20,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self.logout_and_return_to_login
        ).pack(side="left", padx=(8, 0))

    def show_share_tree_screen(self, share_name):
        self.root.title(f"APPLEMANGO ARCHIVER - {share_name} Tree")
        self.clear_screen()

        page = tk.Frame(self.root, bg="white", padx=16, pady=16)
        page.pack(fill="both", expand=True)

        header = tk.LabelFrame(page, text="Shared Folder Tree", bg="white", padx=14, pady=10)
        header.pack(fill="x", pady=(0, 10))

        tk.Label(header, text=f"Server: {default_server_name}", bg="white", anchor="w").pack(fill="x", pady=2)
        tk.Label(header, text=f"Shared Folder: {share_name}", bg="white", anchor="w").pack(fill="x", pady=2)

        mapped_drive_var = tk.StringVar(value=self.find_mapped_drive_for_share(share_name) or "")
        status_var = tk.StringVar(value="View mode: browsing folder tree.")
        edit_enabled = tk.BooleanVar(value=bool(mapped_drive_var.get()))
        mapped_by_edit_mode = tk.BooleanVar(value=False)

        if mapped_drive_var.get():
            status_var.set(f"Edit mode ready via mapped drive {mapped_drive_var.get()}.")

        tk.Label(header, textvariable=status_var, bg="white", fg="#666666", anchor="w").pack(fill="x", pady=(2, 0))

        tree_frame = tk.Frame(page, bg="white")
        tree_frame.pack(fill="both", expand=True)

        tree = ttk.Treeview(tree_frame, columns=("path",), displaycolumns=())
        tree.pack(fill="both", expand=True, side="left")

        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        scroll.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scroll.set)

        def get_root_path():
            return self.get_share_root_path(share_name, mapped_drive_var.get() or None)

        def insert_directory_nodes(parent_item, directory_path):
            try:
                children = sorted(
                    [child for child in directory_path.iterdir() if child.is_dir()],
                    key=lambda p: p.name.casefold()
                )
            except OSError:
                return

            for child in children:
                child_item = tree.insert(parent_item, "end", text=child.name, values=(str(child),))
                insert_directory_nodes(child_item, child)

        def refresh_tree():
            tree.delete(*tree.get_children())
            share_root = get_root_path()
            root_item = tree.insert("", "end", text=share_name, values=(str(share_root),), open=True)
            insert_directory_nodes(root_item, share_root)
            tree.selection_set(root_item)

        def selected_directory_path():
            selection = tree.selection()
            if not selection:
                return get_root_path(), True

            item_id = selection[0]
            values = tree.item(item_id, "values")
            if not values:
                return get_root_path(), True

            selected_path = Path(values[0])
            is_root = selected_path.resolve() == get_root_path().resolve()
            return selected_path, is_root

        def enable_edit_actions(enabled):
            action_state = "normal" if enabled else "disabled"
            new_btn.config(state=action_state)
            rename_btn.config(state=action_state)
            delete_btn.config(state=action_state)

        def enter_edit_mode():
            was_already_mapped = bool(self.find_mapped_drive_for_share(share_name))
            drive, err = self.map_share_with_next_available_letter(share_name)
            if not drive:
                messagebox.showerror("Edit Mode", f"Unable to map shared folder:\n{err}", parent=self.root)
                return

            mapped_drive_var.set(drive)
            edit_enabled.set(True)
            status_var.set(f"Edit mode enabled via mapped drive {drive}.")
            mapped_by_edit_mode.set(not was_already_mapped)

            mapped_message = f"Shared folder '{share_name}' mapped as {drive}/"
            if was_already_mapped:
                mapped_message = f"Shared folder '{share_name}' is already mapped as {drive}/"
            messagebox.showinfo("Edit Mode", mapped_message, parent=self.root)

            edit_toggle_btn.config(text="Disable Edit", command=disable_edit_mode)
            enable_edit_actions(True)
            refresh_tree()

        def disable_edit_mode():
            drive = mapped_drive_var.get().strip()

            if mapped_by_edit_mode.get() and drive:
                ok, err = self.unmap_drive_letter(drive)
                if not ok:
                    messagebox.showerror("Disable Edit", f"Unable to unmap {drive}:\n{err}", parent=self.root)
                    return

            mapped_by_edit_mode.set(False)
            mapped_drive_var.set("")
            edit_enabled.set(False)
            status_var.set("View mode: browsing folder tree.")
            edit_toggle_btn.config(text="Enable Edit", command=enter_edit_mode)
            enable_edit_actions(False)
            refresh_tree()

        def cleanup_edit_mapping():
            drive = mapped_drive_var.get().strip()
            if mapped_by_edit_mode.get() and drive:
                self.unmap_drive_letter(drive)
            mapped_by_edit_mode.set(False)

        def create_subdirectory():
            parent_path, _ = selected_directory_path()
            name = simpledialog.askstring("New Subdirectory", "Enter new subdirectory name:", parent=self.root)
            if not name:
                return

            clean_name = name.strip()
            if not clean_name:
                return

            target = parent_path / clean_name
            if target.exists():
                messagebox.showerror("New Subdirectory", "A directory with that name already exists.", parent=self.root)
                return

            try:
                target.mkdir()
            except OSError as exc:
                messagebox.showerror("New Subdirectory", f"Failed to create directory:\n{exc}", parent=self.root)
                return

            refresh_tree()

        def rename_subdirectory():
            target_path, is_root = selected_directory_path()
            if is_root:
                messagebox.showerror("Rename Subdirectory", "Select a subdirectory to rename.", parent=self.root)
                return

            new_name = simpledialog.askstring("Rename Subdirectory", "Enter new name:", parent=self.root, initialvalue=target_path.name)
            if not new_name:
                return

            clean_name = new_name.strip()
            if not clean_name:
                return

            destination = target_path.parent / clean_name
            if destination.exists():
                messagebox.showerror("Rename Subdirectory", "A directory with that name already exists.", parent=self.root)
                return

            try:
                target_path.rename(destination)
            except OSError as exc:
                messagebox.showerror("Rename Subdirectory", f"Failed to rename directory:\n{exc}", parent=self.root)
                return

            refresh_tree()

        def delete_subdirectory():
            target_path, is_root = selected_directory_path()
            if is_root:
                messagebox.showerror("Delete Subdirectory", "Select a subdirectory to delete.", parent=self.root)
                return

            proceed = messagebox.askyesno(
                "Delete Subdirectory",
                f"Delete '{target_path.name}' and all nested subdirectories?",
                parent=self.root
            )
            if not proceed:
                return

            try:
                shutil.rmtree(target_path)
            except OSError as exc:
                messagebox.showerror("Delete Subdirectory", f"Failed to delete directory:\n{exc}", parent=self.root)
                return

            refresh_tree()

        action_row = tk.Frame(page, bg="white")
        action_row.pack(fill="x", pady=(10, 0))

        edit_toggle_btn = tk.Button(
            action_row,
            text="Enable Edit",
            width=14,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=enter_edit_mode
        )
        edit_toggle_btn.pack(side="left")

        new_btn = tk.Button(
            action_row,
            text="New Subdir",
            width=14,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=create_subdirectory
        )
        new_btn.pack(side="left", padx=(8, 0))

        rename_btn = tk.Button(
            action_row,
            text="Rename",
            width=14,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=rename_subdirectory
        )
        rename_btn.pack(side="left", padx=(8, 0))

        delete_btn = tk.Button(
            action_row,
            text="Delete",
            width=14,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=delete_subdirectory
        )
        delete_btn.pack(side="left", padx=(8, 0))

        nav_row = tk.Frame(page, bg="white")
        nav_row.pack(fill="x", pady=(10, 0))

        tk.Button(
            nav_row,
            text="Back to Shared Folders",
            width=24,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=lambda: (cleanup_edit_mapping(), self.show_archive_architecture_screen())
        ).pack(side="left")

        tk.Button(
            nav_row,
            text="Back to Main",
            width=20,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=lambda: (cleanup_edit_mapping(), self.show_main_archiver_screen())
        ).pack(side="left", padx=(8, 0))

        tk.Button(
            nav_row,
            text="Logout",
            width=20,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=lambda: (cleanup_edit_mapping(), self.logout_and_return_to_login())
        ).pack(side="left", padx=(8, 0))

        if edit_enabled.get():
            edit_toggle_btn.config(text="Disable Edit", command=disable_edit_mode)

        enable_edit_actions(edit_enabled.get())
        refresh_tree()

    def build_archiver_panel(self, parent):
        selected_files = []
        selected_subdirectory_var = tk.StringVar(value="")
        destination_preview_var = tk.StringVar()
        status_var = tk.StringVar(value="0 files ready")

        container = tk.Frame(parent, bg="white", padx=18, pady=16)
        container.pack(fill="both", expand=True)

        button_row = tk.Frame(container, bg="white")
        button_row.pack(fill="x", pady=(0, 10))

        selected_files_list = tk.Frame(container, bg="white")

        def update_preview_and_status(*_):
            subdir = selected_subdirectory_var.get().strip()
            preview_parts = [default_server_name, active_workspace]
            if subdir:
                preview_parts.append(subdir)
            preview_parts.append(str(date.today().year))
            destination_preview_var.set("/".join(preview_parts) + "/")
            status_var.set(f"{len(selected_files)} files ready")

        def get_workspace_subdirectories():
            if not active_workspace:
                return []

            workspace_root = Path(fr"{default_server_name}\{active_workspace}")
            try:
                subdirs = [child.name for child in workspace_root.iterdir() if child.is_dir()]
            except OSError:
                return []

            return sorted(subdirs, key=str.casefold)

        def remove_selected_file(file_path):
            if file_path in selected_files:
                selected_files.remove(file_path)
                refresh_selected_files_view()

        def refresh_selected_files_view():
            for child in selected_files_list.winfo_children():
                child.destroy()

            for file_path in selected_files:
                row = tk.Frame(selected_files_list, bg="white")
                row.pack(fill="x", pady=1)

                tk.Label(
                    row,
                    text=f"- {Path(file_path).name}",
                    font=("Segoe UI", 9),
                    bg="white",
                    fg="#333333",
                    anchor="w",
                    justify="left"
                ).pack(side="left", fill="x", expand=True)

                tk.Button(
                    row,
                    text="x",
                    width=2,
                    bg="white",
                    activebackground="#efefef",
                    fg="#666666",
                    relief="flat",
                    bd=0,
                    highlightthickness=0,
                    cursor="hand2",
                    command=lambda p=file_path: remove_selected_file(p)
                ).pack(side="right")

            update_preview_and_status()

        def add_file_paths(paths):
            normalized_paths = []
            for raw_path in paths:
                candidate = str(raw_path).strip().strip("{}")
                if candidate and Path(candidate).is_file():
                    normalized_paths.append(str(Path(candidate)))

            if not normalized_paths:
                return

            seen = set(selected_files)
            for file_path in normalized_paths:
                if file_path not in seen:
                    selected_files.append(file_path)
                    seen.add(file_path)

            refresh_selected_files_view()

        def add_folder_paths(folder_paths):
            discovered_files = []
            for raw_folder in folder_paths:
                folder_candidate = str(raw_folder).strip().strip("{}")
                folder_path = Path(folder_candidate)
                if folder_candidate and folder_path.is_dir():
                    discovered_files.extend(str(p) for p in folder_path.rglob("*") if p.is_file())

            add_file_paths(discovered_files)

        def pick_files():
            files = filedialog.askopenfilenames(parent=self.root, title="Add files")
            if files:
                add_file_paths(files)

        def pick_folder():
            folder = filedialog.askdirectory(parent=self.root, title="Add folder")
            if folder:
                add_folder_paths([folder])

        def handle_drop(event):
            dropped_items = self.root.tk.splitlist(event.data)
            file_items = []
            folder_items = []

            for item in dropped_items:
                normalized_item = str(item).strip().strip("{}")
                if not normalized_item:
                    continue
                path_obj = Path(normalized_item)
                if path_obj.is_file():
                    file_items.append(normalized_item)
                elif path_obj.is_dir():
                    folder_items.append(normalized_item)

            if file_items:
                add_file_paths(file_items)
            if folder_items:
                add_folder_paths(folder_items)

            return event.action if hasattr(event, "action") else None

        tk.Button(
            button_row,
            text="Add Files",
            width=16,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            fg="black",
            activeforeground="black",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=pick_files
        ).pack(side="left")

        tk.Button(
            button_row,
            text="Add Folder",
            width=16,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            fg="black",
            activeforeground="black",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=pick_folder
        ).pack(side="left", padx=(8, 0))

        attachment_canvas = tk.Canvas(
            container,
            height=94,
            bg="white",
            highlightthickness=0,
            bd=0,
            cursor="hand2"
        )
        attachment_canvas.pack(fill="x", pady=(0, 12))

        attachment_canvas.create_rectangle(8, 8, 538, 86, dash=(3, 3), outline="#9a9a9a", width=1)
        attachment_canvas.create_text(273, 47, text="Click to add or drop files", fill="#666666", font=("Segoe UI", 10))
        attachment_canvas.bind("<Button-1>", lambda _event: pick_files())

        if TkinterDnD is not None and hasattr(attachment_canvas, "drop_target_register"):
            attachment_canvas.drop_target_register(DND_FILES)
            attachment_canvas.dnd_bind("<<Drop>>", handle_drop)

        tk.Label(container, text="Selected files:", font=("Segoe UI", 10, "bold"), bg="white", anchor="w").pack(fill="x", pady=(0, 4))
        selected_files_list.pack(fill="x", pady=(0, 12))

        subdirectory_row = tk.Frame(container, bg="white")
        subdirectory_row.pack(fill="x", pady=(0, 10))

        tk.Label(subdirectory_row, text="Subdirectory:", font=("Segoe UI", 10), bg="white", width=15, anchor="w").pack(side="left")

        subdirectory_combo = ttk.Combobox(
            subdirectory_row,
            textvariable=selected_subdirectory_var,
            width=30,
            values=get_workspace_subdirectories(),
            state="readonly"
        )
        subdirectory_combo.pack(side="left")

        tk.Label(subdirectory_row, text="or type new subfolder", font=("Segoe UI", 9), bg="white", fg="#666666").pack(side="left", padx=(8, 0))

        preview_frame = tk.Frame(container, bg="white")
        preview_frame.pack(fill="x", pady=(0, 10))

        tk.Label(preview_frame, text="Destination Preview:", font=("Segoe UI", 10), bg="white", anchor="w").pack(fill="x")
        tk.Label(preview_frame, textvariable=destination_preview_var, font=("Segoe UI", 10), bg="white", fg="#333333", anchor="w").pack(fill="x", pady=(2, 0))

        tk.Button(
            container,
            text="Archive Files",
            width=24,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            fg="black",
            activeforeground="black",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=lambda: None
        ).pack(pady=(6, 10))

        tk.Label(container, text="Status:", font=("Segoe UI", 10), bg="white", anchor="w").pack(fill="x")
        tk.Label(container, textvariable=status_var, font=("Segoe UI", 10), bg="white", fg="#666666", anchor="w").pack(fill="x", pady=(2, 0))

        selected_subdirectory_var.trace_add("write", update_preview_and_status)
        subdirectory_combo.bind("<<ComboboxSelected>>", update_preview_and_status)
        update_preview_and_status()

    def show_workspace_archiver_screen(self):
        self.root.title("APPLEMANGO ARCHIVER - Workspace")
        self.clear_screen()

        _, ip_addr, status_text = self.get_connection_snapshot()

        page = tk.Frame(self.root, bg="white", padx=16, pady=16)
        page.pack(fill="both", expand=True)

        header = tk.LabelFrame(page, text="Workspace Archiver", bg="white", padx=14, pady=10)
        header.pack(fill="x", pady=(0, 10))

        tk.Label(header, text=f"Logged-in Username: {session_account_name or session_username}", bg="white", anchor="w").pack(fill="x", pady=2)
        tk.Label(header, text=f"Server Name: {default_server_name}", bg="white", anchor="w").pack(fill="x", pady=2)
        tk.Label(header, text=f"IP Address: {ip_addr}", bg="white", anchor="w").pack(fill="x", pady=2)
        tk.Label(header, text=f"Current Workspace: {active_workspace or 'Not selected'}", bg="white", anchor="w").pack(fill="x", pady=2)
        tk.Label(header, text=f"Connection Status: {status_text}", bg="white", anchor="w").pack(fill="x", pady=2)

        action_row = tk.Frame(header, bg="white")
        action_row.pack(anchor="e", pady=(8, 0))

        tk.Button(
            action_row,
            text="Leave Workspace",
            width=20,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self.leave_workspace
        ).pack(side="left")

        tk.Button(
            action_row,
            text="Back to Main",
            width=20,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self.show_main_archiver_screen
        ).pack(side="left", padx=(8, 0))

        tk.Button(
            action_row,
            text="Logout",
            width=20,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self.logout_and_return_to_login
        ).pack(side="left", padx=(8, 0))

        body = tk.Frame(page, bg="white")
        body.pack(fill="both", expand=True)
        self.build_archiver_panel(body)

    def show_main_archiver_screen(self):
        self.root.title("APPLEMANGO ARCHIVER - Main")
        self.clear_screen()

        _, ip_addr, status_text = self.get_connection_snapshot()

        page = tk.Frame(self.root, bg="white", padx=24, pady=28)
        page.pack(fill="both", expand=True)

        tk.Label(page, text="APPLEMANGO ARCHIVER", font=("Segoe UI", 16, "bold"), bg="white", anchor="center", justify="center").pack(pady=(0, 10))
        tk.Label(page, text=f"Logged-in Username: {session_account_name or session_username}", bg="white", anchor="center", justify="center").pack(pady=2)
        tk.Label(page, text=f"Server Name: {default_server_name}", bg="white", anchor="center", justify="center").pack(pady=2)
        tk.Label(page, text=f"IP Address: {ip_addr}", bg="white", anchor="center", justify="center").pack(pady=2)
        tk.Label(page, text=f"Connection Status: {status_text}", bg="white", anchor="center", justify="center").pack(pady=(2, 14))

        tk.Label(page, text="Choose Flow", font=("Segoe UI", 12, "bold"), bg="white", anchor="center", justify="center").pack(pady=(0, 8))

        tk.Button(
            page,
            text="Enter Workspace",
            width=28,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self.show_workspace_selection_screen
        ).pack(pady=(0, 8))

        tk.Button(
            page,
            text="View Archive Architecture",
            width=28,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self.show_archive_architecture_screen
        ).pack()

        tk.Label(
            page,
            text=f"Current Workspace: {active_workspace or 'Not selected'}",
            bg="white",
            fg="#666666",
            anchor="center",
            justify="center"
        ).pack(pady=(14, 0))

        tk.Button(
            page,
            text="Logout",
            width=28,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self.logout_and_return_to_login
        ).pack(pady=(14, 0))

def main():
    app = SequenceArchiverApp()
    app.show_startup_screen()
    app.root.mainloop()

if __name__ == "__main__":
    main()