"""Build and verify the activation-free Windows portable application.

python build_exe.py
python build_exe.py --output-dir ../dist/RootArchitecture_NoKey_V1.0.0
Keep the complete RootArchitecture folder, including _internal.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from app_version import APP_VERSION

ROOT = Path(__file__).resolve().parent


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(args, log, timeout=None):
    env = os.environ.copy()
    # Qt's Windows offscreen plugin otherwise starts with an empty font database.
    # This affects headless checks, not the normal desktop application's fonts.
    font_dir = Path(env.get('WINDIR', 'C:/Windows')) / 'Fonts'
    if sys.platform == 'win32' and font_dir.is_dir():
        env.setdefault('QT_QPA_FONTDIR', str(font_dir))
    with log.open('w', encoding='utf-8') as stream:
        subprocess.run([str(a) for a in args], cwd=ROOT, check=True,
                       stdout=stream, stderr=subprocess.STDOUT, timeout=timeout, env=env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist')
    parser.add_argument('--work-dir', type=Path, default=ROOT / 'build')
    parser.add_argument('--verify-existing', action='store_true',
                        help='recheck a previously built matching portable folder')
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('Windows EXE must be built on Windows; use Python GUI/CLI on macOS.')
    if (ROOT / 'license_manager.py').exists() or (ROOT / 'keys').exists():
        raise RuntimeError('Unexpected activation files in the source release')
    output = args.output_dir.resolve()
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    stage = args.work_dir.resolve() / ('no-key-' + stamp)
    stage.mkdir(parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=True)
    target = output / 'RootArchitecture'
    if target.exists() and not args.verify_existing:
        raise FileExistsError(f'{target} already exists; choose a new output directory.')
    source_files = sorted(ROOT.glob('*.py')) + [ROOT / 'RootArchitecture.spec']
    fingerprints = {p.name: sha256(p) for p in source_files}
    if args.verify_existing:
        app = target
        previous = json.loads((app / 'SOURCE_SHA256.json').read_text())
        # The build driver itself is not part of the frozen application.
        for name, digest in fingerprints.items():
            if name != 'build_exe.py' and previous.get(name) != digest:
                raise RuntimeError('Existing application has different source: ' + name)
    else:
        print('Building Windows application; logs: ' + str(stage), flush=True)
        run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
             '--distpath', stage / 'dist', '--workpath', stage / 'work',
             ROOT / 'RootArchitecture.spec'], stage / 'build.log')
        app = stage / 'dist' / 'RootArchitecture'
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(app / 'RootArchitecture.exe'))
    pure = archive.open_embedded_archive('PYZ.pyz')
    if any('license_manager' in name for name in pure.toc):
        raise RuntimeError('Unexpected activation module in executable')
    print('Checking calculations, parallel workers and normal GUI startup...', flush=True)
    run([app / 'RootArchitecture.exe', '--self-test', stage / 'self-test'],
        stage / 'self-test.log', timeout=600)
    run([app / 'RootArchitecture.exe', '--smoke-test', stage / 'startup'],
        stage / 'startup.log', timeout=240)
    checks = json.loads((stage / 'self-test' / 'self-test.json').read_text())
    startup = json.loads((stage / 'startup' / 'startup.json').read_text())
    assert checks['frozen'] and startup['frozen'] and startup['main_window_created']
    assert checks['activation_required'] is False and startup['activation_required'] is False
    assert startup['root_model_default'] == 'general'
    for path in source_files:
        if sha256(path) != fingerprints[path.name]:
            raise RuntimeError('Source changed during build: ' + path.name)
    for name in ['README.md', 'LICENSE.md', 'LICENSE-DOCS.md']:
        shutil.copy2(ROOT / name, app / name)
    (app / 'docs').mkdir(exist_ok=True)
    for name in ['USER_GUIDE.md', 'THIRD_PARTY_NOTICES.md']:
        shutil.copy2(ROOT / 'docs' / name, app / 'docs' / name)
    (app / 'START_HERE.txt').write_text(
        f'Root Architecture V{APP_VERSION}\n\n'
        'Windows: double-click RootArchitecture.exe. No activation code is required.\n'
        'Keep the entire directory including _internal.\n'
        'Manual: docs/USER_GUIDE.md.\n'
        'macOS: use the separate source distribution and Python GUI/CLI.\n'
        'No reliable image calibration => pixel units; inspect quality flags.\n', encoding='utf-8')
    (app / 'SOURCE_SHA256.json').write_text(json.dumps(fingerprints, indent=2), encoding='utf-8')
    # Preserve the staging copy. Directory renames/deletions can fail under
    # OneDrive even after every executable check has passed.
    if app != target:
        shutil.copytree(app, target)
    report = {'version': APP_VERSION, 'distribution': 'activation-free',
              'built_at_utc': datetime.now(timezone.utc).isoformat(),
              'platform': sys.platform, 'python': sys.version,
              'runtime_checks': checks, 'normal_startup': startup,
              'activation_module_in_archive': False,
              'exe_sha256': sha256(target / 'RootArchitecture.exe'),
              'source_sha256': fingerprints}
    (output / 'release-manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    for name, folder in [('runtime-preview.png', 'self-test'), ('main-window.png', 'startup')]:
        shutil.copy2(stage / folder / name, output / name)
    print('Verified portable application: ' + str(target), flush=True)


if __name__ == '__main__':
    main()
