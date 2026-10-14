"""Filesystem-backed SkillRuntime."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from studio.domain.exceptions.app_error import AppError
from studio.domain.exceptions.entity_not_found_error import EntityNotFoundError
from studio.domain.model.skill_status import SkillStatus
from studio.logging import get_logger

__all__ = ["FsSkillRuntime"]

logger = get_logger(__name__)


class FsSkillRuntime:
    """Runtime install state; installing delegates to the playbook's own
    scripts/install_playbook.py so the copy mechanism has one owner."""

    def __init__(self, playbook_root: Path, runtime_dir: Path) -> None:
        self._playbook_root = playbook_root
        self._source_root = playbook_root / "skills"
        self._runtime_dir = runtime_dir

    def status(self, *, name: str) -> SkillStatus:
        source = self._source_root / name
        target = self._runtime_dir / name
        if not (target / "SKILL.md").is_file():
            return SkillStatus(installed=False, in_sync=False)
        return SkillStatus(installed=True, in_sync=self._same_content(source, target))

    def install(self, *, name: str) -> SkillStatus:
        if not (self._source_root / name / "SKILL.md").is_file():
            raise EntityNotFoundError("skill", name)
        script = self._playbook_root / "scripts" / "install_playbook.py"
        if not script.is_file():
            raise EntityNotFoundError("installer", "scripts/install_playbook.py")
        proc = subprocess.run(
            [
                sys.executable,
                str(script),
                "--only",
                name,
                "--runtime-dir",
                str(self._runtime_dir),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if proc.returncode != 0:
            raise AppError(f"install_playbook.py failed: {proc.stderr.strip()[:500]}")
        logger.info("Installed skill %s via install_playbook.py", name)
        return self.status(name=name)

    def _same_content(self, source: Path, target: Path) -> bool:
        for src_file in sorted(source.rglob("*")):
            if not src_file.is_file() or "__pycache__" in src_file.parts:
                continue
            dst_file = target / src_file.relative_to(source)
            if not dst_file.is_file() or dst_file.read_bytes() != src_file.read_bytes():
                return False
        return True
