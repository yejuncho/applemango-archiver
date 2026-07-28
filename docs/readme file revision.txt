	# files table (17 fields in total)
user-facing vs. system-wide



	# archived filename convention
document_date+document_type+original_filename+ext (double check the filenames.py, build_filename)






	# Dates
document_date
    User-selected business date
    Used in archived filename
    Searchable and editable before saving

source_created_at
    Original operating-system timestamp
    Stored only as system metadata
    Not used as document_date automatically

archived_at
    Actual DMS insertion time
    Generated automatically by SQLite
    Never entered manually
    Not used in the archived filename

