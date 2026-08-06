from pathlib import Path

WORKSPACE_STATUS_ACTIVE = "active"
WORKSPACE_STATUS_AVAILABLE = "available"
WORKSPACE_STATUS_UNAVAILABLE = "unavailable"
WORKSPACE_STATUS_INACTIVE = "inactive"


def _normalize_name(value):
    normalized = str(value or "").strip()

    if not normalized:
        raise ValueError(
            "workspace name is required."
        )

    return normalized


def _normalize_path_key(value):
    normalized = str(value or "").strip()

    if not normalized:
        return ""

    return (
        str(Path(normalized))
        .replace("/", "\\")
        .rstrip("\\")
        .casefold()
    )


def _normalize_name_key(value):
    return _normalize_name(value).casefold()


def _normalize_discovered_candidate(candidate):
    if not isinstance(candidate, dict):
        raise TypeError(
            "Discovered workspace candidates must be dictionaries."
        )

    name = _normalize_name(
        candidate.get("name")
    )

    share_path = str(
        candidate.get("share_path") or ""
    ).strip()

    if not share_path:
        raise ValueError(
            "Discovered workspace candidate has no share_path."
        )

    source = str(
        candidate.get("source") or ""
    ).strip().lower()

    if source not in {"nas", "demo"}:
        raise ValueError(
            f"Unsupported workspace source: {source}"
        )

    return {
        "name": name,
        "share_path": share_path,
        "source": source,
        "is_available": bool(
            candidate.get(
                "is_available",
                True,
            )
        ),
    }


def _normalize_registered_workspace(workspace):
    if not isinstance(workspace, dict):
        raise TypeError(
            "Registered workspaces must be dictionaries."
        )

    workspace_id = int(
        workspace["id"]
    )

    if workspace_id <= 0:
        raise ValueError(
            "workspace id must be greater than zero."
        )

    return {
        "id": workspace_id,
        "name": _normalize_name(
            workspace.get("name")
        ),
        "share_path": str(
            workspace.get("share_path") or ""
        ).strip(),
        "is_active": bool(
            workspace.get("is_active")
        ),
        "created_at": workspace.get(
            "created_at"
        ),
        "deleted_at": workspace.get(
            "deleted_at"
        ),
    }


def build_workspace_designation_rows(
    discovered_candidates,
    registered_workspaces,
):
    """
    Merge current storage discovery with persistent SQLite
    workspace designations.

    This function is read-only. It does not change storage or
    database state.
    """
    discovered = [
        _normalize_discovered_candidate(
            candidate
        )
        for candidate in (
            discovered_candidates or []
        )
    ]

    registered = [
        _normalize_registered_workspace(
            workspace
        )
        for workspace in (
            registered_workspaces or []
        )
    ]

    registered_by_name = {
        _normalize_name_key(
            workspace["name"]
        ): workspace
        for workspace in registered
    }

    registered_by_path = {
        _normalize_path_key(
            workspace["share_path"]
        ): workspace
        for workspace in registered
        if _normalize_path_key(
            workspace["share_path"]
        )
    }

    matched_workspace_ids = set()
    merged_rows = []

    for candidate in discovered:
        path_key = _normalize_path_key(
            candidate["share_path"]
        )
        name_key = _normalize_name_key(
            candidate["name"]
        )

        path_match = registered_by_path.get(
            path_key
        )
        name_match = registered_by_name.get(
            name_key
        )

        if (
            path_match is not None
            and name_match is not None
            and int(path_match["id"])
            != int(name_match["id"])
        ):
            raise ValueError(
                "Discovered workspace name and path match "
                "different registered workspaces."
            )

        registered_workspace = (
            path_match
            if path_match is not None
            else name_match
        )

        if registered_workspace is None:
            merged_rows.append(
                {
                    "workspace_id": None,
                    "name": candidate["name"],
                    "share_path": candidate[
                        "share_path"
                    ],
                    "source": candidate["source"],
                    "is_discovered": True,
                    "is_designated": False,
                    "is_active": False,
                    "is_available": True,
                    "status":
                        WORKSPACE_STATUS_AVAILABLE,
                    "created_at": None,
                    "deleted_at": None,
                }
            )
            continue

        workspace_id = int(
            registered_workspace["id"]
        )

        if workspace_id in matched_workspace_ids:
            raise ValueError(
                "Multiple discovered folders matched the same "
                "registered workspace."
            )

        matched_workspace_ids.add(
            workspace_id
        )

        is_active = bool(
            registered_workspace["is_active"]
        )

        status = (
            WORKSPACE_STATUS_ACTIVE
            if is_active
            else WORKSPACE_STATUS_INACTIVE
        )

        merged_rows.append(
            {
                "workspace_id": workspace_id,
                "name": candidate["name"],
                "share_path": candidate[
                    "share_path"
                ],
                "source": candidate["source"],
                "is_discovered": True,
                "is_designated": True,
                "is_active": is_active,
                "is_available": True,
                "status": status,
                "created_at":
                    registered_workspace[
                        "created_at"
                    ],
                "deleted_at":
                    registered_workspace[
                        "deleted_at"
                    ],
            }
        )

    for workspace in registered:
        workspace_id = int(
            workspace["id"]
        )

        if workspace_id in matched_workspace_ids:
            continue

        is_active = bool(
            workspace["is_active"]
        )

        status = (
            WORKSPACE_STATUS_UNAVAILABLE
            if is_active
            else WORKSPACE_STATUS_INACTIVE
        )

        share_path = workspace[
            "share_path"
        ]

        source = (
            "nas"
            if str(share_path).startswith("\\\\")
            else "demo"
        )

        merged_rows.append(
            {
                "workspace_id": workspace_id,
                "name": workspace["name"],
                "share_path": share_path,
                "source": source,
                "is_discovered": False,
                "is_designated": True,
                "is_active": is_active,
                "is_available": False,
                "status": status,
                "created_at":
                    workspace["created_at"],
                "deleted_at":
                    workspace["deleted_at"],
            }
        )

    status_order = {
        WORKSPACE_STATUS_ACTIVE: 0,
        WORKSPACE_STATUS_AVAILABLE: 1,
        WORKSPACE_STATUS_INACTIVE: 2,
        WORKSPACE_STATUS_UNAVAILABLE: 3,
    }

    merged_rows.sort(
        key=lambda row: (
            status_order.get(
                row["status"],
                99,
            ),
            row["name"].casefold(),
        )
    )

    return merged_rows
