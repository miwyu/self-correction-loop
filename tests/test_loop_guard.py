from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

GUARD = Path(__file__).resolve().parents[1] / 'self-correction-loop/scripts/loop_guard.py'
RUBRIC = '''# RUBRIC

## Goal
code.txt exists and is not empty

## Protected files
- test.txt

## Criteria
### C1: exists
CHECK: {check}
{expect}
### C2: readable
MANUAL: Is code.txt readable?
'''
BASELINE = '# EXPERIMENTS\n\n## Baseline\nCOMMAND: x\nRESULT: fail\n'
ITER = '\n## Iteration {n}\nCHANGE: c\nWHY: w\nRESULT: r\nDECISION: keep\n'
VERDICT = 'GUARDS: PASS - ok\nC1: PASS - ok\nC2: PASS - ok\nOVERALL: PASS\n'


def git(ws, *args):
    subprocess.run(['git', '-C', str(ws), '-c', 'user.name=t', '-c', 'user.email=t@example.invalid',
                    *args], check=True, capture_output=True)


class Guard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='loop guard ')
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name) / 'ws'
        self.ws.mkdir()
        (self.ws / 'code.txt').write_text('v1\n')
        (self.ws / 'test.txt').write_text('strict\n')
        self.ask = Path(self.tmp.name) / 'ask.txt'
        self.ask.write_text('Make code.txt non-empty. Do not modify test.txt.\n')
        self.run_dir = None

    def commit(self):
        git(self.ws, 'init', '-q')
        git(self.ws, 'add', '.')
        git(self.ws, 'commit', '-qm', 'base')

    def guard(self, *args, ok=True, code=None, env=None):
        r = subprocess.run([sys.executable, str(GUARD), *map(str, args)], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, (0 if ok else 1) if code is None else code, r.stdout + r.stderr)
        return r

    def start(self, check='test -s code.txt', expect='', freeze=True):
        out = self.guard('init', self.ws, 'demo', '--request-file', self.ask).stdout
        self.run_dir = Path(out.strip().splitlines()[0])
        (self.run_dir / 'RUBRIC.md').write_text(RUBRIC.format(check=check, expect=expect))
        (self.run_dir / 'EXPERIMENTS.md').write_text(BASELINE + ITER.format(n=1))
        if freeze:
            line = self.guard('freeze', self.run_dir).stdout.strip().splitlines()[-1]
            self.digest = line.rsplit('digest=', 1)[1]

    def frozen(self):
        return json.loads((self.run_dir / 'FREEZE.json').read_text())

    def rewrite_freeze_for_gamed_guard(self, anchor=None):
        data = self.frozen()
        data['protected']['test.txt'] = hashlib.sha256((self.ws / 'test.txt').read_bytes()).hexdigest()
        if anchor is not None:
            data['anchors']['test.txt'] = anchor
        (self.run_dir / 'FREEZE.json').write_text(json.dumps(data, indent=2))

    def test_testcase_run_method_is_not_shadowed(self):
        self.assertTrue(callable(getattr(self, 'run')))

    # --- layout and freeze -------------------------------------------------
    def test_init_creates_unique_run_with_request(self):
        self.start(freeze=False)
        self.assertEqual(self.run_dir.parent, self.ws.resolve() / '.loop')
        self.assertEqual((self.run_dir / 'REQUEST.md').read_text(), self.ask.read_text())
        second = self.guard('init', self.ws, 'demo', '--request-file', self.ask).stdout.strip().splitlines()[0]
        self.assertNotEqual(second, str(self.run_dir))

    def test_freeze_refuses_second_freeze(self):
        self.start()
        self.guard('freeze', self.run_dir, code=2)

    def test_freeze_digest_is_16_hex_and_not_stored(self):
        self.start()
        self.assertRegex(self.digest, r'^[0-9a-f]{16}$')
        self.assertEqual(self.digest, hashlib.sha256((self.run_dir / 'FREEZE.json').read_bytes()).hexdigest()[:16])
        self.assertNotIn(self.digest, (self.run_dir / 'FREEZE.json').read_text())

    # --- the published holes ----------------------------------------------
    def test_rubric_edit_after_freeze_fails_guards(self):          # hole 1
        self.start()
        p = self.run_dir / 'RUBRIC.md'
        p.write_text(p.read_text().replace('test -s code.txt', 'true'))
        self.guard('guards', self.run_dir, ok=False)

    def test_protected_edit_fails_guards(self):
        self.start()
        (self.ws / 'test.txt').write_text('anything passes\n')
        self.guard('guards', self.run_dir, ok=False)

    def test_request_edit_fails_guards(self):
        self.start()
        (self.run_dir / 'REQUEST.md').write_text('Make code.txt non-empty.\n')
        self.guard('guards', self.run_dir, ok=False)

    def test_no_scripts_are_copied_into_the_workspace(self):       # hole 2
        self.start()
        self.assertEqual([p.name for p in self.ws.rglob('*.py')] + [p.name for p in self.ws.rglob('*.sh')], [])

    def test_iteration_without_result_fails_preflight(self):       # hole 3
        self.start()
        with (self.run_dir / 'EXPERIMENTS.md').open('a') as f:
            f.write('\n## Iteration 2\nCHANGE: c\nWHY: w\nDECISION: keep\n')
        r = self.guard('preflight', self.run_dir, ok=False)
        self.assertIn('Iteration 2', r.stdout)

    # --- holes that a freeze alone leaves open -------------------------------
    def test_committed_guard_is_git_anchored(self):
        self.commit()
        self.start()
        self.assertEqual(self.frozen()['anchors']['test.txt']['anchor'], 'git')

    def test_guard_gamed_before_freeze_is_disclosed(self):         # hole 4
        self.commit()
        (self.ws / 'test.txt').write_text('anything passes\n')
        self.start()
        r = self.guard('guards', self.run_dir)
        self.assertIn('GUARDS: NOTE - unanchored: test.txt (differs from HEAD)', r.stdout)

    def test_rewritten_freeze_cannot_pass_a_git_anchor(self):      # hole 5, inside git
        self.commit()
        self.start()
        (self.ws / 'test.txt').write_text('anything passes\n')
        self.rewrite_freeze_for_gamed_guard()
        r = self.guard('guards', self.run_dir, ok=False)
        self.assertIn('git anchor', r.stdout)

    def test_rewritten_freeze_fails_the_expected_digest(self):     # hole 5, outside git
        self.start()
        (self.ws / 'test.txt').write_text('anything passes\n')
        self.rewrite_freeze_for_gamed_guard()
        self.guard('guards', self.run_dir)                      # self-consistent records still pass alone
        r = self.guard('guards', self.run_dir, '--expect', self.digest, ok=False)
        self.assertIn('digest', r.stdout)

    def test_expected_digest_passes_when_untouched(self):
        self.start()
        self.guard('guards', self.run_dir, '--expect', self.digest)

    # --- checks ---------------------------------------------------------------
    def test_checks_run_without_a_shell(self):
        self.start(check='false || true')
        self.guard('checks', self.run_dir, ok=False)

    def test_expect_must_appear_in_output(self):
        self.start(check='cat code.txt', expect='EXPECT: v2')
        self.guard('checks', self.run_dir, ok=False)
        (self.ws / 'code.txt').write_text('v2\n')
        self.guard('checks', self.run_dir)

    def test_protected_path_with_spaces(self):
        (self.ws / 'my test.txt').write_text('x\n')
        out = self.guard('init', self.ws, 'spaces', '--request-file', self.ask).stdout
        run = Path(out.strip().splitlines()[0])
        (run / 'RUBRIC.md').write_text(RUBRIC.format(check='true', expect='').replace('- test.txt', '- my test.txt'))
        self.guard('freeze', run)
        self.guard('guards', run)

    # --- finish gate ----------------------------------------------------------
    def test_finish_pass_needs_a_saved_passing_verdict(self):
        self.start()
        self.guard('finish', self.run_dir, 'pass', '--expect', self.digest, ok=False)
        (self.run_dir / 'VERDICT-01.md').write_text(VERDICT.replace('OVERALL: PASS', 'OVERALL: FAIL'))
        self.guard('finish', self.run_dir, 'pass', '--expect', self.digest, ok=False)
        (self.run_dir / 'VERDICT-02.md').write_text(VERDICT)
        self.guard('finish', self.run_dir, 'pass', '--expect', self.digest)
        self.assertEqual(json.loads((self.run_dir / 'STATE.json').read_text())['status'], 'pass')

    def test_quoted_pass_in_the_middle_does_not_count(self):
        self.start()
        (self.run_dir / 'VERDICT-01.md').write_text('OVERALL: PASS\nC1: FAIL - x\nOVERALL: FAIL\n')
        self.guard('finish', self.run_dir, 'pass', '--expect', self.digest, ok=False)

    def test_finish_pass_refused_when_guards_fail_after_verdict(self):
        self.start()
        (self.run_dir / 'VERDICT-01.md').write_text(VERDICT)
        (self.ws / 'test.txt').write_text('anything passes\n')
        self.guard('finish', self.run_dir, 'pass', '--expect', self.digest, ok=False)

    def test_finish_stopped_needs_no_verdict(self):
        self.start()
        self.guard('finish', self.run_dir, 'stopped', 'budget')
        self.assertEqual(json.loads((self.run_dir / 'STATE.json').read_text())['status'], 'stopped')

    def test_finish_pass_requires_expected_digest(self):
        self.start()
        (self.run_dir / 'VERDICT-01.md').write_text(VERDICT)
        state = (self.run_dir / 'STATE.json').read_bytes()
        r = self.guard('finish', self.run_dir, 'pass', ok=False)
        self.assertIn('--expect', r.stdout)
        self.assertEqual((self.run_dir / 'STATE.json').read_bytes(), state)

    def test_finish_pass_refuses_wrong_digest(self):
        self.start()
        (self.run_dir / 'VERDICT-01.md').write_text(VERDICT)
        state = (self.run_dir / 'STATE.json').read_bytes()
        self.guard('finish', self.run_dir, 'pass', '--expect', '0' * 16, ok=False)
        self.assertEqual((self.run_dir / 'STATE.json').read_bytes(), state)

    def test_finish_pass_refuses_rewritten_freeze_and_downgraded_anchor(self):
        self.commit()
        self.start()
        (self.run_dir / 'VERDICT-01.md').write_text(VERDICT)
        state = (self.run_dir / 'STATE.json').read_bytes()
        (self.ws / 'test.txt').write_text('anything passes\n')
        self.rewrite_freeze_for_gamed_guard({'anchor': 'none', 'reason': 'no git commit'})
        self.guard('finish', self.run_dir, 'pass', '--expect', self.digest, ok=False)
        self.assertEqual((self.run_dir / 'STATE.json').read_bytes(), state)

    def test_guards_reject_incomplete_freeze(self):
        self.start()
        original = self.frozen()
        for missing in ('anchors', 'anchor entry', 'request_sha256'):
            with self.subTest(missing=missing):
                data = json.loads(json.dumps(original))
                if missing == 'anchor entry':
                    del data['anchors']['test.txt']
                else:
                    del data[missing]
                (self.run_dir / 'FREEZE.json').write_text(json.dumps(data))
                r = self.guard('guards', self.run_dir, ok=False)
                self.assertIn('FREEZE.json is incomplete', r.stdout)

    def test_iteration_with_empty_result_fails_preflight(self):
        self.start()
        with (self.run_dir / 'EXPERIMENTS.md').open('a') as f:
            f.write(ITER.format(n=2).replace('RESULT: r', 'RESULT:  \t'))
        r = self.guard('preflight', self.run_dir, ok=False)
        self.assertIn('Iteration 2: missing RESULT:', r.stdout)

    def assert_bad_rubric(self, text):
        self.start()
        (self.run_dir / 'RUBRIC.md').write_text(text)
        for command in ('checks', 'preflight', 'freeze'):
            with self.subTest(command=command):
                if command == 'freeze':
                    (self.run_dir / 'FREEZE.json').unlink()
                r = self.guard(command, self.run_dir, code=2)
                self.assertNotIn('Traceback', r.stderr)
                self.assertIn('RUBRIC.md', r.stdout)
                if command == 'freeze':
                    self.assertFalse((self.run_dir / 'FREEZE.json').exists())

    def test_rubric_rejects_duplicate_checks(self):
        self.assert_bad_rubric(RUBRIC.format(check='true', expect='CHECK: true'))

    def test_rubric_requires_exactly_one_check_or_manual(self):
        for replacement in ('CHECK: true\nMANUAL: inspect', '', 'CHECK:', 'MANUAL:'):
            with self.subTest(replacement=replacement):
                text = RUBRIC.format(check='true', expect='').replace('CHECK: true', replacement)
                self.assert_bad_rubric(text)

    def test_rubric_rejects_duplicate_sections(self):
        for section in ('Criteria', 'Goal', 'Protected files'):
            with self.subTest(section=section):
                self.assert_bad_rubric(RUBRIC.format(check='true', expect='') + '\n## ' + section + '\n')

    def test_rubric_rejects_duplicate_criterion_ids(self):
        self.assert_bad_rubric(RUBRIC.format(check='true', expect='').replace('### C2:', '### C1:'))

    def test_rubric_rejects_orphan_fields(self):
        for field in ('CHECK: true', 'EXPECT: output', 'MANUAL: inspect'):
            with self.subTest(field=field):
                text = RUBRIC.format(check='true', expect='').replace('## Criteria\n', '## Criteria\n' + field + '\n')
                self.assert_bad_rubric(text)

    def assert_format_error(self, command, *args):
        r = self.guard(command, self.run_dir, *args, code=2)
        self.assertNotIn('Traceback', r.stderr)
        lines = (r.stdout + r.stderr).splitlines()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(command.upper() + ':'))

    def test_checks_missing_rubric_is_format_error(self):
        self.start()
        (self.run_dir / 'RUBRIC.md').unlink()
        self.assert_format_error('checks')

    def test_bad_text_inputs_are_format_errors(self):
        cases = (('RUBRIC.md', 'checks'), ('RUBRIC.md', 'guards'), ('RUBRIC.md', 'preflight'),
                 ('EXPERIMENTS.md', 'preflight'), ('VERDICT-01.md', 'finish'))
        for name, command in cases:
            for mode in ('missing', 'directory', 'non-utf8'):
                if name.startswith('VERDICT') and mode == 'missing':
                    continue  # No saved verdict is a gate failure, not a malformed file.
                with self.subTest(name=name, command=command, mode=mode):
                    self.start()
                    p = self.run_dir / name
                    if p.exists():
                        p.unlink()
                    if mode == 'directory':
                        p.mkdir()
                    elif mode == 'non-utf8':
                        p.write_bytes(b'\xff')
                    args = ('pass', '--expect', self.digest) if command == 'finish' else ()
                    self.assert_format_error(command, *args)

    def test_guards_rejects_non_object_freeze(self):
        self.start()
        (self.run_dir / 'FREEZE.json').write_text('[]')
        self.assert_format_error('guards')

    def test_malformed_freeze_is_format_error(self):
        self.start()
        original = self.frozen()
        invalid = ['', '{', 'null', '42', '{}']
        for key, value in (('protected', []), ('anchors', []), ('rubric_sha256', []),
                           ('request_sha256', None), ('protected', {'test.txt': []}),
                           ('anchors', {'test.txt': []}),
                           ('anchors', {'test.txt': {'anchor': 'git'}})):
            data = dict(original)
            data[key] = value
            invalid.append(json.dumps(data))
        for key in ('protected', 'rubric_sha256'):
            data = dict(original)
            del data[key]
            invalid.append(json.dumps(data))
        for content in invalid:
            for command in ('guards', 'preflight'):
                with self.subTest(content=content, command=command):
                    (self.run_dir / 'FREEZE.json').write_text(content)
                    self.assert_format_error(command)

    def test_malformed_state_is_format_error(self):
        self.start()
        p = self.run_dir / 'STATE.json'
        original = json.loads(p.read_text())
        invalid = ['', '{', '[]', 'null', '42', '{}']
        for key in original:
            data = dict(original)
            del data[key]
            invalid.append(json.dumps(data))
            data = dict(original)
            data[key] = []
            invalid.append(json.dumps(data))
        for content in invalid:
            for command, args in (('finish', ('stopped',)), ('preflight', ())):
                with self.subTest(content=content, command=command):
                    p.write_text(content)
                    self.assert_format_error(command, *args)
                    self.assertEqual(p.read_text(), content)

    def test_invalid_check_timeout_falls_back(self):
        self.start()
        for value in ('not-a-number', '', '0', '-1'):
            with self.subTest(value=value):
                env = dict(os.environ, LOOP_CHECK_TIMEOUT=value)
                r = self.guard('checks', self.run_dir, env=env)
                self.assertNotIn('Traceback', r.stderr)

    def test_checks_reject_zero_criteria(self):
        self.start(freeze=False)
        (self.run_dir / 'RUBRIC.md').write_text('## Goal\nx\n## Protected files\n- (none)\n## Criteria\n')
        self.guard('checks', self.run_dir, code=2)

    def test_freeze_rejects_unsafe_protected_paths(self):
        outside = Path(self.tmp.name) / 'outside.txt'
        outside.write_text('outside\n')
        (self.ws / 'sub').mkdir()
        (self.ws / 'linked.txt').symlink_to(self.ws / 'test.txt')
        (self.ws / 'escape').symlink_to(Path(self.tmp.name), target_is_directory=True)
        paths = ('../outside.txt', str(self.ws / 'test.txt'), 'sub/../test.txt',
                 'linked.txt', 'escape/outside.txt')
        for path in paths:
            with self.subTest(path=path):
                self.start(freeze=False)
                rubric = RUBRIC.format(check='true', expect='').replace('- test.txt', '- ' + path)
                (self.run_dir / 'RUBRIC.md').write_text(rubric)
                self.guard('freeze', self.run_dir, code=2)
                self.assertFalse((self.run_dir / 'FREEZE.json').exists())

    def test_guards_rejects_protected_file_replaced_by_symlink(self):
        self.start()
        p = self.ws / 'test.txt'
        target = self.ws / 'copy.txt'
        target.write_bytes(p.read_bytes())
        p.unlink()
        p.symlink_to(target)
        self.guard('guards', self.run_dir, ok=False)

    def test_guards_rejects_unsafe_paths_in_rewritten_freeze(self):
        self.start()
        original = self.frozen()
        outside = Path(self.tmp.name) / 'outside.txt'
        outside.write_text('outside\n')
        (self.ws / 'sub').mkdir()
        (self.ws / 'escape').symlink_to(Path(self.tmp.name), target_is_directory=True)
        for path, target in (('../outside.txt', outside), (str(self.ws / 'test.txt'), self.ws / 'test.txt'),
                             ('sub/../test.txt', self.ws / 'test.txt'), ('escape/outside.txt', outside)):
            with self.subTest(path=path):
                data = dict(original)
                data['protected'] = {path: hashlib.sha256(target.read_bytes()).hexdigest()}
                data['anchors'] = {path: {'anchor': 'none', 'reason': 'no git commit'}}
                (self.run_dir / 'FREEZE.json').write_text(json.dumps(data))
                self.guard('guards', self.run_dir, ok=False)

    def test_complete_untouched_run_passes_preflight(self):
        self.start()
        r = self.guard('preflight', self.run_dir)
        self.assertIn('PREFLIGHT: ALL OK', r.stdout)

    def test_unknown_subcommand_returns_usage_error(self):
        self.guard('unknown', code=2)

    def test_git_helper_and_error_return_cleanup(self):
        source = GUARD.read_text()
        self.assertNotIn('def _git(', source)
        self.assertNotIn('and 0 or 2', source)

    def test_finish_accepts_decorated_last_line(self):
        for last in ('**OVERALL: PASS**', 'OVERALL: PASS.'):
            with self.subTest(last=last):
                self.start()
                (self.run_dir / 'VERDICT-01.md').write_text(VERDICT.replace('OVERALL: PASS', last) + '\n  \n')
                self.guard('finish', self.run_dir, 'pass', '--expect', self.digest, 'verified')
                state = json.loads((self.run_dir / 'STATE.json').read_text())
                self.assertEqual(state['status'], 'pass')
                self.assertEqual(state['note'], 'verified')

    def test_rubric_rejects_empty_alternative_or_repeated_manual(self):
        for fields in ('CHECK: true\nMANUAL:', 'CHECK:\nMANUAL: inspect',
                       'MANUAL: first\nMANUAL: second'):
            with self.subTest(fields=fields):
                self.assert_bad_rubric(RUBRIC.format(check='true', expect='').replace('CHECK: true', fields))

    def test_malformed_nested_state_is_format_error(self):
        self.commit()
        self.start()
        p = self.run_dir / 'STATE.json'
        original = json.loads(p.read_text())
        variants = []
        for key in original['git']:
            data = json.loads(json.dumps(original))
            del data['git'][key]
            variants.append(data)
            data = json.loads(json.dumps(original))
            data['git'][key] = 42
            variants.append(data)
        for key, value in (('finished_at', []), ('note', {}), ('verdicts', [42])):
            data = dict(original)
            data[key] = value
            variants.append(data)
        for data in variants:
            with self.subTest(data=data):
                p.write_text(json.dumps(data))
                self.assert_format_error('finish', 'stopped')

    def test_finish_usage_explains_expected_digest(self):
        self.start()
        r = self.guard('finish', self.run_dir, 'invalid', code=2)
        self.assertIn('pass --expect', r.stdout)


if __name__ == '__main__':
    unittest.main()
