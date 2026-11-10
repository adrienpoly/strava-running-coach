#!/usr/bin/env python3
"""Build the two installable artefacts in dist/ from SKILL.md and scripts/runcoach.py.

    dist/strava-running-coach.zip   the skill folder, ready to upload in the Claude apps
    dist/SKILL.md                   the whole skill in one file, with the script embedded,
                                    for install paths that take a single SKILL.md

    python3 tools/build_dist.py           # write both
    python3 tools/build_dist.py --check   # exit 1 if either is out of date

Both are generated: edit SKILL.md and scripts/runcoach.py, never the files in dist/.
"""
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "strava-running-coach"
BEGIN, END = "<!-- script:begin -->\n", "<!-- script:end -->\n"
GET_SCRIPT = '''Get the script once per conversation. If you were given this skill's directory, extract it; otherwise write the block at the end of this file to `runcoach.py` exactly as it is.

```bash
sed -n '/^```python$/,/^```$/p' "<skill directory>/SKILL.md" | sed '1d;$d' > runcoach.py
```
'''


def single_file():
    skill = (ROOT / "SKILL.md").read_text()
    script = (ROOT / "scripts" / "runcoach.py").read_text().rstrip("\n")
    head, rest = skill.split(BEGIN)
    _, tail = rest.split(END)
    if "```" in script:
        sys.exit("scripts/runcoach.py must not contain a code fence")
    return f"{head}{GET_SCRIPT}{tail}\n## The script\n\n```python\n{script}\n```\n"


def zip_members():
    return {f"{NAME}/SKILL.md": (ROOT / "SKILL.md").read_bytes(),
            f"{NAME}/scripts/runcoach.py": (ROOT / "scripts" / "runcoach.py").read_bytes()}


def write_zip(path):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in zip_members().items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o644 << 16
            z.writestr(info, data)


def zip_is_current(path):
    if not path.exists():
        return False
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()} == zip_members()


if __name__ == "__main__":
    dist = ROOT / "dist"
    md, archive = dist / "SKILL.md", dist / f"{NAME}.zip"
    if "--check" in sys.argv:
        stale = [p.name for p, ok in ((md, md.exists() and md.read_text() == single_file()), (archive, zip_is_current(archive))) if not ok]
        if stale:
            sys.exit(f"out of date: {', '.join(stale)} (run python3 tools/build_dist.py)")
        print("dist/ is up to date")
    else:
        dist.mkdir(exist_ok=True)
        md.write_text(single_file())
        write_zip(archive)
        print(f"wrote dist/SKILL.md ({md.read_text().count(chr(10))} lines) and dist/{NAME}.zip ({archive.stat().st_size} bytes)")
