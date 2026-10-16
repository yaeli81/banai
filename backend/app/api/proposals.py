"""POST /api/proposals/apply: apply a signed proposal to the exact design it was made for."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.errors import domain_error_response, error_response
from app.config import Settings, get_settings
from app.domain.apply import apply_ops
from app.domain.catalog import load_catalog
from app.domain.errors import DomainError
from app.services import signing

router = APIRouter(prefix="/api/proposals")


class SignedProposal(BaseModel):
    # Display-only fields (summary, changes) may come back from the client; they are ignored.
    model_config = ConfigDict(extra="ignore")
    proposal_id: Annotated[str, Field(alias="proposalId", pattern=r"^prop_[0-9a-f]{32}$")]
    base_revision: Annotated[int, Field(alias="baseRevision", ge=1)]
    base_hash: Annotated[str, Field(alias="baseHash", pattern=r"^[0-9a-f]{64}$")]
    ops: Annotated[list, Field(max_length=100)]
    signature: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    design: dict
    revision: Annotated[int, Field(ge=1, le=1_000_000_000)]
    proposal: SignedProposal


@router.post("/apply")
def apply_proposal(body: ApplyRequest, settings: Annotated[Settings, Depends(get_settings)]):
    proposal = body.proposal
    key = settings.proposal_signing_key.get_secret_value()
    if not signing.verify(key, proposal.signature, proposal.proposal_id, proposal.ops,
                          proposal.base_revision, proposal.base_hash):
        return error_response(403, "BAD_SIGNATURE", "This proposal is not valid. Please ask the designer again.")

    catalog = load_catalog()
    try:
        design = apply_ops(body.design, [], catalog)
    except DomainError as error:
        return domain_error_response(error)
    if body.revision != proposal.base_revision or signing.design_hash(design) != proposal.base_hash:
        return error_response(409, "STALE", "The design changed after this proposal was made.")

    try:
        new_design = apply_ops(design, proposal.ops, catalog)
    except DomainError as error:  # cannot happen for a signed, fresh proposal; kept as a guard
        return domain_error_response(error)
    return {"success": True, "data": {"design": new_design, "revision": body.revision + 1}, "error": None}
