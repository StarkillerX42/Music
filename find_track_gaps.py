#!/usr/bin/env python3

import asyncio

import asyncclick as click

from pathlib import Path

from music import track_info


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("path", type=Path)
@click.option("-i", "--ignore", multiple=True)
@click.option("-v", "--verbose", count=True)
async def main(path: Path, ignore: tuple, verbose: int) -> None:
    errors = 0
    if verbose:
        click.echo(f"Path: {path.absolute().as_posix()}")
        click.echo(f"Ignoring: {ignore}")
    for d in sorted(path.rglob("*/")):
        if d.name in ignore or not d.is_dir():
            continue
        for i, t in enumerate(sorted(d.glob("*.flac"))):
            # print(t)
            t_num, t_name = track_info.get_track_info(t)
            if t_num is not None and i + 1 != t_num:
                if t_num == 1 and i + 1 == 10:
                    print(f"No preceding zeroes for {d.absolute().as_posix()}")
                else:
                    print(
                        f"Discrepency at track {i + 1} from {t_num} in {d.absolute().as_posix()}"
                    )
                errors += 1
                break
            elif t_num is None:
                print(f"Unnumbered track in {t.absolute().as_posix()}")
                errors += 1
                break
    print(f"Found {errors} errors")
    return


if __name__ == "__main__":
    asyncio.run(main())
