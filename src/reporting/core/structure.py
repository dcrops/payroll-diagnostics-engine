from dataclasses import dataclass
from typing import Callable, List


@dataclass
class SectionSpec:
    title: str
    level: int  # 1 = ##, 2 = ###
    render: Callable[[], str]


class ReportStructure:
    def __init__(self):
        self._sections: List[SectionSpec] = []

    def add(self, title: str, level: int, render: Callable[[], str]):
        self._sections.append(SectionSpec(title, level, render))

    def render_markdown(self) -> str:
        lines: List[str] = []

        section_no = 0
        subsection_no = 0

        for s in self._sections:
            if s.level == 1:
                section_no += 1
                subsection_no = 0
                heading = f"## {section_no}. {s.title}"
            else:
                subsection_no += 1
                heading = f"### {section_no}.{subsection_no} {s.title}"

            lines.append(heading)
            lines.append("")
            lines.append(s.render())
            lines.append("")

        return "\n".join(lines)