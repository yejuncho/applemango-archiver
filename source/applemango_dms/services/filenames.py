import re
from datetime import date
from pathlib import Path

class FilenameBuilder:
    _invalid_chars = re.compile(r'[<>:"/\\|?*]')

    @classmethod
    def _sanitize_part(cls, value):
        cleaned = cls._invalid_chars.sub('_', str(value or '').strip())
        cleaned = re.sub(r'\s+', ' ', cleaned).strip().strip('.')
        return cleaned

    def build_filename(self, archive_date, document_type, tags, original_name):
        original = Path(original_name)
        stem = self._sanitize_part(original.stem) or 'untitled'
        ext = original.suffix

        date_part = self._sanitize_part(archive_date) or date.today().isoformat()
        doc_part = self._sanitize_part(document_type) or '기타'
        tag_part = self._sanitize_part(tags)

        parts = [date_part, doc_part]
        if tag_part:
            parts.append(tag_part)
        parts.append(stem)
        return '__'.join(parts) + ext

    def ensure_unique_name(self, destination_dir, candidate_name, reserved_names=None):
        reserved_names = reserved_names if reserved_names is not None else set()
        candidate = Path(candidate_name)
        stem = candidate.stem
        ext = candidate.suffix

        name = candidate_name
        idx = 2
        while True:
            taken_in_reserved = name in reserved_names
            taken_on_disk = bool(destination_dir and (destination_dir / name).exists())
            if not taken_in_reserved and not taken_on_disk:
                reserved_names.add(name)
                return name
            name = f'{stem} ({idx}){ext}'
            idx += 1