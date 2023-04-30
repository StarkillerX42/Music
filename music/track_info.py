#!/usr/bin/env python3

import re

from pathlib import Path
from typing import Tuple
from mutagen.flac import FLAC


def get_track_info(path: Path) -> Tuple[int, str]:
    track_num_re = re.compile(r"\d+")
    if track_num_re.match(path.name):
        t_num = track_num_re.search(path.name).group()
        t_name = path.name.split(t_num)[1]
        t_name = t_name.lstrip(" -._").replace("_", " ")
        t_num = int(t_num)
    else:
        flac = FLAC(path)
        t_num = int(flac["tracknumber"][0])
        t_name = path.name

    return t_num, t_name
