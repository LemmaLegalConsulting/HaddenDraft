"""Remove from site-packages what a running container never reads.

Cold start scales with image size -- both the registry pull and, by more than
it looks like it should, the container creation that follows it. This runs at
build time, once, and reports what it took so a silent no-op cannot masquerade
as a saving. An earlier attempt at this in shell did exactly that: the find
expression failed, a trailing `|| true` swallowed it, and the image came out
9MB smaller than the 50MB that was claimed for it.

What is deliberately left alone:

    babel/locale-data   docxcompose formats document properties through babel,
                        and which locales it reaches for is not knowable here.
    nltk                textstat imports it for readability checking.
    setuptools          textstat declares it as a runtime dependency.

Those three are the largest things in site-packages after Django, and every one
of them is load-bearing. There is no more to win here without dropping a
feature.
"""
from __future__ import annotations

import shutil
import site
import sys
from pathlib import Path


def megabytes(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1_048_576


def main() -> int:
    site_dir = Path(site.getsitepackages()[0])
    if not (site_dir / "django").is_dir():
        print(f"Refusing to slim: no django/ under {site_dir}", file=sys.stderr)
        return 1

    before = megabytes(site_dir)

    # Django ships translation catalogues for about a hundred languages.
    # LANGUAGE_CODE is en-us and a missing catalogue falls back to the source
    # string, so the rest are inert weight.
    languages = 0
    for locale_dir in (site_dir / "django").rglob("locale"):
        if not locale_dir.is_dir():
            continue
        for language in locale_dir.iterdir():
            if language.is_dir() and not language.name.startswith("en"):
                shutil.rmtree(language)
                languages += 1

    # Nothing installs packages into a running replica.
    removed = []
    for name in ("pip", "wheel"):
        target = site_dir / name
        if target.is_dir():
            shutil.rmtree(target)
            removed.append(name)
        for metadata in site_dir.glob(f"{name}-*.dist-info"):
            shutil.rmtree(metadata)

    after = megabytes(site_dir)
    print(
        f"Slimmed site-packages {before:.0f}MB -> {after:.0f}MB "
        f"({before - after:.0f}MB: {languages} locale directories"
        + (f", {', '.join(removed)}" if removed else "")
        + ")"
    )
    if before - after < 20:
        # The point of this file is the saving. If it stops finding one, the
        # dependency set has changed and this needs revisiting -- do not let it
        # quietly become a no-op that the Dockerfile still pays a layer for.
        print("Expected to remove at least 20MB; something has changed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
