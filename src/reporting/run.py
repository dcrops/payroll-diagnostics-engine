from datetime import date
from pathlib import Path
from reporting.report_md import generate_leave_leakage_report
from reporting.report_pdf import build_html_and_pdf
from reporting.lsl_report_md import generate_lsl_exposure_report
from reporting.pre_audit_overview_md import generate_pre_audit_overview
from reporting.post_audit_overview_md import generate_post_audit_overview
import argparse
from typing import Optional, List

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--modules",
        nargs="+",
        default=None,
        help="Modules to include in the main report, e.g. TERM RKEG LEAVE",
    )
    p.add_argument(
        "--only-main-report",
        action="store_true",
        help="Only build outputs/report.md(.html/.pdf). Skip LSL/overview packs.",
    )
    return p.parse_args()

def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    outputs = repo_root / "outputs"

    # generate Markdown report
    generate_leave_leakage_report(
    organisation_name="Example Client Pty Ltd",
    modules=args.modules,
)

    if not args.only_main_report:

        generate_lsl_exposure_report(
            organisation_name="Example Client Pty Ltd",
        )

        generate_pre_audit_overview(
            organisation_name="Example Client Pty Ltd",
            prepared_as_at=None,
        )

        generate_post_audit_overview(
            organisation_name="Example Client Pty Ltd",
            prepared_as_at=None,
        )

    # All the HTML/PDF blocks also go inside this if


        # HTML layer (PDF is best-effort on Windows)
    # Leave & Entitlement Leakage report
    build_html_and_pdf(
        md_path=outputs / "report.md",
        html_path=outputs / "report.html",
        pdf_path=outputs / "report.pdf",  # PDF may be skipped if WeasyPrint isn't available
        page_title="Leave & Entitlement Leakage Review",
    )

    # LSL Exposure report
    build_html_and_pdf(
        md_path=outputs / "lsl_report.md",
        html_path=outputs / "lsl_report.html",
        pdf_path=outputs / "lsl_report.pdf",
        page_title="Long Service Leave (LSL) Exposure Review",
    )

        # Pre-Audit overview
    build_html_and_pdf(
        md_path=outputs / "pre_audit_overview.md",
        html_path=outputs / "pre_audit_overview.html",
        pdf_path=outputs / "pre_audit_overview.pdf",
        page_title="Pre-Audit Payroll Compliance Review",
    )

    # Post-Audit overview
    build_html_and_pdf(
        md_path=outputs / "post_audit_overview.md",
        html_path=outputs / "post_audit_overview.html",
        pdf_path=outputs / "post_audit_overview.pdf",
        page_title="Post-Audit Payroll Compliance Review",
    )

    # Public Holiday report
    ph_md = outputs / "public_holiday_compliance_report.md"

    if ph_md.exists():
        build_html_and_pdf(
            md_path=ph_md,
            html_path=outputs / "public_holiday_report.html",
            pdf_path=outputs / "public_holiday_report.pdf",
            page_title="Public Holiday Compliance Review",
        )
    else:
        print("Skipping Public Holiday HTML/PDF – markdown not found in this repo's outputs/")

    print("Wrote outputs/report.md / report.html")
    print("Wrote outputs/lsl_report.md / lsl_report.html")
    print("Wrote outputs/pre_audit_overview.md / pre_audit_overview.html")
    print("Wrote outputs/post_audit_overview.md / post_audit_overview.html")
    # PDFs are best-effort; they may or may not exist depending on WeasyPrint setup.
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
