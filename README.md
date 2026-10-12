# StorefrontFunnel — Site vs Stripe Catalog Consistency Scanner

Scans a storefront website for advertised products or courses and compares them against a Stripe product catalog. Reports what is advertised but not sellable, what is sellable but not advertised, broken product/course links, and missing prices.

## Why
Marketing pages and payment catalogs drift apart. A product gets renamed in Stripe, a landing page keeps the old name, the buy button 404s, and nobody notices until a customer emails. StorefrontFunnel makes that drift visible in one scan.

## Usage
```
python3 storefrontfunnel.py https://example.com
python3 storefrontfunnel.py https://example.com --format markdown
```
Edit `STRIPE_PRODUCTS` in the script with your catalog names (live Stripe API fetch is on the roadmap).

## Output
JSON or Markdown report: matched items, missing from catalog, missing from site, broken links, price gaps.

## Roadmap
- Live Stripe catalog fetch
- Scheduled scans with email/Slack alerts
- White-label reports
- Hosted version

## License
MIT

Built by Oridian Consulting LLC.
