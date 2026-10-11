"""Startskript (Entwicklung und PyInstaller-Einstieg)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from imagetopdf.app import main  # noqa: E402

if __name__ == "__main__":
    main()
