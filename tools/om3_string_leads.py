#!/usr/bin/env python3
"""Extract ASCII leads from the pinned OM-3 1100 main image (offline, read-only)."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from oly_container import sha256

BASE = 0x60021020
STOCK_MAIN = Path('analysis/om3_1100/00_0100_50000020.decoded.bin')
STOCK_MAIN_SHA = '5e8d376e9111a44ac0352f26030d7c1b17026d42c45f3600cfa02a0e8c5b7d59'
KEYWORDS = (
    b'shutter', b'silent', b'beep', b'sound', b'wav', b'audio', b'se_',
    b'power', b'on/off', b'onoff', b'dial', b'assign', b'lever', b'button',
    b'btn', b'custom', b'func', b'mode',
)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--main', type=Path, default=STOCK_MAIN)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    data = args.main.read_bytes()
    if sha256(data) != STOCK_MAIN_SHA:
        raise SystemExit(f'Unexpected main hash at {args.main}')
    hits = []
    for match in re.finditer(rb'[\x20-\x7e]{5,100}', data):
        text = match.group()
        low = text.lower()
        keys = [k.decode() for k in KEYWORDS if k in low]
        if not keys:
            continue
        hits.append({
            'analysis_address': hex(BASE + match.start()),
            'text': text.decode('ascii'),
            'keys': keys,
        })
    unique, seen = [], set()
    for row in hits:
        if row['text'] in seen:
            continue
        seen.add(row['text'])
        unique.append(row)
    args.out.mkdir(parents=True, exist_ok=False)
    report = {
        'main_sha256': STOCK_MAIN_SHA,
        'hit_count': len(hits),
        'unique_count': len(unique),
        'leads': unique,
        'scope': 'ASCII string leads only; not proof of call sites or UI wiring',
    }
    (args.out / 'leads.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'unique_count': len(unique), 'out': str(args.out / 'leads.json')}, indent=2))


if __name__ == '__main__':
    main()
