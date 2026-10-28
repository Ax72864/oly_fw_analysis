#!/usr/bin/env python3
"""Build the pinned GNU MN103 core and offline harness locally (no network).

For a fresh checkout, supply --archive with the upstream tar.gz named in
EMULATOR.md. Subsequent builds reuse the source tree and build dependencies.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'toolchains/mn103-gnu-src'
BUILD = ROOT / 'toolchains/mn103-gnu-build'
REVISION = '87ffb882e0f4d73401a0746177ffabb8e8bbe4ac'
# Exact googlesource +archive bytes have drifted across mirrors/repacks. Accept the
# historically documented digest and the 2026-10-28 download after verifying the
# two pristine MN103 sources that prepare_mn103_sim.py pins.
ARCHIVE_SHA256_ACCEPTED = {
    'a5e7cd02f844bb2873c25e0ac8e9a5b50a72c3e8e6570a6b7821d2e4c21178ad',
    'c9506ffb995ce66f1a1332928732913f03e29d1dcfa604d208b5a62021639e1c',
}
PRISTINE_SHA256 = {
    'sim/mn10300/interp.c': 'f6c34c6c81ff67bda52d6b57d0ea47954587e36908923cd7e4e59a90424cd37b',
    'sim/mn10300/mn10300.igen': '355754c61879dc24bf6128bbba5a7931355731000e8cb213082b9b9cd4df0129',
}
CONFIGURE = ['--target=mn10300-elf', '--disable-gdb', '--disable-gdbserver',
             '--disable-binutils', '--disable-gas', '--disable-ld', '--disable-gprof',
             '--disable-gprofng', '--disable-nls', '--disable-werror',
             '--without-debuginfod', '--enable-sim', '--disable-sim-hardware']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, log, cwd=BUILD):
    print('Running:', ' '.join(map(str, args)), flush=True)
    with log.open('w') as out:
        proc = subprocess.run(args, cwd=cwd, stdout=out, stderr=subprocess.STDOUT)
    if proc.returncode:
        print('\n'.join(log.read_text(errors='replace').splitlines()[-35:]))
        raise SystemExit(f'Build failed; see {log}')


def verify_pristine_tree(root):
    for relative, digest in PRISTINE_SHA256.items():
        path = root / relative
        if sha(path) != digest:
            raise SystemExit(f'Unexpected pristine source: {relative}')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path)
    p.add_argument('--jobs', type=int, default=4)
    args = p.parse_args()
    if not (SRC / '.penf-source.json').is_file():
        if not args.archive:
            p.error('A fresh build requires --archive with a pinned upstream tar.gz')
        archive_digest = sha(args.archive)
        if archive_digest not in ARCHIVE_SHA256_ACCEPTED:
            p.error('Unexpected archive SHA-256; see docs/tooling/EMULATOR.md')
        SRC.mkdir(parents=True, exist_ok=True)
        with tarfile.open(args.archive) as archive:
            archive.extractall(SRC, filter='data')
        verify_pristine_tree(SRC)
        (SRC / '.penf-source.json').write_text(json.dumps({
            'revision': REVISION,
            'archive_sha256': archive_digest,
            'accepted_archive_sha256': sorted(ARCHIVE_SHA256_ACCEPTED),
            'pristine_source_sha256': PRISTINE_SHA256,
        }, indent=2) + '\n')
    source = json.loads((SRC / '.penf-source.json').read_text())
    if source['revision'] != REVISION or source['archive_sha256'] not in ARCHIVE_SHA256_ACCEPTED:
        p.error('Unexpected source provenance')
    # prepare_mn103_sim.py re-checks pristine digests via .penf-pristine after the first patch.
    subprocess.run([sys.executable, str(ROOT / 'tools/prepare_mn103_sim.py')], check=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    if not (BUILD / 'Makefile').is_file():
        run([str(SRC / 'configure'), *CONFIGURE], BUILD / 'configure.log')
    run(['make', f'-j{args.jobs}', 'all-sim', 'MAKEINFO=true'], BUILD / 'build.log')
    # Reuse exactly the simulator's include paths and dependency/link settings.
    makefile = BUILD / 'sim/penf-harness.mk'
    makefile.write_text('''mn10300/penf_runner.o: ../../../tools/mn103_runner.c
\t$(COMPILE) -c -o $@ $<

../penf-mn103: mn10300/penf_runner.o mn10300/libsim.a $(SIM_COMMON_LIBS)
\t$(LINK) mn10300/penf_runner.o mn10300/libsim.a $(SIM_COMMON_LIBS) $(LIBS)
''')
    run(['make', '-f', 'Makefile', '-f', makefile.name, '../penf-mn103', 'V=1'],
        BUILD / 'harness-build.log', BUILD / 'sim')
    files = ['tools/mn103_runner.c', 'tools/prepare_mn103_sim.py', 'tools/mn103_strict.patch',
             'toolchains/mn103-gnu-src/sim/mn10300/interp.c',
             'toolchains/mn103-gnu-src/sim/mn10300/mn10300.igen',
             'toolchains/mn103-gnu-build/penf-mn103']
    (BUILD / 'penf-build.json').write_text(json.dumps({'upstream': source, 'configure': CONFIGURE,
                                                    'sha256': {p: sha(ROOT / p) for p in files}}, indent=2)+'\n')
    print('Built:', BUILD / 'penf-mn103')


if __name__ == '__main__':
    main()
