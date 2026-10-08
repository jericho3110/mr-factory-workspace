"""batch.py and AdsPower.plan_batch / create_batch. All data is made up;
IPs are RFC 5737 documentation addresses."""

import unittest

from mrfactory.adspower import (
    AdsPower,
    AdsPowerApiError,
    BatchCreator,
    BatchSettings,
    Group,
    Outcome,
    PlanStatus,
    Proxy,
    Tag,
    TagNotFound,
    free_proxies,
    name_key,
    plan,
    results_text,
    summarize,
)
from mrfactory.adspower.batch import NAME_MAX
from mrfactory.adspower.models import Profile
from tests.fakes import FakeApi


def proxy(pid: str, used: int = 0) -> Proxy:
    return Proxy(id=pid, type="socks5", host=f"203.0.113.{pid}", port="1080", tags=("Acme",), profile_count=used)


def profile(name: str) -> Profile:
    return Profile(id="x", serial_number="1", name=name, group_id="g", group_name="G")


SETTINGS = BatchSettings(Group("103", "Acme"), Tag("900", "acme"), proxy_tag="Acme", remark="r")


class FakeAds:
    """Just what BatchCreator calls: proxies(tag=) and create_profile().
    Marks a proxy used when it's given out, as AdsPower does."""

    def __init__(self, proxies, profiles=()):
        self.proxy_list = list(proxies)
        self.profile_list = list(profiles)
        self.created = []
        self.fail = {}
        self.before_create = None

    def proxies(self, tag=None, unused=False):
        return list(self.proxy_list)     # ignores `tag` on purpose: the creator must check tags itself

    def profiles(self, group=None, tag=None):
        return list(self.profile_list)

    def create_profile(self, name, group, tag, proxy=None, remark=""):
        if self.before_create:
            self.before_create(name)
        if name in self.fail:
            raise self.fail[name]
        if any(c[1] == proxy.id for c in self.created):
            raise AssertionError("proxy given out twice")
        self.created.append((name, proxy.id, remark))
        new = Profile(id=f"new{len(self.created)}", serial_number=str(500 + len(self.created)), name=name,
                      group_id=group.id, group_name=group.name)
        self.profile_list.append(new)
        return new


class TestPlan(unittest.TestCase):
    def test_one_free_proxy_each_in_order(self):
        planned = plan(["A", "B"], [], [proxy("10"), proxy("12")])
        self.assertEqual([(p.status, p.proxy.id) for p in planned],
                         [(PlanStatus.READY, "10"), (PlanStatus.READY, "12")])

    def test_skips_existing_repeated_too_long_without_using_proxies(self):
        planned = plan(["shop 7", "A", "a", "x" * (NAME_MAX + 1), "B"], [profile("Shop 7")],
                       [proxy("10"), proxy("12")])
        self.assertEqual([p.status for p in planned], [PlanStatus.EXISTS, PlanStatus.READY, PlanStatus.REPEATED,
                                                       PlanStatus.TOO_LONG, PlanStatus.READY])
        self.assertEqual([p.proxy.id for p in planned if p.proxy], ["10", "12"])

    def test_runs_out_of_proxies(self):
        self.assertEqual([p.status for p in plan(["A", "B"], [], [proxy("10")])],
                         [PlanStatus.READY, PlanStatus.NO_PROXY])

    def test_similar_names_are_duplicates(self):
        existing = [Profile(id="x", serial_number="16", name="Shop-8", group_id="g", group_name="Other")]
        planned = plan(["shop 8", "SHOP_8", "Shop.9", "shop9"], existing, [proxy("10"), proxy("12")])
        self.assertEqual([p.status for p in planned],
                         [PlanStatus.SIMILAR, PlanStatus.SIMILAR, PlanStatus.READY, PlanStatus.REPEATED])
        self.assertEqual(planned[0].note, "similar name exists: #16 Shop-8")

    def test_allow_similar_only_blocks_exact_names(self):
        existing = [profile("Shop-8")]
        planned = plan(["shop 8", "SHOP-8"], existing, [proxy("10")], allow_similar=True)
        self.assertEqual([p.status for p in planned], [PlanStatus.READY, PlanStatus.EXISTS])

    def test_name_key(self):
        self.assertEqual(name_key(" Shop-Eig_ht.X "), "shopeightx")

    def test_free_proxies(self):
        self.assertEqual([p.id for p in free_proxies([proxy("10"), proxy("11", used=1)])], ["10"])


class TestBatchCreator(unittest.TestCase):
    def test_creates_with_remark_and_reports_each(self):
        ads, seen = FakeAds([proxy("10"), proxy("12")]), []
        planned = plan(["A", "Shop 7", "B"], [profile("Shop 7")], free_proxies(ads.proxies()))

        results = BatchCreator(ads, on_result=seen.append).run(planned, SETTINGS)

        self.assertEqual([r.outcome for r in results], [Outcome.CREATED, Outcome.SKIPPED, Outcome.CREATED])
        self.assertEqual(ads.created, [("A", "10", "r"), ("B", "12", "r")])
        self.assertEqual(seen, results)
        self.assertEqual(summarize(results), "2 created, 1 skipped")
        self.assertEqual(results_text(results).splitlines()[1], "A\t501\tnew1\t203.0.113.10:1080\tcreated")

    def test_taken_proxy_is_swapped_never_stealing_a_later_one(self):
        ads = FakeAds([proxy("10"), proxy("12"), proxy("14")])
        planned = plan(["A", "B"], [], free_proxies(ads.proxies()))      # A:10, B:12
        ads.proxy_list[0] = proxy("10", used=1)                           # 10 got used meanwhile

        results = BatchCreator(ads).run(planned, SETTINGS)

        self.assertEqual([r.proxy.id for r in results], ["14", "12"])

    def test_no_replacement_left_skips(self):
        ads = FakeAds([proxy("10")])
        planned = plan(["A"], [], free_proxies(ads.proxies()))
        ads.proxy_list[0] = proxy("10", used=1)
        result = BatchCreator(ads).run(planned, SETTINGS)[0]
        self.assertEqual((result.outcome, result.message), (Outcome.SKIPPED, "no free proxy tagged 'Acme' left"))

    def test_running_the_same_batch_twice_creates_nothing_the_second_time(self):
        # Regression (asked for): Create pressed twice, or a profile made
        # elsewhere after the plan. The creator re-reads the account first.
        ads = FakeAds([proxy("10"), proxy("12"), proxy("14")])
        planned = plan(["A", "B"], [], free_proxies(ads.proxies()))
        BatchCreator(ads).run(planned, SETTINGS)

        again = BatchCreator(ads).run(planned, SETTINGS)

        self.assertEqual([r.outcome for r in again], [Outcome.SKIPPED, Outcome.SKIPPED])
        self.assertEqual(again[0].message, "already exists: #501 A (created after the plan)")
        self.assertEqual(len(ads.created), 2)

    def test_similar_profile_created_after_the_plan_is_caught(self):
        ads = FakeAds([proxy("10")])
        planned = plan(["Shop 8"], [], free_proxies(ads.proxies()))
        ads.profile_list.append(profile("shop-8"))            # someone made it meanwhile
        result = BatchCreator(ads).run(planned, SETTINGS)[0]
        self.assertEqual(result.outcome, Outcome.SKIPPED)
        self.assertTrue(result.message.startswith("similar name exists"))

    def test_never_uses_a_proxy_without_the_tag(self):
        # Even if the plan (or the API) offers one: tags are re-checked at creation.
        other = Proxy(id="99", type="socks5", host="203.0.113.99", port="1080", tags=("Other",))
        ads = FakeAds([other, proxy("10")])
        planned = plan(["A", "B"], [], [other, proxy("10")])   # a plan built from the wrong list
        results = BatchCreator(ads).run(planned, SETTINGS)
        # A's untagged proxy is refused; the only tagged one is B's, and isn't stolen.
        self.assertEqual([r.proxy.id if r.proxy else None for r in results], [None, "10"])
        self.assertEqual(results[0].outcome, Outcome.SKIPPED)
        self.assertNotIn("99", [c[1] for c in ads.created])

    def test_failure_carries_on_and_stop_is_between_profiles(self):
        ads = FakeAds([proxy("10"), proxy("12"), proxy("14")])
        ads.fail["A"] = AdsPowerApiError("limit reached")
        creator = BatchCreator(ads)
        ads.before_create = lambda name: creator.stop() if name == "B" else None   # Stop pressed during B
        results = creator.run(plan(["A", "B", "C"], [], free_proxies(ads.proxies())), SETTINGS)
        self.assertEqual([r.outcome for r in results], [Outcome.FAILED, Outcome.CREATED, Outcome.NOT_RUN])
        self.assertEqual(results[0].message, "limit reached")


class TestClientBatch(unittest.TestCase):
    def test_plan_batch_defaults_proxy_tag_to_the_tag(self):
        api = FakeApi()
        batch = AdsPower(api).plan_batch(["New A", "New B", "John Shop"], group="acme", tag="ACME")

        self.assertEqual(batch.settings.group.name, "Acme")
        self.assertEqual(batch.settings.proxy_tag, "acme")
        # Only p2 is free among the Acme-tagged proxies; John Shop exists.
        self.assertEqual([p.status for p in batch.planned],
                         [PlanStatus.READY, PlanStatus.NO_PROXY, PlanStatus.EXISTS])
        self.assertEqual(batch.summary(), "1 of 3 ready; 1 free proxy tagged 'acme'.")
        self.assertEqual(api.created, [])                                  # planning creates nothing

    def test_create_batch(self):
        api = FakeApi()
        ads = AdsPower(api)
        results = ads.create_batch(ads.plan_batch(["New A"], group="Acme", tag="acme", remark="batch 1"))
        self.assertEqual(results[0].outcome, Outcome.CREATED)
        body = api.created[0]
        self.assertEqual((body["name"], body["group_id"], body["profile_tag_ids"], body["proxyid"], body["remark"]),
                         ("New A", "103", ["900"], "p2", "batch 1"))

    def test_typo_in_tag_fails_before_planning(self):
        with self.assertRaises(TagNotFound):
            AdsPower(FakeApi()).plan_batch(["X"], group="Acme", tag="acm")


if __name__ == "__main__":
    unittest.main()
