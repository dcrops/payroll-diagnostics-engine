from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from founder_copilot.copilot import answer_query
from founder_copilot.rule_browser import list_rules_by_risk_dimension
from founder_copilot.explain_finding import explain_finding_id
from founder_copilot.trace_finding import trace_finding_id
from founder_copilot.discovery_assistant import suggest_crc_scope
from founder_copilot.coverage_audit import build_coverage_report, print_report


def cmd_ask(args: argparse.Namespace) -> None:
    filters: dict[str, Any] = {}

    if args.module:
        filters["module"] = args.module
    if args.tier is not None:
        filters["tier"] = args.tier
    if args.risk_dimension:
        filters["risk_dimension"] = args.risk_dimension
    if args.source_type:
        filters["source_type"] = args.source_type

    result = answer_query(
        query=args.query,
        k=args.k,
        filters=filters or None,
    )
    print(result)


def cmd_rule_browser(args: argparse.Namespace) -> None:
    rows = list_rules_by_risk_dimension(
        risk_dimension=args.risk_dimension,
        module=args.module,
        tier=args.tier,
    )

    if not rows:
        print("No rules found.")
        return

    for r in rows:
        print(
            f"- {r['rule_id']} "
            f"(Module={r['module']}, Tier={r['tier']}, Severity={r['severity']}): "
            f"{r['title']}"
        )


def cmd_explain_finding(args: argparse.Namespace) -> None:
    result = explain_finding_id(
        csv_path=args.csv_path,
        finding_id=args.finding_id,
    )
    print(result)


def cmd_trace_finding(args: argparse.Namespace) -> None:
    result = trace_finding_id(
        findings_csv=args.csv_path,
        finding_id=args.finding_id,
    )
    print(result)


def cmd_discovery(args: argparse.Namespace) -> None:
    concerns = [c.strip() for c in args.concerns if c and c.strip()]
    if not concerns:
        print("No concerns supplied.")
        return

    result = suggest_crc_scope(
        concerns=concerns,
        module=args.module,
        k=args.k,
    )
    print(result)


def cmd_coverage_audit(args: argparse.Namespace) -> None:
    report = build_coverage_report(
        yaml_path=Path(args.yaml_path),
        code_root=Path(args.code_root),
        restrict_to_prefix=args.prefix,
    )
    print_report(report, show_occurrences=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="founder_copilot",
        description="CRC Founder Copilot CLI",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ----------------------------
    # ask
    # ----------------------------
    ask_parser = subparsers.add_parser(
        "ask",
        help="Ask the Founder Copilot a question using RAG retrieval",
    )
    ask_parser.add_argument("query", type=str, help="Question to ask")
    ask_parser.add_argument("--k", type=int, default=3, help="Top-k retrieval count")
    ask_parser.add_argument("--module", type=str, default=None, help="Optional module filter")
    ask_parser.add_argument("--tier", type=int, default=None, help="Optional tier filter")
    ask_parser.add_argument(
        "--risk-dimension",
        dest="risk_dimension",
        type=str,
        default=None,
        help="Optional risk dimension filter",
    )
    ask_parser.add_argument(
        "--source-type",
        dest="source_type",
        type=str,
        default=None,
        help="Optional source type filter",
    )
    ask_parser.set_defaults(func=cmd_ask)

    # ----------------------------
    # rule-browser
    # ----------------------------
    browser_parser = subparsers.add_parser(
        "rule-browser",
        help="List rules by risk dimension",
    )
    browser_parser.add_argument("risk_dimension", type=str, help="Risk dimension to browse")
    browser_parser.add_argument("--module", type=str, default=None, help="Optional module filter")
    browser_parser.add_argument("--tier", type=int, default=None, help="Optional tier filter")
    browser_parser.set_defaults(func=cmd_rule_browser)

    # ----------------------------
    # explain-finding
    # ----------------------------
    explain_parser = subparsers.add_parser(
        "explain-finding",
        help="Explain a finding from a findings CSV using finding_id",
    )
    explain_parser.add_argument("csv_path", type=str, help="Path to findings CSV")
    explain_parser.add_argument("finding_id", type=str, help="Finding ID")
    explain_parser.set_defaults(func=cmd_explain_finding)

    # ----------------------------
    # trace-finding
    # ----------------------------
    trace_parser = subparsers.add_parser(
        "trace-finding",
        help="Trace the evidence for a finding from a findings CSV",
    )
    trace_parser.add_argument("csv_path", type=str, help="Path to findings CSV")
    trace_parser.add_argument("finding_id", type=str, help="Finding ID")
    trace_parser.set_defaults(func=cmd_trace_finding)

    # ----------------------------
    # discovery
    # ----------------------------
    discovery_parser = subparsers.add_parser(
        "discovery",
        help="Suggest CRC scope from client concerns",
    )
    discovery_parser.add_argument(
        "concerns",
        nargs="+",
        help="One or more client concerns (quote each concern if needed)",
    )
    discovery_parser.add_argument("--module", type=str, default="RKEG", help="Module filter")
    discovery_parser.add_argument("--k", type=int, default=5, help="Top-k retrieval count")
    discovery_parser.set_defaults(func=cmd_discovery)

    # ----------------------------
    # coverage-audit
    # ----------------------------
    coverage_parser = subparsers.add_parser(
        "coverage-audit",
        help="Check YAML rule coverage against code implementation",
    )
    coverage_parser.add_argument(
        "--yaml-path",
        type=str,
        default="src/rkeg/config/rkeg_rules.yml",
        help="Path to rules YAML",
    )
    coverage_parser.add_argument(
        "--code-root",
        type=str,
        default="src",
        help="Root code directory to scan",
    )
    coverage_parser.add_argument(
        "--prefix",
        type=str,
        default="RKEG-",
        help="Rule ID prefix to restrict coverage check",
    )
    coverage_parser.set_defaults(func=cmd_coverage_audit)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())