from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
DEMO_DIR = PROJECT_ROOT / "demo"
DEMO_WORKSPACES_DIR = DEMO_DIR / "workspaces"

PRODUCTION_DB_PATH = DATA_DIR / "applemango.db"
DEMO_DB_PATH = DEMO_DIR / "demo.db"

default_server_name = r"\\applemango"
default_drive_letter = "Z"
allowed_mapping_letters = list("ABDEFHIJKLMNOPQRSTUVWXYZ")
default_server_port = 445
credential_store_path = Path.home() / ".applemango_archiver_credentials.json"
archive_db_path = Path(fr"{default_server_name}\database\applemango.db")

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_SOURCE_DIR = PACKAGE_DIR.parent
#PROJECT_ROOT = PROJECT_SOURCE_DIR.parent

logo_path = PROJECT_ROOT / "assets" / "logos" / "applemango_logo.png"
    
DEFAULT_DOCUMENT_TYPES = [
    "계약서",
    "청구서",
    "영수증",
    "명단",
    "출석",
    "양식",
    "보고서",
    "회의록",
    "사진",
    "문서",
    "기타",
]