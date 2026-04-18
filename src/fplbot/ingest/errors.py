"""Ingest-specific errors."""


class FplIngestError(RuntimeError):
    """Raised when FPL ingest cannot complete (HTTP, shape, or IO)."""


class TeamSnapshotError(RuntimeError):
    """Raised when authenticated team sync cannot complete."""
