"""Stateless proposal signing: the server stores nothing between /chat and /apply.

A proposal is bound to the exact design it was made for (`baseHash`) and to its
revision (`baseRevision`). The HMAC covers those plus the ops, so a client can
neither edit the ops nor replay them on a different design.
"""

from __future__ import annotations

import hashlib
import hmac
import json


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def design_hash(design: dict) -> str:
    return hashlib.sha256(canonical_json(design)).hexdigest()


def _payload(proposal_id: str, ops: list, base_revision: int, base_hash: str) -> bytes:
    return canonical_json(
        {"proposalId": proposal_id, "ops": ops, "baseRevision": base_revision, "baseHash": base_hash}
    )


def sign(key: str, proposal_id: str, ops: list, base_revision: int, base_hash: str) -> str:
    payload = _payload(proposal_id, ops, base_revision, base_hash)
    return hmac.new(key.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify(key: str, signature: str, proposal_id: str, ops: list, base_revision: int, base_hash: str) -> bool:
    expected = sign(key, proposal_id, ops, base_revision, base_hash)
    return hmac.compare_digest(expected, signature)
