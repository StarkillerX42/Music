#!/usr/bin/env python3
import time
import re
import click

import xml.etree.ElementTree as ETree

import subprocess as sub
import multiprocessing as mp

from pathlib import Path
from pprint import pprint
from rich.progress import track


def safe_path(path: str, handle_parens: bool = False,
              handle_space: bool = False) -> str:
    for char in "$[]":
        path = path.replace(char, f"\{char}")
    if handle_parens:
        path = path.replace("(", "\(")
        path = path.replace(")", "\)")
    if handle_space:
        path = path.replace(" ", "\ ")
    return path


def sync(
    playlist_file: Path | str,
    dest: Path | str,
    threads: int = 1,
    verbose: int = 0,
    dry_run: bool = False,
) -> list[str]:
    dest += "/" if dest[-1] != "/" else ""
    playlist_file = Path(playlist_file)
    rsync_out_re = re.compile("(?<=receiving incremental file list)\.+")
    xspf = ETree.parse(playlist_file)
    root = xspf.getroot()
    trackList = root[0]
    pool = []
    f_names = []
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
                f_names.append(location.name)
                if not location.exists():
                    raise FileNotFoundError(
                        f"File {location.as_posix()} does not exist!"
                    )
                kwargs = "-Przch" + "".join("v" for _ in range(verbose))
                kwargs += "n" if dry_run else ""
                cmd = " ".join([
                    "rsync",
                    kwargs,
                    safe_path(f'"{location.as_posix()}"'),
                    safe_path(f'"{dest}{location.name}"'),
                ])
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
                                        if isinstance(p.args, str):
                                            print(p.args)
                                        else:
                                            print(f"{' '.join(p.args)}")
                                        out = rsync_out_re.search(p.stdout.read())
                                        if out is not None:
                                            pprint(out, indent=2)
                                case _:
                                    print(f"{cmd} returned {p.poll()}")
                                    print(p.stdout.read(), p.stderr.read())
                    time.sleep(0.05)
                if verbose >= 3:
                    print(cmd)
                pool.append(
                    sub.Popen(
                        cmd,
                        shell=True,
                        encoding="utf-8",
                        stdout=sub.PIPE,
                        stderr=sub.PIPE
                    )
                )
                entry.text = location.name

    # Copy playlist to server to relative path names
    tmp = Path("test.xspf")
    xspf.write(tmp)
    psp = sub.run(
        ["rsync", "-Pzlhc", tmp.as_posix(), dest + safe_path(playlist_file.name)],
        encoding="utf-8",
        stdout=sub.PIPE,
        stderr=sub.PIPE,
    )
    tmp.unlink()

    return f_names


def delete_extras(f_names, dest, verbose=0) -> None:
    # Get a list of files
    if ":" in dest:
        dest_host, dest_p = dest.split(":")
        ls_files = sub.run(
            ["ssh", dest_host, f"ls -1 {dest_p}"],
            encoding="utf-8",
            stdout=sub.PIPE,
            stderr=sub.PIPE,
        )
    else:
        dest_p = dest
        ls_files = sub.run(
            ["ls", "-1", dest],
            encoding="utf-8",
            stdout=sub.PIPE,
            stderr=sub.PIPE
        )
    if ls_files.returncode == 0:
        ls_files = ls_files.stdout
    else:
        print(ls_files.stderr)
    for file in track(ls_files.split("\n")):
        if (file == "") or ("xspf" in file):
            continue
        if file not in f_names:
            print(f"Deleting {file}")
            if ":" in dest:
                p = sub.run(
                    " ".join([
                        "ssh",
                        dest_host,
                        f'"rm {dest_p}{safe_path(file, handle_space=True)}"',
                    ]),
                    shell=True,
                    encoding="utf-8",
                    stdout=sub.PIPE,
                    stderr=sub.PIPE,
                )
            else:
                p = sub.run(
                    ["rm", dest_p + safe_path(file)],
                    encoding="utf-8",
                    stdout=sub.PIPE,
                    stderr=sub.PIPE,
                )
            if p.returncode != 0:
                if isinstance(p.args, str):
                    print(
                        f"{p.args} returned {p.returncode} with"
                        f" {p.stderr}"
                    )


                else:
                    print(
                        f"{' '.join(p.args)} returned {p.returncode} with"
                        f" {p.stderr}"
                    )


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("playlist_file", type=click.Path(exists=True))
@click.argument("dest", type=str)
@click.option("-n", "--dry-run", is_flag=True)
@click.option("--delete", is_flag=True)
@click.option(
    "-j",
    "--threads",
    default=mp.cpu_count(),
    type=click.IntRange(min=1, max=mp.cpu_count()),
)
@click.option("-v", "--verbose", count=True)
def main(playlist_file, dest, dry_run, delete, threads, verbose) -> None:
    dest_spl = dest.split(":")
    if dest[-1] != "/":
        dest += "/"
 
    if len(dest_spl) == 2:
        dest_machine, dest_path = dest_spl
        dest_path = Path(dest_path)
        sub.run(
            ["ssh", dest_machine, f"mkdir -p {dest_path.as_posix()}"],
            encoding="utf-8",
            stdout=sub.PIPE,
            stderr=sub.PIPE,
        )
        dest = f"{dest_machine}:{dest_path.as_posix()}"
    elif len(dest_spl) == 1:
        Path(dest).mkdir(exist_ok=True)
    else:
        raise ValueError("Destination not understood")

    f_names = sync(
        playlist_file, dest, threads=threads, dry_run=dry_run, verbose=verbose
    )
    if delete:
        delete_extras(f_names, dest, verbose=verbose)


if __name__ == "__main__":
    main()
