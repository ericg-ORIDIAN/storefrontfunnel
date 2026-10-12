#!/usr/bin/env python3
"""
StorefrontFunnel v0.4 — Site vs Stripe Catalog Consistency Scanner
FIXED: Courses are on the homepage (not /courses). Extracts course/program names
from homepage HTML, compares against Stripe catalog, reports gaps.
v0.4b: Filtered extraction — only real course names, not feature descriptions.
"""

import json, sys, re, os
from urllib.request import urlopen, Request
from html.parser import HTMLParser
from datetime import datetime, timezone

# ── Known course names for Oridian Consulting ──
KNOWN_COURSES = [
    "Business Operations Fundamentals",
    "Strategic Planning for Owners and Managers",
    "Leadership Essentials",
    "Change Management Practitioner",
    "Automation Architect Program",
    "Advanced Program",
    "Executive Automation Mastermind",
]

# ── Stripe product names (from live catalog) ──
STRIPE_PRODUCTS = {
    "prod_VH77fG8etmYCoV": "Executive Automation Mastermind — 6 Months",
    "prod_VH7702MgoYyBK7": "Automation Architect Program — 12 Weeks",
    "prod_VMvPNaYXh19kPy": "Service Invoice",
    "prod_VMv4Od6jBJgOMZ": "Services Invoice",
}

# ── Phrases that are features, not course names ──
FEATURE_PATTERNS = [
    "graded capstone", "instructor feedback", "coming soon",
    "peer practice", "instructor review", "practice assessments",
    "next up", "live program", "instructor capstone",
    "written feedback", "between sessions", "each module",
    "with instructor", "with written", "group between",
]


class TextExtractor(HTMLParser):
    """Extract visible text from HTML, skipping script/style blocks."""
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tag = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip_tag = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip_tag = False

    def handle_data(self, data):
        if not self.skip_tag:
            t = data.strip()
            if t:
                self.text_parts.append(t)

    def get_text(self):
        return ' '.join(self.text_parts)


def fetch_url(url, timeout=15):
    """Fetch a URL and return (status_code, html_text, error_string)."""
    try:
        req = Request(url, headers={'User-Agent': 'StorefrontFunnel/0.4'})
        resp = urlopen(req, timeout=timeout)
        html = resp.read().decode('utf-8', errors='replace')
        return resp.status, html, None
    except Exception as e:
        return None, '', str(e)


def is_feature_text(name):
    """Check if a name is actually a feature description, not a course."""
    nl = name.lower()
    for pat in FEATURE_PATTERNS:
        if pat in nl:
            return True
    return False


def extract_courses_from_homepage(html):
    """
    Extract course/program names from homepage HTML.
    Uses a curated list of known courses + pattern matching for named programs.
    Filters out feature descriptions that look like courses.
    """
    ext = TextExtractor()
    ext.feed(html)
    full_text = ext.get_text()

    # Match known courses by substring (case-insensitive)
    found = []
    for kc in KNOWN_COURSES:
        if kc.lower() in full_text.lower():
            found.append(kc)

    # Also look for "Certificate in X" or "X Certificate" patterns
    cert_patterns = re.findall(
        r'(?:Certificate\s+in\s+)?[A-Z][A-Za-z\s]{3,40}(?:Certificate|Program)',
        full_text
    )
    for cp in cert_patterns:
        cp = cp.strip()
        if cp not in found and len(cp) > 10 and not is_feature_text(cp):
            found.append(cp)

    return found, full_text


def scan_site(target_url='https://oridianconsulting.com', timeout=15):
    """
    Scan a website for advertised courses and compare against Stripe catalog.
    Returns a dict with scan results.
    """
    ts = datetime.now(timezone.utc).isoformat()

    # Fetch homepage
    status, html, error = fetch_url(target_url, timeout)
    if error:
        return {"ts": ts, "target": target_url, "error": error}

    # Extract courses from homepage
    courses_found, full_text = extract_courses_from_homepage(html)

    # Check for prices on homepage
    prices = re.findall(r'\$\s*\d[\d,]+', full_text)

    # Check for enroll/waitlist CTAs
    enroll_now = bool(re.search(r'Enroll now', html, re.IGNORECASE))
    waitlist = bool(re.search(r'Join the waitlist', html, re.IGNORECASE))

    # Compare against Stripe catalog
    stripe_product_names = list(STRIPE_PRODUCTS.values())
    matched_in_stripe = []
    not_in_stripe = []

    for c in courses_found:
        matched = False
        for sp in stripe_product_names:
            c_clean = c.lower().replace('certificate ', '').replace('certificate in ', '').strip()
            sp_clean = sp.lower()
            if c_clean in sp_clean or sp_clean in c_clean:
                matched = True
                break
        if matched:
            matched_in_stripe.append(c)
        else:
            not_in_stripe.append(c)

    # Build issues list
    issues = []
    if not enroll_now:
        issues.append({"type": "NO_ENROLL_CTA",
                       "detail": "No 'Enroll now' CTA found on homepage — waitlist only"})
    if not prices:
        issues.append({"type": "NO_PRICES_ON_HOMEPAGE",
                       "detail": "No prices detected on homepage text"})
    if not_in_stripe:
        issues.append({"type": "COURSES_NOT_IN_STRIPE",
                       "detail": f"{len(not_in_stripe)} courses found on site but not in Stripe catalog: {not_in_stripe}"})

    result = {
        "ts": ts,
        "scanner_version": "0.4b",
        "target": target_url,
        "homepage_status": status,
        "site_courses_found": courses_found,
        "matched_in_stripe": matched_in_stripe,
        "not_in_stripe": not_in_stripe,
        "stripe_product_count": len(stripe_product_names),
        "stripe_products": stripe_product_names,
        "prices_found": prices,
        "enroll_now_available": enroll_now,
        "waitlist_available": waitlist,
        "issues": issues,
        "healthy": len(issues) == 0,
    }
    return result


def generate_report(result, fmt='md'):
    """Generate a human-readable report from scan results."""
    if fmt == 'md':
        lines = [
            f"# StorefrontFunnel Scan Report",
            f"**Target:** {result.get('target', 'N/A')}",
            f"**Scanner:** v{result.get('scanner_version', '?')}",
            f"**Timestamp:** {result.get('ts', 'N/A')}",
            f"**Homepage Status:** {result.get('homepage_status', 'ERROR')}",
            f"**Healthy:** {'✅' if result.get('healthy') else '❌'}",
            "",
            "## Courses Found on Site",
        ]
        for c in result.get('site_courses_found', []):
            marker = "✅" if c in result.get('matched_in_stripe', []) else "❌"
            lines.append(f"- {marker} {c}")

        lines += [
            "",
            "## Stripe Products",
        ]
        for p in result.get('stripe_products', []):
            lines.append(f"- {p}")

        lines += [
            "",
            "## Issues",
        ]
        for issue in result.get('issues', []):
            lines.append(f"- **{issue['type']}**: {issue['detail']}")

        lines += [
            "",
            "## Prices on Site",
            str(result.get('prices_found', [])),
        ]
        return '\n'.join(lines)

    return json.dumps(result, indent=2)


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'https://oridianconsulting.com'
    result = scan_site(target)
    print(generate_report(result, fmt='md'))
    # Also save JSON
    out_dir = os.path.dirname(os.path.abspath(__file__))
    ts_safe = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S')
    out_path = os.path.join(out_dir, f'scan_result_{ts_safe}.json')
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\n--- Saved to {out_path} ---")