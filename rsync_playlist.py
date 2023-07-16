#!/usr/bin/env python3
import time
import re
import click

import xml.etree.ElementTree as ETree

import subprocess as sub
import multiprocessing as mp

from pathlib import Path
from rich.progress import track


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("playlist_file", type=click.Path(exists=True))
@click.argument("dest", type=str)
@click.option("-n", "--dry-run", is_flag=True)
@click.option(
    "-j",
    "--threads",
    default=mp.cpu_count(),
    type=click.IntRange(min=1, max=mp.cpu_count()),
)
@click.option("-v", "--verbose", count=True)
def main(playlist_file, dest, dry_run, threads, verbose):
    dest_spl = dest.split(":")
    rsync_out_re = re.compile("(?<=receiving incremental file list)\.+")
    if len(dest_spl) == 2:
        dest_machine, dest_path = dest_spl
        dest_path = Path(dest_path)
        dest = f"{dest_machine}:{dest_path.as_posix()}"
    elif len(dest_spl) == 1:
        Path(dest).mkdir(exist_ok=True)
    else:
        raise ValueError("Destination not understood")

    xspf = ETree.parse(playlist_file)
    root = xspf.getroot()
    trackList = root[0]
    pool = []
    if verbose == 0:
        looper = track(trackList)
    else:
        looper = trackList
    for song in looper:
        location = None
        assert (
            song.tag == "{http://xspf.org/ns/0/}track"
        ), f"Expected track, got {song.tag}"
        location = None
        for entry in song:
            if entry.tag == "{http://xspf.org/ns/0/}location":
                location = Path(entry.text)
                assert location.exists(), f"File {location.as_posix()} does not exist!"
                kwargs = "-Przch" + "".join("v" for i in range(verbose))
                kwargs += "n" if dry_run else ""
                cmd = [
                    "rsync",
                    kwargs,
                    location.as_posix(),
                    dest + location.name,
                ]
                while len(pool) >= threads:
                    for p in pool:
                        if verbose >= 3:
                            print(p.args, p.stdout.read())
                        status = p.poll()
                        if status is not None:
                            pool.remove(p)
                            match status:
                                case 0:
                                    if verbose >= 2:
                                        print(f"{' '.join(p.args)}")
                                        out = rsync_out_re.search(p.stdout.read())
                                        if out is not None:
                                            pprint(out, indent=2)
                                case _:
                                    print(f"{cmd} returned {p.poll()}")
                                    print(p.stderr.read())
                    time.sleep(0.1)
                if verbose >= 3:
                    print(cmd)
                pool.append(
                    sub.Popen(cmd, encoding="utf-8", stdout=sub.PIPE, stderr=sub.PIPE)
                )


if __name__ == "__main__":
    main()
