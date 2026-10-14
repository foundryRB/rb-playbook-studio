"""Who may change what: the playbook's OWNERS file, parsed, and the one rights function.

OWNERS sits at the playbook root in CODEOWNERS syntax: a path anchored at the
root, then the people who own it, named by the email their sign-in carries.

    /                              admin@example.com
    /galaxies/craft/               writer@example.com
    /galaxies/craft/skills/x/      owner@example.com other@example.com
    not-before someone@example.com 2026-10-01

A person may change a path a line gives them, or anything under it. Rights are
the union of every line that names the person, so a narrower line never takes
away what a wider one gives. A `not-before` line records that the personal
tokens a person was issued before that date (UTC midnight) or timestamp are
refused. A path is literal: no wildcards and no unanchored patterns. With no
OWNERS file, nobody owns anything and every person is a reader.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from studio.domain.exceptions.invalid_owners_error import InvalidOwnersError
from studio.domain.model.actor import Actor

__all__ = [
    "OWNERS_FILE",
    "Action",
    "Owners",
    "OwnersRule",
    "Role",
    "atom_of",
    "check_owners",
    "galaxy_of",
    "normalise_path",
    "rule_line",
    "valid_email",
    "with_owners",
]

#: The rights file, at the playbook root.
OWNERS_FILE = "OWNERS"

_NOT_BEFORE = "not-before"
_EMAIL = re.compile(r"^[^@\s<>,;\"'`\\]+@[^@\s<>,;\"'`\\]+$")
_PATTERN_CHARS = set("*?[]!\\")
_ATOM_SHELVES = ("skills", "agents", "mcps", "rags")


class Action(StrEnum):
    """What a write asks to do."""

    EDIT = "edit"
    CREATE = "create"
    #: OWNERS itself, and the sync acts (push, refresh): the admin's alone.
    ADMINISTER = "administer"
    #: Running the gates on demand: anyone who may write somewhere.
    VALIDATE = "validate"


class Role(StrEnum):
    """The widest thing a person owns, for display and for refusals."""

    ADMIN = "admin"
    GALAXY_WRITER = "galaxy writer"
    ATOM_OWNER = "atom owner"
    READER = "reader"


@dataclass(frozen=True)
class OwnersRule:
    """One ownership line: a corpus path ("" is the root) and its owners."""

    path: str
    owners: tuple[str, ...]
    line: int


def valid_email(value: str) -> bool:
    """Whether a value is an email OWNERS can name and git can carry."""
    return bool(_EMAIL.fullmatch(value))


def normalise_path(path: str) -> str | None:
    """A corpus-relative POSIX path with no leading or trailing slash, "" for the
    root, or None when the path leaves the corpus or carries a pattern."""
    if any(ch in _PATTERN_CHARS for ch in path):
        return None
    parts = [p for p in path.strip().split("/") if p]
    if any(p in (".", "..") for p in parts):
        return None
    return "/".join(parts)


def galaxy_of(path: str) -> str | None:
    """The galaxy a corpus path sits in, or None for a path outside galaxies/."""
    parts = path.split("/")
    if len(parts) >= 2 and parts[0] == "galaxies" and parts[1]:
        return parts[1]
    return None


def atom_of(path: str) -> str | None:
    """The atom (a skill folder, an agent, an MCP or RAG card) a path belongs to."""
    parts = path.split("/")
    if len(parts) < 4 or parts[0] != "galaxies" or parts[2] not in _ATOM_SHELVES:
        return None
    if parts[2] == "skills":
        return "/".join(parts[:4])
    return path if len(parts) == 4 else None


def rule_line(path: str, owners: list[str], *, directory: bool) -> str:
    """The OWNERS line naming `owners` for `path`, in the file's own syntax."""
    anchored = "/" + path + ("/" if directory and path else "")
    return f"{anchored} {' '.join(owners)}"


def check_owners(owners: list[str]) -> None:
    """Refuse a list of owners OWNERS could not carry."""
    bad = [owner for owner in owners if not valid_email(owner)]
    if bad:
        raise InvalidOwnersError(f"owners are emails ({', '.join(bad)})")


def with_owners(text: str | None, *, path: str, owners: list[str], directory: bool) -> str:
    """OWNERS text with one more line, naming `owners` for `path`."""
    check_owners(owners)
    base = (text or "").rstrip("\n")
    line = rule_line(path, owners, directory=directory)
    return f"{base}\n{line}\n" if base else f"{line}\n"


def _within(path: str, owned: str) -> bool:
    return owned == "" or path == owned or path.startswith(owned + "/")


def _parse_instant(value: str, line: int) -> datetime:
    try:
        if len(value) == 10:
            return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidOwnersError(
            f"OWNERS line {line}: {value!r} is not a date (YYYY-MM-DD) or an ISO timestamp"
        ) from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class Owners:
    """The parsed rights of one corpus state. Immutable once built."""

    def __init__(
        self, rules: tuple[OwnersRule, ...] = (), not_before: dict[str, datetime] | None = None
    ) -> None:
        self.rules = rules
        self._not_before = dict(not_before or {})

    @classmethod
    def parse(cls, text: str) -> Owners:
        """Parse OWNERS text; raise InvalidOwnersError naming the first bad line."""
        rules: list[OwnersRule] = []
        not_before: dict[str, datetime] = {}
        for number, raw in enumerate(text.splitlines(), start=1):
            tokens = raw.split("#", 1)[0].split()
            if not tokens:
                continue
            head, rest = tokens[0], tokens[1:]
            if head == _NOT_BEFORE:
                if len(rest) != 2 or not valid_email(rest[0]):
                    raise InvalidOwnersError(
                        f"OWNERS line {number}: write 'not-before <email> <date>'"
                    )
                email = rest[0].lower()
                instant = _parse_instant(rest[1], number)
                not_before[email] = max(instant, not_before.get(email, instant))
                continue
            if not head.startswith("/"):
                raise InvalidOwnersError(
                    f"OWNERS line {number}: a path starts at the root with '/' ({head!r})"
                )
            path = normalise_path(head)
            if path is None:
                raise InvalidOwnersError(
                    f"OWNERS line {number}: {head!r} is not a literal corpus path"
                )
            if not rest:
                raise InvalidOwnersError(f"OWNERS line {number}: {head} names no owner")
            bad = [owner for owner in rest if not valid_email(owner)]
            if bad:
                raise InvalidOwnersError(
                    f"OWNERS line {number}: owners are emails ({', '.join(bad)})"
                )
            rules.append(OwnersRule(path, tuple(o.lower() for o in rest), number))
        return cls(tuple(rules), not_before)

    # -- facts about a person ------------------------------------------------

    def paths_of(self, email: str) -> tuple[str, ...]:
        """Every path a line gives this person, in file order, without repeats."""
        who = email.lower()
        seen: dict[str, None] = {}
        for rule in self.rules:
            if who in rule.owners:
                seen.setdefault(rule.path, None)
        return tuple(seen)

    def owns(self, email: str, path: str) -> bool:
        """Whether a line gives this person `path` or a path above it."""
        target = normalise_path(path)
        if target is None:
            return False
        return any(_within(target, owned) for owned in self.paths_of(email))

    def tokens_not_before(self, email: str) -> datetime | None:
        """The instant before which this person's personal tokens are refused."""
        return self._not_before.get(email.lower())

    def role_of(self, actor: Actor | None) -> Role:
        """The widest thing the actor owns."""
        if actor is None:
            return Role.READER
        if actor.service:
            return Role.ADMIN
        paths = self.paths_of(actor.email)
        if "" in paths:
            return Role.ADMIN
        if any(p == "galaxies" or (galaxy_of(p) and p.count("/") == 1) for p in paths):
            return Role.GALAXY_WRITER
        return Role.ATOM_OWNER if paths else Role.READER

    def galaxies_written(self, actor: Actor | None, galaxies: list[str]) -> list[str]:
        """The galaxies, of those named, the actor may create atoms in."""
        return [g for g in galaxies if self.may(actor, Action.CREATE, f"galaxies/{g}")]

    def atoms_owned(self, actor: Actor | None) -> list[str]:
        """The atom paths a line gives the actor by name."""
        if actor is None or actor.service:
            return []
        return [p for p in self.paths_of(actor.email) if atom_of(p) == p]

    # -- the rights function -------------------------------------------------

    def may(self, actor: Actor | None, action: Action, path: str = "") -> bool:
        """Whether the actor may take `action` on `path`. Every write asks this."""
        if actor is None:
            return False
        if actor.service:
            return True
        if action is Action.ADMINISTER:
            return "" in self.paths_of(actor.email)
        if action is Action.VALIDATE:
            return bool(self.paths_of(actor.email))
        return self.owns(actor.email, path)

    def refusal(self, actor: Actor | None, action: Action, path: str = "") -> str:
        """Why `may` says no, naming the role that would allow the act."""
        role = self.role_of(actor)
        you = f"{'an' if role[0] in 'aeiou' else 'a'} {role}"
        if action is Action.ADMINISTER:
            return f"this needs the admin role; you are {you}"
        if action is Action.VALIDATE:
            return (
                "running the gates needs a role that writes (atom owner, galaxy writer "
                f"or admin); you are {you}"
            )
        target = normalise_path(path) or path
        galaxy = galaxy_of(target)
        atom = atom_of(target)
        verb = "editing" if action is Action.EDIT else "creating"
        if galaxy is None:
            needed = "the admin role"
        elif atom is not None and action is Action.EDIT:
            needed = f"the owner of {atom}, a galaxy writer of {galaxy}, or an admin"
        else:
            needed = f"a galaxy writer of {galaxy}, or an admin"
        return f"{verb} {target} needs {needed}; you are {you}"
