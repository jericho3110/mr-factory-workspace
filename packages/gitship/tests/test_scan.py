"""Plant bad content and check the scan reports it; plant harmless content and check it doesn't.

Fake secrets are assembled at run time ("sk-" + "ant-" + ...) so this file
itself never contains one, and stays committable.
"""

import unittest

from mrfactory.gitship.scan import personal_patterns, scan_file


def reasons(path, text, size=10, **kw):
    return " | ".join(str(f) for f in scan_file(path, size, text, **kw))


class SecretTests(unittest.TestCase):
    def test_planted_secrets_are_found(self):
        planted = {
            "Anthropic": "key = '" + "sk-" + "ant-" + "a1" * 15 + "'",
            "GitHub token": "token: " + "gh" + "p_" + "A" * 36,
            "AWS": "AKIA" + "ABCDEFGHIJKLMNOP",
            "private key": "-----BEGIN " + "RSA PRIVATE KEY-----",
            "password": 'password = "' + "hunter22" + '"',
        }
        for label, text in planted.items():
            self.assertIn("looks like", reasons("config.py", text), label)

    def test_harmless_text_is_clean(self):
        self.assertEqual(reasons("a.py", "password = input('Password: ')\nversion 1.2.3.4000\n"), "")


class FileNameTests(unittest.TestCase):
    def test_secret_files_and_build_output(self):
        self.assertIn("secret", reasons(".env", None))
        self.assertIn("secret", reasons("deploy/server.pem", None))
        self.assertIn("build output", reasons("dist/app.exe", None))
        self.assertIn("build output", reasons("pkg/__pycache__/m.cpython-314.pyc", None))

    def test_large_file(self):
        self.assertIn("large file", reasons("video.mp4", None, size=50 * 1024 * 1024))

    def test_allow_list_skips_a_path(self):
        self.assertEqual(reasons("tests/fixtures/.env", None, allow=["tests/fixtures/*"]), "")


class PersonalDataTests(unittest.TestCase):
    def test_home_path_and_email(self):
        personal = personal_patterns("alice", "alice@example.com")
        self.assertIn("home folder", reasons("doc.md", r"see C:\Users\alice\AppData", personal=personal))
        self.assertIn("home folder", reasons("doc.md", "see /home/alice/x", personal=personal))
        self.assertIn("email", reasons("doc.md", "mail Alice@Example.com", personal=personal))
        self.assertEqual(reasons("doc.md", r"C:\Users\<you>\AppData", personal=personal), "")

    def test_noreply_email_is_fine(self):
        self.assertEqual(len(personal_patterns("bob", "123+bob@users.noreply.github.com")), 1)

    def test_real_ip_found_documentation_ip_not(self):
        public_ip = ".".join(["8", "8", "4", "4"])  # built at run time, like the fake keys above
        self.assertIn("IP address", reasons("proxies.txt", f"{public_ip}:8080"))
        self.assertEqual(reasons("proxies.txt", "203.0.113.10:8080 127.0.0.1 192.168.1.5"), "")


if __name__ == "__main__":
    unittest.main()
