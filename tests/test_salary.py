import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from salary import extract_salary, format_salary, salary_from_jobposting  # noqa: E402


class ExtractSalaryTests(unittest.TestCase):
    def check(self, text, annual_min, annual_max, period, currency='EUR'):
        s = extract_salary(text)
        self.assertIsNotNone(s, text)
        self.assertEqual((s['annual_min'], s['annual_max'], s['period'], s['currency']),
                         (annual_min, annual_max, period, currency), text)

    # Formats seen on real source pages (2026-10).
    def test_karriere_yearly_range(self):
        self.check("Employment type Full Time Salary 58,000 € to 59,500 € yearly Seniority level",
                   58000, 59500, 'year')

    def test_ait_collective_agreement(self):
        self.check("The minimum gross annual salary on a full-time basis (38,5 h / week) according "
                   "to the collective agreement is EUR 61.334,--. The actual salary will be",
                   61334, 61334, 'year')

    def test_prewave_minimum(self):
        self.check("The Package Minimum EUR 45,738 gross annually based on IT Collective Agreement.",
                   45738, 45738, 'year')

    def test_greenhouse_monthly_14(self):
        self.check("Austrian salary range, based on 14 months €4.000 - €4.200 EUR Join us",
                   56000, 58800, 'month')

    def test_devjobs_from(self):
        self.check("Contract Type Permanent employment Salary from 53.802 € gross/year Job Summary",
                   53802, 53802, 'year')

    def test_remotive_usd_k(self):
        self.check("Software Development Salary $80k - $150k Remote Location Worldwide",
                   80000, 150000, 'year', 'USD')

    def test_monthly_with_cents(self):
        self.check("minimum salary of EUR 3.461,43 gross per month (14 times a year)",
                   48460, 48460, 'month')

    def test_lowercase_text(self):
        # fetch_full_text lowercases everything.
        self.check("salary from 53.802 € gross/year", 53802, 53802, 'year')

    def test_karriere_german_template(self):
        self.check("Anstellungsart Vollzeit (Festanstellung) Gehalt 2.303 EUR bis 4.300 EUR monatlich",
                   32242, 60200, 'month')

    def test_no_salary(self):
        self.assertIsNone(extract_salary("Jobicy Salary API For Candidates. Salary Undisclosed"))
        self.assertIsNone(extract_salary("We raised EUR 20 million in our Series B."))
        self.assertIsNone(extract_salary("full-time basis (38,5 h / week)"))
        self.assertIsNone(extract_salary(""))

    def test_format(self):
        self.assertEqual(format_salary(extract_salary("Salary from 53.802 € gross/year")), "€53.8k+ /yr")
        self.assertEqual(format_salary(extract_salary("salary €4.000 - €4.200 per month")), "€56k–58.8k /yr")


class JobPostingSalaryTests(unittest.TestCase):
    def test_monthly_range(self):
        s = salary_from_jobposting({"@type": "MonetaryAmount", "currency": "EUR", "value": {
            "@type": "QuantitativeValue", "minValue": 2303, "maxValue": 4300, "unitText": "MONTH"}})
        self.assertEqual((s['annual_min'], s['annual_max'], s['period']), (32242, 60200, 'month'))

    def test_yearly_single(self):
        s = salary_from_jobposting({"currency": "EUR", "value": {"value": "58000", "unitText": "YEAR"}})
        self.assertEqual((s['annual_min'], s['annual_max']), (58000, 58000))

    def test_unusable(self):
        self.assertIsNone(salary_from_jobposting(None))
        self.assertIsNone(salary_from_jobposting({"currency": "EUR", "value": {"value": 25, "unitText": "HOUR"}}))
        self.assertIsNone(salary_from_jobposting({"currency": "EUR", "value": {"unitText": "YEAR"}}))


if __name__ == '__main__':
    unittest.main()
