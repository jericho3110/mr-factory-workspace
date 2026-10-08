"""proxycheck.py and AdsPower.check_proxy, with a fake fetch (no browser,
no network). IPs are RFC 5737 documentation addresses."""

import sys
import unittest
from unittest import mock

from mrfactory.adspower import (
    AdsPower,
    OpenedBrowser,
    ProxyCheckUnavailable,
    check_browser,
    error_code,
    parse_ip,
)
from mrfactory.adspower.proxycheck import CHECK_URL, playwright_fetch
from tests.fakes import FakeApi

BROWSER = OpenedBrowser(profile_id="k1a", debug_port="1", puppeteer="ws://127.0.0.1:1/x")


def answer(text):
    def fetch(ws, url):
        fetch.calls.append((ws, url))
        if isinstance(text, Exception):
            raise text
        return text
    fetch.calls = []
    return fetch


class TestParsing(unittest.TestCase):
    def test_parse_ip(self):
        self.assertEqual(parse_ip('{"ip":"198.51.100.7"}'), "198.51.100.7")
        self.assertEqual(parse_ip('{"ip":"2001:db8::1"}'), "2001:db8::1")
        for bad in ("", "<html>", '{"ip":"localhost"}', '{"x":1}', "[1]", '"198.51.100.7"'):
            with self.subTest(bad=bad):
                self.assertIsNone(parse_ip(bad))

    def test_error_code(self):
        self.assertEqual(error_code("Page.goto: net::ERR_PROXY_CONNECTION_FAILED at https://x/"),
                         "ERR_PROXY_CONNECTION_FAILED")
        self.assertEqual(error_code("Timeout 45000ms exceeded.\nmore"), "Timeout 45000ms exceeded.")


class TestCheckBrowser(unittest.TestCase):
    def test_ok(self):
        fetch = answer('{"ip":"198.51.100.7"}')
        result = check_browser(BROWSER, fetch=fetch)
        self.assertEqual((result.ok, result.ip, result.text), (True, "198.51.100.7", "ok (198.51.100.7)"))
        self.assertEqual(fetch.calls, [("ws://127.0.0.1:1/x", CHECK_URL)])

    def test_proxy_error_is_a_result_not_an_exception(self):
        result = check_browser(BROWSER, fetch=answer(RuntimeError("net::ERR_TUNNEL_CONNECTION_FAILED")))
        self.assertEqual(result.text, "failed: ERR_TUNNEL_CONNECTION_FAILED")

    def test_block_page_fails(self):
        self.assertEqual(check_browser(BROWSER, fetch=answer("<h1>Forbidden</h1>")).error, "unexpected answer")

    def test_without_playwright_says_how_to_install(self):
        with mock.patch.dict(sys.modules, {"playwright": None, "playwright.sync_api": None}), \
                self.assertRaisesRegex(ProxyCheckUnavailable, r"mrfactory-adspower\[browser\]"):
            playwright_fetch("ws://x", CHECK_URL)


class TestClientCheckProxy(unittest.TestCase):
    def test_opens_checks_and_closes(self):
        api = FakeApi()
        result = AdsPower(api).check_proxy("10", fetch=answer('{"ip":"198.51.100.7"}'))
        self.assertTrue(result.ok)
        self.assertEqual(result.profile.serial_number, "10")
        self.assertEqual(api.open_browsers, set())                      # closed again
        paths = [path for path, _ in api.calls]
        self.assertIn("/api/v1/browser/start", paths)
        self.assertIn("/api/v1/browser/stop", paths)

    def test_leaves_an_already_open_profile_open(self):
        api = FakeApi()
        api.open_browsers.add("k1a")
        AdsPower(api).check_proxy("10", fetch=answer('{"ip":"198.51.100.7"}'))
        self.assertEqual(api.open_browsers, {"k1a"})
        self.assertNotIn("/api/v1/browser/stop", [path for path, _ in api.calls])

    def test_closes_even_when_the_fetch_crashes_unexpectedly(self):
        api = FakeApi()

        def broken(ws, url):
            raise ProxyCheckUnavailable("no playwright")

        with self.assertRaises(ProxyCheckUnavailable):
            AdsPower(api).check_proxy("10", fetch=broken)
        self.assertEqual(api.open_browsers, set())


if __name__ == "__main__":
    unittest.main()
