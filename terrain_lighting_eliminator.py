#!/usr/bin/env python3

# Terrain Lighting Eliminator: eliminate terrain lighting from all your
# NSMBW levels!

# Copyright (C) 2022 RoadrunnerWMC
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


import argparse
from pathlib import Path
import struct
import traceback
from typing import List

import nsmbpy2.u8

import lz77


def fix_course_file(data: bytes) -> (bytes, int):
    """Fix an individual course file ("courseN.bin")"""
    # I'm doing this manually because nsmbpy's API is a bit
    # up-in-the-air at the moment and I want this to Just Work™ into the
    # future

    data = bytearray(data)

    zones_off, zones_size = struct.unpack_from('>II', data, 0x48)  # 10th block

    num_fixes = 0

    for i in range(zones_size // 24):
        off = zones_off + i * 24 + 10
        terrain_lighting, = struct.unpack_from('>H', data, off)
        if terrain_lighting != 0:
            num_fixes += 1
            struct.pack_into('>H', data, off, 0)

    return data, num_fixes


def scan_file(fp: Path) -> None:
    """Scan an individual file (.arc or .arc.lz)"""
    with fp.open('rb') as f:
        first_4 = f.read(4)

    if first_4 == b'U\xAA8-':
        is_compressed = False
    elif first_4[0] == 0x11:  # LZ11
        is_compressed = True
    elif first_4[0] >> 4 == 4:  # Probably LH
        return  # We can't recompress LH, so we skip these
    else:
        # Probably not a NSMBW level at all?
        return

    data = fp.read_bytes()

    if is_compressed:
        data = lz77.LZS11().Decompress11LZS(data)

    u8 = nsmbpy2.u8.load(data)

    if list(u8.keys()) != ['course']:
        # Probably not a NSMBW level (some other arc file instead)
        return

    course = u8['course']

    # Fix each area
    total_fixes = 0
    total_areas_fixed = 0
    for i in range(1, 5):
        course_fn = f'course{i}.bin'
        if course_fn in course:
            new_course_data, num_fixes = fix_course_file(course[course_fn])
            if num_fixes > 0:
                total_fixes += num_fixes
                total_areas_fixed += 1
                course[course_fn] = new_course_data

    if total_fixes > 0:
        # Print output line
        line = [f'Fixed {total_fixes} zone']
        if total_fixes != 1:
            line.append('s')
        line.append(f' in {total_areas_fixed} area')
        if total_areas_fixed != 1:
            line.append('s')
        line.append(f' in {fp}')
        print(''.join(line))

        # Prepare output data and save

        data = nsmbpy2.u8.save(u8)

        if is_compressed:
            data = lz77.LZS11().Compress11LZS(data)

        fp.write_bytes(data)


def scan_file_safe(fp: Path) -> None:
    """scan_file() wrapper that catches and prints exceptions"""
    try:
        return scan_file(fp)
    except Exception:
        print(f'ERROR while checking "{fp}":')
        traceback.print_exc()


def does_path_look_like_level(fp: Path) -> bool:
    """Check if a Path looks like a NSMBW level file we can open"""
    if fp.suffix.lower() == '.arc':
        return True
    elif len(fp.suffixes) >= 2 and fp.suffixes[-2].lower() == '.arc' and fp.suffixes[-1].lower() == '.lz':
        return True
    else:
        return False


def scan_folder(fp: Path, *, recursive:bool=False) -> None:
    """Scan a folder, optionally recursively"""
    # First handle all files in this folder...
    for child in sorted(fp.iterdir()):
        if child.is_dir():
            continue

        if does_path_look_like_level(child):
            scan_file_safe(child)

    # ...and then all subfolders (if recursive)
    if recursive:
        for child in sorted(fp.iterdir()):
            if child.is_file():
                continue

            scan_folder(child, recursive=True)


def main(argv:List[str]=None) -> None:
    """Script main function"""
    print("""
Terrain Lighting Eliminator, copyright (C) 2022 RoadrunnerWMC
This program comes with ABSOLUTELY NO WARRANTY; for details, see the
included `LICENSE` file.
This is free software, and you are welcome to redistribute it
under certain conditions; see the included `LICENSE` file for details.
You should have received a copy of the GNU General Public License (the
`LICENSE` file) along with this program.  If not, see
<https://www.gnu.org/licenses/>.
"""[1:])

    parser = argparse.ArgumentParser(
        description='Terrain Lighting Eliminator: eliminate terrain lighting from all your NSMBW levels!')

    parser.add_argument('path', type=Path,
        help='a level file or folder (will be edited in-place)')
    parser.add_argument('--recursive', action='store_true',
        help='search through subfolders too')

    args = parser.parse_args(argv)

    if args.path.is_file():
        scan_file(args.path)
    elif args.path.is_dir():
        scan_folder(args.path, recursive=args.recursive)
    else:
        print(f'Error: "{args.path}" does not exist.')


if __name__ == '__main__':
    main()
