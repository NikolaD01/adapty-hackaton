from tests.fakes import FakeValueStore
from tests.service.test_insight_service import Dataset, service


async def test_live_outcomes_come_from_explicit_seed_dataset_not_offline_csv():
    class SeedOutcomes(Dataset):
        def transactions(self):
            frame = super().transactions()
            frame["price_usd"] = 5.0
            return frame

    values = FakeValueStore()
    await values.put_many("app", "edits", {f"u{i:05d}": float(i // 1000) for i in range(3000)})
    svc = service(value_store=values, live_dataset=SeedOutcomes())
    offline = await svc.run("app", "offline")
    live = await svc.run("app", "live")
    assert any(item.passed for item in offline.rankings)
    assert live.source == "live"
    assert live.rankings and not any(item.passed for item in live.rankings)
    assert all(item.lift == 1 for item in live.rankings)
