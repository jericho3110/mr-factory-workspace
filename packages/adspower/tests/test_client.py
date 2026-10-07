import unittest
from unittest import mock

from mrfactory.adspower import (
    AdsPower,
    AdsPowerApiError,
    AdsPowerNotRunning,
    AmbiguousProfile,
    Group,
    GroupNotFound,
    ProfileNotFound,
    ProxyNotFound,
    TagNotFound,
)
from tests.fakes import FakeApi


class TestGroups(unittest.TestCase):
    def setUp(self):
        self.ads = AdsPower(FakeApi())

    def test_lists_every_group(self):
        groups = self.ads.groups()
        self.assertEqual([g.name for g in groups], ["Ungrouped", "Shopify", "Socials", "Jericho"])
        self.assertEqual(groups[1], Group(id="101", name="Shopify", remark="stores"))
        self.assertEqual(groups[2].remark, "")  # null in the API becomes ""

    def test_filters_groups_by_part_of_the_name(self):
        self.assertEqual([g.name for g in self.ads.groups(name="JER")], ["Jericho"])
        self.assertEqual([g.name for g in self.ads.groups(name="s")], ["Shopify", "Socials"])

    def test_finds_group_by_name_ignoring_case_or_by_id(self):
        self.assertEqual(self.ads.find_group("shopify").id, "101")
        self.assertEqual(self.ads.find_group("102").name, "Socials")

    def test_unknown_group_lists_the_real_ones(self):
        with self.assertRaises(GroupNotFound) as caught:
            self.ads.find_group("Nope")
        self.assertIn("Shopify", str(caught.exception))


class TestTags(unittest.TestCase):
    def setUp(self):
        self.ads = AdsPower(FakeApi())

    def test_lists_and_filters_tags(self):
        self.assertEqual([t.name for t in self.ads.tags()], ["jericho", "Sales"])
        self.assertEqual([t.name for t in self.ads.tags(name="SAL")], ["Sales"])

    def test_finds_tag_ignoring_case(self):
        self.assertEqual(self.ads.find_tag("Jericho").id, "900")

    def test_unknown_tag_is_an_error_not_a_new_tag(self):
        with self.assertRaises(TagNotFound) as caught:
            self.ads.find_tag("Jerico")
        self.assertIn("jericho", str(caught.exception))


class TestProfiles(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.ads = AdsPower(self.api)

    def test_lists_all_profiles_sorted_by_serial_number(self):
        serials = [p.serial_number for p in self.ads.profiles()]
        self.assertEqual(serials, ["2", "3", "10"])  # numeric, not "10" < "2"

    def test_group_filter_sends_the_group_id_to_the_api(self):
        profiles = self.ads.profiles(group="Shopify")
        self.assertEqual({p.group_name for p in profiles}, {"Shopify"})
        path, body = self.api.calls[-1]
        self.assertEqual((path, body["group_id"]), ("/api/v2/browser-profile/list", "101"))

    def test_tag_filter_sends_the_tag_id_to_the_api(self):
        profiles = self.ads.profiles(tag="sales")
        self.assertEqual([p.id for p in profiles], ["k2a"])
        self.assertEqual(profiles[0].tags, ("Sales",))
        self.assertEqual(self.api.calls[-1][1]["tag_ids"], ["901"])

    def test_group_object_is_used_without_looking_it_up(self):
        self.ads.profiles(group=Group(id="102", name="Socials"))
        self.assertEqual(len(self.api.calls), 1)

    def test_parses_last_open_time(self):
        by_id = {p.id: p for p in self.ads.profiles()}
        self.assertEqual(by_id["k1a"].last_open_time.year, 2023)
        self.assertIsNone(by_id["k1b"].last_open_time)  # "0" = never opened
        self.assertIsNone(by_id["k2a"].last_open_time)  # "" = never opened

    def test_search_matches_name_remark_serial_and_id(self):
        def ids(text):
            return {p.id for p in self.ads.search_profiles(text)}

        self.assertEqual(ids("JOHN"), {"k1a", "k2a"})  # name, and remark "johnny's"
        self.assertEqual(ids("10"), {"k1a"})           # serial number
        self.assertEqual(ids("k2"), {"k2a"})           # profile ID
        self.assertEqual(ids("zzz"), set())

    def test_search_within_a_group(self):
        found = self.ads.search_profiles("john", group="Shopify")
        self.assertEqual([p.id for p in found], ["k1a"])


class TestFindProfile(unittest.TestCase):
    def setUp(self):
        self.ads = AdsPower(FakeApi())

    def test_serial_number_or_id_is_an_exact_match(self):
        self.assertEqual(self.ads.find_profile("2").id, "k1b")  # serial 2 wins over ID "k2a" containing "2"
        self.assertEqual(self.ads.find_profile("k2a").name, "Insta\nmain")

    def test_single_text_match(self):
        self.assertEqual(self.ads.find_profile("jane").id, "k1b")

    def test_several_matches_are_reported_with_the_candidates(self):
        with self.assertRaises(AmbiguousProfile) as caught:
            self.ads.find_profile("shop")
        self.assertEqual({p.id for p in caught.exception.matches}, {"k1a", "k1b"})

    def test_group_narrows_the_search(self):
        self.assertEqual(self.ads.find_profile("john", group="Socials").id, "k2a")

    def test_blank_text_matches_nothing_instead_of_everything(self):
        for blank in ("", "   "):
            with self.assertRaises(ProfileNotFound):
                self.ads.find_profile(blank)

    def test_no_match(self):
        with self.assertRaises(ProfileNotFound):
            self.ads.find_profile("zzz", group="Shopify")


class TestExactLookup(unittest.TestCase):
    """Serial numbers and IDs are looked up on AdsPower's side with one
    small request, instead of downloading every profile."""

    def setUp(self):
        self.api = FakeApi()
        self.ads = AdsPower(self.api)

    def test_serial_number_is_one_request(self):
        self.assertEqual(self.ads.find_profile("10").id, "k1a")
        self.assertEqual(self.api.calls, [("/api/v2/browser-profile/list",
                                           {"profile_no": ["10"], "page": 1, "limit": 1})])

    def test_id_is_one_request(self):
        self.assertEqual(self.ads.find_profile("k2a").serial_number, "3")
        self.assertEqual(len(self.api.calls), 1)

    def test_plain_text_skips_the_exact_lookup(self):
        self.ads.find_profile("jane")
        self.assertNotIn("/api/v2/browser-profile/list",
                         [path for path, body in self.api.calls if body and "profile_no" in body])

    def test_exact_match_in_another_group_falls_back_to_search(self):
        # "10" is John Shop's serial, but he's in Shopify; in Socials nothing contains "10"
        with self.assertRaises(ProfileNotFound):
            self.ads.find_profile("10", group="Socials")


class TestOpenProfile(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.ads = AdsPower(self.api)

    def test_opens_by_search_and_returns_connection_details(self):
        browser = self.ads.open_profile("jane")
        self.assertEqual(browser.profile_id, "k1b")
        self.assertEqual(browser.puppeteer, "ws://127.0.0.1:1/k1b")
        self.assertTrue(self.ads.is_profile_open("k1b"))

    def test_profile_object_is_opened_without_a_lookup(self):
        profile = self.ads.find_profile("jane")
        calls_before = len(self.api.calls)
        self.ads.open_profile(profile)
        self.assertEqual(self.api.calls[calls_before:], [("/api/v1/browser/start", {"user_id": "k1b"})])

    def test_browser_still_downloading_gets_a_hint(self):
        def start_fails(path, **params):
            raise AdsPowerApiError("/api/v1/browser/start failed: SunBrowser 153 is updating, waiting for download.")

        self.api.get = start_fails
        with self.assertRaisesRegex(AdsPowerApiError, "Wait a minute"):
            self.ads.open_profile(self.ads.find_profile("jane"))

    def test_close(self):
        self.ads.open_profile("k1b")
        self.ads.close_profile("k1b")
        self.assertFalse(self.ads.is_profile_open("k1b"))


class TestProxies(unittest.TestCase):
    def setUp(self):
        self.ads = AdsPower(FakeApi())

    def test_filters_by_tag_ignoring_case_and_by_unused(self):
        self.assertEqual([p.id for p in self.ads.proxies(tag="jericho")], ["p1", "p2"])
        self.assertEqual([p.id for p in self.ads.proxies(tag="Jericho", unused=True)], ["p2"])
        self.assertEqual(len(self.ads.proxies()), 3)

    def test_password_is_never_kept(self):
        proxy = self.ads.proxies()[0]
        self.assertFalse(hasattr(proxy, "password"))
        self.assertNotIn("secret", repr(proxy))

    def test_choose_picks_an_unused_tagged_proxy(self):
        self.assertEqual(self.ads.choose_proxy(tag="Jericho").id, "p2")

    def test_choose_by_id_must_have_the_tag(self):
        self.assertEqual(self.ads.choose_proxy(tag="Jericho", proxy_id="p1").id, "p1")  # in use is fine when named
        with self.assertRaises(ProxyNotFound):
            self.ads.choose_proxy(tag="Jericho", proxy_id="p3")  # tagged Support

    def test_choose_fails_when_every_tagged_proxy_is_in_use(self):
        api = FakeApi()
        api.post_all = lambda path, limit, **body: [
            {"proxy_id": "x", "profile_count": "1", "proxy_tags": [{"name": "Jericho"}]}
        ]
        with self.assertRaisesRegex(ProxyNotFound, "all in use"):
            AdsPower(api).choose_proxy(tag="Jericho")


class TestChangeProxy(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.ads = AdsPower(self.api)

    def test_profile_shows_its_proxy_without_the_password(self):
        profile = self.ads.find_profile("10")
        self.assertEqual(profile.proxy, "http://1.1.1.1:8000")
        self.assertNotIn("secret", repr(profile))
        self.assertEqual(self.ads.find_profile("2").proxy, "")  # no_proxy

    def test_current_proxy_is_found_through_the_proxy_list(self):
        self.assertEqual(self.ads.current_proxy("10").id, "p1")   # p1.used_by contains "10"
        self.assertIsNone(self.ads.current_proxy("2"))

    def test_set_proxy_equips_a_chosen_proxy(self):
        self.ads.set_proxy("2", self.ads.choose_proxy(tag="Jericho"))
        self.assertEqual(self.api.updates, [{"profile_id": "k1b", "proxyid": "p2"}])
        self.assertEqual(self.ads.find_profile("2").proxy, "socks5://2.2.2.2:9000")

    def test_set_proxy_none_removes_it(self):
        self.ads.set_proxy("10", None)
        self.assertEqual(self.api.updates, [{"profile_id": "k1a", "user_proxy_config": {"proxy_soft": "no_proxy"}}])
        self.assertEqual(self.ads.find_profile("10").proxy, "")


class TestCreateProfile(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.ads = AdsPower(self.api)

    def test_creates_in_group_with_tag_and_no_proxy(self):
        profile = self.ads.create_profile("Shop 8", group="jericho", tag="JERICHO")
        body = self.api.created[0]
        self.assertEqual(body["group_id"], "103")
        self.assertEqual(body["profile_tag_ids"], ["900"])
        self.assertEqual(body["user_proxy_config"], {"proxy_soft": "no_proxy"})
        self.assertNotIn("proxyid", body)
        self.assertEqual((profile.id, profile.serial_number, profile.group_name, profile.tags),
                         ("new1", "500", "Jericho", ("jericho",)))

    def test_creates_with_a_chosen_proxy(self):
        proxy = self.ads.choose_proxy(tag="Jericho")
        self.ads.create_profile("Shop 8", group="Jericho", tag="jericho", proxy=proxy)
        body = self.api.created[0]
        self.assertEqual(body["proxyid"], "p2")
        self.assertNotIn("user_proxy_config", body)

    def test_missing_group_or_tag_creates_nothing(self):
        with self.assertRaises(GroupNotFound):
            self.ads.create_profile("x", group="Nope", tag="jericho")
        with self.assertRaises(TagNotFound):
            self.ads.create_profile("x", group="Jericho", tag="Nope")
        self.assertEqual(self.api.created, [])


class TestOpen(unittest.TestCase):
    def test_open_without_wait_does_not_touch_the_api(self):
        api = FakeApi(running=False)
        with mock.patch("mrfactory.adspower.client.open_adspower", return_value="exe") as opened:
            self.assertEqual(AdsPower(api).open("path"), "exe")
        opened.assert_called_once_with("path")

    def test_open_with_wait_times_out_if_api_never_answers(self):
        ads = AdsPower(FakeApi(running=False))
        with mock.patch("mrfactory.adspower.client.open_adspower"), \
                mock.patch("mrfactory.adspower.client.time.sleep"), self.assertRaises(AdsPowerNotRunning):
            ads.open(wait=0.01)

    def test_open_with_wait_returns_once_running(self):
        ads = AdsPower(FakeApi(running=True))
        with mock.patch("mrfactory.adspower.client.open_adspower", return_value="exe"):
            self.assertEqual(ads.open(wait=5), "exe")


if __name__ == "__main__":
    unittest.main()
