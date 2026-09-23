"""Keep the evidence small: downscale the screenshots in place.

shrink_screenshots.py [max_width] [quality]

Full-page screenshots of a long console tab run to several megabytes each. The
first walkthrough's evidence was 62 MB and had to be pruned; this pass keeps
every screen but re-encodes it at a modest width, which leaves the text
readable at 100 % and the evidence a fraction of the size. Run it between
sections; it is idempotent (an image already at or below the width is only
re-encoded if that makes it smaller).
"""
import pathlib
import sys

from PIL import Image

SHOTS = pathlib.Path(__file__).resolve().parent.parent / 'screenshots'
MAX_W = int(sys.argv[1]) if len(sys.argv) > 1 else 1100
QUALITY = int(sys.argv[2]) if len(sys.argv) > 2 else 45
MAX_H = 6000        # a very long page is cropped at the bottom, not squeezed


def main():
    before = after = 0
    for path in sorted(SHOTS.glob('*.jpg')):
        size0 = path.stat().st_size
        before += size0
        try:
            with Image.open(path) as im:
                im = im.convert('RGB')
                w, h = im.size
                if w > MAX_W:
                    h = int(h * MAX_W / w)
                    im = im.resize((MAX_W, h), Image.LANCZOS)
                if h > MAX_H:
                    im = im.crop((0, 0, im.size[0], MAX_H))
                tmp = path.with_suffix('.tmp.jpg')
                im.save(tmp, 'JPEG', quality=QUALITY, optimize=True)
            if tmp.stat().st_size < size0:
                tmp.replace(path)
            else:
                tmp.unlink()
        except Exception as exc:
            print('skip %s: %s' % (path.name, str(exc)[:80]))
        after += path.stat().st_size
    print('%d files: %.1f MB -> %.1f MB' % (len(list(SHOTS.glob('*.jpg'))),
                                            before / 1e6, after / 1e6))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
