"""Shared pytest fixtures.

Adds the project root to ``sys.path`` so ``scripts`` is importable as a
package without each test module repeating the boilerplate that the
production scripts themselves use.
"""

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
import sys

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
