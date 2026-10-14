import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from fetch_theses import (
    clean_str,
    categorize_thesis,
    detect_language,
    extract_thesis_tags,
    parse_duration_and_workload
)


class TestFetchTheses(unittest.TestCase):

    def test_clean_str(self):
        raw = "  Master Thesis \u201cBi-Static Sensing\u201d &amp; \xa0UAVs  "
        self.assertEqual(clean_str(raw), 'Master Thesis "Bi-Static Sensing" & UAVs')

    def test_categorize_thesis(self):
        cat_cyber = categorize_thesis("Master Thesis 'Bi-Static Sensing of UAVs'", "wireless 5G/6G communication and sensing")
        self.assertEqual(cat_cyber, "Cybersecurity & Networks")

        cat_ai = categorize_thesis("Master-Thesis 'World Models for Physical AI'", "deep learning and computer vision")
        self.assertEqual(cat_ai, "AI & Data Science")

        cat_mobility = categorize_thesis("Master Thesis Driving Dynamics", "motorcycle probe vehicle telemetry")
        self.assertEqual(cat_mobility, "Mobility & Autonomous Systems")

        cat_bio = categorize_thesis("Masterarbeit Biosensoren", "Nukleinsäuredetektion und Bioresources")
        self.assertEqual(cat_bio, "Health & Biotech")

    def test_detect_language(self):
        self.assertEqual(detect_language("Master Thesis 'Bi-Static Sensing of UAVs'", "This master thesis focuses on..."), "English")
        self.assertEqual(detect_language("Masterarbeit Cybersecurity Landwirtschaft", "Für unsere Forschungsgruppe suchen wir..."), "German")

    def test_extract_thesis_tags(self):
        tags = extract_thesis_tags("Master Thesis UAV Sensing", "5G/6G SDR MIMO wireless antenna design")
        self.assertIn("5G/6G", tags)
        self.assertIn("SDR", tags)
        self.assertIn("MIMO", tags)
        self.assertIn("Wireless", tags)

    def test_parse_duration_and_workload(self):
        sample = """
        Duration of the master’s thesis project: 6 months.
        EUR 1.379,60 gross per month for 20 hours/week based on the collective agreement.
        """
        dur, work, comp = parse_duration_and_workload(sample)
        self.assertEqual(dur, "6 months")
        self.assertEqual(work, "20 hrs/week")
        self.assertIn("1.379,60", comp)

    def test_parse_duration_split_tags(self):
        # AIT CMS split tag case: EUR 1</strong><strong>027,40
        sample = "Duration: 6 months (flexible start). EUR 1</strong><strong>027,40 </strong>gross per month for 20 hours/week."
        dur, work, comp = parse_duration_and_workload(sample)
        self.assertIn("6 months", dur)
        self.assertEqual(work, "20 hrs/week")
        self.assertIn("1027,40", comp)


if __name__ == '__main__':
    unittest.main()
