import json
import subprocess

from applemango_dms.config import credential_store_path, default_server_name
from applemango_dms import state

def _normalize_server_name(server_name):
    raw = str(server_name or "").strip()
    raw = raw.lstrip("\\")
    if "\\" in raw:
        raw = raw.split("\\", 1)[0]
    return raw

def _wipe_server_connections(server_name):
    normalized = _normalize_server_name(server_name)
    if not normalized:
        return

    server_unc = fr"\\{normalized}"
    subprocess.run(
        ["net", "use", server_unc, "/delete", "/y"],
        capture_output=True,
        text=True,
        encoding="cp949",
        errors="replace",
    )
    subprocess.run(
        ["net", "use", fr"{server_unc}\IPC$", "/delete", "/y"],
        capture_output=True,
        text=True,
        encoding="cp949",
        errors="replace",
    )

def _connect_ipc(username, password):
    login_cmd = ["net", "use", fr"{default_server_name}\IPC$", password, f"/user:{username}", "/persistent:no"]
    return subprocess.run(login_cmd, capture_output=True, text=True, encoding="cp949", errors="replace")

def extract_account_name(raw_username):
    cleaned = (raw_username or "").strip()
    if "\\" in cleaned:
        cleaned = cleaned.split("\\")[-1]
    if "@" in cleaned:
        cleaned = cleaned.split("@")[0]
    return cleaned

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
    _wipe_server_connections(default_server_name)
    login_result = _connect_ipc(username, password)
    if login_result.returncode == 0:
        return True, ""

    first_err = login_result.stderr.strip() or login_result.stdout.strip() or "알 수 없는 오류"
    if "1219" in first_err:
        subprocess.run(
            ["net", "use", "*", "/delete", "/y"],
            capture_output=True,
            text=True,
            encoding="cp949",
            errors="replace",
        )
        _wipe_server_connections(default_server_name)
        retry_result = _connect_ipc(username, password)
        if retry_result.returncode == 0:
            return True, ""
        err = retry_result.stderr.strip() or retry_result.stdout.strip() or first_err
        return False, err

    err = first_err
    return False, err

def update_session_login(username, password):
    state.session_logged_in = True
    state.session_username = username.strip()
    state.session_password = password
    state.session_account_name = extract_account_name(username)

def clear_session_login():
    state.session_logged_in = False
    state.session_username = ""
    state.session_password = ""
    state.session_account_name = ""