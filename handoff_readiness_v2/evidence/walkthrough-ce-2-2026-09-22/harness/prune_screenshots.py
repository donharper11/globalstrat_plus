"""Keep what a reader needs: drop the near-duplicate per-round decision screens.

prune_screenshots.py [--apply]

Rounds 3 and 4 photograph the same decision screens as rounds 1 and 2, with
different numbers on them. The record cites the round-1 and round-2 screens for
every control, and rounds 3 and 4 only for what is new there: the Summary, the
lock, compliance investment and M&A. Everything else from `p<team>-r3-*` and
`p<team>-r4-*`, and the duplicate second-team round-2 set, is dropped; every
screen is still named in its run's JSON record, which keeps the full list.

Without `--apply` it only prints what it would remove.
"""
import pathlib
import re
import sys

SHOTS = pathlib.Path(__file__).resolve().parent.parent / 'screenshots'
APPLY = '--apply' in sys.argv

# p<team>-r<round>-<nn>-… screens from rounds 3 and 4: keep only these steps.
KEEP_STEPS = {'53', '62', '95', '96', '97', '71', '72'}
LATER_ROUND = re.compile(r'^p(\d)-r([34])-(\d\d)[a-z]?-')


def main():
    drop = []
    for path in sorted(SHOTS.glob('*.jpg')):
        m = LATER_ROUND.match(path.name)
        if m and m.group(3) not in KEEP_STEPS:
            drop.append(path)
    total = sum(p.stat().st_size for p in drop)
    print('%d files, %.1f MB %s'
          % (len(drop), total / 1e6, 'removed' if APPLY else 'would be removed'))
    if APPLY:
        for path in drop:
            path.unlink()
    left = list(SHOTS.glob('*.jpg'))
    print('%d screenshots left, %.1f MB'
          % (len(left), sum(p.stat().st_size for p in left) / 1e6))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
