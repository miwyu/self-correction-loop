from pathlib import Path
import hashlib
import json
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
        self.run = None

    def commit(self):
        git(self.ws, 'init', '-q')
        git(self.ws, 'add', '.')
        git(self.ws, 'commit', '-qm', 'base')

    def guard(self, *args, ok=True):
        r = subprocess.run([sys.executable, str(GUARD), *map(str, args)], capture_output=True, text=True)
        (self.assertEqual if ok else self.assertNotEqual)(r.returncode, 0, r.stdout + r.stderr)
        return r

    def start(self, check='test -s code.txt', expect='', freeze=True):
        out = self.guard('init', self.ws, 'demo', '--request-file', self.ask).stdout
        self.run = Path(out.strip().splitlines()[0])
        (self.run / 'RUBRIC.md').write_text(RUBRIC.format(check=check, expect=expect))
        (self.run / 'EXPERIMENTS.md').write_text(BASELINE + ITER.format(n=1))
        if freeze:
            line = self.guard('freeze', self.run).stdout.strip().splitlines()[-1]
            self.digest = line.rsplit('digest=', 1)[1]

    def frozen(self):
        return json.loads((self.run / 'FREEZE.json').read_text())

    def rewrite_freeze_for_gamed_guard(self, anchor=None):
        data = self.frozen()
        data['protected']['test.txt'] = hashlib.sha256((self.ws / 'test.txt').read_bytes()).hexdigest()
        if anchor is not None:
            data['anchors']['test.txt'] = anchor
        (self.run / 'FREEZE.json').write_text(json.dumps(data, indent=2))

    # --- layout and freeze -------------------------------------------------
    def test_init_creates_unique_run_with_request(self):
        self.start(freeze=False)
        self.assertEqual(self.run.parent, self.ws.resolve() / '.loop')
        self.assertEqual((self.run / 'REQUEST.md').read_text(), self.ask.read_text())
        second = self.guard('init', self.ws, 'demo', '--request-file', self.ask).stdout.strip().splitlines()[0]
        self.assertNotEqual(second, str(self.run))

    def test_freeze_refuses_second_freeze(self):
        self.start()
        self.guard('freeze', self.run, ok=False)

    def test_freeze_digest_is_16_hex_and_not_stored(self):
        self.start()
        self.assertRegex(self.digest, r'^[0-9a-f]{16}$')
        self.assertNotIn(self.digest, (self.run / 'FREEZE.json').read_text())

    # --- the published holes ----------------------------------------------
    def test_rubric_edit_after_freeze_fails_guards(self):          # hole 1
        self.start()
        p = self.run / 'RUBRIC.md'
        p.write_text(p.read_text().replace('test -s code.txt', 'true'))
        self.guard('guards', self.run, ok=False)

    def test_protected_edit_fails_guards(self):
        self.start()
        (self.ws / 'test.txt').write_text('anything passes\n')
        self.guard('guards', self.run, ok=False)

    def test_request_edit_fails_guards(self):
        self.start()
        (self.run / 'REQUEST.md').write_text('Make code.txt non-empty.\n')
        self.guard('guards', self.run, ok=False)

    def test_no_scripts_are_copied_into_the_workspace(self):       # hole 2
        self.start()
        self.assertEqual([p.name for p in self.ws.rglob('*.py')] + [p.name for p in self.ws.rglob('*.sh')], [])

    def test_iteration_without_result_fails_preflight(self):       # hole 3
        self.start()
        with (self.run / 'EXPERIMENTS.md').open('a') as f:
            f.write('\n## Iteration 2\nCHANGE: c\nWHY: w\nDECISION: keep\n')
        r = self.guard('preflight', self.run, ok=False)
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
        r = self.guard('guards', self.run)
        self.assertIn('GUARDS: NOTE - unanchored: test.txt (differs from HEAD)', r.stdout)

    def test_rewritten_freeze_cannot_pass_a_git_anchor(self):      # hole 5, inside git
        self.commit()
        self.start()
        (self.ws / 'test.txt').write_text('anything passes\n')
        self.rewrite_freeze_for_gamed_guard()
        r = self.guard('guards', self.run, ok=False)
        self.assertIn('git anchor', r.stdout)

    def test_rewritten_freeze_fails_the_expected_digest(self):     # hole 5, outside git
        self.start()
        (self.ws / 'test.txt').write_text('anything passes\n')
        self.rewrite_freeze_for_gamed_guard()
        self.guard('guards', self.run)                      # self-consistent records still pass alone
        r = self.guard('guards', self.run, '--expect', self.digest, ok=False)
        self.assertIn('digest', r.stdout)

    def test_expected_digest_passes_when_untouched(self):
        self.start()
        self.guard('guards', self.run, '--expect', self.digest)

    # --- checks ---------------------------------------------------------------
    def test_checks_run_without_a_shell(self):
        self.start(check='false || true')
        self.guard('checks', self.run, ok=False)

    def test_expect_must_appear_in_output(self):
        self.start(check='cat code.txt', expect='EXPECT: v2')
        self.guard('checks', self.run, ok=False)
        (self.ws / 'code.txt').write_text('v2\n')
        self.guard('checks', self.run)

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
        self.guard('finish', self.run, 'pass', ok=False)
        (self.run / 'VERDICT-01.md').write_text(VERDICT.replace('OVERALL: PASS', 'OVERALL: FAIL'))
        self.guard('finish', self.run, 'pass', ok=False)
        (self.run / 'VERDICT-02.md').write_text(VERDICT)
        self.guard('finish', self.run, 'pass')
        self.assertEqual(json.loads((self.run / 'STATE.json').read_text())['status'], 'pass')

    def test_quoted_pass_in_the_middle_does_not_count(self):
        self.start()
        (self.run / 'VERDICT-01.md').write_text('OVERALL: PASS\nC1: FAIL - x\nOVERALL: FAIL\n')
        self.guard('finish', self.run, 'pass', ok=False)

    def test_finish_pass_refused_when_guards_fail_after_verdict(self):
        self.start()
        (self.run / 'VERDICT-01.md').write_text(VERDICT)
        (self.ws / 'test.txt').write_text('anything passes\n')
        self.guard('finish', self.run, 'pass', ok=False)

    def test_finish_stopped_needs_no_verdict(self):
        self.start()
        self.guard('finish', self.run, 'stopped', 'budget')
        self.assertEqual(json.loads((self.run / 'STATE.json').read_text())['status'], 'stopped')


if __name__ == '__main__':
    unittest.main()
