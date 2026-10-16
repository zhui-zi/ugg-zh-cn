"""Apply a version-pinned U.GG UI localization patch."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

BUNDLE = Path(__file__).resolve().parent
BACKUP_NAME = 'app.asar.ugg-zh-cn.original'
STATE_NAME = 'ugg-zh-cn-state.json'
MAIN = 'build/electron/main.js'
HOOK = b'\n;require("./zh-cn.cjs");\n'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def unpack(data):
    if len(data) < 16 or struct.unpack_from('<I', data)[0] != 4:
        raise ValueError('Invalid ASAR archive.')
    header_size = struct.unpack_from('<I', data, 4)[0]
    json_size = struct.unpack_from('<I', data, 12)[0]
    if json_size > header_size - 8 or 8 + header_size > len(data):
        raise ValueError('Invalid ASAR header size.')
    header = json.loads(data[16:16 + json_size])
    return header, 8 + header_size


def entries(header):
    def walk(files, prefix=''):
        for name, entry in files.items():
            relative = prefix + name
            if 'files' in entry:
                yield from walk(entry['files'], relative + '/')
            else:
                yield relative, entry
    return walk(header['files'])


def packed_files(data, header, base):
    result = {}
    for name, entry in entries(header):
        if entry.get('unpacked') or 'link' in entry:
            continue
        offset = int(entry['offset'])
        size = entry['size']
        if offset < 0 or size < 0 or base + offset + size > len(data):
            raise ValueError('Invalid ASAR file bounds: ' + name)
        result[name] = data[base + offset:base + offset + size]
    return result


def integrity(data, block_size=4 * 1024 * 1024):
    return {
        'algorithm': 'SHA256',
        'hash': digest(data),
        'blockSize': block_size,
        'blocks': [digest(data[start:start + block_size]) for start in range(0, len(data), block_size)]
    }


def add_entry(header, name):
    parts = name.split('/')
    current = header['files']
    for part in parts[:-1]:
        current = current.setdefault(part, {'files': {}})['files']
    if parts[-1] in current:
        raise ValueError('Localization asset already exists: ' + name)
    current[parts[-1]] = {}


def bundle():
    manifest = json.loads((BUNDLE / 'manifest.json').read_text(encoding='utf-8'))
    payloads = {}
    for filename, expected in manifest['assets'].items():
        data = (BUNDLE / filename).read_bytes()
        if digest(data) != expected:
            raise ValueError('Patch asset checksum mismatch: ' + filename)
        payloads['build/electron/' + filename] = data
    return manifest, payloads


def build(original):
    manifest, payloads = bundle()
    if digest(original) != manifest['originalSha256']:
        raise ValueError('Unsupported app.asar. This patch requires the original U.GG 2.3.3 archive.')
    header, base = unpack(original)
    header = copy.deepcopy(header)
    files = packed_files(original, header, base)
    package = json.loads(files['package.json'])
    if package['name'] != 'U.GG' or package['version'] != manifest['appVersion']:
        raise ValueError('U.GG package version mismatch.')
    files[MAIN] += HOOK
    for name, data in payloads.items():
        add_entry(header, name)
        files[name] = data
    chunks = []
    offset = 0
    for name, entry in entries(header):
        if name not in files:
            continue
        data = files[name]
        entry['offset'] = str(offset)
        entry['size'] = len(data)
        if name == MAIN or name in payloads:
            block_size = entry.get('integrity', {}).get('blockSize', 4 * 1024 * 1024)
            entry['integrity'] = integrity(data, block_size)
        chunks.append(data)
        offset += len(data)
    encoded = json.dumps(header, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    payload = struct.pack('<I', len(encoded)) + encoded
    payload += b'\0' * ((-len(payload)) % 4)
    header_pickle = struct.pack('<I', len(payload)) + payload
    output = struct.pack('<II', 4, len(header_pickle)) + header_pickle + b''.join(chunks)
    verify(output)
    return output


def verify(data):
    header, base = unpack(data)
    files = packed_files(data, header, base)
    for name, entry in entries(header):
        if name not in files or 'integrity' not in entry:
            continue
        value = entry['integrity']
        if value['algorithm'] != 'SHA256' or integrity(files[name], value['blockSize']) != value:
            raise ValueError('ASAR integrity mismatch: ' + name)


def running():
    if os.name != 'nt':
        raise RuntimeError('Installation is supported on Windows only.')
    result = subprocess.run(
        ['tasklist.exe', '/FI', 'IMAGENAME eq U.GG.exe', '/FO', 'CSV', '/NH'],
        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, check=True
    )
    return b'u.gg.exe' in result.stdout.lower()


def ensure_stopped():
    if running():
        raise RuntimeError('U.GG is running. Exit U.GG from the system tray, then run this command again.')


def check_executable(target):
    executable = target.parent.parent / 'U.GG.exe'
    if not executable.is_file():
        raise ValueError('U.GG.exe was not found beside the resources directory.')
    data = executable.read_bytes()
    marker = b'dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX'
    start = data.find(marker)
    if start < 0:
        raise ValueError('Unable to read Electron package compatibility flags.')
    flags = data[start + len(marker):]
    if len(flags) < 7 or flags[0] != 1 or flags[1] < 5:
        raise ValueError('Unsupported Electron package flags.')
    if flags[2 + 4] != ord('0'):
        raise ValueError('This executable requires signed ASAR integrity. The patch cannot be installed.')


def atomic_write(path, data):
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install(target):
    ensure_stopped()
    check_executable(target)
    manifest, _ = bundle()
    original = target.read_bytes()
    state_path = target.parent / STATE_NAME
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding='utf-8'))
        if digest(original) == state['installedSha256']:
            if state.get('patchId') != manifest['patchId']:
                raise ValueError('A different localization patch is installed. Restore it first.')
            print('U.GG Simplified Chinese patch is already installed.')
            return
    modified = build(original)
    backup_path = target.parent / BACKUP_NAME
    if backup_path.exists():
        if digest(backup_path.read_bytes()) != manifest['originalSha256']:
            raise ValueError('An incompatible backup already exists. No files were replaced.')
    else:
        with backup_path.open('xb') as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
    state = {
        'patchId': manifest['patchId'],
        'appVersion': manifest['appVersion'],
        'originalSha256': digest(original),
        'installedSha256': digest(modified)
    }
    ensure_stopped()
    atomic_write(state_path, (json.dumps(state, indent=2) + '\n').encode('utf-8'))
    try:
        atomic_write(target, modified)
    except Exception:
        state_path.unlink(missing_ok=True)
        raise
    print('U.GG Simplified Chinese patch installed. Start U.GG normally.')


def restore(target):
    ensure_stopped()
    state_path = target.parent / STATE_NAME
    manifest, _ = bundle()
    if not state_path.exists():
        if digest(target.read_bytes()) == manifest['originalSha256']:
            print('The original U.GG archive is already installed.')
            return
        raise ValueError('Localization installation record was not found.')
    state = json.loads(state_path.read_text(encoding='utf-8'))
    backup = (target.parent / BACKUP_NAME).read_bytes()
    if digest(backup) != state['originalSha256'] or state['originalSha256'] != manifest['originalSha256']:
        raise ValueError('Backup checksum mismatch. No files were replaced.')
    current = digest(target.read_bytes())
    if current not in [state['installedSha256'], state['originalSha256']]:
        raise ValueError('U.GG has changed since installation. No files were replaced.')
    ensure_stopped()
    atomic_write(target, backup)
    state_path.unlink()
    print('Original U.GG archive restored.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'install', 'restore', 'build'])
    parser.add_argument('--target', type=Path, default=Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/U.GG/resources/app.asar')
    parser.add_argument('--output', type=Path)
    arguments = parser.parse_args()
    target = arguments.target.resolve()
    if arguments.command == 'install':
        install(target)
    elif arguments.command == 'restore':
        restore(target)
    elif arguments.command == 'check':
        check_executable(target)
        data = build(target.read_bytes())
        print('Compatible: U.GG 2.3.3; patch archive verified; ' + str(len(data)) + ' bytes.')
    else:
        if arguments.output is None:
            parser.error('--output is required for build')
        output = arguments.output.resolve()
        if output == target or output.exists():
            raise ValueError('Build output must be a new file separate from the source archive.')
        output.write_bytes(build(target.read_bytes()))
        print('Patch archive built and verified: ' + str(output))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Error: ' + str(error), file=sys.stderr)
        sys.exit(1)
