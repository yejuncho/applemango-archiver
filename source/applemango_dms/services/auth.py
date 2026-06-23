from applemango_dms.config import credential_store_path, default_server_name
from applemango_dms import state

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
    subprocess.run(["net", "use", fr"{default_server_name}\IPC$", "/delete", "/y"],
                   capture_output=True, text=True, encoding="cp949", errors="replace")

    login_cmd = ["net", "use", fr"{default_server_name}\IPC$", password, f"/user:{username}", "/persistent:no"]
    login_result = subprocess.run(login_cmd, capture_output=True, text=True, encoding="cp949", errors="replace")
    if login_result.returncode == 0:
        return True, ""

    err = login_result.stderr.strip() or login_result.stdout.strip() or "알 수 없는 오류"
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