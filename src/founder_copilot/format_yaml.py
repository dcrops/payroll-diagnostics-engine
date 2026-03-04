from __future__ import annotations

import re
from pathlib import Path

from .config import RKEG_RULES_YAML


def _ensure_blank_lines_between_rules(text: str) -> str:
    # Ensure blank line after risk_dimension block before next rule
    text = re.sub(
        r"(risk_dimension:\n(?:\s+- .*\n)+)(- id:)",
        r"\1\n\2",
        text
    )

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


def _indent_list_items(text: str, key: str, key_indent: int) -> str:
    """
    Normalize list indentation for blocks like:
      <indent>key:
      <indent>- item
    into:
      <indent>key:
      <indent+2>- item
    Only touches consecutive list items following the key.
    """
    # Match block: "<indent>key:\n<indent>- ...\n<indent>- ...\n"
    pattern = rf"^(?P<indent>[ \t]{{{key_indent}}}){re.escape(key)}:\n(?P<body>(?:[ \t]*-\s.*\n?)+)"
    rx = re.compile(pattern, flags=re.MULTILINE)

    def repl(m: re.Match) -> str:
        indent = m.group("indent")
        body = m.group("body").splitlines()
        fixed = []
        for ln in body:
            if not ln.strip():
                continue
            # force indent+2 spaces then "- "
            ln2 = re.sub(r"^[ \t]*-\s+", indent + "  - ", ln)
            fixed.append(ln2)
        return f"{indent}{key}:\n" + "\n".join(fixed) + "\n"

    return rx.sub(repl, text)


def format_rules_yaml(path: Path = RKEG_RULES_YAML) -> None:
    text = path.read_text(encoding="utf-8")

    # 1) Blank lines between rules
    text = _ensure_blank_lines_between_rules(text)

    # 2) Normalize indentation for known list keys in your rule schema
    # risk_dimension is typically at 2 spaces indent under a rule
    text = _indent_list_items(text, key="risk_dimension", key_indent=2)

    # references is typically at 4 spaces indent under datasets:
    text = _indent_list_items(text, key="references", key_indent=4)

    path.write_text(text, encoding="utf-8")
    print("YAML formatting applied (blank lines + list indentation for risk_dimension/references).")


def main() -> None:
    format_rules_yaml()


if __name__ == "__main__":
    main()