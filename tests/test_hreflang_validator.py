import functools
import http.server
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from click.testing import CliRunner

from hreflang_validator import cli, core

SITE = Path(__file__).parent.parent / "examples" / "site"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve_examples():
    """Serve a copy of examples/site on a free port, with localhost:8000 replaced by the real base."""
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(root)))
    base = f"http://127.0.0.1:{server.server_port}"
    shutil.copytree(SITE, root, dirs_exist_ok=True)
    for f in root.rglob("*"):
        if f.suffix in (".xml", ".html"):
            f.write_text(f.read_text(encoding="utf-8").replace("http://localhost:8000", base), encoding="utf-8")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return tmp, server, base


class CodeTest(unittest.TestCase):
    def test_valid_codes(self):
        for code in ["en", "en-GB", "de-AT", "zh-Hant-TW", "es-419", "x-default", "pt-br"]:
            self.assertIsNone(core.check_code(code), code)

    def test_bad_codes(self):
        self.assertEqual(core.check_code("en-uk")[0], "error")
        self.assertIn("ja", core.check_code("jp")[1])
        self.assertIn("underscore", core.check_code("de_DE")[1])
        self.assertEqual(core.check_code("english")[0], "error")
        self.assertEqual(core.check_code("qq")[0], "notice")

    def test_link_header(self):
        out = core.parse_link_header('<https://x.com/de/a.pdf>; rel="alternate"; hreflang="de", '
                                     '<https://x.com/a.pdf>; rel="canonical"', "https://x.com/a.pdf")
        self.assertEqual(out, [("de", "https://x.com/de/a.pdf", "http header")])


class AnalyseTest(unittest.TestCase):
    def page(self, url, tags, status=200, canonical="", noindex=False):
        return {"url": url, "status": status, "location": "", "canonical": canonical, "noindex": noindex,
                "hreflang": [(c, h, "html") for c, h in tags], "error": ""}

    def test_clean_pair_has_no_errors(self):
        a, b = "https://x.com/en/", "https://x.com/de/"
        tags = [("en", a), ("de", b), ("x-default", a)]
        pages = {core.norm(a): self.page(a, tags), core.norm(b): self.page(b, tags)}
        issues, notes, _ = core.analyse(pages)
        self.assertEqual(len(issues), 0)
        self.assertEqual(set(notes["return_link"]), {"yes", "self"})

    def test_missing_return_and_duplicate_code(self):
        a, b, c = "https://x.com/en/", "https://x.com/de/", "https://x.com/de2/"
        pages = {core.norm(a): self.page(a, [("en", a), ("de", b), ("de", c)]),
                 core.norm(b): self.page(b, [("de", b)])}
        issues, _, _ = core.analyse(pages)
        found = set(issues["issue"])
        self.assertIn("No return link from the alternate page", found)
        self.assertIn("Same hreflang code points to different URLs", found)

    def test_empty(self):
        issues, notes, pages = core.analyse({})
        self.assertTrue(issues.empty and notes.empty and pages.empty)
        self.assertTrue(core.summarise(issues).empty)


class ExampleSiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.server, cls.base = serve_examples()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def test_audit_sitemap(self):
        r = core.audit(self.base + "/sitemap.xml", delay=0.5)
        issues = r["issues"]
        by = lambda name: issues[issues["issue"] == name]
        self.assertEqual(len(r["pages"]), 11)
        self.assertEqual(by("No return link from the alternate page")["page"].iloc[0], self.base + "/de/pricing.html")
        self.assertEqual(len(by("hreflang URL is relative")), 1)
        self.assertEqual(len(by("hreflang target returns 404")), 2)
        self.assertEqual(len(by("hreflang target is noindex")), 1)
        self.assertEqual(len(by("hreflang target canonicalises elsewhere")), 1)
        self.assertEqual(set(by("Invalid or unusual hreflang code")["hreflang"]), {"en-uk", "jp", "de_DE"})

    def test_cli_writes_reports(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            res = runner.invoke(cli.main, [self.base + "/en/pricing.html", "-o", "out"])
            self.assertEqual(res.exit_code, 0, res.output)
            self.assertTrue(os.path.exists("out.html") and os.path.exists("out.xlsx"))
            self.assertIn("hreflang report", Path("out.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
