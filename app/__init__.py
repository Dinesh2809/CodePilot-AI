"""Top-level proxy package for development convenience."""

from pathlib import Path


# Keep ``app.*`` imports working when pytest runs from the repository root.
__path__.append(str(Path(__file__).resolve().parent.parent / "backend" / "app"))
