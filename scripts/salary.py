"""
Salary extraction for job postings.

Austrian job ads must state the minimum gross pay (Gleichbehandlungsgesetz §9 Abs. 2),
so most detail pages carry a line like "Salary from 53.802 € gross/year" or
"€4.000 - €4.200 based on 14 months". This module pulls the first such amount out of
free text and normalises it to a gross yearly figure so jobs can be compared/sorted.

Monthly figures are annualised with 14 salaries (Austria pays 13th/14th month), which
is what Austrian ads mean by "per month" - except for non-EUR (e.g. USD remote roles),
which are annualised with 12.
"""
import re

_CURRENCY = r'(?:€|eur(?:o|os)?\b|\$|usd\b|£|gbp\b|chf\b)'
# A number in either European (61.334,--  /  45.738) or English (58,000.50 / 45,738) style,
# optionally with a k suffix ("$80k").
_NUM = r'\d{1,3}(?:[.,\s  ]\d{3})+(?:[.,](?:\d{1,2}|--|-))?|\d+(?:[.,]\d+)?\s?k\b|\d{3,7}(?:[.,](?:\d{1,2}|--|-))?'


def _amount(name):
    return rf'(?:{_CURRENCY}\s*)?(?P<{name}>{_NUM})(?:\s*{_CURRENCY})?'


_RANGE_RE = re.compile(
    _amount('lo') + r'\s*(?:-|–|—|to|bis)\s*' + _amount('hi'),
    re.IGNORECASE,
)
_SINGLE_RE = re.compile(_amount('lo'), re.IGNORECASE)

# Salary amounts only count when a salary keyword is close by, otherwise we'd pick up
# revenue figures, funding rounds, headcounts, etc.
_KEYWORD_RE = re.compile(
    r'salary|salaries|gross|brutto|gehalt|compensation|pay(?:ment)?\b|remuneration|'
    r'kollektivvertrag|collective agreement|annual(?:ly)?\b|per (?:year|month|annum)|/\s*(?:year|month)|'
    r'yearly|monthly|monatlich|jährlich|p\.a\.',
    re.IGNORECASE,
)

_MONTH_RE = re.compile(r'month|monat|/\s*mo\b|p\.m\.|14 (?:times|salaries|months)|14x', re.IGNORECASE)
_YEAR_RE = re.compile(r'year|annual|annum|jahr|jährlich|p\.a\.|yearly', re.IGNORECASE)


def _to_number(raw):
    s = raw.strip().lower().replace(' ', '').replace(' ', '').replace(' ', '')
    s = re.sub(r'[.,](?:--|-)$', '', s)
    mult = 1
    if s.endswith('k'):
        mult, s = 1000, s[:-1]
    # Decide which separator (if any) is the decimal one: a trailing ,dd / .dd group.
    m = re.match(r'^(.*?)[.,](\d{1,2})$', s)
    if m:
        whole, dec = m.group(1), m.group(2)
    else:
        whole, dec = s, ''
    whole = re.sub(r'[.,]', '', whole)
    if not whole.isdigit():
        return None
    value = float(f"{whole}.{dec}" if dec else whole)
    return value * mult


def _currency_of(text):
    t = text.lower()
    if '$' in t or 'usd' in t:
        return 'USD'
    if '£' in t or 'gbp' in t:
        return 'GBP'
    if 'chf' in t:
        return 'CHF'
    return 'EUR'


def _build(lo, hi, currency, period, raw):
    if hi < lo:
        lo, hi = hi, lo
    factor = 1 if period == 'year' else (14 if currency == 'EUR' else 12)
    annual_lo, annual_hi = round(lo * factor), round(hi * factor)
    # Sanity bounds for a gross yearly tech salary.
    if not (12_000 <= annual_lo <= 400_000 and annual_hi <= 600_000):
        return None
    return {
        "min": round(lo),
        "max": round(hi),
        "currency": currency,
        "period": period,
        "annual_min": annual_lo,
        "annual_max": annual_hi,
        "raw": ' '.join(raw.split()),
    }


def salary_from_jobposting(base_salary):
    """Salary dict from a schema.org JobPosting `baseSalary` (MonetaryAmount), or None."""
    if not isinstance(base_salary, dict):
        return None
    value = base_salary.get('value')
    if isinstance(value, dict):
        lo = value.get('minValue', value.get('value'))
        hi = value.get('maxValue', lo)
        unit = str(value.get('unitText', '')).upper()
    else:
        lo = hi = value
        unit = str(base_salary.get('unitText', '')).upper()
    period = {'MONTH': 'month', 'YEAR': 'year'}.get(unit)
    try:
        lo, hi = float(lo), float(hi)
    except (TypeError, ValueError):
        return None
    if not period or lo <= 0:
        return None
    currency = str(base_salary.get('currency') or 'EUR').upper()
    raw = f"{currency} {lo:,.0f}" + (f" - {hi:,.0f}" if hi != lo else "") + f" per {period}"
    return _build(lo, hi, currency, period, raw)


def extract_salary(text):
    """Return a salary dict or None.

    {"min": 4000, "max": 4200, "currency": "EUR", "period": "month",
     "annual_min": 56000, "annual_max": 58800, "raw": "€4.000 - €4.200 EUR"}
    """
    if not text:
        return None

    for kw in _KEYWORD_RE.finditer(text):
        # Look at a window around the keyword: amounts usually follow it, but
        # "58,000 € gross/year" puts the keyword after.
        start = max(0, kw.start() - 60)
        window = text[start:kw.end() + 120]

        for regex in (_RANGE_RE, _SINGLE_RE):
            for m in regex.finditer(window):
                # Require a currency marker in the match - avoids grabbing
                # "38,5 h / week", years, or headcounts near the keyword.
                matched = m.group(0)
                if not re.search(_CURRENCY, matched, re.IGNORECASE):
                    continue
                lo = _to_number(m.group('lo'))
                hi = _to_number(m.group('hi')) if 'hi' in m.groupdict() and m.group('hi') else lo
                if lo is None or hi is None:
                    continue
                context = window[max(0, m.start() - 80):m.end() + 60]
                period = _period(lo, context)
                if period is None:
                    continue
                result = _build(lo, hi, _currency_of(matched), period, matched)
                if result:
                    return result
    return None


def _period(amount, context):
    has_month = bool(_MONTH_RE.search(context))
    has_year = bool(_YEAR_RE.search(context))
    if has_month and not has_year:
        return 'month'
    if has_year and not has_month:
        return 'year'
    # Ambiguous or unstated: infer from magnitude.
    if 1_000 <= amount <= 12_000:
        return 'month'
    if amount >= 15_000:
        return 'year'
    return None


def format_salary(s):
    """Short human label, e.g. '€53.8k+ /yr' or '€56k–59k /yr'."""
    if not s:
        return ''
    sym = {'EUR': '€', 'USD': '$', 'GBP': '£'}.get(s['currency'], s['currency'] + ' ')
    lo, hi = s['annual_min'] / 1000, s['annual_max'] / 1000
    fmt = lambda v: f"{v:.1f}".rstrip('0').rstrip('.') + 'k'
    if hi > lo:
        return f"{sym}{fmt(lo)}–{fmt(hi)} /yr"
    return f"{sym}{fmt(lo)}+ /yr"
