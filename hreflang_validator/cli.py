"""Command line entry point: `hreflang-validator SOURCE`."""
from pathlib import Path

import click

from . import __version__, core
from .benchmark import STATS
from .report import Report, write_excel


@click.command()
@click.argument("source")
@click.option("--max-pages", default=300, show_default=True, help="Most pages to fetch (start URLs + alternates).")
@click.option("--delay", default=0.5, show_default=True, help="Seconds between requests (min 0.5).")
@click.option("-o", "--output", default="hreflang_report", show_default=True,
              help="Report name; writes <name>.html and <name>.xlsx")
@click.version_option(__version__)
def main(source, max_pages, delay, output):
    """Validate hreflang for SOURCE: a page URL, a sitemap URL (.xml) or a file with one URL per line.

    Built by Meer Hamza - linkedin.com/in/meerhamza-seo
    """
    click.echo(f"Checking hreflang from {source} ...")
    r = core.audit(source, delay=delay, max_pages=max_pages)
    pages, notes, issues = r["pages"], r["annotations"], r["issues"]
    errors = int((issues["severity"] == "error").sum()) if not issues.empty else 0
    warnings = int((issues["severity"] == "warning").sum()) if not issues.empty else 0
    no_return = int((notes["return_link"] == "no").sum()) if not notes.empty else 0
    with_tags = int((pages["hreflang_tags"] > 0).sum()) if not pages.empty else 0

    report = Report(title="hreflang report", subtitle=f"{source} · {len(pages)} pages · {r['requests']} requests",
                    tool="hreflang-validator")
    report.add_cards([("Pages checked", len(pages)), ("Pages with hreflang", with_tags),
                      ("hreflang links", len(notes)),
                      ("Missing return links", no_return, "bad" if no_return else "good"),
                      ("Errors", errors, "bad" if errors else "good"),
                      ("Warnings", warnings, "warn" if warnings else "good")])
    report.add_benchmark(STATS[0], how_used="One of NP Digital's actionable insights is \"Use Hreflang "
                         "Correctly\". Translated pages only reach the right audience when every language "
                         "version points to the others and to itself, so this report checks exactly that.")
    report.add_table("Issues by type", r["summary"], sheet="Summary")
    report.add_table("All issues", issues, sheet="Issues",
                     note="Errors make Google ignore an hreflang pair. Warnings and notices are worth fixing next.")
    report.add_table("hreflang links", notes, sheet="Annotations",
                     note="Every hreflang entry found, with the target's status and whether it links back.")
    report.add_table("Pages", pages, sheet="Pages")

    html_path = report.save_html(Path(output).with_suffix(".html"))
    xlsx_path = write_excel(report.sheets, Path(output).with_suffix(".xlsx"))
    click.secho(f"Report: {html_path}\nData:   {xlsx_path}", fg="green", bold=True)
    click.echo(f"{len(pages)} pages, {len(notes)} hreflang links, {errors} errors, {warnings} warnings")
    if not r["summary"].empty:
        click.echo(r["summary"].to_string(index=False))


if __name__ == "__main__":
    main()
