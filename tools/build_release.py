"""Build from an allowlisted, clean staging tree, never the live project folder."""
import argparse
import hashlib
import json
from importlib.metadata import distribution
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STATIC_EXTENSIONS = {'.html', '.css', '.js', '.svg'}


def stage_sources(destination):
    destination = Path(destination)
    if (ROOT/'app').is_symlink() or (ROOT/'app'/'static').is_symlink():
        raise ValueError('Symlinked source directories are not release inputs')
    (destination / 'app' / 'static').mkdir(parents=True)
    for source in sorted((ROOT / 'app').glob('*.py')):
        if source.is_symlink():
            raise ValueError('Symlinked source files are not release inputs')
        shutil.copyfile(source, destination / 'app' / source.name)
    for source in sorted((ROOT / 'app' / 'static').iterdir()):
        if source.is_symlink() or not source.is_file() or source.suffix not in STATIC_EXTENSIONS:
            raise ValueError('Unexpected static asset; review the release allowlist')
        shutil.copyfile(source, destination / 'app' / 'static' / source.name)
    example = json.loads((ROOT / 'config.example.json').read_text())
    if example['local_user'] != 'owner' or any(
        peer['owner'] != 'owner' or peer.get('grants') or any(
            target.get('enabled', True) or target['host'] not in {'192.0.2.10','192.0.2.11','1.1.1.1','8.8.8.8'}
            for target in peer['targets']) for peer in example['peers']):
        raise ValueError('Release defaults must contain only generic, disabled examples')
    (destination / 'config.example.json').write_text(json.dumps(example, indent=2)+'\n')
    (destination / 'run_app.py').write_text('from app.launch import main\n\nif __name__ == "__main__":\n    main()\n')


def write_notices(stage):
    parts = ['Ping_A_Friend: third-party notices', 'Python: ' + sys.copyright,
             'Python license: https://docs.python.org/3/license.html']
    python_license = Path('/usr/share/doc/python3.12/copyright')
    if python_license.is_file():
        parts.append(python_license.read_text())
    packages = [line.split('==')[0] for line in (ROOT/'requirements.lock').read_text().splitlines() if '==' in line]
    for name in packages + ['pyinstaller']:
        dist = distribution(name)
        parts.append(f'\n{name} {dist.version}')
        for file in dist.files or []:
            if any(word in file.name.upper() for word in ('LICENSE','COPYING','NOTICE')):
                try: parts.append(dist.locate_file(file).read_text())
                except (OSError, UnicodeError): pass
    (stage/'THIRD_PARTY_NOTICES.txt').write_text('\n\n'.join(parts)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'dist')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    tag = f'{platform.system().lower()}-{platform.machine().lower()}'
    name = 'Ping_A_Friend-' + tag
    with tempfile.TemporaryDirectory(prefix='paf-build-') as temporary:
        stage = Path(temporary)
        stage_sources(stage)
        write_notices(stage)
        command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
                   '--name', name, '--distpath', str(stage/'dist'), '--workpath', str(stage/'work'),
                   '--specpath', str(stage), '--paths', str(stage),
                   '--add-data', f'{stage / "app" / "static"}{os.pathsep}app/static',
                   '--add-data', f'{stage / "config.example.json"}{os.pathsep}.',
                   '--add-data', f'{stage / "THIRD_PARTY_NOTICES.txt"}{os.pathsep}.',
                   '--hidden-import', 'app.main', '--hidden-import', 'uvicorn.loops.asyncio',
                   '--hidden-import', 'uvicorn.protocols.http.h11_impl', '--hidden-import', 'uvicorn.lifespan.on',
                   '--exclude-module', 'pytest', '--exclude-module', 'pip', '--exclude-module', 'setuptools',
                   str(stage/'run_app.py')]
        # Build logs are sanitized before being written into the project.
        env = os.environ.copy()
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONSTARTUP', None)
        env['PYINSTALLER_CONFIG_DIR'] = str(stage/'cache')
        result = subprocess.run(command, cwd=stage, env=env, capture_output=True, text=True)
        log = (result.stdout + result.stderr).replace(str(ROOT), '[PROJECT]').replace(str(Path.home()), '[USER_HOME]').replace(str(stage), '[BUILD_STAGE]')
        log_dir = ROOT/'build'
        log_dir.mkdir(exist_ok=True)
        (log_dir/'build.log').write_text(log)
        if result.returncode:
            raise SystemExit('Build failed; see build/build.log (host paths sanitized)')
        suffix = '.exe' if sys.platform == 'win32' else ''
        from audit_release import audit_binary
        candidate = stage/'dist'/(name+suffix)
        report = audit_binary(candidate, ROOT)
        if not report['passed']:
            raise SystemExit('Release privacy audit failed; candidate not published')
        binary = output / (name + suffix)
        shutil.copyfile(candidate, binary)
        binary.chmod(0o755)
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    (output/(name+'.sha256')).write_text(f'{digest}  {binary.name}\n')
    archive = output/(name+'.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        bundle.write(binary, binary.name)
    report.update(binary=binary.name, bytes=binary.stat().st_size, zip_bytes=archive.stat().st_size, sha256=digest,
                  architecture=platform.machine(), build_libc=' '.join(platform.libc_ver()),
                  private_data_bundled=False, signed=False)
    (output/(name+'.audit.json')).write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
