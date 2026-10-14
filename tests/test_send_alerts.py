import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from send_alerts import TELEGRAM_LIMIT, build_messages, matches, new_jobs  # noqa: E402

SALARY_60K = {"annual_min": 55000, "annual_max": 60000, "label": "€55k–60k /yr"}


def job(id="a", **extra):
    base = {"id": id, "title": "Python Developer", "company": "Acme", "location": "Vienna",
            "cities": ["Vienna"], "seniority": "Mid-Level", "category": "Software Engineering",
            "description": "Build APIs", "tags": ["Python"], "url": "https://example.com/a"}
    return {**base, **extra}


class NewJobsTests(unittest.TestCase):
    def test_only_ids_missing_from_previous(self):
        self.assertEqual([j["id"] for j in new_jobs([job("a"), job("b")], [job("a")])], ["b"])


class MatchesTests(unittest.TestCase):
    def test_no_filters_matches_everything(self):
        self.assertTrue(matches(job(), {}))

    def test_cities_any_of(self):
        self.assertTrue(matches(job(cities=["Linz", "Vienna"]), {"cities": ["Vienna", "Remote"]}))
        self.assertFalse(matches(job(cities=["Graz"]), {"cities": ["Vienna"]}))

    def test_min_salary(self):
        self.assertTrue(matches(job(salary=SALARY_60K), {"min_salary": 60000}))
        self.assertFalse(matches(job(salary=SALARY_60K), {"min_salary": 70000}))
        self.assertFalse(matches(job(), {"min_salary": 50000}))
        self.assertTrue(matches(job(), {"min_salary": 50000, "include_no_salary": True}))

    def test_keywords(self):
        self.assertTrue(matches(job(), {"keywords": ["python"]}))
        self.assertFalse(matches(job(), {"keywords": ["rust"]}))
        self.assertFalse(matches(job(), {"exclude_keywords": ["apis"]}))

    def test_seniority(self):
        self.assertFalse(matches(job(), {"seniority": ["Senior"]}))


class BuildMessagesTests(unittest.TestCase):
    def test_escapes_scraped_text(self):
        text = build_messages([job(title="<b>Dev</b> & Ops", url='https://x.com/?a="1"')], {}, "")[0]
        self.assertIn("&lt;b&gt;Dev&lt;/b&gt; &amp; Ops", text)
        self.assertIn('href="https://x.com/?a=&quot;1&quot;"', text)

    def test_header_filters_and_overflow(self):
        jobs = [job(str(i)) for i in range(30)]
        messages = build_messages(jobs, {"cities": ["Vienna"], "min_salary": 50000}, "https://board")
        joined = "\n".join(messages)
        self.assertIn("30 new tech jobs", joined)
        self.assertIn("Filters: Vienna · €50k+", joined)
        self.assertIn("+5 more", joined)
        self.assertEqual(joined.count("View posting"), 25)
        self.assertTrue(all(len(m) <= TELEGRAM_LIMIT for m in messages))

    def test_splits_long_messages(self):
        jobs = [job(str(i), title="x" * 400) for i in range(20)]
        messages = build_messages(jobs, {}, "")
        self.assertGreater(len(messages), 1)
        self.assertTrue(all(len(m) <= TELEGRAM_LIMIT for m in messages))


if __name__ == '__main__':
    unittest.main()
