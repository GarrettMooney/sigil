"""Project instruction discovery for Zeta prompts."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_CONTEXT_FILES = ("AGENTS.md", "AGENTS.MD", "CLAUDE.md", "CLAUDE.MD")


def load_project_context(cwd: str | Path | None = None) -> str:
    """Load project instruction files from parent directories, global to local."""
    current = Path(cwd or os.getcwd()).resolve()
    directories = [*reversed(current.parents), current]
    sections: list[str] = []
    seen: set[Path] = set()
    for directory in directories:
        for filename in PROJECT_CONTEXT_FILES:
            path = directory / filename
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved in seen or not path.is_file():
                continue
            seen.add(resolved)
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if text.strip():
                sections.append(f"Project context from {path}:\n{text.strip()}")
    return "\n\n".join(sections)
