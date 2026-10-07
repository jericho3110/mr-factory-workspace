import json
import unittest
import urllib.error
import urllib.parse

from mrfactory.adspower import AdsPowerApiError, AdsPowerNotRunning, LocalApi
from tests.fakes import FakeOpener


def ok(data=None):
    return {"code": 0, "data": data or {}, "msg": "Success"}


def make_api(*responses, **kwargs):
    opener = FakeOpener(*responses)
    api = LocalApi(base_url="http://api.test", min_interval=0, retry_delay=0, opener=opener, **kwargs)
    return api, opener


class TestLocalApi(unittest.TestCase):
    def test_returns_data_and_leaves_out_none_params(self):
        api, opener = make_api(ok({"x": 1}))
        self.assertEqual(api.get("/thing", a="1", b=None), {"x": 1})
        url = urllib.parse.urlsplit(opener.requests[0].full_url)
        self.assertEqual((url.path, url.query), ("/thing", "a=1"))

    def test_sends_api_key_as_bearer_token(self):
        api, opener = make_api(ok(), api_key="secret")
        api.get("/thing")
        self.assertEqual(opener.requests[0].get_header("Authorization"), "Bearer secret")

    def test_failure_code_raises_with_the_api_message(self):
        api, _ = make_api({"code": -1, "data": {}, "msg": "group not exist"})
        with self.assertRaisesRegex(AdsPowerApiError, "group not exist"):
            api.get("/thing")

    def test_retries_when_rate_limited(self):
        too_many = {"code": -1, "data": {}, "msg": "Too many request per second, please check"}
        api, opener = make_api(too_many, too_many, ok({"x": 1}))
        self.assertEqual(api.get("/thing"), {"x": 1})
        self.assertEqual(len(opener.requests), 3)

    def test_gives_up_after_a_few_rate_limit_retries(self):
        too_many = {"code": -1, "data": {}, "msg": "Too many request per second, please check"}
        api, opener = make_api(*[too_many] * 10)
        with self.assertRaisesRegex(AdsPowerApiError, "Too many"):
            api.get("/thing")
        self.assertEqual(len(opener.requests), 4)  # first try + 3 retries

    def test_get_all_reads_pages_until_a_short_one(self):
        api, opener = make_api(
            ok({"list": [1, 2]}),
            ok({"list": [3, 4]}),
            ok({"list": [5]}),
        )
        self.assertEqual(api.get_all("/list", page_size=2), [1, 2, 3, 4, 5])
        pages = [urllib.parse.parse_qs(urllib.parse.urlsplit(r.full_url).query)["page"] for r in opener.requests]
        self.assertEqual(pages, [["1"], ["2"], ["3"]])

    def test_post_sends_json_and_leaves_out_none_values(self):
        api, opener = make_api(ok({"id": "1"}))
        self.assertEqual(api.post("/create", {"name": "x", "remark": None}), {"id": "1"})
        request = opener.requests[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(json.loads(request.data), {"name": "x"})

    def test_post_all_pages_with_page_and_limit_in_the_body(self):
        api, opener = make_api(ok({"list": [1, 2]}), ok({"list": [3]}))
        self.assertEqual(api.post_all("/list", limit=2, group_id="7"), [1, 2, 3])
        bodies = [json.loads(r.data) for r in opener.requests]
        self.assertEqual(bodies, [{"group_id": "7", "page": 1, "limit": 2}, {"group_id": "7", "page": 2, "limit": 2}])

    def test_unreachable_api_means_not_running(self):
        api, _ = make_api(urllib.error.URLError("refused"))
        with self.assertRaises(AdsPowerNotRunning):
            api.get("/thing")

        api, _ = make_api(urllib.error.URLError("refused"))
        self.assertFalse(api.is_running())

    def test_is_running_when_status_answers(self):
        api, opener = make_api(ok())
        self.assertTrue(api.is_running())
        self.assertTrue(opener.requests[0].full_url.endswith("/status"))

    def test_http_error_is_an_api_error_not_not_running(self):
        error = urllib.error.HTTPError("http://api.test/x", 500, "boom", {}, None)
        self.addCleanup(error.close)
        api, _ = make_api(error)
        with self.assertRaises(AdsPowerApiError):
            api.get("/x")


if __name__ == "__main__":
    unittest.main()
