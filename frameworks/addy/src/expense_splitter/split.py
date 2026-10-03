"""Allocation of an expense total into per-member shares, exact to the cent."""

from collections.abc import Sequence

from expense_splitter.money import Cents

Share = tuple[str, Cents]


def split_equally(total: Cents, member_ids: Sequence[str]) -> list[Share]:
    """Split `total` cents equally; the first `total % n` members each get one extra cent."""
    if not member_ids:
        raise ValueError("cannot split between zero members")
    base, remainder = divmod(total, len(member_ids))
    return [
        (member_id, base + (1 if i < remainder else 0)) for i, member_id in enumerate(member_ids)
    ]
