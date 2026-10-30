<div align="center">

# 🌍 hreflang-validator

### Check every hreflang tag on your site: codes, return links, x-default and canonical conflicts.

[![tests](https://github.com/marketing-MEER/hreflang-validator/actions/workflows/ci.yml/badge.svg)](https://github.com/marketing-MEER/hreflang-validator/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![No API keys](https://img.shields.io/badge/API%20keys-none%20needed-brightgreen)
[![Part of SEO Toolbox](https://img.shields.io/badge/part%20of-SEO%20Toolbox-orange)](https://github.com/marketing-MEER/seo-toolbox)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Meer%20Hamza-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/meerhamza-seo)

[🚀 Quick start](#quick-start) · [⚙️ How it works](#how-it-works) · [📄 Report](#report) · [❓ FAQ](#faq) · [👤 Author](#author)

</div>

---

## 💡 What it does

Checking hreflang by hand means opening every language version, copying its tags into a sheet and matching
them pair by pair. This tool does that for you: give it a page, a sitemap or a list of URLs, and it fetches
each page and its alternates, then tells you which pairs Google will ignore and why.

- ✅ Finds missing return links, wrong codes (`en-uk`, `jp`, `de_DE`), relative URLs, missing self references and x-default
- ✅ Catches the quiet killers: alternates that redirect, 404, are noindex or canonicalise to another URL
- ✅ Reads hreflang from HTML `<link>` tags, HTTP `Link` headers and XML sitemaps
- ✅ Free, MIT licensed, no API keys. Works with the exports you already have.

## 📊 Why this matters

> **Global Internet Users & Web Content by Language** · DataReportal, We Are Social Meltwater, W3Techs, InternetWorldStats, Kepios, January 2025
> - English accounts for 49.4 percent of global web content, yet only 1.2 billion users speak it online.
> - Spanish-speaking users total 363 million, while Spanish content makes up just 6 percent of the web.
>
> Data: [Neil Patel marketing stats](https://neilpatel.com/marketing-stats/global-internet-users-by-language/)

**How hreflang-validator uses this:** the stat page's actionable insights say to translate your best pages
for underserved languages and to use hreflang correctly so each region gets the right version. This tool
checks the second part: every language version must list itself and the others, and every pair must link both ways.

<a id="quick-start"></a>

## 🚀 Quick start

```bash
git clone https://github.com/marketing-MEER/hreflang-validator.git
cd hreflang-validator
pip install -e .
hreflang-validator https://www.example.com/sitemap.xml
```

This writes **`hreflang_report.html`** (a formatted report you can open, share or print to PDF) and **`hreflang_report.xlsx`** (all the data).

> [!TIP]
> If the `hreflang-validator` command isn't found, use `python -m hreflang_validator`.

## 📥 Input

| Input | Example | What happens |
|---|---|---|
| One page URL | `https://www.example.com/en/pricing/` | Checks the page and every alternate it lists |
| Sitemap URL (`.xml`) | `https://www.example.com/sitemap.xml` | Checks every URL in it, plus `xhtml:link` hreflang entries; sitemap indexes are followed |
| Text or CSV file | `urls.txt` | One URL per line (the first URL in each line is used), e.g. a Screaming Frog or GSC export |

Alternates on the same hosts as your input are fetched too, so one URL is often enough to check a whole page set.
Alternates on other domains (for example a ccTLD) are listed as "not checked"; add that domain's URLs to the input to include them.

<a id="how-it-works"></a>

## ⚙️ How it works

1. Reads the input and fetches each URL (own user agent, at least 0.5 s between requests, redirects are not followed so they show up).
2. Collects hreflang from `<link rel="alternate" hreflang>`, the HTTP `Link` header and the sitemap, plus the canonical and robots meta / `X-Robots-Tag`.
3. Fetches every alternate on the same hosts, up to `--max-pages`.
4. Checks each page and each pair (based on Google Search Central's guidance on localized versions):

| Check | Severity |
|---|---|
| hreflang URL is relative | error |
| Code is not `language` or `language-REGION` (underscore, country code as language like `jp`, region `uk` instead of `gb`) | error |
| Language code outside the tool's short list of common codes | notice |
| Same code points to two different URLs | error |
| Page with hreflang does not return 200, or canonicalises elsewhere | error |
| Alternate returns a redirect / 404, is noindex or canonicalises elsewhere | error |
| Alternate does not link back (no return link) | error |
| No self-referencing hreflang / hreflang on a noindex page | warning |
| No x-default | notice |

### Options

| Option | Default | What it does |
|---|---|---|
| `--max-pages` | `300` | Most pages to fetch (start URLs + alternates) |
| `--delay` | `0.5` | Seconds between requests (never less than 0.5) |
| `-o`, `--output` | `hreflang_report` | File name for the report (`.html` + `.xlsx`) |

<a id="report"></a>

## 📄 The report

- **Cards**: pages checked, pages with hreflang, hreflang links, missing return links, errors, warnings.
- **Benchmark**: the Neil Patel stat above, with source and link.
- **Issues by type** (`Summary` sheet): how often each problem appears and on how many pages.
- **All issues** (`Issues` sheet): page, severity, issue, code, target and a short fix.
- **hreflang links** (`Annotations` sheet): every entry found, where it came from (html, http header, sitemap), the target's status and canonical, and whether it links back.
- **Pages** (`Pages` sheet): status, canonical, indexable, number of tags, languages, self reference and x-default per page.

<details>
<summary>📄 Example: real output from <code>examples/</code></summary>

Run on the fictional site in `examples/site` (`hreflang-validator http://localhost:8000/sitemap.xml`):
11 pages, 27 hreflang links, 10 errors, 2 warnings.

| issue | severity | count | pages |
|---|---|---|---|
| Invalid or unusual hreflang code | error | 3 | 2 |
| hreflang target returns 404 | error | 2 | 2 |
| No return link from the alternate page | error | 1 | 1 |
| hreflang URL is relative | error | 1 | 1 |
| hreflang on a page that canonicalises elsewhere | error | 1 | 1 |
| hreflang target canonicalises elsewhere | error | 1 | 1 |
| hreflang target is noindex | error | 1 | 1 |
| No self-referencing hreflang | warning | 1 | 1 |
| hreflang on a noindex page | warning | 1 | 1 |
| No x-default | notice | 4 | 4 |

First rows of the issue list:

| page | severity | issue | hreflang | target |
|---|---|---|---|---|
| http://localhost:8000/de/features.html | error | hreflang on a page that canonicalises elsewhere |  |  |
| http://localhost:8000/de/pricing.html | error | No return link from the alternate page | fr | http://localhost:8000/fr/pricing.html |
| http://localhost:8000/en/about.html | error | hreflang URL is relative | de | /de/about.html |
| http://localhost:8000/en/about.html | error | hreflang target is noindex | de | http://localhost:8000/de/about.html |
| http://localhost:8000/en/blog.html | error | Invalid or unusual hreflang code | de_DE | http://localhost:8000/de/blog.html |
| http://localhost:8000/en/blog.html | error | hreflang target returns 404 | de_DE | http://localhost:8000/de/blog.html |
| http://localhost:8000/en/features.html | error | Invalid or unusual hreflang code | en-uk | http://localhost:8000/en/features.html |
| http://localhost:8000/en/features.html | error | Invalid or unusual hreflang code | jp | http://localhost:8000/ja/features.html |

</details>

## 🧰 More free SEO tools

This repo is one tool in the **[SEO Toolbox](https://github.com/marketing-MEER/seo-toolbox)**, a family of free, single-purpose SEO tools. Related:
- [robots-sitemap-validator](https://github.com/marketing-MEER/robots-sitemap-validator): robots.txt and XML sitemap checks
- [redirect-chain-fixer](https://github.com/marketing-MEER/redirect-chain-fixer): find redirect chains and loops
- [schema-markup-checker](https://github.com/marketing-MEER/schema-markup-checker): structured data checks
- [seo-workhorse](https://github.com/marketing-MEER/seo-workhorse): audit, clustering, redirects and GSC quick wins in one CLI

<a id="faq"></a>

## ❓ FAQ

<details><summary><b>Does the alternate really need to link back?</b></summary>

Yes. Google only uses an hreflang pair when both pages point to each other. A one-way link is ignored, which is
the most common reason a German page shows up for English searchers.
</details>

<details><summary><b>Is x-default required?</b></summary>

No, so it is only a notice. It tells Google which page to show users who match none of your languages, usually
the English page or a language picker.
</details>

<details><summary><b>Why is my code flagged as a notice and not an error?</b></summary>

The tool knows a short list of common language codes. A code outside it is not wrong by itself; the notice just
asks you to check it against ISO 639-1.
</details>

<details><summary><b>Is my data sent anywhere?</b></summary>

No. Everything runs on your machine. The only requests are plain GETs to the URLs you give it and their
alternates on the same hosts, with the user agent `hreflang-validator/1.0`.
</details>

## 🧪 Tests

```bash
python -m unittest discover -s tests -t . -v
```

## 📄 License

[MIT](LICENSE). Free for personal and commercial use. Benchmark figures © their original publishers and quoted with a link to the source.

<a id="author"></a>

## 👤 Author

**Meer Hamza** · SEO Team Lead · Berlin 🇩🇪
10+ years in SEO, AEO and GEO. I build small tools that take the spreadsheet work out of SEO.

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/meerhamza-seo)
[![Email](https://img.shields.io/badge/Email-meerhamza5%40gmail.com-D14836?logo=gmail&logoColor=white)](mailto:meerhamza5@gmail.com)

<div align="center">

**If this saved you time, a ⭐ helps other SEOs find it.**

</div>
