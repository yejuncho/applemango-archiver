import re
from datetime import date
from pathlib import Path
class FilenameBuilder:
    _invalid_chars = re.compile(r'[<>:"/\\|?*]')
    _tag_splitter = re.compile(r'[,;|]+')
    _max_filename_length = 220

    @classmethod
    def _sanitize_part(cls, value):
        cleaned = cls._invalid_chars.sub('_', str(value or '').strip())
        cleaned = re.sub(r'\s+', ' ', cleaned).strip().strip('.')
        return cleaned

    @classmethod
    def _normalize_tags(cls, tags):
        if isinstance(tags, (list, tuple, set)):
            raw_tags = [str(item or '').strip() for item in tags]
        else:
            raw_tags = [piece.strip() for piece in cls._tag_splitter.split(str(tags or ''))]

        normalized = []
        seen = set()
        for raw in raw_tags:
            if not raw:
                continue
            cleaned = cls._sanitize_part(raw).replace(' ', '-')
            if not cleaned or cleaned in seen:
                continue
            normalized.append(cleaned)
            seen.add(cleaned)
        return normalized

    @classmethod
    def _trim_stem_for_extension(cls, stem, ext):
        max_stem_length = max(1, cls._max_filename_length - len(ext))
        if len(stem) <= max_stem_length:
            return stem
        return stem[:max_stem_length].rstrip(' ._') or 'untitled'

    def build_filename(self, archive_date, document_type, tags, original_name):
        original = Path(original_name)
        stem = self._sanitize_part(original.stem) or 'untitled'
        ext = original.suffix

        date_part = self._sanitize_part(archive_date) or date.today().isoformat()
        doc_part = self._sanitize_part(document_type) or '기타'
        tag_tokens = self._normalize_tags(tags)
        tag_part = '-'.join(tag_tokens) if tag_tokens else 'no-tag'

        composite_stem = '__'.join([date_part, doc_part, tag_part, stem])
        composite_stem = self._trim_stem_for_extension(composite_stem, ext)
        return composite_stem + ext

    def ensure_unique_name(self, destination_dir, candidate_name, reserved_names=None):
        reserved_names = reserved_names if reserved_names is not None else set()
        candidate = Path(candidate_name)
        stem = candidate.stem
        ext = candidate.suffix

        name = candidate_name
        idx = 1
        while True:
            taken_in_reserved = name in reserved_names
            taken_on_disk = bool(destination_dir and (destination_dir / name).exists())
            if not taken_in_reserved and not taken_on_disk:
                reserved_names.add(name)
                return name
            name = f'{stem} ({idx}){ext}'
            idx += 1