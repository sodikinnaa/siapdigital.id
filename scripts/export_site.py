#!/usr/bin/env python3
"""Ekspor situs kanonik ke clone repo publikasi dan verifikasi kesetaraan byte.

Pemakaian: python3 scripts/export_site.py /path/ke/clone/siapdigital.id
"""

import hashlib
import shutil
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__"}


def tree(root):
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts) or not p.is_file():
            continue
        out[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    dest = Path(argv[1]).resolve()
    if not (dest / ".git").is_dir():
        sys.exit(f"{dest} bukan clone git")
    if dest == SRC or SRC in dest.parents or dest in SRC.parents:
        sys.exit("tujuan tidak boleh tumpang tindih dengan sumber")

    src_files = tree(SRC)
    for rel in tree(dest):
        if rel not in src_files:
            (dest / rel).unlink()
    for rel in src_files:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SRC / rel, target)
    # Bersihkan direktori kosong yang tersisa.
    for d in sorted(dest.rglob("*"), reverse=True):
        if d.is_dir() and ".git" not in d.relative_to(dest).parts and not any(d.iterdir()):
            d.rmdir()

    dest_files = tree(dest)
    if dest_files != src_files:
        missing = set(src_files) - set(dest_files)
        extra = set(dest_files) - set(src_files)
        differ = {k for k in src_files.keys() & dest_files.keys() if src_files[k] != dest_files[k]}
        sys.exit(f"verifikasi gagal: hilang={missing} lebih={extra} beda={differ}")
    for rel, digest in src_files.items():
        print(f"{digest}  {rel}")
    print(f"OK: {len(src_files)} berkas identik byte-per-byte")


if __name__ == "__main__":
    main(sys.argv)
