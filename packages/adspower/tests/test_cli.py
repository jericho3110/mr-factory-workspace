import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mrfactory.adspower import cli
from tests.fakes import FakeApi


def run(*argv, api=None, interactive=False, answers=()):
    """Run the CLI with a fake API; return (exit code, stdout, stderr).
    `answers` are fed to input() when the CLI asks a question."""
    out, err = io.StringIO(), io.StringIO()
    answers = list(answers)
    with mock.patch("mrfactory.adspower.cli.app.LocalApi", return_value=api or FakeApi()), \
            mock.patch("mrfactory.adspower.cli.prompts.is_interactive", return_value=interactive), \
            mock.patch("builtins.input", side_effect=lambda prompt: answers.pop(0)), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class TestHelp(unittest.TestCase):
    def test_no_command_prints_help_with_every_command(self):
        code, out, _ = run()
        self.assertEqual(code, 0)
        for command in ("open", "status", "groups", "tags", "profiles", "search", "open-profile",
                        "close-profile", "proxies", "create", "examples:"):
            self.assertIn(command, out)

    def test_version_flag(self):
        with self.assertRaises(SystemExit) as caught, contextlib.redirect_stdout(io.StringIO()) as out:
            cli.main(["--version"])
        self.assertEqual(caught.exception.code, 0)
        self.assertRegex(out.getvalue(), r"^adspower \S+$")  # "adspower 0.3.0", or "0+unknown" uninstalled

    def test_help_flag_on_a_command(self):
        with self.assertRaises(SystemExit) as caught, contextlib.redirect_stdout(io.StringIO()) as out:
            cli.main(["create", "--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("--proxy", out.getvalue())


class TestListing(unittest.TestCase):
    def test_groups_filtered_by_name(self):
        code, out, _ = run("groups", "-n", "acm")
        self.assertEqual(code, 0)
        self.assertIn("Acme", out)
        self.assertNotIn("Shopify", out)
        self.assertIn("1 group\n", out)

    def test_tags(self):
        code, out, _ = run("tags")
        self.assertEqual(code, 0)
        self.assertIn("Sales", out)
        self.assertIn("2 tags", out)

    def test_profiles_in_a_group_with_line_breaks_cleaned(self):
        code, out, _ = run("profiles", "-g", "socials")
        self.assertEqual(code, 0)
        self.assertIn("Insta main", out)  # "Insta\nmain" kept on one row
        self.assertNotIn("John Shop", out)

    def test_profiles_by_tag(self):
        code, out, _ = run("profiles", "-t", "ACME")
        self.assertEqual(code, 0)
        self.assertIn("John Shop", out)
        self.assertIn("1 profile\n", out)

    def test_search_as_json(self):
        code, out, _ = run("search", "john", "--json")
        rows = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual({row["id"] for row in rows}, {"k1a", "k2a"})
        self.assertEqual(rows[0]["tags"], ["Sales"])

    def test_proxies_by_tag_hide_passwords(self):
        code, out, _ = run("proxies", "-t", "acme", "--unused", "--json")
        rows = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual([row["id"] for row in rows], ["p2"])
        self.assertNotIn("secret", out)


class TestOpenProfile(unittest.TestCase):
    def test_opens_a_single_match(self):
        api = FakeApi()
        code, out, _ = run("open-profile", "jane", api=api)
        self.assertEqual(code, 0)
        self.assertIn('Opened #2 "Jane Shop"', out)
        self.assertIn("stays open", out)
        self.assertEqual(api.open_browsers, {"k1b"})

    def test_several_matches_ask_which_one(self):
        api = FakeApi()
        code, out, _ = run("open-profile", "shop", api=api, interactive=True, answers=["9", "2"])
        self.assertEqual(code, 0)
        self.assertIn("Please enter a number", out)   # "9" is out of range, asked again
        self.assertEqual(api.open_browsers, {"k1a"})  # 2nd in serial order: #2 Jane, #10 John

    def test_enter_cancels_the_choice(self):
        api = FakeApi()
        code, _, _ = run("open-profile", "shop", api=api, interactive=True, answers=[""])
        self.assertEqual(code, 1)
        self.assertEqual(api.open_browsers, set())

    def test_several_matches_without_a_terminal_list_them_and_fail(self):
        api = FakeApi()
        code, out, err = run("open-profile", "shop", api=api, interactive=False)
        self.assertEqual(code, 1)
        self.assertIn("Jane Shop", out)
        self.assertIn("be more specific", err)
        self.assertEqual(api.open_browsers, set())

    def test_close_profile(self):
        api = FakeApi()
        api.open_browsers.add("k1b")
        code, _, _ = run("close-profile", "2", api=api)
        self.assertEqual(code, 0)
        self.assertEqual(api.open_browsers, set())


class TestSetProxy(unittest.TestCase):
    def test_auto_with_yes_uses_the_profiles_tag(self):
        api = FakeApi()
        code, out, _ = run("set-proxy", "10", "--proxy", "auto", "--yes", api=api)
        self.assertEqual(code, 0)
        self.assertIn("http://203.0.113.11:8000  ->  socks5://203.0.113.22:9000", out)  # shown before changing
        self.assertEqual(api.updates, [{"profile_id": "k1a", "proxyid": "p2"}])  # p2: unused, tagged Acme

    def test_asks_first_in_a_terminal(self):
        api = FakeApi()
        code, out, _ = run("set-proxy", "10", "--proxy", "auto", api=api, interactive=True, answers=["n"])
        self.assertEqual(code, 1)
        self.assertIn("Nothing was changed", out)
        self.assertEqual(api.updates, [])

        code, _, _ = run("set-proxy", "10", "--proxy", "auto", api=api, interactive=True, answers=["y"])
        self.assertEqual(code, 0)
        self.assertEqual(len(api.updates), 1)

    def test_without_a_terminal_it_needs_yes(self):
        api = FakeApi()
        code, _, err = run("set-proxy", "10", "--proxy", "auto", api=api, interactive=False)
        self.assertEqual(code, 1)
        self.assertIn("--yes", err)
        self.assertEqual(api.updates, [])

    def test_proxy_without_the_tag_is_refused(self):
        api = FakeApi()
        code, _, err = run("set-proxy", "10", "--proxy", "p3", "--yes", api=api)  # p3 is tagged Support
        self.assertEqual(code, 1)
        self.assertIn("No proxy with ID 'p3' is tagged 'acme'", err)
        self.assertEqual(api.updates, [])

    def test_profile_without_one_tag_needs_proxy_tag(self):
        api = FakeApi()
        code, _, err = run("set-proxy", "2", "--proxy", "auto", "--yes", api=api)  # #2 has no tags
        self.assertEqual(code, 1)
        self.assertIn("--proxy-tag", err)
        code, _, _ = run("set-proxy", "2", "--proxy", "auto", "--proxy-tag", "acme", "--yes", api=api)
        self.assertEqual(code, 0)

    def test_no_proxy_when_already_none_changes_nothing(self):
        api = FakeApi()
        code, out, _ = run("set-proxy", "2", "--no-proxy", "--yes", api=api)
        self.assertEqual(code, 0)
        self.assertIn("Nothing to change", out)
        self.assertEqual(api.updates, [])

    def test_open_browser_gets_a_reopen_hint(self):
        api = FakeApi()
        api.open_browsers.add("k1a")
        _, out, _ = run("set-proxy", "10", "--no-proxy", "--yes", api=api)
        self.assertIn("close and reopen", out)

    def test_proxy_and_no_proxy_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            cli.main(["set-proxy", "10", "--proxy", "auto", "--no-proxy"])


class TestCreate(unittest.TestCase):
    def test_create_without_proxy(self):
        api = FakeApi()
        code, out, _ = run("create", "Shop 8", "-g", "Acme", "-t", "acme", api=api)
        self.assertEqual(code, 0)
        self.assertIn('Created #500 "Shop 8"', out)
        self.assertIn("Proxy: no proxy", out)

    def test_create_with_auto_proxy_uses_the_profile_tag_for_proxies(self):
        api = FakeApi()
        code, _, _ = run("create", "Shop 8", "-g", "Acme", "-t", "acme", "--proxy", "auto", api=api)
        self.assertEqual(code, 0)
        self.assertEqual(api.created[0]["proxyid"], "p2")

    def test_group_and_tag_are_required(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            cli.main(["create", "Shop 8"])

    def test_unknown_tag_creates_nothing(self):
        api = FakeApi()
        code, _, err = run("create", "x", "-g", "Acme", "-t", "Acmee", api=api)
        self.assertEqual(code, 1)
        self.assertIn("No profile tag", err)
        self.assertEqual(api.created, [])


class TestSafeExit(unittest.TestCase):
    def test_unknown_group_is_an_error_exit(self):
        code, _, err = run("profiles", "-g", "nope")
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_ctrl_c_exits_with_130(self):
        api = FakeApi()
        api.get_all = mock.Mock(side_effect=KeyboardInterrupt)
        code, _, err = run("groups", api=api)
        self.assertEqual(code, 130)
        self.assertIn("Cancelled", err)

    def test_unexpected_bug_is_logged_not_dumped(self):
        api = FakeApi()
        api.get_all = mock.Mock(side_effect=ZeroDivisionError("boom"))
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "crash.log"
            with mock.patch("mrfactory.adspower.cli.app.CRASH_LOG", log):
                code, _, err = run("groups", "--api-key", "SECRET-1", api=api)
                run("groups", "--api-key=SECRET-2", api=api)
            text = log.read_text(encoding="utf-8")
            self.assertEqual(code, 1)
            self.assertIn("unexpected error: ZeroDivisionError: boom", err)
            self.assertNotIn("Traceback", err)
            self.assertIn("Traceback", text)
            self.assertIn("adspower groups --api-key ***", text)   # the command is logged...
            self.assertNotIn("SECRET", text)                        # ...but never the key

    def test_redact_hides_secret_values_in_both_forms(self):
        self.assertEqual(cli.app.redact(["groups", "--api-key", "k", "--json"]),
                         ["groups", "--api-key", "***", "--json"])
        self.assertEqual(cli.app.redact(["--api-key=k", "groups"]), ["--api-key=***", "groups"])
        self.assertEqual(cli.app.redact(["--api-url", "http://x"]), ["--api-url", "http://x"])

    def test_abbreviated_options_are_rejected(self):
        # argparse would otherwise accept --api-k as --api-key, slipping past redact()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            cli.main(["groups", "--api-k", "SECRET"])

    def test_non_http_api_url_is_an_error_not_a_file_read(self):
        # Not run(): that replaces LocalApi with a fake, and the check lives in the real one.
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main(["groups", "--api-url", "file:///C:/Windows/win.ini"])
        self.assertEqual(code, 1)
        self.assertIn("must start with http:// or https://", err.getvalue())

    def test_status_when_not_running(self):
        code, out, _ = run("status", api=FakeApi(running=False))
        self.assertEqual(code, 1)
        self.assertIn("not running", out)

    def test_open_launches_the_app(self):
        with mock.patch("mrfactory.adspower.client.open_adspower", return_value="C:/AdsPower.exe"):
            code, out, _ = run("open")
        self.assertEqual(code, 0)
        self.assertIn("Opened C:/AdsPower.exe", out)


class TestCreateMany(unittest.TestCase):
    def test_shows_the_plan_and_asks_first(self):
        api = FakeApi()
        code, out, _ = run("create-many", "New A", "John Shop", "-g", "Acme", "-t", "acme",
                           api=api, interactive=True, answers=["n"])
        self.assertEqual(code, 1)
        self.assertIn("ready", out)
        self.assertIn("already exists", out)
        self.assertIn("1 of 2 ready; 1 free proxy tagged 'acme'.", out)
        self.assertIn("Nothing was created", out)
        self.assertEqual(api.created, [])

    def test_yes_creates_and_prints_the_table(self):
        api = FakeApi()
        code, out, _ = run("create-many", "New A", "-g", "Acme", "-t", "acme", "--remark", "b1", "--yes", api=api)
        self.assertEqual(code, 0)
        self.assertEqual(api.created[0]["proxyid"], "p2")
        self.assertEqual(api.created[0]["remark"], "b1")
        self.assertIn("1 created", out)

    def test_names_from_a_file_skip_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            names = Path(tmp) / "names.txt"
            names.write_text("# new ones\nNew A\n\n", encoding="utf-8")
            api = FakeApi()
            code, _, _ = run("create-many", "--from-file", str(names), "-g", "Acme", "-t", "acme", "--yes", api=api)
        self.assertEqual(code, 0)
        self.assertEqual([b["name"] for b in api.created], ["New A"])

    def test_refuses_without_terminal_or_yes(self):
        api = FakeApi()
        code, _, err = run("create-many", "New A", "-g", "Acme", "-t", "acme", api=api)
        self.assertEqual(code, 1)
        self.assertIn("--yes", err)
        self.assertEqual(api.created, [])

    def test_no_names(self):
        code, _, err = run("create-many", "-g", "Acme", "-t", "acme", "--yes")
        self.assertEqual(code, 1)
        self.assertIn("No names given", err)


class TestCheckProxy(unittest.TestCase):
    def test_ok_and_failed_exit_codes(self):
        ok = mock.patch("mrfactory.adspower.proxycheck.playwright_fetch", return_value='{"ip":"198.51.100.7"}')
        with ok:
            code, out, _ = run("check-proxy", "10")
        self.assertEqual(code, 0)
        self.assertIn("proxy ok (198.51.100.7)", out)

        bad = mock.patch("mrfactory.adspower.proxycheck.playwright_fetch",
                         side_effect=RuntimeError("net::ERR_PROXY_CONNECTION_FAILED"))
        with bad:
            code, out, _ = run("check-proxy", "10")
        self.assertEqual(code, 1)
        self.assertIn("failed: ERR_PROXY_CONNECTION_FAILED", out)


if __name__ == "__main__":
    unittest.main()
