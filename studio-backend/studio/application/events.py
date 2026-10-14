"""The facts this studio states on the platform event bus, and the one way to state one.

REF-Events gives each domain exactly one owner, and this studio owns ``playbook``
by its grant. The constants below are its whole vocabulary; the docs page
``architecture/events.md`` states the same rows for consumers, and a test holds
the two equal so neither can drift (REF-Events section 3: each owner states its
own types, held by its own tests). A type is never composed at a call site. A
document's body never enters an event: the corpus is the store, and a reader
fetches from it by name.

Every mutation here already passes Trust Calibration (write, run the corpus
gates, roll back byte-identical on failure), so each act has exactly two
outcomes and each is a fact: the edit was accepted and committed, or a gate
refused it and the clone is as it was. The generated back-link sections are
``sync_backlinks.py``'s output and are not facts of their own.

``state_fact`` is where the one-way rule is enforced for every caller at once.
A publisher is contractually forbidden from raising, but a caller that trusted
that contract and was wrong would fail an act it had already committed, which
is the single failure REF-Events section 6 exists to prevent. So the guarantee
is made true here rather than assumed.
"""

from __future__ import annotations

from studio.application.ports.outbound.event_publisher import EventPublisher
from studio.domain.model.validation_report import ValidationReport
from studio.logging import get_logger

__all__ = [
    "AGENT_CREATED",
    "AGENT_UPDATED",
    "CHANGES_PUSHED",
    "DOOR_CREATED",
    "DOOR_UPDATED",
    "GALAXY_UPDATED",
    "OWNERS_UPDATED",
    "PLAYBOOK_UPDATED",
    "REF_CREATED",
    "REF_UPDATED",
    "SKILL_CREATED",
    "SKILL_UPDATED",
    "VALIDATION_FAILED",
    "state_fact",
    "state_refusal",
]

logger = get_logger(__name__)

# The playbook domain: the corpus this studio edits behind its gates.
REF_CREATED = "com.foundry.playbook.ref.created"
REF_UPDATED = "com.foundry.playbook.ref.updated"
SKILL_CREATED = "com.foundry.playbook.skill.created"
SKILL_UPDATED = "com.foundry.playbook.skill.updated"
AGENT_CREATED = "com.foundry.playbook.agent.created"
AGENT_UPDATED = "com.foundry.playbook.agent.updated"
PLAYBOOK_UPDATED = "com.foundry.playbook.playbook.updated"
GALAXY_UPDATED = "com.foundry.playbook.galaxy.updated"
DOOR_CREATED = "com.foundry.playbook.door.created"
DOOR_UPDATED = "com.foundry.playbook.door.updated"
OWNERS_UPDATED = "com.foundry.playbook.owners.updated"
VALIDATION_FAILED = "com.foundry.playbook.validation.failed"
CHANGES_PUSHED = "com.foundry.playbook.changes.pushed"


def state_fact(
    publisher: EventPublisher | None,
    *,
    event_type: str,
    subject: str,
    data: dict[str, object],
) -> None:
    """Publish a fact, and let nothing about it reach the caller.

    Every failure mode ends the same way: dropped, logged at warning, and the
    act that caused it completes with the outcome it already had. No publisher
    wired (a studio with no bus grant) states nothing.
    """
    if publisher is None:
        return
    try:
        publisher.publish(event_type=event_type, subject=subject, data=data)
    except Exception as exc:  # noqa: BLE001 - a publish never fails its cause
        logger.warning("dropped event %s for %s: %s", event_type, subject, exc)


def state_refusal(
    publisher: EventPublisher | None,
    *,
    subject: str,
    kind: str,
    report: ValidationReport,
) -> None:
    """State that a gate refused an edit and the clone was rolled back.

    The fact names the gate that refused (the intent tests, the link checker,
    or both); the gates' output stays in the report the caller receives.
    """
    checks = (("tests", report.tests_passed), ("links", report.links_ok))
    gates = [name for name, ok in checks if not ok]
    state_fact(
        publisher,
        event_type=VALIDATION_FAILED,
        subject=subject,
        data={"target": subject, "kind": kind, "gates": gates},
    )
