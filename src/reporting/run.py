from pathlib import Path
import argparse

from reporting.modules.leave_report_md import generate_leave_report
from reporting.modules.term_report_md import generate_term_report
from reporting.modules.rkeg_report_md import generate_rkeg_report
from reporting.modules.lsl_report_md import generate_lsl_exposure_report

from reporting.executive.exec_pack_md import (
    generate_leave_leakage_report,
    MODULE_LEAVE,
    MODULE_LSL,
    MODULE_TERM,
    MODULE_RKEG,
    DEFAULT_MODULES,
    normalise_modules,
)

from reporting.render import build_html_and_pdf
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
    p.add_argument(
        "--organisation-name",
        default="Example Client Pty Ltd",
        help="Organisation name to show in report headers.",
    )
    p.add_argument(
        "--review-period",
        default=None,
        help='Optional override for the review period text, e.g. "1 Jan 2020 to 31 Dec 2020".',
    )
    p.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Optional output directory for rendered HTML/PDF. "
            "If omitted, HTML/PDF are written to repo_root/outputs."
        ),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    # Base outputs dir where CSVs and Markdown live
    repo_outputs = repo_root / "outputs"

    # Where to write rendered reports (may be a client-specific subfolder)
    if args.output_dir:
        output_dir = Path(args.output_dir)
        if not output_dir.is_absolute():
            # Treat as relative to repo root
            output_dir = repo_root / output_dir
    else:
        output_dir = repo_outputs

    repo_outputs.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    org_name = args.organisation_name
    review_period_override = args.review_period

    # Normalise module selection
    # If no modules specified, fall back to DEFAULT_MODULES from exec_pack_md
    raw_modules = args.modules or DEFAULT_MODULES
    included_modules = normalise_modules(raw_modules)

    # 1) Main executive pack markdown (always)
    exec_md_path = generate_leave_leakage_report(
        organisation_name=org_name,
        review_period=review_period_override,
        modules=included_modules,
    )

    # 2) Main executive pack HTML/PDF (always)
    build_html_and_pdf(
        md_path=exec_md_path,
        html_path=output_dir / "crc_executive_pack.html",
        pdf_path=output_dir / "crc_executive_pack.pdf",
        page_title="CRC Executive Pack — Payroll Risk & Evidence Review",
    )

    if not args.only_main_report:
        # 3) Generate extra markdown packs (module detailed reports, controlled by --modules)

        # a) Leave-only detailed module report
        if MODULE_LEAVE in included_modules:
            leave_md = generate_leave_report(
                organisation_name=org_name,
                review_period=review_period_override,
            )
            build_html_and_pdf(
                md_path=leave_md,
                html_path=output_dir / "leave_report.html",
                pdf_path=output_dir / "leave_report.pdf",
                page_title="Leave & Entitlement Leakage – Detailed Report",
            )

        # b) LSL module report
        if MODULE_LSL in included_modules:
            lsl_md = generate_lsl_exposure_report(
                organisation_name=org_name,
                review_period=review_period_override,
            )
            build_html_and_pdf(
                md_path=lsl_md,
                html_path=output_dir / "lsl_report.html",
                pdf_path=output_dir / "lsl_report.pdf",
                page_title="Long Service Leave (LSL) Exposure Review",
            )

        # c) Termination Exposure module report
        if MODULE_TERM in included_modules:
            term_md = generate_term_report(
                organisation_name=org_name,
                review_period=review_period_override,
            )
            build_html_and_pdf(
                md_path=term_md,
                html_path=output_dir / "term_report.html",
                pdf_path=output_dir / "term_report.pdf",
                page_title="Termination Exposure – Detailed Report",
            )

        # d) Record-Keeping & Evidence Gaps (RKEG) module report
        if MODULE_RKEG in included_modules:
            rkeg_md = generate_rkeg_report(
                organisation_name=org_name,
                review_period=review_period_override,
            )
            build_html_and_pdf(
                md_path=rkeg_md,
                html_path=output_dir / "rkeg_report.html",
                pdf_path=output_dir / "rkeg_report.pdf",
                page_title="Record-Keeping & Evidence Gaps – Detailed Report",
            )

        # e) Pre-/Post-audit narrative overviews (engagement-level, not per-module)
        pre_md = generate_pre_audit_overview(
            organisation_name=org_name,
            prepared_as_at=None,
        )
        post_md = generate_post_audit_overview(
            organisation_name=org_name,
            prepared_as_at=None,
        )

        # Render Pre-/Post-audit HTML/PDF
        build_html_and_pdf(
            md_path=pre_md,
            html_path=output_dir / "pre_audit_overview.html",
            pdf_path=output_dir / "pre_audit_overview.pdf",
            page_title="Pre-Audit Payroll Compliance Review",
        )
        build_html_and_pdf(
            md_path=post_md,
            html_path=output_dir / "post_audit_overview.html",
            pdf_path=output_dir / "post_audit_overview.pdf",
            page_title="Post-Audit Payroll Compliance Review",
        )

        # Public Holiday report (external tool output, optional)
        ph_md = repo_outputs / "public_holiday_compliance_report.md"
        if ph_md.exists():
            build_html_and_pdf(
                md_path=ph_md,
                html_path=output_dir / "public_holiday_report.html",
                pdf_path=output_dir / "public_holiday_report.pdf",
                page_title="Public Holiday Compliance Review",
            )
        else:
            print("Skipping Public Holiday HTML/PDF – markdown not found in this repo's outputs/")

        # Summary
        if MODULE_LEAVE in included_modules:
            print("Wrote leave_report.md and HTML/PDF")
        if MODULE_LSL in included_modules:
            print("Wrote lsl_report.md and HTML/PDF")
        if MODULE_TERM in included_modules:
            print("Wrote term_report.md and HTML/PDF")
        if MODULE_RKEG in included_modules:
            print("Wrote rkeg_report.md and HTML/PDF")
        print("Wrote pre_audit_overview.md and HTML/PDF")
        print("Wrote post_audit_overview.md and HTML/PDF")
    else:
        print("Wrote crc_executive_pack.md and HTML/PDF only")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())