import os
import tempfile
import unittest
from pathlib import Path

import update_archive


class ArchiveGenerationTests(unittest.TestCase):
    def test_archive_uses_brand_system_and_preserves_every_issue(self):
        previous_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                os.chdir(tmpdir)
                magazines = Path("magazines")
                magazines.mkdir()
                for filename in ("2026-06-30.html", "2026-07-12.html", "2026-07-13.html"):
                    (magazines / filename).write_text("issue", encoding="utf-8")

                update_archive.generate_index()

                html = Path("index.html").read_text(encoding="utf-8")
                self.assertIn("<span>WILDERNESS</span><span>SIGNAL</span>", html)
                self.assertIn("Daily Hacker News intelligence for AI-native builders.", html)
                self.assertIn("Daily Issue Archive from wildernesstudio.com", html)
                self.assertIn("A Wilderness Studio product", html)
                self.assertIn("Experience leads. AI amplifies.", html)
                self.assertIn("--deep-forest: #073D2D", html)
                self.assertIn("--builder-yellow: #F5B82E", html)
                self.assertIn("Issue 003", html)
                self.assertIn("Issue 002", html)
                self.assertIn("Issue 001", html)
                self.assertIn("July 2026", html)
                self.assertIn("June 2026", html)
                self.assertEqual(html.count('href="magazines/'), 3)
                self.assertIn('href="#archive">Skip to issue archive</a>', html)
        finally:
            os.chdir(previous_cwd)


if __name__ == "__main__":
    unittest.main()
