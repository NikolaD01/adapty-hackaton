"""C6 - ask Adapty which flow each user gets (the demo proof). Depends only on the `FlowLookup` port."""

import asyncio
from collections.abc import Sequence

from feature_signal.domain.models import ServedFlow
from feature_signal.domain.ports import FlowLookup


class LookupService:
    def __init__(self, lookup: FlowLookup) -> None:
        self._lookup = lookup

    async def lookup(self, placement: str, customer_user_ids: Sequence[str]) -> list[ServedFlow]:
        return list(await asyncio.gather(*(self._lookup.served(user, placement) for user in customer_user_ids)))
