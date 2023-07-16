#!/usr/bin/env python3
"""Splits up very large rsync tasks into sub-commands to get earlier results
"""
import click
import time

import subprocess as sub
import multiprocessing as mp
import regex as re

from pathlib import Path
from rich.progress import track
from pprint import pprint


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("source", type=str)
@click.argument("dest", type=click.Path(exists=True))
@click.option("-n", "--dry-run", is_flag=True)
@click.option(
    "-j",
    "--threads",
    default=mp.cpu_count(),
    type=click.IntRange(min=1, max=mp.cpu_count()),
)
@click.option("-v", "--verbose", count=True)
def rsync(source, dest, dry_run, threads, verbose):
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
    kwargs = "-Przch" + "".join("v" for i in range(verbose))
    kwargs += "n" if dry_run else ""
    if verbose == 0:
        looper = track(dirs.splitlines())
    else:
        looper = dirs.splitlines()
    for d in looper:
        cmd = [
            "rsync",
            kwargs,
            f"{source}{d}/",
            f"{(dest / d).as_posix()}/",
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
                                out = rsync_out_re.search(
                                    p.stdout.read()
                                )
                                if out is not None:
                                    pprint(out, indent=2)
                        case _:
                            print(f"{cmd} returned {p.poll()}")
                            print(p.stderr.read())

            time.sleep(0.1)
        if verbose >= 3:
            print(cmd)
        pool.append(sub.Popen(cmd, encoding="utf-8", stdout=sub.PIPE, stderr=sub.PIPE))


def main():
    rsync()


if __name__ == "__main__":
    main()
