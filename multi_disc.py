#!/usr/bin/env python3
import re
import asyncio

import numpy as np
import asyncclick as click

from pprint import pprint
from pathlib import Path
from rich.progress import track
from tinytag import TinyTag
from mutagen.flac import FLAC

from music import track_info

track_num_re = re.compile(r"\d+")


async def merge_disc(p: Path, unsorted=False, verbose=0):
    discPs = list(sorted(p.glob("Disc *"))) + list(sorted(p.glob("Volume *")))
    offset = 0
    counter = 0
    total = len(list(p.rglob("*.flac")))
    for disc in discPs:
        off_num = 0
        for flac_name in sorted(disc.glob("*.flac")):
            counter += 1
            t_num, t_name = track_info.get_track_info(flac_name)
            # print(f"{t_num:0>2.0f} - {t_name}")
            t_name = t_name.replace("_", " ")
            new_num = t_num + offset
            if not unsorted and counter != new_num:
                raise ValueError(f"Counter has lost its place for {p} at {counter}")
            if total < 100:
                new_path = p / f"{new_num:0>2.0f} - {t_name}"
            else:
                new_path = p / f"{new_num:0>3.0f} - {t_name}"

            # assert f"{new_num:0>2.0f}" == TinyTag.get(new_path).track
            flac = FLAC(flac_name)
            flac["tracknumber"] = f"{new_num}"
            flac["discnumber"] = "1"
            flac["totaldiscs"] = "1"
            flac.save()
            flac_name.rename(new_path)
            if verbose >= 2:
                print(f"{flac_name.name} -> {new_path.name}")
            off_num = max(t_num, off_num)
        offset += off_num
        assert len(list(disc.glob("*"))) == 0, "Folder must be empty"
        disc.rmdir()


@click.command()
@click.argument("path")
@click.option("-d", "--dry-run", is_flag=True)
@click.option("-u", "--unsorted", is_flag=True)
@click.option("-v", "--verbose", count=True)
async def main(path, dry_run, unsorted, verbose):
    if verbose:
        click.echo(f"Verbose: {verbose}")
        click.echo(f"Dry run: {dry_run}")
        click.echo(f"Unsorted: {unsorted}")
    root = Path(path).absolute()
    assert root.exists()
    multi_discs = set()
    flacs = list(root.rglob("*.flac"))
    for p in track(flacs):
        if p.parent.parent in multi_discs:
            continue
        if "Disc " in p.parent.name or "Volume " in p.parent.name:
            multi_discs.add(p.parent.parent)
    if verbose:
        print(f"There are {len(multi_discs)} multi-disc folders")
    if verbose >= 2:
        pprint(multi_discs)
    if not dry_run:
        coros = [merge_disc(p, unsorted, verbose=verbose) for p in multi_discs]
        await asyncio.gather(*coros)
    return 0


if __name__ == "__main__":
    asyncio.run(main())
