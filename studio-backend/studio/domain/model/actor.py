"""Who acts on the corpus: a person signed in on a door, or the service itself."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Actor"]


@dataclass(frozen=True)
class Actor:
    """The identity a request acts as, resolved at the door it came through.

    A person is named by the email the OIDC proxy forwards (the human door) or a
    personal token carries (the machine door); their rights come from OWNERS and
    their commits carry their name. The service is the studio's own identity: the
    shared machine credential, the stand-alone Basic gate, and the content poll
    act as it, with the authority of the deployment and the configured git
    identity as author.
    """

    name: str
    email: str
    service: bool = False
