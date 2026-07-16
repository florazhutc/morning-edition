import tempfile
import unittest
from pathlib import Path

from issue_branding import update_issue_pages


LEGACY_ISSUE = '''<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Morning Edition</title></head>
<body>
<!-- FLOATING ACTION BAR --><div>Old controls</div>
<!-- MASTHEAD --><div class="masthead">Old title</div>
<!-- TABLE OF CONTENTS --><div class="toc" id="toc"><div class="toc-header">In This Issue / 本期提要</div></div>
<!-- STORIES --><section id="story-1"><h2>English story</h2><p style="font-family:'Noto Serif SC',serif;">中文内容</p></section>
<!-- COLOPHON --><footer>Morning Edition</footer>
</body></html>'''


class IssueBrandingTests(unittest.TestCase):
    def test_updates_branding_english_content_and_adjacent_navigation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            magazines = Path(tmpdir)
            first = magazines / "2026-07-12.html"
            second = magazines / "2026-07-13.html"
            first.write_text(LEGACY_ISSUE, encoding="utf-8")
            second.write_text(LEGACY_ISSUE, encoding="utf-8")

            self.assertEqual(update_issue_pages(magazines), 2)

            first_html = first.read_text(encoding="utf-8")
            second_html = second.read_text(encoding="utf-8")
            self.assertIn("A Wilderness Studio product · Issue 001", first_html)
            self.assertIn('href="2026-07-13.html"', first_html)
            self.assertIn('href="2026-07-12.html"', second_html)
            self.assertIn("Latest published issue", second_html)
            self.assertIn('../assets/issue.css', second_html)
            self.assertIn("Wilderness Signal — July 13, 2026", second_html)
            self.assertIn("Wilderness Signal issue 002", second_html)
            self.assertNotIn("Morning Edition", second_html)
            self.assertNotIn("中文内容", second_html)
            self.assertIn('id="toc-title"', second_html)

            update_issue_pages(magazines)
            self.assertEqual(second.read_text(encoding="utf-8").count("<!-- ISSUE HEADER START -->"), 1)


if __name__ == "__main__":
    unittest.main()
