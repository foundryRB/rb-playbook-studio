"""Keeping the generated back-link sections consistent inside a gated write.

The tail sections of a REF quote the frontmatter of every planet that cites it,
and ``scripts/sync_backlinks.py`` in the playbook is their author. A write that
changes frontmatter stales them by construction, so the write path regenerates
them before the gates read the corpus (INT-DERIVE-002).

That puts a corpus script between the mutation and the gates, which is where the
two helpers below earn their place. ``regenerate`` runs the script and turns a
rejection into a refusal report rather than an exception: the script rejects the
same malformed documents the gates exist to catch, so its verdict is a verdict
about the write, never an infrastructure error (INT-GATE-001). ``snapshot_refs``
and ``restore_refs`` carry the bytes the sync may rewrite anywhere in the corpus,
so a rejected write restores every REF it touched, the idiom ``CreateSkill``
already uses for the documents its scaffolder rewrites.
"""

from __future__ import annotations

from studio.application.ports.outbound.playbook_repository import PlaybookRepository
from studio.domain.exceptions.app_error import AppError
from studio.domain.model.validation_report import ValidationReport
from studio.logging import get_logger

__all__ = ["regenerate", "restore_refs", "snapshot_refs"]

logger = get_logger(__name__)


def snapshot_refs(repository: PlaybookRepository) -> dict[str, str]:
    """Capture every REF's bytes, because the sync may rewrite any of them.

    Names are unique universe-wide, and the snapshot is keyed by name because
    that is how a restore addresses a REF. A corpus carrying the same name twice
    would collapse two REFs into one key and restore one of them over the other,
    so it is refused here rather than silently rewritten on the rollback path.
    """
    snapshot: dict[str, str] = {}
    for ref in repository.list_refs():
        if ref.name in snapshot:
            raise AppError(f"the corpus carries {ref.name} more than once")
        snapshot[ref.name] = ref.raw
    return snapshot


def restore_refs(repository: PlaybookRepository, snapshot: dict[str, str]) -> None:
    """Write back the REFs the sync changed, leaving the rest untouched."""
    for name, raw in snapshot.items():
        if repository.get_ref(name=name).raw != raw:
            repository.write_ref_document(ref_name=name, raw=raw)


def regenerate(repository: PlaybookRepository) -> ValidationReport | None:
    """Regenerate the sections; report a refusal when the script rejects the corpus.

    Returns ``None`` when the sections are consistent, and a failing report when
    the script refused, so the caller rolls back and answers with the refusal it
    answers a failing gate with.
    """
    try:
        repository.sync_backlinks()
    except AppError as exc:
        logger.warning("Back-link sync refused the corpus: %s", exc)
        return ValidationReport(
            tests_passed=False,
            links_ok=True,
            tests_output=str(exc),
            links_output="",
        )
    return None
