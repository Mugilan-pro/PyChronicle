"""Frame filtering engine for PyChronicle's execution tracer.

Ensures that only target user code is traced, completely filtering out Python
standard library internals, site-packages, and PyChronicle's own subsystems.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from types import FrameType
from typing import Iterable, Optional, Set


class TraceFilter:
    """Evaluates Python execution frames to determine if they should be traced."""

    def __init__(
        self,
        target_files: Optional[Iterable[str]] = None,
        ignore_stdlib: bool = True,
        ignore_site_packages: bool = True,
        ignore_pychronicle_internals: bool = True,
    ) -> None:
        self.target_files: Set[str] = set()
        if target_files:
            for f in target_files:
                self.target_files.add(os.path.abspath(f).lower())
                self.target_files.add(Path(f).name.lower())

        self.ignore_stdlib = ignore_stdlib
        self.ignore_site_packages = ignore_site_packages
        self.ignore_pychronicle_internals = ignore_pychronicle_internals

        # Cache standard library paths
        self._stdlib_paths: Set[str] = set()
        if hasattr(sys, "base_prefix"):
            self._stdlib_paths.add(os.path.abspath(sys.base_prefix).lower())
        if hasattr(sys, "prefix"):
            self._stdlib_paths.add(os.path.abspath(sys.prefix).lower())

        # Cache PyChronicle root directory
        self._pychronicle_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        ).lower()

    def should_trace(self, frame: FrameType) -> bool:
        """Return True if frame belongs to target user code and should be recorded."""
        filename = frame.f_code.co_filename
        if not filename:
            return False

        # Virtual filenames for in-memory code are always traced
        if filename.startswith("<") and filename.endswith(">"):
            if filename in ("<string>", "<stdin>", "<test>", "<script>"):
                return True
            return False

        abs_path = os.path.abspath(filename).lower()
        basename = Path(filename).name.lower()

        # If explicit target files are registered, whitelist them directly
        if self.target_files:
            if abs_path in self.target_files or basename in self.target_files:
                return True
            return False

        # Exclude PyChronicle internals
        if self.ignore_pychronicle_internals and abs_path.startswith(self._pychronicle_dir):
            return False

        # Exclude site-packages
        if self.ignore_site_packages and "site-packages" in abs_path:
            return False

        # Exclude standard library
        if self.ignore_stdlib:
            for std_path in self._stdlib_paths:
                if abs_path.startswith(std_path) and "site-packages" not in abs_path:
                    return False

        return True
