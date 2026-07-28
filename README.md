# Applemango DMS

A lightweight Python-based **Document Management System (DMS)** designed for organizations that store and manage documents on a shared network drive (NAS).

The application streamlines document archiving by providing a modern desktop interface for uploading, organizing, and searching files using structured metadata stored in an SQLite database.

---

## Features

* Secure workspace login
* Automatic network drive mapping
* File upload directly to shared folders
* Automatic document renaming
* Metadata-based document indexing
* Fast SQL-powered search
* Workspace-specific document types
* File preview
* Modern desktop interface built with CustomTkinter
* Local demo mode for offline development

---

## Project Structure

```text
applemango-dms/
│
├── src/
│   └── applemango_dms/
│
├── assets/
│   ├── icons/
│   ├── fonts/
│   ├── logos/
│
├── demo/
│
├── docs/
│
├── legacy/
|
├── README.md
├── requirements.txt
└── .gitignore
```

---

## Technology Stack

* Python 3.13
* CustomTkinter
* SQLite
* pathlib
* hashlib
* Pillow
* PyInstaller

---

## File Naming Convention

Uploaded files are automatically renamed following the convention:

```
YYYY-MM-DD_DocumentType_Tag_OriginalFilename.ext
```

Example:

```
2026-07-16_Invoice_HQ_Invoice_348.pdf
```

The original filename is preserved in the database for reference.

---

## Database

The application stores searchable metadata in SQLite.

### Applemango DMS Metadata Contract

#### 1. User-facing document metadata

These fields may be displayed, searched, filtered, or edited through the application, subject to permissions.

##### Primary document information

- **Original filename** (`original_filename`)  
  The filename of the source document when it was uploaded.

- **Archived filename** (`archived_filename`)  
  The physical filename assigned to the archived NAS copy.

- **Document date** (`document_date`)  
  The business-relevant date selected for the document.

- **Document type** (`document_type`)  
  The workspace-specific document type, such as 출석, 영수증, 계약서, or 보고서.

- **Tags** (`tags`)  
  Workspace-specific descriptive labels associated with the document.

- **Uploaded by** (`uploaded_by`)  
  The user account that originally uploaded the document.

##### File information

- **File extension** (`file_ext`)  
  The normalized extension, such as `.pdf`, `.docx`, or `.jpg`.

- **File size** (`file_size`)  
  The physical file size in bytes, displayed in a readable unit in the UI.

- **MIME type** (`mime_type`)  
  The detected content type, such as `application/pdf` or `image/jpeg`.

##### Dates and lifecycle information

- **Archived at** (`archived_at`)  
  The time at which the file was stored through the DMS.

- **Source created at** (`source_created_at`)  
  The creation timestamp reported by the original source filesystem.

- **Source modified at** (`source_modified_at`)  
  The modification timestamp reported by the original source filesystem.

- **Status** (`status`)  
  The document’s current lifecycle state:
  - `active`
  - `missing`
  - `deleted`

##### Location information

- **Workspace** (`workspace`)  
  The organizational or personal DMS workspace containing the document.

- **Relative path** (`relative_path`)  
  The file’s location relative to the workspace root. This may be shown in a details view.

- **Full path** (`full_path`)  
  The resolved physical path used for opening and file operations. It is computed from the workspace share path and relative path.

#### 2. Complete SQLite-backed file metadata

Each stored document is represented by the following database-backed metadata.

##### Identity and relationships

- `id`  
  Stable database identity for the file record. Exposed to application code as `file_id`.

- `workspace_id`  
  Identifies the workspace that owns the record.

- `document_type_id`  
  Identifies the workspace-specific document type.

- `uploaded_by`  
  Textual identity of the original uploader.

##### Filenames and location

- `original_filename`
- `archived_filename`
- `relative_path`

The workspace’s `share_path` is stored in the `workspaces` table rather than repeated in every file record.

##### Document dates

- `document_date`
- `source_created_at`
- `source_modified_at`
- `archived_at`

##### Technical file metadata

- `file_ext`
- `mime_type`
- `file_size`
- `checksum`

`checksum` stores a content hash used for integrity verification and future reconciliation of moved, replaced, or modified files.

##### Lifecycle metadata

- `status`
- `deleted_at`

`deleted_at` is `NULL` for ordinary active or missing records and is populated when a record is soft-deleted.

##### Tags

Tags are stored through two related tables rather than directly in `files`:

- `tags.id`
- `tags.workspace_id`
- `tags.name`
- `tags.created_at`
- `file_tags.file_id`
- `file_tags.tag_id`

This permits multiple tags per file and allows one workspace tag to be reused across multiple files.

#### 3. Supporting workspace metadata

The `workspaces` table stores:

- `id`
- `name`
- `share_path`
- `is_active`
- `created_at`
- `deleted_at`

Planned future workspace metadata may include:

- `workspace_type` — `organization` or `personal`
- `owner_user_id` — owner of a personal workspace
- `display_name`
- workspace registration and administration metadata

#### 4. Supporting document-type metadata

The `document_types` table stores:

- `id`
- `workspace_id`
- `name`
- `is_active`
- `sort_order`
- `created_at`
- `deleted_at`

Document types are workspace-specific. `DEFAULT_DOCUMENT_TYPES` should be used only to seed a newly created workspace, after which SQLite becomes the source of truth.

#### 5. Computed metadata not stored as authoritative file columns

The following values are calculated when needed and should not be treated as independent stored metadata:

- `full_path`  
  Computed from `workspaces.share_path` and `files.relative_path`.

- `document_type`  
  Resolved from `files.document_type_id`.

- `tags`  
  Resolved through `file_tags` and `tags`.

- `tags_text`  
  Display-formatted tag names, such as `finance, urgent`.

- `relevance_score`  
  Calculated for a particular search query.

- human-readable file size  
  Formatted from `file_size`.

- file availability  
  Checked against the physical NAS file and reflected through `status`.

#### 6. Default simple-search fields

The main Search Files box searches the approved user-facing fields:

- Original filename
- Archived filename
- Document date
- Document type
- Tags
- Uploaded by
- File extension

The “All metadata” option in the simple-search UI means all fields in this approved list. It does not literally search every SQLite column.

#### 7. Detailed-search fields

Detailed Search may expose:

- Original filename
- Archived filename
- Document date or date range
- Document type
- Tags
- Tag matching mode: all or any
- Uploaded by
- File extension
- MIME type
- Minimum and maximum file size
- Source-created date range
- Source-modified date range
- Archived date range
- Status
- Workspace, where administratively appropriate

Administrative or diagnostic searches may additionally use:

- File ID
- Workspace ID
- Document-type ID
- Relative path
- Checksum
- Deleted timestamp

#### 8. Editing policy

##### User-editable metadata

Subject to ownership and future workspace permissions:

- Document date
- Document type
- Tags
- Archived filename through the explicit rename action

##### System-managed or normally read-only metadata

- File ID
- Workspace ID
- Uploader
- Original filename
- Relative path
- File extension
- MIME type
- File size
- Checksum
- Source timestamps
- Archived timestamp
- Status
- Deleted timestamp

System-managed fields may change only through controlled operations such as rename, soft delete, restore, missing-file detection, or future reconciliation.

#### 9. Record identity rule

All backend actions must identify documents using:

```text
workspace_id + file_id
```

Filenames and physical paths are display and location data. They must never replace `file_id` as the stable application identity.

---

## Workspaces

Each workspace represents a document repository.

A workspace contains:

* its own shared folder
* its own list of document types
* its own archived documents

Users select a workspace before performing file operations.

---

## Search

Documents can be searched using combinations of:

* Keywords
* Document type
* Date or date range
* Tags
* Original filename
* Archived filename

Search results are retrieved from SQLite and displayed inside the application.

---

## Local Demo Mode

For development without access to the organization's NAS, the application supports a local demo mode.

The demo directory mimics the production folder structure, allowing UI development and testing without requiring network connectivity.

---

## Building

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
python -m applemango_dms.main
```

Build executable:

```bash
pyinstaller app.spec
```

---

## Roadmap

* File version history
* Advanced metadata filters
* OCR integration
* Full-text document search
* Role-based permissions
* User management
* Audit logging
* Automatic backups
* Batch upload improvements

---

## License

This project is proprietary software developed for internal organizational document management.

All rights reserved.

---

## Author

Developed by **Daniel Cho**.
