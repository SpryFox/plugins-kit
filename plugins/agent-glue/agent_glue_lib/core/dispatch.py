"""Variant-dispatch library primitive.

Reads the discriminator field of a tagged-union value (default `kind`) and invokes the matching
handler. Used by the graph runtime to route on Edge `Source.on_variant`; usable directly by
any consumer that wants the same shape inside a single worker's post-processing.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from pydantic import BaseModel

_MISSING = object()


class NoHandlerForVariant(Exception):
    """Raised when no handler matches the variant's discriminator and no default was supplied."""

    def __init__(self, discriminator: str, value: str, known: list[str]) -> None:
        self.discriminator = discriminator
        self.value = value
        self.known = known
        super().__init__(
            f"No handler for variant {discriminator}={value!r}; known: {sorted(known)!r}."
        )


def _read_discriminator(variant: Any, discriminator: str) -> str:
    if isinstance(variant, BaseModel):
        if discriminator not in type(variant).model_fields:
            raise TypeError(
                f"Variant {type(variant).__name__!r} has no field {discriminator!r}."
            )
        value = getattr(variant, discriminator)
    elif isinstance(variant, dict):
        if discriminator not in variant:
            raise KeyError(
                f"Variant dict has no key {discriminator!r}: {sorted(variant.keys())!r}."
            )
        value = variant[discriminator]
    else:
        value = getattr(variant, discriminator, _MISSING)
        if value is _MISSING:
            raise TypeError(
                f"Variant {type(variant).__name__!r} has no attribute {discriminator!r}."
            )
    if not isinstance(value, str):
        raise TypeError(
            f"Discriminator {discriminator!r} must be a string, got {type(value).__name__!r}."
        )
    return value


def dispatch(
    variant: Any,
    handlers: dict[str, Callable[[Any], Any]],
    *,
    discriminator: str = "kind",
    default: Optional[Callable[[Any], Any]] = None,
) -> Any:
    """Call `handlers[variant.kind](variant)`; on no match call `default(variant)` or raise."""
    value = _read_discriminator(variant, discriminator)
    handler = handlers.get(value)
    if handler is not None:
        return handler(variant)
    if default is not None:
        return default(variant)
    raise NoHandlerForVariant(discriminator, value, list(handlers.keys()))
