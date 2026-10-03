"""Divide an amount of cents into shares that add up exactly to the total."""

from collections.abc import Iterable


def split_equally(total_cents: int, member_ids: Iterable[int]) -> dict[int, int]:
    """Split total_cents equally; leftover cents go one each to the lowest member ids."""
    ids = sorted(member_ids)
    if not ids:
        raise ValueError("cannot split between zero members")
    if len(set(ids)) != len(ids):
        raise ValueError("member ids must be unique")
    if total_cents < 0:
        raise ValueError("total must not be negative")
    base, remainder = divmod(total_cents, len(ids))
    return {member_id: base + (1 if index < remainder else 0) for index, member_id in enumerate(ids)}
