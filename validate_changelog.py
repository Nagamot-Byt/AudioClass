"""validate_changelog.py — Validador de formato de CHANGELOG.md.

Verifica que el changelog siga el estandar Keep a Changelog (keepachangelog.com):
- Header principal "# Changelog"
- Secciones versionadas con formato "## [X.Y.Z] - YYYY-MM-DD"
- Subsecciones categorizadas (Added, Changed, Deprecated, Removed, Fixed, Security)
- Fechas en formato ISO 8601
- Al menos una entrada por version

Uso:
    python validate_changelog.py                    # valida todo
    python validate_changelog.py --version 9.1.11   # valida una version especifica
    python validate_changelog.py --check-latest     # valida solo la version mas reciente
"""

import re
import sys
from datetime import datetime
from pathlib import Path

CHANGELOG_PATH = Path(__file__).parent / "CHANGELOG.md"

VALID_CATEGORIES = {
    "Added",
    "Changed",
    "Deprecated",
    "Removed",
    "Fixed",
    "Security",
    "Improved",
    "Architecture",
    "Testing",
    "DevOps",
    "Type Safety",
}

VERSION_PATTERN = re.compile(r"^## \[(\d+\.\d+\.\d+)\] - (\d{4}-\d{2}-\d{2})$", re.MULTILINE)

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ChangelogError:
    def __init__(self, line: int, message: str, severity: str = "error"):
        self.line = line
        self.message = message
        self.severity = severity

    def __str__(self):
        return f"[{self.severity.upper()}] Line {self.line}: {self.message}"


def validate_changelog(filepath: Path = CHANGELOG_PATH) -> list[ChangelogError]:
    """Valida el formato completo del CHANGELOG.md.

    Returns:
        Lista de errores encontrados (vacia si todo esta OK).
    """
    errors = []

    if not filepath.exists():
        errors.append(ChangelogError(0, f"File not found: {filepath}"))
        return errors

    with open(filepath, encoding="utf-8") as f:
        content = f.read()
        lines = content.split("\n")

    # Check header
    if not lines or not lines[0].strip().startswith("# Changelog"):
        errors.append(ChangelogError(1, "Missing or incorrect header '# Changelog'"))

    # Find all version sections
    versions = []
    for i, line in enumerate(lines, 1):
        match = VERSION_PATTERN.match(line.strip())
        if match:
            version, date_str = match.groups()
            versions.append((i, version, date_str))

    if not versions:
        errors.append(ChangelogError(0, "No version sections found (## [X.Y.Z] - YYYY-MM-DD)"))
        return errors

    # Validate each version section
    seen_versions = set()
    for line_num, version, date_str in versions:
        # Check version format
        if version in seen_versions:
            errors.append(ChangelogError(line_num, f"Duplicate version: [{version}]"))
        seen_versions.add(version)

        # Check date format
        if not DATE_PATTERN.match(date_str):
            errors.append(ChangelogError(line_num, f"Invalid date format: '{date_str}' (expected YYYY-MM-DD)"))
        else:
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                errors.append(ChangelogError(line_num, f"Invalid date: '{date_str}'"))

        # Check that version has at least one category
        section_start = line_num
        section_end = len(lines)
        for j in range(line_num, len(lines)):
            if j > line_num and lines[j].strip().startswith("## ["):
                section_end = j
                break

        section_content = "\n".join(lines[section_start:section_end])
        has_category = any(f"### {cat}" in section_content for cat in VALID_CATEGORIES)
        if not has_category:
            errors.append(
                ChangelogError(
                    line_num,
                    f"Version [{version}] has no category sections "
                    f"(expected at least one of: {', '.join(sorted(VALID_CATEGORIES))})",
                    severity="warning",
                )
            )

        # Check that version has at least one bullet point
        has_bullet = bool(re.search(r"^- ", section_content, re.MULTILINE))
        if not has_bullet:
            errors.append(
                ChangelogError(
                    line_num,
                    f"Version [{version}] has no bullet points (entries start with '- ')",
                    severity="warning",
                )
            )

    # Check version ordering (newest first)
    version_tuples = []
    for _, ver, _ in versions:
        parts = ver.split(".")
        try:
            version_tuples.append(tuple(int(p) for p in parts))
        except ValueError:
            pass

    for i in range(len(version_tuples) - 1):
        if version_tuples[i] < version_tuples[i + 1]:
            errors.append(
                ChangelogError(
                    0,
                    f"Versions not in descending order: "
                    f"v{'.'.join(map(str, version_tuples[i]))} before "
                    f"v{'.'.join(map(str, version_tuples[i + 1]))}",
                    severity="warning",
                )
            )

    return errors


def validate_version(version: str, filepath: Path = CHANGELOG_PATH) -> list[ChangelogError]:
    """Valida que una version especifica exista y este bien formateada."""
    errors = []

    if not filepath.exists():
        errors.append(ChangelogError(0, f"File not found: {filepath}"))
        return errors

    with open(filepath, encoding="utf-8") as f:
        content = f.read()
        lines = content.split("\n")

    # Find the specific version
    found = False
    for i, line in enumerate(lines, 1):
        match = VERSION_PATTERN.match(line.strip())
        if match and match.group(1) == version:
            found = True
            # Validate this section
            section_end = len(lines)
            for j in range(i, len(lines)):
                if j > i and lines[j].strip().startswith("## ["):
                    section_end = j
                    break

            section = "\n".join(lines[i:section_end])

            # Check categories
            has_category = any(f"### {cat}" in section for cat in VALID_CATEGORIES)
            if not has_category:
                errors.append(ChangelogError(i, f"Version [{version}] has no category sections"))

            # Check bullets
            has_bullet = bool(re.search(r"^- ", section, re.MULTILINE))
            if not has_bullet:
                errors.append(ChangelogError(i, f"Version [{version}] has no entries"))
            break

    if not found:
        errors.append(ChangelogError(0, f"Version [{version}] not found in CHANGELOG.md"))

    return errors


def main():
    args = sys.argv[1:]
    filepath = CHANGELOG_PATH

    if "--file" in args:
        idx = args.index("--file")
        filepath = Path(args[idx + 1])

    if "--version" in args:
        idx = args.index("--version")
        version = args[idx + 1]
        errors = validate_version(version, filepath)
    else:
        errors = validate_changelog(filepath)

    if errors:
        for err in errors:
            print(err)
        severity_counts = {}
        for e in errors:
            severity_counts[e.severity] = severity_counts.get(e.severity, 0) + 1
        summary = ", ".join(f"{v} {k}" for k, v in severity_counts.items())
        print(f"\nValidation failed: {summary}")
        sys.exit(1)
    else:
        print(f"CHANGELOG.md validation passed ({filepath})")
        sys.exit(0)


if __name__ == "__main__":
    main()
