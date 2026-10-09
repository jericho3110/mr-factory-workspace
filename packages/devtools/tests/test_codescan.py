"""Every rule gets a planted bad line (must be found) and a safe twin (must not be).

Dangerous snippets are assembled at run time where needed, so this test file
itself stays clean for the real scanner.
"""

import re
import unittest

from mrfactory.devtools.codescan import scan_text

S = "shell" + "=True"


class PlantedTests(unittest.TestCase):
    def found(self, path, line):
        return [f.description for f in scan_text(path, line + "\n")]

    def test_each_language_rule(self):
        planted = {
            "a.py": f"subprocess.run(cmd, {S})",
            "b.py": "ev" + "al(user_text)",
            "c.py": "pickle." + "loads(blob)",
            "d.py": "db.exe" + 'cute(f"SELECT * FROM t WHERE x = {x}")',  # noqa: S608 - a planted bad line, never run
            "e.py": "requests.get(url, verify=" + "False)",
            "f.ts": "el.inner" + "HTML = text",
            "g.go": 'exec.Command("' + 'sh", "-c", cmd)',
            "h.rs": 'Command::new("' + 'cmd")',
            "i.c": "str" + "cpy(dst, src);",
            "j.cpp": "int n = at" + "oi(argv[1]);",
            "k.ps1": "Invoke-" + "Expression $text",
            "l.sh": "curl https://example.com/x | " + "sh",
            "m.java": "Runtime.getRuntime().ex" + "ec(cmd)",
            "n.cs": "UseShellExecute = " + "true",
        }
        for path, line in planted.items():
            self.assertTrue(self.found(path, line), path)

    def test_safe_twins_are_clean(self):
        safe = {
            "a.py": "subprocess.run(['git', 'status'])",
            "d.py": 'db.execute("SELECT * FROM t WHERE x = ?", (x,))',
            "f.ts": "el.textContent = text",
            "i.c": "memcpy(dst, src, n);",
            "j.cpp": "auto [end, err] = std::from_chars(s, s + n, v);",
        }
        for path, line in safe.items():
            self.assertEqual(self.found(path, line), [], path)

    def test_rules_only_apply_to_their_language(self):
        self.assertEqual(self.found("notes.md", f"never use {S} in Python"), [])

    def test_comments_and_allow_marker_skip_a_line(self):
        self.assertEqual(self.found("a.py", f"# {S} is dangerous"), [])
        self.assertEqual(self.found("a.c", "// str" + "cpy is banned"), [])
        self.assertEqual(self.found("a.py", f"run(x, {S})  # security-scan: allow (fixed command)"), [])

    def test_project_rules_with_exceptions(self):
        rule = ("delete outside the cleaner", ("*.py",), re.compile(r"shutil\.rmtree"), ("src/clean.py",))
        self.assertTrue(scan_text("src/sizes.py", "shutil.rmtree(p)\n", [rule]))
        self.assertEqual(scan_text("src/clean.py", "shutil.rmtree(p)\n", [rule]), [])

    def test_finding_has_path_and_line(self):
        [f] = scan_text("x.py", "ok = 1\n" + "ev" + "al(y)\n")
        self.assertEqual((f.path, f.line), ("x.py", 2))


if __name__ == "__main__":
    unittest.main()
