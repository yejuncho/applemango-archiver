import os
from datetime import datetime


def format_size_for_display(size_bytes):
    gb = 1024 ** 3
    mb = 1024 ** 2
    if size_bytes >= gb:
        return f"{size_bytes / gb:.1f} GB"
    return f"{size_bytes / mb:.1f} MB"


def collect_workspace_filesystem_stats(root_path):
    total_size = 0
    file_count = 0
    last_mtime = None

    stack = [str(root_path)]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        stat = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue

                    if last_mtime is None or stat.st_mtime > last_mtime:
                        last_mtime = stat.st_mtime

                    if entry.is_file(follow_symlinks=False):
                        file_count += 1
                        total_size += int(stat.st_size)
                    elif entry.is_dir(follow_symlinks=False):
                        stack.append(entry.path)
        except OSError:
            continue

    last_modified_text = datetime.fromtimestamp(last_mtime).strftime("%Y/%m/%d") if last_mtime else "정보 없음"
    return {
        "last_modified": last_modified_text,
        "size_bytes": total_size,
        "size_text": format_size_for_display(total_size),
        "fs_file_count": file_count,
    }
