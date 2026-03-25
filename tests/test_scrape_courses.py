import unittest
from unittest.mock import patch, MagicMock
import scrape_courses
import os
import json

class TestScrapeCourses(unittest.TestCase):

    # ---------- SAFE PARSE AI ----------
    def test_safe_parse_ai_valid_json(self):
        content = '[{"title":"Course A"}]'
        result = scrape_courses.safe_parse_ai(content)
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]['title'], "Course A")

    def test_safe_parse_ai_with_extra_text(self):
        content = "Intro text\n[{'title':'Course B'}]\nFooter"
        # use double quotes for valid JSON
        content = content.replace("'", '"')
        result = scrape_courses.safe_parse_ai(content)
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]['title'], "Course B")

    def test_safe_parse_ai_invalid(self):
        content = "No JSON here"
        result = scrape_courses.safe_parse_ai(content)
        self.assertEqual(result, [])

    # ---------- DEDUPLICATE ----------
    def test_deduplicate(self):
        courses = [
            {"title": "A", "link": "url1"},
            {"title": "A", "link": "url1"},
            {"title": "B", "link": "url2"},
        ]
        result = scrape_courses.deduplicate(courses)
        self.assertEqual(len(result), 2)

    # ---------- PRE-FILTER ----------
    def test_pre_filter_matches(self):
        courses = [{"title":"Math Class", "location":"San Jose"}]
        result = scrape_courses.pre_filter(courses)
        self.assertEqual(len(result), 1)

    def test_pre_filter_no_matches(self):
        courses = [{"title":"Math Class", "location":"New York"}]
        result = scrape_courses.pre_filter(courses)
        self.assertEqual(result, [])

    # ---------- FETCH ----------
    @patch('scrape_courses.requests.get')
    def test_fetch_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html>OK</html>"
        mock_get.return_value = mock_resp
        result = scrape_courses.fetch("http://example.com")
        self.assertEqual(result, "<html>OK</html>")

    @patch('scrape_courses.requests.get')
    def test_fetch_fail(self, mock_get):
        mock_get.side_effect = Exception("fail")
        result = scrape_courses.fetch("http://bad.com", retries=2, delay=0)
        self.assertIsNone(result)

    # ---------- AI FILTER ----------
    @patch('scrape_courses.client.chat.completions.create')
    def test_ai_filter_and_rank(self, mock_ai):
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = '[{"title":"AI Course"}]'
        mock_ai.return_value = mock_resp

        courses = [{"title":"Course 1"}]
        result = scrape_courses.ai_filter_and_rank(courses)
        self.assertEqual(result[0]['title'], "AI Course")

if __name__ == '__main__':
    unittest.main()
