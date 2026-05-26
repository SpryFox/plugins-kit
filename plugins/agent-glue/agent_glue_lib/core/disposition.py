"""The Disposition primitive: typed-outcome ADT for `Accepted | AcceptedWithAudit | Rejected`.

Composable with any subsystem-specific success type via the generic `T`.
"""

from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Accepted(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["accepted"] = "accepted"
    value: T


class AcceptedWithAudit(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["accepted_with_audit"] = "accepted_with_audit"
    value: T
    audit_reason: str
    audit_metadata: dict[str, Any] = Field(default_factory=dict)


class Rejected(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["rejected"] = "rejected"
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


Disposition = Union[Accepted[T], AcceptedWithAudit[T], Rejected]
