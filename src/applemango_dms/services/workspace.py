import subprocess

from applemango_dms.config import default_drive_letter, default_server_name
from applemango_dms.services.nas import (
    get_mapped_network_drives,
    get_available_mapping_letters,
    normalize_drive_letter,
)
class WorkspaceManager:
    def map_workspace(self, workspace_name, username, password):
        normalized = str(workspace_name or '').strip()
        if not normalized:
            return None, False, '워크스페이스 이름이 비어 있습니다.'

        unc_path = fr'{default_server_name}\{normalized}'

        existing = get_mapped_network_drives()
        if existing is not None:
            for drive, remote in existing:
                if str(remote).rstrip('\\').lower() == unc_path.rstrip('\\').lower():
                    return drive, False, ''

        available = get_available_mapping_letters()
        if not available:
            return None, False, '사용 가능한 드라이브 문자가 없습니다.'

        target_drive = normalize_drive_letter(default_drive_letter)
        if target_drive and target_drive.rstrip(':') in available:
            drive = target_drive
        else:
            drive = f"{available[0]}:"

        cmd = ['net', 'use', drive, unc_path, password, f'/user:{username}', '/persistent:no']
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='cp949', errors='replace')
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip() or '알 수 없는 오류'
            return None, False, err

        return drive, True, ''

    def unmap_drive(self, drive_letter):
        drive = normalize_drive_letter(drive_letter)
        if not drive:
            return
        subprocess.run(['net', 'use', drive, '/delete', '/y'], capture_output=True, text=True, encoding='cp949', errors='replace')