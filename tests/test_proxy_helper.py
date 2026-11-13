"""Exercise proxy publication with local stand-ins, without credentials or services."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


HELPER = Path(__file__).resolve().parents[1] / "examples/atlas-proxy.sh"
MOCK = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['PROXY_TEST_LOG'], 'a') as stream:
    stream.write(json.dumps({'name': name, 'args': args}) + '\n')
mode = os.environ.get('PROXY_TEST_MODE', '')
if name == 'voms-proxy-init':
    pathlib.Path(args[args.index('-out') + 1]).write_text('new dummy credential')
    sys.exit(17 if mode == 'init-fails' else 0)
if mode == 'info-fails':
    sys.exit(18)
if '-timeleft' in args:
    print(40000)
elif '-actimeleft' in args:
    print(0 if mode == 'expired-ac' else 39000)
'''


class ProxyHelperTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.root = Path(self.scratch.name)
        (self.root / '.globus').mkdir()
        for name in ('usercert.pem', 'userkey.pem'):
            (self.root / '.globus' / name).write_text('dummy fixture, not a credential')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for name in ('voms-proxy-init', 'voms-proxy-info'):
            path = self.bin / name
            path.write_text(MOCK)
            path.chmod(0o700)
        self.log = self.root / 'calls.jsonl'
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ('ATLAS_PROXY_DIR', 'X509_USER_PROXY', 'BASH_ENV')}
        self.env.update(HOME=str(self.root), PATH=f'{self.bin}:{os.environ["PATH"]}',
                        PROXY_TEST_LOG=str(self.log))

    def tearDown(self):
        # Only remove the exact private directories created by this test's helper.
        for call in self.calls():
            if call['name'] == 'voms-proxy-init':
                directory = Path(call['args'][call['args'].index('-out') + 1]).parent
                if directory.parent == Path('/tmp') and directory.name.startswith('atlas-proxy.'):
                    shutil.rmtree(directory, ignore_errors=True)
        self.scratch.cleanup()

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def shell(self, command, **variables):
        env = dict(self.env, **variables)
        return subprocess.run(['bash', '--noprofile', '--norc', '-c',
                               f'source {shlex.quote(str(HELPER))}\n{command}'],
                              env=env, text=True, capture_output=True)

    def test_source_only_has_no_side_effects(self):
        result = self.shell('declare -F atlas_proxy')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [])

    def test_new_proxy_uses_explicit_paths_and_private_permissions(self):
        result = self.shell('umask 022; atlas_proxy; status=$?; '
                            'printf "RESULT=%s|%s|%s|%s\\n" "$status" '
                            '"$ATLAS_PROXY_DIR" "$X509_USER_PROXY" "$(umask)"')
        self.assertEqual(result.returncode, 0, result.stderr)
        line = next(line for line in result.stdout.splitlines() if line.startswith('RESULT='))
        status, directory, proxy, mask = line.removeprefix('RESULT=').split('|')
        self.assertEqual(status, '0', result.stderr)
        self.assertEqual(proxy, f'{directory}/x509up')
        self.assertEqual(mask, '0022')
        self.assertEqual(Path(directory).stat().st_mode & 0o777, 0o700)
        self.assertEqual(Path(proxy).stat().st_mode & 0o777, 0o600)
        args = self.calls()[0]['args']
        self.assertEqual(args[args.index('-cert') + 1], str(self.root / '.globus/usercert.pem'))
        self.assertEqual(args[args.index('-key') + 1], str(self.root / '.globus/userkey.pem'))
        self.assertEqual(args[args.index('-valid') + 1], '12:00')
        self.assertNotEqual(args[args.index('-out') + 1], proxy)

    def test_failed_creation_removes_temporary_files_and_preserves_exports(self):
        for mode in ('init-fails', 'info-fails', 'expired-ac'):
            with self.subTest(mode=mode):
                result = self.shell('atlas_proxy; status=$?; '
                                    'printf "RESULT=%s|%s|%s\\n" "$status" '
                                    '"${ATLAS_PROXY_DIR-UNSET}" "$X509_USER_PROXY"',
                                    PROXY_TEST_MODE=mode, X509_USER_PROXY='/existing/other-proxy')
                self.assertIn('RESULT=1|UNSET|/existing/other-proxy', result.stdout)
                init = [c for c in self.calls() if c['name'] == 'voms-proxy-init'][-1]
                self.assertFalse(Path(init['args'][init['args'].index('-out') + 1]).parent.exists())

    def test_renewal_keeps_path_and_failed_renewal_keeps_existing_content(self):
        result = self.shell('atlas_proxy || exit; before=$X509_USER_PROXY; '
                            'printf old > "$before"; export PROXY_TEST_MODE=init-fails; '
                            'atlas_proxy; status=$?; '
                            '[[ $status == 1 && $X509_USER_PROXY == "$before" '
                            '&& $(cat "$before") == old ]] || exit 8; '
                            'unset PROXY_TEST_MODE; atlas_proxy || exit; '
                            '[[ $X509_USER_PROXY == "$before" ]]')
        self.assertEqual(result.returncode, 0, result.stderr)
        parents = {Path(c['args'][c['args'].index('-out') + 1]).parent
                   for c in self.calls() if c['name'] == 'voms-proxy-init'}
        self.assertEqual(len(parents), 1)

    def test_empty_proxy_variable_and_launcher_with_spaces(self):
        launcher = self.root / 'isolated launcher.sh'
        launcher.write_text('#!/bin/bash\nexec "$@"\n')
        launcher.chmod(0o700)
        result = self.shell(f'atlas_proxy 06:30 {shlex.quote(str(launcher))}', X509_USER_PROXY='')
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.calls()[0]['args']
        self.assertEqual(args[args.index('-valid') + 1], '06:30')

    def test_invalid_duration_and_unsafe_directory_fail_before_authentication(self):
        for duration in ('0:00', '12:60', 'bad'):
            with self.subTest(duration=duration):
                self.assertNotEqual(self.shell(f'atlas_proxy {duration}').returncode, 0)
        self.assertNotEqual(self.shell('atlas_proxy', ATLAS_PROXY_DIR=str(self.root)).returncode, 0)
        self.assertEqual(self.calls(), [])


if __name__ == '__main__':
    unittest.main()
