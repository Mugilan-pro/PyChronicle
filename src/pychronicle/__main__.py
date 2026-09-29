"""Entrypoint for python -m pychronicle."""

from __future__ import annotations

import sys
from pychronicle.cli.commands import main

if __name__ == "__main__":
    sys.exit(main())
