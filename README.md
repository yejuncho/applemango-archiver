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

Typical metadata includes:

* Workspace
* Upload user
* Original filename
* Archived filename
* Display title
* Document type
* Document date
* Tags
* Description
* Notes
* File extension
* MIME type
* File size
* SHA-256 checksum
* Archive timestamp

The actual document files remain stored on the organization's shared network drive.

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
