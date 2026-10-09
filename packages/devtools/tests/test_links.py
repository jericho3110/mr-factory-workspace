import tempfile
import unittest
import urllib.error
from pathlib import Path

from mrfactory.devtools.links import check_local, check_url, check_web, extract

DOC = """# Title
See [Plug-in](https://en.wikipedia.org/wiki/Plug-in_(computing)) and <https://example.com/auto>.
Bare: https://example.com/bare.
Local: [arch](docs/ARCHITECTURE.md#layers), [top](#title), [mail](mailto:a@example.com).

```
[not a link](https://example.com/in-a-code-block)
```
Inline `https://example.com/inline-code` too.
"""


class ExtractTests(unittest.TestCase):
    def test_finds_every_kind_and_skips_code(self):
        web, local = extract(DOC)
        self.assertIn("https://en.wikipedia.org/wiki/Plug-in_(computing)", web)  # parentheses kept
        self.assertIn("https://example.com/auto", web)
        self.assertIn("https://example.com/bare", web)  # trailing period dropped
        self.assertNotIn("https://example.com/in-a-code-block", web)
        self.assertNotIn("https://example.com/inline-code", web)
        self.assertEqual(local, ["docs/ARCHITECTURE.md"])  # anchors and mailto skipped


class LocalTests(unittest.TestCase):
    def test_broken_and_working_local_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "ARCHITECTURE.md").write_text("x", encoding="utf-8")
            good, bad = root / "good.md", root / "bad.md"
            good.write_text("[a](docs/ARCHITECTURE.md)", encoding="utf-8")
            bad.write_text("[a](docs/MISSING.md)", encoding="utf-8")
            self.assertEqual(check_local([good], root), [])
            self.assertIn("docs/MISSING.md", check_local([bad], root)[0])


class FakeResponse:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_for(outcomes):
    """outcomes: url -> int status or an exception to raise."""
    def opener(req, timeout):
        o = outcomes[req.full_url]
        if isinstance(o, Exception):
            raise o
        if o >= 400:
            raise urllib.error.HTTPError(req.full_url, o, "x", {}, None)
        return FakeResponse(o)
    return opener


class WebTests(unittest.TestCase):
    def test_statuses(self):
        op = opener_for({"https://a.test": 200, "https://b.test": 403, "https://c.test": 404,
                         "https://d.test": OSError("dropped")})
        self.assertEqual(check_url("https://a.test", op), "ok 200")
        self.assertEqual(check_url("https://b.test", op), "blocked 403")  # blocks scripts: not dead
        self.assertEqual(check_url("https://c.test", op), "DEAD 404")
        self.assertEqual(check_url("https://d.test", op), "DEAD OSError")
        self.assertEqual(check_url("file:///etc/passwd", op), "DEAD not-http")

    def test_ignore_prefixes_and_localhost_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            md = root / "r.md"
            md.write_text("https://a.test/x https://private.test/repo http://localhost:8080/", encoding="utf-8")
            op = opener_for({"https://a.test/x": 200})
            results = check_web([md], root, ignore=["https://private.test"], opener=op)
            self.assertEqual([(r.url, r.status, r.sources) for r in results],
                             [("https://a.test/x", "ok 200", ("r.md",))])


if __name__ == "__main__":
    unittest.main()
