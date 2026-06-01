import re
import importlib
import ctypes
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox, simpledialog
import subprocess
from datetime import date
from ctypes import wintypes
from pathlib import Path

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

def map_network_drive(root, on_drive_changed):
    global session_logged_in, session_username, session_password

    if not session_logged_in:
        messagebox.showerror("Login Required", "Please log in first.")
        return

    # 1) Discover shares on the configured server (Unicode-safe first path)
    shares = get_server_share_names(default_server_name) or []

    # Secondary path: filesystem enumeration.
    if not shares:
        try:
            server_root = Path(default_server_name)
            for child in server_root.iterdir():
                name = child.name
                if name and not name.endswith("$"):
                    shares.append(name)
        except OSError:
            shares = []

    # Final fallback to net view parsing if API and UNC listing fail.
    if not shares:
        shares_result = run_net_command(f"net view {default_server_name}")

        if shares_result.returncode != 0:
            messagebox.showerror(
                "Share Discovery Failed",
                shares_result.stderr.strip() or shares_result.stdout.strip() or "Unable to list shares."
            )
            return

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

    # Remove duplicates while preserving order.
    shares = list(dict.fromkeys(shares))

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
    archiver_window = tk.Toplevel(root)
    archiver_window.title("Run Archiver")
    archiver_window.geometry("560x680")
    archiver_window.configure(bg = "white")
    archiver_window.transient(root)
    archiver_window.grab_set()

    selected_files = []
    selected_directory_var = tk.StringVar(value = "사단법인 애플망고러브트리")
    selected_subdirectory_var = tk.StringVar(value = "")
    destination_preview_var = tk.StringVar()
    status_var = tk.StringVar(value = "0 files ready")

    default_top_directories = [
        "사단법인 애플망고러브트리",
        "애플망고 선교회",
        "주식회사 히즈컴",
        "필레오 기독국제학교",
        "한소망교회"
    ]

    container = tk.Frame(archiver_window, bg = "white", padx = 18, pady = 16)
    container.pack(fill = "both", expand = True)

    button_row = tk.Frame(container, bg = "white")
    button_row.pack(fill = "x", pady = (0, 10))

    selected_files_list = tk.Frame(container, bg = "white")

    def update_preview_and_status(*_):
        subdir = selected_subdirectory_var.get().strip()
        preview_parts = [get_drive_target(), "Archive", selected_directory_var.get().strip()]
        if subdir:
            preview_parts.append(subdir)
        preview_parts.append(str(date.today().year))
        destination_preview_var.set("/".join(preview_parts) + "/")
        status_var.set(f"{len(selected_files)} files ready")

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
        values = default_top_directories
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
        values = []
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

    selected_directory_var.trace_add("write", update_preview_and_status)
    selected_subdirectory_var.trace_add("write", update_preview_and_status)
    top_directory_combo.bind("<<ComboboxSelected>>", update_preview_and_status)
    subdirectory_combo.bind("<<ComboboxSelected>>", update_preview_and_status)
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

def main():
    root = TkinterDnD.Tk() if TkinterDnD is not None else tk.Tk()
    root.title("Applemango Archiver")
    root.geometry("360x540")
    root.configure(bg = "white")
    root.resizable(False, False)

    container = tk.Frame(root, padx = 20, pady = 20, bg = "white")
    container.pack(expand = True, fill = "both")

    login_status_var = tk.StringVar(value = "")
    network_var = tk.StringVar(value = get_network_info_text())

    status_font = ("Segoe UI", 10)
    status_line_pady = (3, 3)

    auth_button_frame = tk.Frame(container, bg = "white")
    auth_button_frame.pack(fill = "x", pady = (0, 4))

    tk.Label(
        container,
        text  = "APPLEMANGO ARCHIVER",
        font = ("Segoe UI", 12, "bold"),
        bg = "white"
    ).pack(pady = (0, 10))

    status_box = tk.LabelFrame(
        container,
        text = "Status",
        bg = "white",
        padx = 12,
        pady = 8,
        labelanchor = "n"
    )
    status_box.pack(fill = "x", pady = (0, 12))

    login_status_label = tk.Label(status_box, textvariable = login_status_var, font = status_font, bg = "white", anchor = "center", justify = "center")
    network_label = tk.Label(status_box, textvariable = network_var, font = status_font, bg = "white", anchor = "center", justify = "center")

    path_var = tk.StringVar()

    path_label = tk.Label(status_box, textvariable = path_var, font = status_font, bg = "white", anchor = "center", justify = "center")

    def refresh_login_status_label():
        if session_logged_in and session_account_name:
            login_status_var.set(f"Logged in as {session_account_name}")
            if not login_status_label.winfo_ismapped():
                login_status_label.pack(fill = "x", pady = status_line_pady)
        else:
            login_status_var.set("")
            if login_status_label.winfo_ismapped():
                login_status_label.pack_forget()

    network_label.pack(fill = "x", pady = status_line_pady)
    path_label.pack(fill = "x", pady = status_line_pady)

    def refresh_path_label():
        path_var.set("Current Server Name: " + default_server_name)
    def refresh_labels():
        network_var.set(get_network_info_text())
        refresh_path_label()

    refresh_labels()

    def refresh_auth_button():
        for child in auth_button_frame.winfo_children():
            child.destroy()

        if session_logged_in:
            button_text = "Logout"
            button_command = lambda: logout_from_server(root, refresh_labels, refresh_auth_button, refresh_login_status_label)
        else:
            button_text = "Login"
            button_command = lambda: login_to_server(root, refresh_labels, refresh_auth_button, refresh_login_status_label)

        tk.Button(
            auth_button_frame,
            text = button_text,
            width = 10,
            bg = "#d9d9d9",
            activebackground = "#c0c0c0",
            fg = "black",
            activeforeground = "black",
            relief = "flat",
            bd = 0,
            highlightthickness = 0,
            cursor = "hand2",
            command = button_command
        ).pack(anchor = "e")

    refresh_login_status_label()
    refresh_auth_button()

    tk.Button(
        container,
        text = "Map Network Drive",
        width = 28,
        height = 2,
        bg = "#d9d9d9",
        activebackground = "#c0c0c0",
        fg = "black",
        activeforeground = "black",
        relief = "flat",
        bd = 0,
        highlightthickness = 0,
        cursor = "hand2",
        command = lambda: map_network_drive(root, refresh_labels)
    ).pack(pady = 6)
    
    tk.Button(
        container,
        text = "Unmap Network Drive",
        width = 28,
        height = 2,
        bg = "#d9d9d9",
        activebackground = "#c0c0c0",
        fg = "black",
        activeforeground = "black",
        relief = "flat",
        bd = 0,
        highlightthickness = 0,
        cursor = "hand2",
        command = lambda: unmap_network_drive(root, refresh_labels)
    ).pack(pady = 6)

    tk.Button(
        container,
        text = "Show Mapped Drive(s)",
        width = 28,
        height = 2,
        bg = "#d9d9d9",
        activebackground = "#c0c0c0",
        fg = "black",
        activeforeground = "black",
        relief = "flat",
        bd = 0,
        highlightthickness = 0,
        cursor = "hand2",
        command = lambda: show_mapped_drives_window(root)
    ).pack(pady = 6)

    tk.Button(
        container,
        text = "Run Archiver",
        width = 28,
        height = 2,
        bg = "#d9d9d9",
        activebackground = "#c0c0c0",
        fg = "black",
        activeforeground = "black",
        relief = "flat",
        bd = 0,
        highlightthickness = 0,
        cursor = "hand2",
        command = lambda: run_archiver(root)
    ).pack(pady = 6)

    tk.Button(
        container,
        text = "Settings",
        width = 28,
        height = 2,
        bg = "#d9d9d9",
        activebackground = "#c0c0c0",
        fg = "black",
        activeforeground = "black",
        relief = "flat",
        bd = 0,
        highlightthickness = 0,
        cursor = "hand2",
        command = lambda: admin(root, refresh_labels)
    ).pack(pady = 6)

    root.mainloop()

if __name__ == "__main__":
    main()