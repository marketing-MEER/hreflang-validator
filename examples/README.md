# 📂 Examples

`site/` is a tiny made-up website for a fictional CRM brand (`brightcrm`) in English, German, French and
Japanese. All names and pages are invented. It has typical hreflang mistakes built in on purpose: a missing
return link, codes like `en-uk`, `jp` and `de_DE`, a relative hreflang URL, an alternate that is noindex, one
that canonicalises to another URL, alternates that return 404, a page without a self reference, and pages
without x-default. One page carries its hreflang in `sitemap.xml` only.

Serve it locally and point the tool at it:

```bash
python -m http.server 8000 --directory examples/site
# in a second terminal:
hreflang-validator http://localhost:8000/sitemap.xml
# or start from a URL list:
hreflang-validator examples/urls.txt
```

The pages use `http://localhost:8000`, so keep port 8000.
