import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from enrich import (  # noqa: E402
    _dead_sources, is_placeholder_description, jobposting_location, normalize_cities,
    parse_jobposting, summarize,
)


class NormalizeCitiesTests(unittest.TestCase):
    def test_location_values_seen_in_data(self):
        cases = {
            "Vienna": ["Vienna"],
            "Wien 9. Bezirk (Alsergrund)": ["Vienna"],
            "Linz, Vienna, Hamburg, Dusseldorf, Munich": ["Vienna", "Linz"],
            "Graz, Vienna, Pörtschach am Wörther See": ["Vienna", "Graz", "Carinthia"],
            "Villach": ["Carinthia"],
            "Remote, UK": ["Remote"],
            "Northern America, LATAM, Europe, APAC": ["Remote"],
            "Kronstorf": ["Austria (Other)"],
            "Perchtoldsdorf": ["Austria (Other)"],
        }
        for location, expected in cases.items():
            self.assertEqual(normalize_cities(location), expected, location)

    def test_specific_location_ignores_text(self):
        # Regression: a Kronstorf job was labelled Vienna from its description.
        self.assertEqual(normalize_cities("Kronstorf", "Join our Vienna office"), ["Austria (Other)"])

    def test_generic_location_falls_back_to_text(self):
        self.assertEqual(normalize_cities("Österreich", "Software Engineer in Graz"), ["Graz"])
        self.assertEqual(normalize_cities("Austria", "Software Engineer"), ["Austria (Other)"])


class JobPostingTests(unittest.TestCase):
    PAGE = '''<html><script type="application/ld+json">{"@context":"https://schema.org",
        "@graph":[{"@type":"Organization"},{"@type":"JobPosting","title":"Dev",
        "description":"<p>Hi</p>","jobLocation":[{"@type":"Place","address":
        {"addressLocality":"Graz","addressCountry":"AT"}}]}]}</script></html>'''

    def test_finds_posting_in_graph(self):
        posting = parse_jobposting(self.PAGE)
        self.assertEqual(posting['title'], 'Dev')
        self.assertEqual(jobposting_location(posting), 'Graz')

    def test_no_or_broken_jsonld(self):
        self.assertIsNone(parse_jobposting('<html></html>'))
        self.assertIsNone(parse_jobposting('<script type="application/ld+json">{nope</script>'))


class SummarizeTests(unittest.TestCase):
    def test_skips_header_facts(self):
        text = ("karriere.at/jobs/1 Data Analyst Employment type Full Time Salary 58,000 EUR "
                "Place of work Graz | Mid. We are a fast-growing online retailer that builds "
                "its own shop software in Graz. You will turn our sales data into decisions "
                "that the whole company relies on every day.")
        self.assertTrue(summarize(text).startswith("We are a fast-growing online retailer"))

    def test_skips_title_case_fact_header(self):
        # Real karriere.at JSON-LD description opening (2026-10).
        text = ("karriere.at/jobs/10030983 Lead AI Engineer (Java) About this job Employment type "
                "Full Time (Permanent employment) Salary 75,000 EUR to 95,000 EUR yearly Seniority "
                "level Professional Experience, Project or Team Lead, Senior Position Work model "
                "Hybrid Place of work Wien 9. Bezirk (Alsergrund) About SQUER We are a consultancy "
                "that helps companies build software they are proud of. You will lead a small team "
                "shipping AI features to production for our clients.")
        self.assertTrue(summarize(text).startswith("We are a consultancy"), summarize(text))

    def test_skips_german_sentences(self):
        text = ("Wir wollen unsere hohen Qualitätsansprüche halten und ausbauen. "
                "We are an online retailer that builds its own shop software and logistics in Graz.")
        self.assertTrue(summarize(text).startswith("We are an online retailer"))

    def test_nothing_usable(self):
        self.assertEqual(summarize("Apply now | Share"), "")

    def test_truncates(self):
        sentence = "This is a long and perfectly ordinary sentence about the role. "
        self.assertLessEqual(len(summarize(sentence * 20, limit=100)), 103)


class PlaceholderTests(unittest.TestCase):
    def test_templates(self):
        self.assertTrue(is_placeholder_description({"title": "Dev", "description": "Tech role at X in Y."}))
        self.assertTrue(is_placeholder_description({"title": "Dev", "description": "Dev at X in Vienna."}))
        self.assertFalse(is_placeholder_description({"title": "Dev", "description": "We build things. " * 20}))


class DeadSourceTests(unittest.TestCase):
    def test_mostly_dead_source_is_suspicious(self):
        jobs = [{"source": "A"}] * 4 + [{"source": "B"}] * 4
        statuses = [404, 404, 404, 200, 410, 200, 200, 200]
        self.assertEqual(_dead_sources(jobs, statuses), {"A"})


if __name__ == '__main__':
    unittest.main()
