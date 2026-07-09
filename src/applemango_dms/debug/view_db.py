import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = r"\\applemango\database\applemango.db"

try:
    from applemango_dms import config
except Exception:
    config = None

def _resolve_db_path():
    if config is not None and getattr(config, "archive_db_path", None):
        return Path(config.archive_db_path)
    return Path(DEFAULT_DB_PATH)

def _print_table(conn, table_name):
    columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
    print(f"\n[{table_name}] columns: {', '.join(columns) if columns else '(none)'}")

    rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
    print(f"[{table_name}] rows: {len(rows)}")
    for idx, row in enumerate(rows, start=1):
        print(f"  {idx}. {row}")

def main():
    db_path = _resolve_db_path()
    print(f"Database path: {db_path}")

    try:
        with sqlite3.connect(db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            table_names = [row[0] for row in tables]

            if not table_names:
                print("No tables found.")
                return

            print(f"Tables: {', '.join(table_names)}")
            for table_name in table_names:
                _print_table(conn, table_name)
    except Exception as exc:
        print(f"Failed to open or read database: {exc}")

if __name__ == "__main__":
    main()