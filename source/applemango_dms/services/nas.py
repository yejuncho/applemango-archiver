import ctypes
import re
import socket
import subprocess
from pathlib import Path
from ctypes import wintypes

from applemango_dms.config import (
    allowed_mapping_letters,
    default_server_port,
)

def run_net_command(command):
    return subprocess.run(
        ["cmd", "/d", "/c", f"chcp 949>nul & {command}"],
        capture_output=True,
        text=True,
        encoding="cp949",
        errors="replace",
    )

def normalize_drive_letter(raw):
    letter = (raw or "").strip().upper().rstrip(":")
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

def get_server_ip(server_name):
    normalized_server = server_name.strip().lstrip("\\")
    if not normalized_server:
        return "연결 불가"

    try:
        return socket.gethostbyname(normalized_server)
    except OSError:
        return "연결 불가"
    
def check_server_availability(server_name):
    normalized_server = server_name.strip().lstrip("\\")
    if not normalized_server:
        return False, "연결 불가"

    ip_addr = get_server_ip(server_name)
    ping_result = subprocess.run(["ping", "-n", "1", normalized_server], capture_output=True, text=True)
    return ping_result.returncode == 0, ip_addr

def check_local_network_connectivity(server_name, port=default_server_port, timeout=1.2):
    normalized_server = server_name.strip().lstrip("\\")
    if not normalized_server:
        return False, "서버 주소 미설정"

    try:
        with socket.create_connection((normalized_server, port), timeout=timeout):
            return True, "NAS 연결 가능"
    except OSError:
        return False, "NAS 연결 불가"
    
def get_server_share_names(server_name):
    normalized_server = server_name.strip().lstrip("\\")
    if not normalized_server:
        return None

    class SHARE_INFO_1(ctypes.Structure):
        _fields_ = [
            ("shi1_netname", wintypes.LPWSTR),
            ("shi1_type", wintypes.DWORD),
            ("shi1_remark", wintypes.LPWSTR),
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
        ctypes.POINTER(wintypes.DWORD),
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
            ctypes.byref(resume_handle),
        )

        if status not in (0, 234):
            if buffer:
                net_api_buffer_free(buffer)
            return None

        if entries_read.value and buffer:
            share_array = ctypes.cast(buffer, ctypes.POINTER(SHARE_INFO_1))
            for idx in range(entries_read.value):
                share_name = share_array[idx].shi1_netname
                if share_name and not share_name.endswith("$"):
                    shares.append(share_name)

        if buffer:
            net_api_buffer_free(buffer)

        if status == 0:
            break

    return list(dict.fromkeys(shares))

def discover_server_shares(server_name):
    shares = get_server_share_names(server_name) or []

    if not shares:
        try:
            server_root = Path(server_name)
            for child in server_root.iterdir():
                if child.name and not child.name.endswith("$"):
                    shares.append(child.name)
        except OSError:
            shares = []

    if not shares:
        shares_result = run_net_command(f"net view {server_name}")
        if shares_result.returncode == 0:
            in_table = False
            header_skipped = False
            for raw_line in shares_result.stdout.splitlines():
                stripped = raw_line.strip()
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