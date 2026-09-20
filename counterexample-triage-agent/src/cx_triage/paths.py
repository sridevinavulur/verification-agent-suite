"""Path portability helpers.

Reports must never embed absolute, machine-specific paths (they leak usernames
and break byte-for-byte golden comparisons across checkout locations). These
helpers render paths relative to a base directory (the current working
directory by default), keeping reproduction commands and artifact lists
meaningful while staying identical on any machine.
"""

from __future__ import annotations

import os
from pathlib import Path


def portable_path(path: str | os.PathLike[str], base: str | os.PathLike[str] | None = None) -> str:
    """Return ``path`` expressed relative to ``base`` (default: CWD).

    * If ``path`` is inside ``base``, a clean relative path is returned
      (e.g. ``examples/toy_counter/counter_fail.vcd``).
    * If ``path`` is already relative, it is normalized and returned as-is.
    * If ``path`` lives outside ``base`` it is still emitted relative to it
      (``../..`` chain) rather than as an absolute path, so the output never
      embeds a machine-specific, username-bearing absolute path.
    * If ``path`` cannot be made relative at all (e.g. a different Windows
      drive), it is returned unchanged.

    The result always uses forward slashes so goldens are OS-independent.
    """
    base_path = Path(base) if base is not None else Path.cwd()
    p = Path(path)

    try:
        rel = Path(os.path.relpath(p, base_path))
    except ValueError:
        # e.g. paths on different drives on Windows: no relative form exists.
        return p.as_posix()

    return rel.as_posix()
