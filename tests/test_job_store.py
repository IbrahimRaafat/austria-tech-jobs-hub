import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from job_store import dedup_key, dedupe, source_report, stamp_first_seen  # noqa: E402


def job(id, title, company="Acme GmbH", **extra):
    return {"id": id, "title": title, "company": company, "description": "", **extra}


class DedupTests(unittest.TestCase):
    def test_gender_markers_and_company_suffixes(self):
        variants = [
            job("a", "Senior DevOps Engineer (f/m/d)", "Raiffeisen Digital Bank AG"),
            job("b", "Senior DevOps Engineer (m/w/d)", "Raiffeisen Digital Bank"),
            job("c", "Senior DevOps Engineer m/f/d", "raiffeisen digital bank ag"),
            job("d", "Senior DevOps Engineer (all genders)", "Raiffeisen Digital Bank AG"),
        ]
        self.assertEqual(len({dedup_key(v) for v in variants}), 1)

    def test_different_jobs_stay_apart(self):
        self.assertNotEqual(dedup_key(job("a", "Data Engineer")), dedup_key(job("b", "Data Engineer II")))
        self.assertNotEqual(dedup_key(job("a", "Dev", "Acme")), dedup_key(job("b", "Dev", "Other")))

    def test_keeps_longest_description_in_original_order(self):
        jobs = [job("a", "Dev (m/w/d)", description="short"), job("x", "Other"),
                job("b", "Dev (f/m/d)", description="a much longer description")]
        result = dedupe(jobs)
        self.assertEqual([j["id"] for j in result], ["b", "x"])


class FirstSeenTests(unittest.TestCase):
    def test_carry_over_and_new(self):
        previous = [job("a", "Dev", first_seen="2026-09-01"),
                    job("b", "Ops", posted_at="2026-09-20"),          # before first_seen existed
                    job("old-id", "QA Engineer (m/w/d)", first_seen="2026-09-05")]
        jobs = [job("a", "Dev"), job("b", "Ops"), job("new-id", "QA Engineer (f/m/d)"), job("c", "New")]
        stamp_first_seen(jobs, previous, "2026-10-04")
        self.assertEqual([j["first_seen"] for j in jobs], ["2026-09-01", "2026-09-20", "2026-09-05", "2026-10-04"])

    def test_first_run(self):
        jobs = [job("a", "Dev")]
        stamp_first_seen(jobs, [], "2026-10-04")
        self.assertEqual(jobs[0]["first_seen"], "2026-10-04")


class SourceReportTests(unittest.TestCase):
    def test_warns_when_established_source_vanishes(self):
        previous = [job(str(i), "x", source="DEVjobs.at") for i in range(5)] + [job("g", "x", source="GoStudent")]
        warnings = source_report([job("k", "x", source="Karriere.at")], previous)
        self.assertEqual(len(warnings), 1)
        self.assertIn("DEVjobs.at", warnings[0])


if __name__ == '__main__':
    unittest.main()
