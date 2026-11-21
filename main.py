#!/usr/bin/env python3
"""The Passport Page of a Country That Isn't There — make.fun entry.

Writes the invented passport spread of the fictional Republic of
Talveria to /output/entry.png. Standard library only, no network,
deterministic: the spread is rendered by tools/render.py and shipped
as assets/passport.png; this program only copies it to the output
path the grader reads.
"""

import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "assets", "passport.png")


def main():
    os.makedirs("/output", exist_ok=True)
    shutil.copyfile(SRC, "/output/entry.png")


if __name__ == "__main__":
    main()
