"""Draw the 24x24 icons of the Grasshopper components, as compas_vol does.

Each icon is a 12x12 text sketch, doubled: ``#`` dark ink, ``+`` mid grey,
``.`` transparent. Edit a sketch, run ``python scripts/make_icons.py``, and
commit both.
"""

import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
COMPONENTS = os.path.join(HERE, os.pardir, "grasshopper", "components")
SCALE, SIZE = 2, 12
PALETTE = {"#": (49, 49, 49, 255), "+": (140, 140, 140, 255), ".": (0, 0, 0, 0)}

ICONS = {
    # A page of numbers.
    "Roof_Brief": [
        "..########..",
        "..#......#..",
        "..#.####.#..",
        "..#......#..",
        "..#.###..#..",
        "..#......#..",
        "..#.####.#..",
        "..#......#..",
        "..#.##...#..",
        "..#......#..",
        "..########..",
        "............",
    ],
    # The plan: a bay with an opening and a drain.
    "Roof_Drawing": [
        "############",
        "#.....#....#",
        "#.++..#....#",
        "#+..+.#..#.#",
        "#.++..#....#",
        "############",
        "#.....#....#",
        "#..#..#.++.#",
        "#.....#+..+#",
        "#.....#.++.#",
        "#.....#....#",
        "############",
    ],
    # The roof in section: slab on two beams, pores below.
    "Roof_Design": [
        "............",
        "............",
        "############",
        "############",
        "##.+##+.+.##",
        "##+.+..+..##",
        "##........##",
        "##........##",
        "##........##",
        "##........##",
        "............",
        "............",
    ],
    # One piece with a dowel.
    "Roof_Piece": [
        "............",
        "............",
        "...######...",
        "..#......#..",
        ".#........#.",
        "############",
        "#..........#",
        "#..++......#",
        "#..........#",
        "############",
        "............",
        "............",
    ],
}


def png(pixels, width, height):
    raw = b"".join(b"\x00" + bytes(v for pixel in row for v in pixel) for row in pixels)

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def render(sketch):
    if len(sketch) != SIZE or any(len(row) != SIZE for row in sketch):
        raise ValueError("Every sketch must be {0}x{0} characters.".format(SIZE))
    rows = []
    for line in sketch:
        row = [PALETTE[c] for c in line for _ in range(SCALE)]
        rows.extend([row] * SCALE)
    return rows


def main():
    for name, sketch in sorted(ICONS.items()):
        target = os.path.join(COMPONENTS, name, "icon.png")
        with open(target, "wb") as f:
            f.write(png(render(sketch), SIZE * SCALE, SIZE * SCALE))
        print("wrote", os.path.relpath(target, os.path.join(HERE, os.pardir)))
    missing = sorted(set(os.listdir(COMPONENTS)) - set(ICONS) - {"__pycache__"})
    if missing:
        raise SystemExit("These components have no sketch: {}".format(", ".join(missing)))


if __name__ == "__main__":
    main()
