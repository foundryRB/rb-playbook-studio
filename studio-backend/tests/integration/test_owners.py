"""OWNERS: the corpus's rights, in CODEOWNERS syntax (INT-AUTH-011).

A path anchored at the root, then the owners' emails; rights are the union of
the lines naming a person. No OWNERS, or one that does not parse, leaves every
person a reader. An admin's edit that does not parse, or names a path the corpus
lacks, is refused; a valid one takes effect on the next request.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pytest_intent import intent

from studio.domain.exceptions.invalid_owners_error import InvalidOwnersError
from studio.domain.model.actor import Actor
from studio.domain.model.rights import Action, Owners, Role
from tests.conftest import FakeGitSync
from tests.people import (
    ADMIN,
    DOOR_CARD,
    OWNER,
    OWNERS_TEXT,
    READER,
    WRITER,
    app_for,
    configure_proxy_mode,
    shelve,
    sidecar_client,
    signed_in,
)


def _person(email: str) -> Actor:
    return Actor(name=email, email=email)


@intent("INT-AUTH-011")
def test_a_line_gives_its_path_and_everything_under_it() -> None:
    owners = Owners.parse(
        "# comment\n"
        "/                 root@example.com\n"
        "/galaxies/craft/  w@example.com   # the craft writer\n"
        "/galaxies/craft/skills/x  o@example.com O2@Example.com\n"
        "\n"
    )
    w, o, o2 = _person("w@example.com"), _person("o@example.com"), _person("o2@example.com")
    assert owners.may(w, Action.EDIT, "galaxies/craft/REF-X.md")
    assert owners.may(w, Action.CREATE, "galaxies/craft/skills/new")
    assert not owners.may(w, Action.EDIT, "galaxies/maker/GALAXY.md")
    assert owners.may(o, Action.EDIT, "galaxies/craft/skills/x")
    assert owners.may(o, Action.EDIT, "galaxies/craft/skills/x/templates/a.md")
    assert not owners.may(o, Action.EDIT, "galaxies/craft/skills/xy")
    assert not owners.may(o, Action.CREATE, "galaxies/craft/skills/new")
    assert owners.may(o2, Action.EDIT, "galaxies/craft/skills/x"), "emails match case-blind"
    assert not owners.may(o, Action.EDIT, "galaxies/craft/skills/x/../../REF-X.md")
    # Union, not last-match: the narrower line takes nothing from the root's owner.
    assert owners.may(_person("root@example.com"), Action.EDIT, "galaxies/craft/skills/x")
    assert [owners.role_of(p) for p in (_person("root@example.com"), w, o, _person("n@x.y"))] == [
        Role.ADMIN,
        Role.GALAXY_WRITER,
        Role.ATOM_OWNER,
        Role.READER,
    ]
    assert owners.may(o, Action.VALIDATE) and not owners.may(o, Action.ADMINISTER)
    assert not owners.may(_person("n@x.y"), Action.VALIDATE)
    assert not owners.may(None, Action.EDIT, "galaxies/craft/REF-X.md")
    assert owners.may(Actor("svc", "svc@x.y", service=True), Action.ADMINISTER)


@intent("INT-AUTH-011")
def test_no_owners_makes_everyone_a_reader() -> None:
    nobody = Owners()
    assert not nobody.may(_person(ADMIN), Action.EDIT, "AI-PLAYBOOK.md")
    assert nobody.role_of(_person(ADMIN)) is Role.READER


@intent("INT-AUTH-011")
def test_not_before_takes_a_date_or_a_timestamp() -> None:
    owners = Owners.parse(
        "not-before a@x.y 2026-10-01\nnot-before b@x.y 2026-10-02T12:30:00Z\n"
        "not-before a@x.y 2026-09-01\n"
    )
    assert owners.tokens_not_before("A@x.y") == datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert owners.tokens_not_before("b@x.y") == datetime(2026, 10, 2, 12, 30, tzinfo=timezone.utc)
    assert owners.tokens_not_before("c@x.y") is None


@intent("INT-AUTH-011")
@pytest.mark.parametrize(
    "text",
    [
        "galaxies/craft/ w@example.com",
        "/galaxies/*/ w@example.com",
        "/galaxies/../ w@example.com",
        "/galaxies/craft/",
        "/galaxies/craft/ @writers",
        "not-before w@example.com",
        "not-before w@example.com yesterday",
    ],
    ids=["unanchored", "pattern", "escapes", "no-owner", "handle", "no-date", "bad-date"],
)
def test_text_that_does_not_parse_is_refused_naming_the_line(text: str) -> None:
    with pytest.raises(InvalidOwnersError, match="OWNERS line 2"):
        Owners.parse("/ admin@example.com\n" + text)


def _owners_put(client, raw: str, who: str = ADMIN):
    return client.put("/api/owners", json={"raw": raw}, headers=signed_in(who))


@intent("INT-AUTH-011")
def test_an_admin_edit_takes_effect_on_the_next_request(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    git = FakeGitSync()
    client = sidecar_client(app_for(root, git))
    assert client.get("/api/owners").json() == {"raw": OWNERS_TEXT}
    assert client.get("/api/me", headers=signed_in(WRITER)).json()["galaxies"] == ["craft"]

    granted = OWNERS_TEXT + f"/galaxies/maker/  {WRITER}\n"
    res = _owners_put(client, granted)
    assert res.status_code == 200, res.text
    assert git.commits[-1] == "chore(owners): replace OWNERS" and git.authors[-1].email == ADMIN
    assert (root / "OWNERS").read_text(encoding="utf-8") == granted
    assert client.get("/api/me", headers=signed_in(WRITER)).json()["galaxies"] == ["craft", "maker"]


@intent("INT-AUTH-011")
@pytest.mark.parametrize(
    ("raw", "names"),
    [
        (OWNERS_TEXT + "/galaxies/craft/skills/no-such-skill/ owner@example.com\n", "line 6"),
        (OWNERS_TEXT + "/galaxies/craft/ writer@example.com,\n", "line 6"),
        (OWNERS_TEXT + "galaxies/maker/ writer@example.com\n", "line 6"),
    ],
    ids=["missing-path", "bad-owner", "unanchored"],
)
def test_an_edit_that_does_not_parse_or_names_a_missing_path_is_refused(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch, raw: str, names: str
) -> None:
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    git = FakeGitSync()
    client = sidecar_client(app_for(root, git))
    res = _owners_put(client, raw)
    assert res.status_code == 400
    assert names in res.json()["detail"]
    assert (root / "OWNERS").read_text(encoding="utf-8") == OWNERS_TEXT
    assert git.commits == []


@intent("INT-AUTH-011")
def test_a_gate_refusal_restores_owners(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    git = FakeGitSync()
    client = sidecar_client(app_for(root, git, ok=False))
    assert _owners_put(client, OWNERS_TEXT + f"/galaxies/maker/ {WRITER}\n").status_code == 422
    assert (root / "OWNERS").read_text(encoding="utf-8") == OWNERS_TEXT
    assert git.commits == []


@intent("INT-AUTH-011")
@pytest.mark.parametrize(
    "owners",
    [None, f"/ {ADMIN}\ngalaxies/craft/ {WRITER}\n"],
    ids=["none", "unparsable"],
)
def test_a_corpus_without_parsable_owners_fails_closed(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch, owners: str | None
) -> None:
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root, owners=owners)
    client = sidecar_client(app_for(root, FakeGitSync()))
    for who in (ADMIN, WRITER, OWNER, READER):
        assert client.get("/api/me", headers=signed_in(who)).json()["role"] == "reader"
        skill = root / "galaxies/craft/skills/do-alpha/SKILL.md"
        res = client.put(
            "/api/skills/do-alpha",
            json={"raw": skill.read_text(encoding="utf-8") + "\nx\n"},
            headers=signed_in(who),
        )
        assert res.status_code == 403


@intent("INT-AUTH-011")
def test_a_writer_names_the_owners_of_what_they_create(
    playbook_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The owners named at creation get one OWNERS line in the same transaction, and
    may edit the new atom at once; a refused creation takes the line away again."""
    configure_proxy_mode(monkeypatch)
    root = shelve(playbook_root)
    git = FakeGitSync()
    client = sidecar_client(app_for(root, git))
    card = {
        "kind": "mcp",
        "name": "beta-door",
        "galaxy": "craft",
        "raw": DOOR_CARD.format(name="beta-door"),
        "owners": [READER],
    }
    res = client.post("/api/doors", json=card, headers=signed_in(WRITER))
    assert res.status_code == 201, res.text
    assert (root / "OWNERS").read_text(encoding="utf-8").endswith(
        f"/galaxies/craft/mcps/beta-door.md {READER}\n"
    )
    assert client.get("/api/doors/beta-door", headers=signed_in(READER)).json()["can_edit"]
    assert len(git.commits) == 1

    bad = {**card, "name": "gamma-door", "raw": DOOR_CARD.format(name="gamma-door")}
    refused = sidecar_client(app_for(root, git, ok=False))
    assert refused.post("/api/doors", json=bad, headers=signed_in(WRITER)).status_code == 422
    assert "gamma-door" not in (root / "OWNERS").read_text(encoding="utf-8")
    assert not (root / "galaxies/craft/mcps/gamma-door.md").exists()
    not_emails = {**card, "name": "delta-door", "owners": ["@readers"]}
    assert client.post("/api/doors", json=not_emails, headers=signed_in(WRITER)).status_code == 400
