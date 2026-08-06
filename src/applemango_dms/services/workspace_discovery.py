from pathlib import Path

from applemango_dms.services.nas import (
    discover_server_shares,
)

WORKSPACE_SOURCE_NAS = "nas"
WORKSPACE_SOURCE_DEMO = "demo"


def _normalize_discovered_names(names):
    """
    Normalize, deduplicate, and sort discovered folder names.

    Matching is case-insensitive, while the first encountered
    display spelling is retained.
    """
    normalized = []
    seen = set()

    for value in names or []:
        name = str(value or "").strip()

        if not name:
            continue

        key = name.casefold()

        if key in seen:
            continue

        normalized.append(name)
        seen.add(key)

    return sorted(
        normalized,
        key=lambda value: value.casefold(),
    )


def discover_demo_workspace_candidates(
    demo_workspace_root,
):
    """
    Discover direct child directories under the demo workspace
    root.

    Returns normalized candidate dictionaries. No database writes
    occur here.
    """
    root = Path(demo_workspace_root)

    if not root.exists():
        raise FileNotFoundError(
            f"Demo workspace directory does not exist: {root}"
        )

    if not root.is_dir():
        raise NotADirectoryError(
            f"Demo workspace path is not a directory: {root}"
        )

    names = []

    try:
        children = list(root.iterdir())
    except OSError as exc:
        raise OSError(
            f"Unable to read demo workspace directory: {root}"
        ) from exc

    for child in children:
        try:
            if child.is_dir():
                names.append(child.name)
        except OSError:
            continue

    normalized_names = _normalize_discovered_names(
        names
    )

    return [
        {
            "name": name,
            "share_path": str(root / name),
            "source": WORKSPACE_SOURCE_DEMO,
            "is_available": True,
        }
        for name in normalized_names
    ]


def discover_nas_workspace_candidates(
    server_name,
):
    """
    Discover shared folders exposed by the configured NAS server.

    Returns normalized candidate dictionaries. An empty list means
    no shares were discovered or the server could not currently be
    enumerated.
    """
    normalized_server = str(
        server_name or ""
    ).strip().rstrip("\\")

    if not normalized_server:
        raise ValueError(
            "server_name is required."
        )

    names = discover_server_shares(
        normalized_server
    )

    normalized_names = _normalize_discovered_names(
        names
    )

    return [
        {
            "name": name,
            "share_path": str(
                Path(
                    f"{normalized_server}\\{name}"
                )
            ),
            "source": WORKSPACE_SOURCE_NAS,
            "is_available": True,
        }
        for name in normalized_names
    ]


def discover_workspace_candidates(
    *,
    is_demo_mode,
    demo_workspace_root=None,
    server_name=None,
):
    """
    Discover possible DMS workspaces for the current runtime mode.

    The result structure is identical for demo and NAS operation.
    This function performs discovery only and never changes SQLite.
    """
    if not isinstance(is_demo_mode, bool):
        raise TypeError(
            "is_demo_mode must be a boolean."
        )

    if is_demo_mode:
        if demo_workspace_root is None:
            raise ValueError(
                "demo_workspace_root is required "
                "in demo mode."
            )

        return discover_demo_workspace_candidates(
            demo_workspace_root
        )

    return discover_nas_workspace_candidates(
        server_name
    )
