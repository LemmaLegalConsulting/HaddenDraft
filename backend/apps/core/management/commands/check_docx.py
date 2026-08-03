"""Structural checks for a generated DOCX, so "Word says it is damaged" is diagnosable.

Word's repair prompt names no cause, and the ECMA schema does not describe most
of what it objects to: a relationship that resolves to nothing, a part with no
content type, a header reference contradicting the section settings. Each of
those has cost a round trip to find by hand.

Passing here does not prove Word is happy -- Word enforces rules no public schema
states. It does prove the package is internally consistent, which is enough to
tell whether a problem was introduced here or inherited from the source file.
Run it against both to find out which.
"""

import posixpath
import re
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from lxml import etree


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
R_EMBED = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
PACKAGE_RELS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
CONTENT_TYPES = "{http://schemas.openxmlformats.org/package/2006/content-types}"
STORY_RE = re.compile(r"word/(header|footer)\d*\.xml$")


def _rels_for(part_name):
    return posixpath.join(
        posixpath.dirname(part_name), "_rels", posixpath.basename(part_name) + ".rels"
    )


def check_docx(path: Path) -> list[str]:
    """Return every internal inconsistency found, newest complaint first."""
    problems = []
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())

        # Content types: a part Word cannot type is a part it will not read.
        types = etree.fromstring(archive.read("[Content_Types].xml"))
        defaults = {node.get("Extension").lower() for node in types.findall(CONTENT_TYPES + "Default")}
        overrides = {node.get("PartName") for node in types.findall(CONTENT_TYPES + "Override")}
        for name in names:
            if name == "[Content_Types].xml" or f"/{name}" in overrides:
                continue
            basename = posixpath.basename(name)
            extension = basename.rsplit(".", 1)[-1].lower() if "." in basename else ""
            if extension not in defaults:
                problems.append(f"no content type for part: {name}")
        for part_name in overrides:
            if part_name.lstrip("/") not in names:
                problems.append(f"content type declares a missing part: {part_name}")

        # Relationships: targets must exist, and every r:id must resolve.
        for rels_name in [name for name in names if name.endswith(".rels")]:
            base = posixpath.dirname(posixpath.dirname(rels_name))
            for rel in etree.fromstring(archive.read(rels_name)).findall(PACKAGE_RELS + "Relationship"):
                if rel.get("TargetMode") == "External":
                    continue
                target = rel.get("Target", "")
                resolved = (
                    target.lstrip("/")
                    if target.startswith("/")
                    else posixpath.normpath(posixpath.join(base, target))
                )
                if resolved not in names:
                    problems.append(f"{rels_name}: relationship {rel.get('Id')} targets missing {target}")

        for part_name in [name for name in names if name.endswith(".xml")]:
            try:
                root = etree.fromstring(archive.read(part_name))
            except etree.XMLSyntaxError as error:
                problems.append(f"{part_name}: not well-formed XML: {error}")
                continue
            rels_name = _rels_for(part_name)
            declared = set()
            if rels_name in names:
                declared = {node.get("Id") for node in etree.fromstring(archive.read(rels_name))}
            used = {node.get(R_ID) for node in root.iter() if node.get(R_ID)}
            used |= {node.get(R_EMBED) for node in root.iter() if node.get(R_EMBED)}
            for missing in sorted(reference for reference in used if reference not in declared):
                problems.append(f"{part_name}: r:id {missing} resolves to no relationship")

        document = etree.fromstring(archive.read("word/document.xml"))
        body = document.find(W + "body")

        # sectPr must close the body, and its header references must agree with
        # the section settings: an even-page reference without
        # evenAndOddHeaders is a contradiction Word rejects.
        children = [etree.QName(child).localname for child in body]
        if "sectPr" in children and children.index("sectPr") != len(children) - 1:
            problems.append("word/document.xml: sectPr is not the last child of the body")

        settings = etree.fromstring(archive.read("word/settings.xml")) if "word/settings.xml" in names else None
        even_enabled = settings is not None and settings.find(W + "evenAndOddHeaders") is not None
        for section in document.iter(W + "sectPr"):
            title_page = section.find(W + "titlePg") is not None
            for reference in section:
                tag = etree.QName(reference).localname
                if tag not in {"headerReference", "footerReference"}:
                    continue
                kind = reference.get(W + "type")
                if kind == "even" and not even_enabled:
                    problems.append(f"{tag} type=even but evenAndOddHeaders is off")
                if kind == "first" and not title_page:
                    problems.append(f"{tag} type=first but titlePg is not set")

        # Styles, numbering, and bookmarks referenced but never defined.
        style_ids = set()
        if "word/styles.xml" in names:
            style_ids = {
                node.get(W + "styleId")
                for node in etree.fromstring(archive.read("word/styles.xml")).iter(W + "style")
            }
        num_ids = set()
        if "word/numbering.xml" in names:
            num_ids = {
                node.get(W + "numId")
                for node in etree.fromstring(archive.read("word/numbering.xml")).iter(W + "num")
            }
        for part_name in [name for name in names if name.startswith("word/") and name.endswith(".xml")]:
            root = etree.fromstring(archive.read(part_name))
            for node in list(root.iter(W + "pStyle")) + list(root.iter(W + "rStyle")):
                if node.get(W + "val") and node.get(W + "val") not in style_ids:
                    problems.append(f"{part_name}: style {node.get(W + 'val')} is not defined")
            for node in root.iter(W + "numPr"):
                num = node.find(W + "numId")
                value = num.get(W + "val") if num is not None else None
                if value and value != "0" and value not in num_ids:
                    problems.append(f"{part_name}: numId {value} is not defined")
            starts = [node.get(W + "id") for node in root.iter(W + "bookmarkStart")]
            ends = [node.get(W + "id") for node in root.iter(W + "bookmarkEnd")]
            if sorted(starts) != sorted(ends):
                problems.append(f"{part_name}: bookmarkStart and bookmarkEnd do not pair up")

    return problems


class Command(BaseCommand):
    help = "Check a .docx for the internal inconsistencies that make Word offer to repair it."

    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="+", help="One or more .docx files.")

    def handle(self, *args, **options):
        failures = 0
        for raw in options["paths"]:
            path = Path(raw).expanduser()
            if not path.is_file():
                raise CommandError(f"Not a file: {path}")
            problems = check_docx(path)
            if problems:
                failures += 1
                self.stdout.write(self.style.WARNING(f"{path.name}: {len(problems)} problem(s)"))
                for problem in problems:
                    self.stdout.write(f"    {problem}")
            else:
                self.stdout.write(self.style.SUCCESS(f"{path.name}: internally consistent"))

        self.stdout.write(
            "\nA clean result means the package is self-consistent. Word enforces rules "
            "no public schema states, so compare against the source file to tell whether "
            "a problem was introduced or inherited."
        )
        if failures:
            raise CommandError(f"{failures} file(s) had problems.")
