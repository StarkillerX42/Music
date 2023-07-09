#!/usr/bin/env python3
"""Splits up very large rsync tasks into sub-commands to get earlier results
"""
import click
import time

import subprocess as sub
import multiprocessing as mp
import regex as re

from pathlib import Path
from rich import progress_bar
from pprint import pprint


@click.command()
@click.argument("source", type=str)
@click.argument("dest", type=Path)
@click.option("-n", "--dry-run", is_flag=True)
@click.option(
    "-j",
    "--threads",
    default=mp.cpu_count(),
    type=click.IntRange(min=1, max=mp.cpu_count()),
)
@click.option("-v", "--verbose", count=True)
def rsync(source, dest, dry_run, threads, verbose):
    assert dest.exists(), "Given directory doesn't exist"

    assert "flac" in dest.as_posix(), "'flac' must be in the provided path"
    assert ":" in source, "Source must be a remote host: <uname>@<domain>:<path>"

    source += "/" if source[-1] != "/" else ""

    dirs_cmd = sub.run(
        f'ssh {source.split(":")[0]} "ls {source.split(":")[1]}"',
        shell=True,
        stdout=sub.PIPE,
        encoding="utf-8",
        check=True,
    )
    dirs = dirs_cmd.stdout
    assert len(dirs) > 0, "No subdirectories found"

    print(f"Syncing {len(dirs.splitlines())} directories")

    rsync_out_re = re.compile("(?<=receiving incremental file list)\.+")
    pool = []
    kwargs = "-Przch"
    kwargs += "n" if dry_run else ""
    if verbose == 0:
        looper = progress_bar(dirs.splitlines())
    else:
        looper = dirs.splitlines()
    for d in looper:
        cmd = [
            "rsync",
            kwargs,
            f"{source}{d}",
            f"{(dest / d).as_posix()}",
        ]

        while len(pool) >= threads:
            for p in pool:
                if p.poll() is not None:
                    match p.poll():
                        case 0:
                            pool.remove(p)
                            if verbose >= 2:
                                print(f"{' '.join(p.args)}")
                                out = rsync_out_re.search(
                                    p.stdout.read().decode("utf-8")
                                )
                                if out is not None:
                                    pprint(out, indent=2)
                        case _:
                            print(f"{cmd} returned {p.poll()}")

            time.sleep(0.1)
        if verbose >= 3:
            print(cmd)
        pool.append(sub.Popen(cmd, stdout=sub.PIPE))


def main():
    rsync()


if __name__ == "__main__":
    main()
