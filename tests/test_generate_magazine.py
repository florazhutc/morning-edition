import unittest
from unittest import mock

import generate_magazine as magazine


class KeywordMatchingTests(unittest.TestCase):
    def test_short_keyword_uses_word_boundaries(self):
        self.assertTrue(magazine.keyword_matches("ai", "new ai model"))
        self.assertFalse(magazine.keyword_matches("ai", "daily briefing"))

    def test_phrase_keyword_uses_substring_match(self):
        self.assertTrue(magazine.keyword_matches("machine learning", "a machine learning guide"))


class EnrichmentTests(unittest.TestCase):
    def test_missing_source_is_not_replaced_with_inferred_summary(self):
        story = {
            "id": 1,
            "title": "Unavailable article",
            "url": "https://example.com/article",
            "hn_url": "https://news.ycombinator.com/item?id=1",
            "domain": "example.com",
            "score": 10,
            "comments": 0,
            "by": "author",
            "flagged": False,
        }

        with (
            mock.patch.object(magazine, "fetch_html", return_value=None),
            mock.patch.object(magazine, "fetch_json", return_value=None),
            mock.patch.object(magazine, "fetch_hn_algolia_content", return_value=""),
            mock.patch.object(magazine, "fetch_top_comments", return_value=[]),
            mock.patch.object(
                magazine,
                "generate_editorial_package",
                return_value={
                    "headline": story["title"],
                    "category": "💡 Worth Watching",
                    "insight": "Fallback insight.",
                    "community_analysis": "",
                    "ai_enriched": False,
                },
            ),
        ):
            result = magazine.enrich_stories([story])[0]

        self.assertEqual(result["summary_en"], "")
        self.assertEqual(result["summary_source"], "unavailable")


class RenderingTests(unittest.TestCase):
    def setUp(self):
        self.story = {
            "title": "A <safe> title",
            "url": "https://example.com/article",
            "hn_url": "https://news.ycombinator.com/item?id=1",
            "domain": "example.com",
            "score": 10,
            "comments": 2,
            "by": "author",
            "flagged": False,
            "summary_en": "A sourced summary.",
            "summary_source": "article",
            "insight_cat_en": "Developer Tooling",
            "insight_en": "An insight.",
            "community_en": "",
        }

    def test_render_escapes_text_and_displays_summary_source(self):
        html = magazine.render_story_section(self.story, 0, magazine.PAGE_STYLES[0])

        self.assertIn("A &lt;safe&gt; title", html)
        self.assertIn("Source: original article", html)

    def test_render_displays_unavailable_summary_message(self):
        self.story["summary_en"] = ""
        self.story["summary_source"] = "unavailable"

        html = magazine.render_story_section(self.story, 0, magazine.PAGE_STYLES[0])

        self.assertIn("Summary unavailable. Read the original source for details.", html)

    def test_magazine_uses_branded_issue_shell(self):
        html = magazine.render_magazine([self.story], "2026-07-13")

        self.assertIn("HN Daily Brief — July 13, 2026", html)
        self.assertIn("A Wilderness Studio product", html)
        self.assertIn('../assets/issue.css', html)
        self.assertIn('href="../index.html">Issue archive</a>', html)
        self.assertNotIn("Morning Edition", html)


if __name__ == "__main__":
    unittest.main()
