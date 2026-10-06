"""Module execution entry point for PyChronicle.

Allows running:
    python -m pychronicle run script.py
"""

import sys
from pychronicle.cli import main

if __name__ == "__main__":
    sys.exit(main())
