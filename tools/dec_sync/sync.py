"""Merge official carrot-wip locally and validate before allowing a push."""
import json
import os
from pathlib import Path
import subprocess

UPSTREAM = 'https://github.com/ajouatom/openpilot.git'
BRANCH = 'carrotpilot-dec'
FEATURE_BASE = 'ec3451446723cd1da3680a0c49e50a1af20caec2'


def git(root, *args):
  return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def validate(root):
  # Test files must be present; missing or incompatible integration is a failure.
  for path in ('openpilot/selfdrive/controls/tests/test_carrot_dec.py',
               'openpilot/selfdrive/modeld/tests/test_parked_switch.py',
               'openpilot/selfdrive/modeld/tests/test_parked_switch_config.py'):
    subprocess.run(['python3', path], cwd=root, check=True)
  subprocess.run(['python3', '-m', 'py_compile',
                  'openpilot/selfdrive/controls/lib/carrot_dec.py',
                  'openpilot/selfdrive/controls/lib/longitudinal_planner.py',
                  'openpilot/selfdrive/modeld/jetlink/daemon.py',
                  'openpilot/selfdrive/modeld/jetlink/mac.py',
                  'openpilot/selfdrive/modeld/jetlink/model.py',
                  'openpilot/selfdrive/modeld/jetlink/parked.py',
                  'openpilot/tools/jetlink/configure_parked_switch.py'], cwd=root, check=True)


def prepare(root, upstream=UPSTREAM, required=FEATURE_BASE, validator=validate):
  base = git(root, 'rev-parse', 'HEAD')
  git(root, 'merge-base', '--is-ancestor', required, base)
  if git(root, 'status', '--porcelain', '--untracked-files=no'):
    raise RuntimeError('Refusing to merge a dirty checkout')
  git(root, 'config', 'remote.dec-upstream.url', upstream)
  git(root, 'fetch', '--no-tags', '--filter=blob:none', 'dec-upstream',
      '+refs/heads/carrot-wip:refs/remotes/dec-upstream/carrot-wip')
  official = git(root, 'rev-parse', 'refs/remotes/dec-upstream/carrot-wip')
  # No force pushing, rebasing, or automatic conflict resolution.
  already = subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', official, base]).returncode == 0
  if already:
    return dict(ready=False, base=base, upstream=official, candidate=base)
  try:
    git(root, 'merge', '--no-ff', '--no-edit', official, '-m',
        'Sync official carrot-wip into carrotpilot-dec\n\n'
        'Keep DEC and parked-switch integration; focused checks gate publication.\n\n'
        'Docs-Not-Needed: upstream synchronization without new downstream settings.')
  except subprocess.CalledProcessError:
    subprocess.run(['git', '-C', str(root), 'merge', '--abort'], check=False)
    raise
  # Never allow upstream edits to silently weaken/remove the downstream tests.
  protected = ('openpilot/selfdrive/controls/tests/test_carrot_dec.py',
               'openpilot/selfdrive/modeld/tests/test_parked_switch.py',
               'openpilot/selfdrive/modeld/tests/test_parked_switch_config.py')
  if git(root, 'diff', '--name-only', base, 'HEAD', '--', *protected):
    raise RuntimeError('Downstream tests changed during merge; manual review required')
  validator(root)
  candidate = git(root, 'rev-parse', 'HEAD')
  if git(root, 'status', '--porcelain', '--untracked-files=no'):
    raise RuntimeError('Validation modified tracked files; refusing publication')
  return dict(ready=True, base=base, upstream=official, candidate=candidate)


if __name__ == '__main__':
  result = prepare(Path.cwd())
  print(json.dumps(result))
  if os.environ.get('GITHUB_OUTPUT'):
    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
      for key, value in result.items():
        f.write(f'{key}={str(value).lower() if isinstance(value, bool) else value}\n')
  if os.environ.get('GITHUB_STEP_SUMMARY'):
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
      f.write(f"## Carrot DEC upstream sync\n\nOfficial: `{result['upstream']}`\n\n"
              f"Candidate: `{result['candidate']}`\n\n"
              f"{'Focused checks passed; ready to publish.' if result['ready'] else 'Already up to date; no push needed.'}\n")
