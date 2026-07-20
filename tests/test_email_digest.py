import re
import unittest

from email_digest import build_issue_url, render_email_digest, render_email_text
from generate_magazine import build_email_message


class EmailDigestTests(unittest.TestCase):
    def setUp(self):
        self.story = {
            "title": "A <safe> launch for builders",
            "url": "https://example.com/article?a=1&b=2",
            "hn_url": "https://news.ycombinator.com/item?id=1",
            "domain": "example.com",
            "score": 94,
            "flagged": True,
            "summary_en": "A concise sourced summary for people reading the daily brief on a phone.",
            "insight_cat_en": "Developer Tooling",
        }
        self.issue_url = "https://signals.wildernesstudio.com/magazines/2026-07-14.html"

    def test_issue_url_points_to_exact_date(self):
        self.assertEqual(
            build_issue_url("https://signals.wildernesstudio.com/", "2026-07-14"),
            self.issue_url,
        )

    def test_html_uses_email_safe_layout_and_absolute_links(self):
        html = render_email_digest([self.story] * 10, "2026-07-14", self.issue_url)
        lowered = html.lower()

        self.assertIn("max-width:640px", html)
        self.assertIn("A &lt;safe&gt; launch for builders", html)
        self.assertIn("example.com · 94 pts", html)
        self.assertIn(self.issue_url, html)
        self.assertLess(len(html.encode("utf-8")), 100_000)
        for forbidden in ("<style", "<script", "<svg", "var(", "display:grid", "display:flex", "position:sticky", "position:fixed", "@media"):
            self.assertNotIn(forbidden, lowered)
        for href in re.findall(r'href="([^"]+)"', html):
            self.assertTrue(href.startswith("https://"), href)

    def test_plain_text_contains_story_and_fallback_links(self):
        text = render_email_text([self.story], "2026-07-14", self.issue_url)

        self.assertIn("WILDERNESS SIGNAL — July 14, 2026", text)
        self.assertIn(self.issue_url, text)
        self.assertIn("A <safe> launch for builders", text)
        self.assertIn(self.story["url"], text)
        self.assertIn(self.story["hn_url"], text)

    def test_structure_survives_aggressive_style_stripping(self):
        html = render_email_digest([self.story], "2026-07-14", self.issue_url)
        stripped = re.sub(r'\sstyle="[^"]*"', "", html)

        self.assertIn('role="presentation"', stripped)
        self.assertIn(f'bgcolor="#073D2D"', stripped)
        self.assertIn(f'bgcolor="#F5B82E"', stripped)
        self.assertIn("A &lt;safe&gt; launch for builders", stripped)
        self.assertIn(self.issue_url, stripped)

    def test_mime_message_contains_plain_and_html_alternatives(self):
        message = build_email_message(
            "sender@example.com",
            ["reader@example.com"],
            "Wilderness Signal",
            "<html><body>HTML digest</body></html>",
            "Plain digest",
        )

        payload = message.get_payload()
        self.assertEqual([part.get_content_type() for part in payload], ["text/plain", "text/html"])
        self.assertIn("Plain digest", payload[0].get_payload(decode=True).decode("utf-8"))
        self.assertIn("HTML digest", payload[1].get_payload(decode=True).decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
