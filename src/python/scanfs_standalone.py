#!/usr/bin/env python3
# Copyright 2017, Inderpreet Singh, All rights reserved.
# Self-contained scanfs script - can run on remote servers without dependencies

import pickle
import sys
import os
import re
import argparse
from typing import List
from datetime import datetime


class SystemFile:
    def __init__(self, name, size, is_dir=False, time_created=None, time_modified=None):
        if size < 0:
            raise ValueError("File size must be greater than zero")
        self.__name = name
        self.__size = size
        self.__is_dir = is_dir
        self.__timestamp_created = time_created
        self.__timestamp_modified = time_modified
        self.__children = []

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __repr__(self):
        return str(self.__dict__)

    @property
    def name(self): return self.__name

    @property
    def size(self): return self.__size

    @property
    def is_dir(self): return self.__is_dir

    @property
    def timestamp_created(self): return self.__timestamp_created

    @property
    def timestamp_modified(self): return self.__timestamp_modified

    @property
    def children(self): return self.__children

    def add_child(self, file):
        if not self.__is_dir:
            raise TypeError("Cannot add children to a file")
        self.__children.append(file)

# Override module so pickle serializes as system.file.SystemFile
# This is required for the receiving end (seedsync) to unpickle correctly
SystemFile.__module__ = 'system.file'


class SystemScannerError(Exception):
    pass


class SystemScanner:
    __LFTP_STATUS_FILE_SUFFIX = ".lftp-pget-status"

    def __init__(self, path_to_scan):
        self.path_to_scan = path_to_scan
        self.exclude_prefixes = []
        self.exclude_suffixes = [SystemScanner.__LFTP_STATUS_FILE_SUFFIX]
        self.__lftp_temp_file_suffix = None

    def add_exclude_prefix(self, prefix):
        self.exclude_prefixes.append(prefix)

    def scan(self):
        if not os.path.exists(self.path_to_scan):
            raise SystemScannerError("Path does not exist: {}".format(self.path_to_scan))
        elif not os.path.isdir(self.path_to_scan):
            raise SystemScannerError("Path is not a directory: {}".format(self.path_to_scan))
        return self.__create_children(self.path_to_scan)

    def __create_system_file(self, entry):
        if entry.is_dir():
            sub_children = self.__create_children(entry.path)
            name = entry.name.encode('utf-8', 'surrogateescape').decode('utf-8', 'replace')
            size = sum(sub_child.size for sub_child in sub_children)
            time_created = None
            try:
                time_created = datetime.fromtimestamp(entry.stat().st_birthtime)
            except AttributeError:
                pass
            time_modified = datetime.fromtimestamp(entry.stat().st_mtime)
            sys_file = SystemFile(name, size, True,
                                  time_created=time_created,
                                  time_modified=time_modified)
            for sub_child in sub_children:
                sys_file.add_child(sub_child)
        else:
            file_size = entry.stat().st_size
            lftp_status_file_path = entry.path + SystemScanner.__LFTP_STATUS_FILE_SUFFIX
            if os.path.isfile(lftp_status_file_path):
                with open(lftp_status_file_path, "r") as f:
                    file_size = SystemScanner._lftp_status_file_size(f.read())
            file_name = entry.name.encode('utf-8', 'surrogateescape').decode('utf-8', 'replace')
            if self.__lftp_temp_file_suffix is not None and \
                    file_name != self.__lftp_temp_file_suffix and \
                    file_name.endswith(self.__lftp_temp_file_suffix):
                file_name = file_name[:-len(self.__lftp_temp_file_suffix)]
            time_created = None
            try:
                time_created = datetime.fromtimestamp(entry.stat().st_birthtime)
            except AttributeError:
                pass
            time_modified = datetime.fromtimestamp(entry.stat().st_mtime)
            sys_file = SystemFile(file_name, file_size, False,
                                  time_created=time_created,
                                  time_modified=time_modified)
        return sys_file

    def __create_children(self, path):
        children = []
        for entry in os.scandir(path):
            skip = False
            for prefix in self.exclude_prefixes:
                if entry.name.startswith(prefix):
                    skip = True
            for suffix in self.exclude_suffixes:
                if entry.name.endswith(suffix):
                    skip = True
            if skip:
                continue
            try:
                sys_file = self.__create_system_file(entry)
            except FileNotFoundError:
                continue
            children.append(sys_file)
        children.sort(key=lambda fl: fl.name)
        return children

    @staticmethod
    def _lftp_status_file_size(status):
        size_pattern_m = re.compile(r"^size=(\d+)$")
        pos_pattern_m = re.compile(r"^\d+\.pos=(\d+)$")
        limit_pattern_m = re.compile(r"^\d+\.limit=(\d+)$")
        lines = [s.strip() for s in status.splitlines()]
        lines = list(filter(None, lines))
        if not lines:
            return 0
        empty_size = 0
        result = size_pattern_m.search(lines[0])
        if not result:
            return 0
        total_size = int(result.group(1))
        lines.pop(0)
        while lines:
            if len(lines) < 2:
                return 0
            result_pos = pos_pattern_m.search(lines[0])
            result_limit = limit_pattern_m.search(lines[1])
            if not result_pos or not result_limit:
                return 0
            pos = int(result_pos.group(1))
            limit = int(result_limit.group(1))
            empty_size += limit - pos
            lines.pop(0)
            lines.pop(0)
        return total_size - empty_size


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
        def print_file(file, level):
            sys.stdout.write("  " * level)
            sys.stdout.write("{} {} {}\n".format(
                file.name,
                "d" if file.is_dir else "f",
                file.size
            ))
            for child in file.children:
                print_file(child, level + 1)
        for root_file in root_files:
            print_file(root_file, 0)
    else:
        bytes_out = pickle.dumps(root_files)
        sys.stdout.buffer.write(bytes_out)
