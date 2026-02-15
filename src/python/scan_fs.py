# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
import sys
import argparse

# my libs
from system import SystemScanner, SystemFile, SystemScannerError


def file_to_dict(file: SystemFile) -> dict:
    """Convert a SystemFile to a JSON-serializable dict."""
    d = {
        "name": file.name,
        "size": file.size,
        "is_dir": file.is_dir,
        "timestamp_created": file.timestamp_created.timestamp() if file.timestamp_created else None,
        "timestamp_modified": file.timestamp_modified.timestamp() if file.timestamp_modified else None,
    }
    if file.is_dir and file.children:
        d["children"] = [file_to_dict(c) for c in file.children]
    return d


if __name__ == "__main__":
    if sys.hexversion < 0x03050000:
        sys.exit("Python 3.5 or newer is required to run this program.")

    parser = argparse.ArgumentParser(description="File size scanner")
    parser.add_argument("path", help="Path of the root directory to scan")
    parser.add_argument("-e", "--exclude-hidden", action="store_true", default=False,
                        help="Exclude hidden files")
    parser.add_argument("-H", "--human-readable", action="store_true", default=False,
                        help="Human readable output")
    args = parser.parse_args()

    scanner = SystemScanner(args.path)
    if args.exclude_hidden:
        scanner.add_exclude_prefix(".")
    try:
        root_files = scanner.scan()
    except SystemScannerError as e:
        sys.exit("SystemScannerError: {}".format(str(e)))
    if args.human_readable:
        def print_file(file: SystemFile, level: int):
            sys.stdout.write("  "*level)
            sys.stdout.write("{} {} {}\n".format(
                file.name,
                "d" if file.is_dir else "f",
                file.size
            ))
            for child in file.children:
                print_file(child, level+1)
        for root_file in root_files:
            print_file(root_file, 0)
    else:
        json_out = json.dumps([file_to_dict(f) for f in root_files])
        sys.stdout.write(json_out)
