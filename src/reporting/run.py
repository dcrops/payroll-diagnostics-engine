from pathlib import Path
import argparse

from reporting.leave_report_md import generate_leave_report
from reporting.term_report_md import generate_term_report
from reporting.rkeg_report_md import generate_rkeg_report
from reporting.exec_pack_md import (
    generate_leave_leakage_report,
    MODULE_LEAVE,
    MODULE_LSL,
    MODULE_TERM,
    MODULE_RKEG,
    DEFAULT_MODULES,
    normalise_modules,
)
from reporting.render import build_html_and_pdf
from reporting.lsl_report_md import generate_lsl_exposure_report
from reporting.pre_audit_overview_md import generate_pre_audit_overview
from reporting.post_audit_overview_md import generate_post_audit_overview


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--modules",
        nargs="+",
        default=None,
        help="Modules to include in the main report and detailed packs, e.g. TERM RKEG LEAVE",
    )
    p.add_argument(
        "--only-main-report",
        action="store_true",
        help=(
            "Only build outputs/crc_executive_pack.md(.html/.pdf). "
            "Skip module detailed packs and overview packs."
        ),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    outputs = repo_root / "outputs"

    # Normalise module selection
    # If no modules specified, fall back to DEFAULT_MODULES from exec_pack_md
    raw_modules = args.modules or DEFAULT_MODULES
    included_modules = normalise_modules(raw_modules)

    # 1) Main executive pack markdown (always)
    generate_leave_leakage_report(
        organisation_name="Example Client Pty Ltd",
        modules=included_modules,
    )

    # 2) Main executive pack HTML/PDF (always)
    build_html_and_pdf(
        md_path=outputs / "crc_executive_pack.md",
        html_path=outputs / "crc_executive_pack.html",
        pdf_path=outputs / "crc_executive_pack.pdf",
        page_title="CRC Executive Pack — Payroll Risk & Evidence Review",
    )

    if not args.only_main_report:
        # 3) Generate extra markdown packs (module detailed reports, controlled by --modules)

        # a) Leave-only detailed module report
                # a) Leave-only detailed module report
        if MODULE_LEAVE in included_modules:
            generate_leave_report(
                organisation_name="Example Client Pty Ltd",
            )

        # b) LSL module report
        if MODULE_LSL in included_modules:
            generate_lsl_exposure_report(
                organisation_name="Example Client Pty Ltd",
            )

        # c) Termination Exposure module report
        if MODULE_TERM in included_modules:
            generate_term_report(
                organisation_name="Example Client Pty Ltd",
            )

        # d) Record-Keeping & Evidence Gaps (RKEG) module report
        if MODULE_RKEG in included_modules:
            generate_rkeg_report(
                organisation_name="Example Client Pty Ltd",
            )

        # e) Pre-/Post-audit narrative overviews (engagement-level, not per-module)
        generate_pre_audit_overview(
            organisation_name="Example Client Pty Ltd",
            prepared_as_at=None,
        )

        generate_post_audit_overview(
            organisation_name="Example Client Pty Ltd",
            prepared_as_at=None,
        )

        # 4) Render extra HTML/PDF

        # Leave-only detailed report
                # Leave-only detailed report
        if MODULE_LEAVE in included_modules:
            build_html_and_pdf(
                md_path=outputs / "leave_report.md",
                html_path=outputs / "leave_report.html",
                pdf_path=outputs / "leave_report.pdf",
                page_title="Leave & Entitlement Leakage – Detailed Report",
            )

        # LSL Exposure report
        if MODULE_LSL in included_modules:
            build_html_and_pdf(
                md_path=outputs / "lsl_report.md",
                html_path=outputs / "lsl_report.html",
                pdf_path=outputs / "lsl_report.pdf",
                page_title="Long Service Leave (LSL) Exposure Review",
            )

        # Termination Exposure detailed report
        if MODULE_TERM in included_modules:
            build_html_and_pdf(
                md_path=outputs / "term_report.md",
                html_path=outputs / "term_report.html",
                pdf_path=outputs / "term_report.pdf",
                page_title="Termination Exposure – Detailed Report",
            )

        # Record-Keeping & Evidence Gaps detailed report
        if MODULE_RKEG in included_modules:
            build_html_and_pdf(
                md_path=outputs / "rkeg_report.md",
                html_path=outputs / "rkeg_report.html",
                pdf_path=outputs / "rkeg_report.pdf",
                page_title="Record-Keeping & Evidence Gaps – Detailed Report",
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

        # Public Holiday report (external tool output, optional)
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

        # Summary
        if MODULE_LEAVE in included_modules:
            print("Wrote outputs/leave_report.md / leave_report.html")
        if MODULE_LSL in included_modules:
            print("Wrote outputs/lsl_report.md / lsl_report.html")
        if MODULE_TERM in included_modules:
            print("Wrote outputs/term_report.md / term_report.html")
        if MODULE_RKEG in included_modules:
            print("Wrote outputs/rkeg_report.md / rkeg_report.html")
        print("Wrote outputs/pre_audit_overview.md / pre_audit_overview.html")
        print("Wrote outputs/post_audit_overview.md / post_audit_overview.html")
    else:
        print("Wrote outputs/crc_executive_pack.md / crc_executive_pack.html")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())