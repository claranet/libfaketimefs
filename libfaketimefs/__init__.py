from __future__ import print_function

import re

from collections import defaultdict
from errno import ENOENT, EPERM
from heapq import heappop, heappush
from itertools import chain
from os.path import basename
from tempfile import TemporaryFile
from time import time
from threading import Lock
from stat import S_IFDIR, S_IFREG

from vendored.fusepy.fuse import FuseOSError, LoggingMixIn, Operations


CONTROL_COMMAND = re.compile(' '.join((
    r'(?P<ref>\d+)',
    r'(?P<time1>\d+)',
    r'(?P<time2>\d+)',
    r'(?P<rate>\d+)',
)))


class Faketime(LoggingMixIn, Operations):

    def __init__(self):

        self.file_handles = list(range(1, 1024 + 1))
        self.file_handles_lock = Lock()

        self.fake_files = set([
            '/faketimerc',
            '/realtime',
            '/status',
        ])
        self.temp_files = {
            '/control': TemporaryFile(),
        }

        self.file_locks = defaultdict(Lock)

        now = int(time())
        self.faketime_control = (now, now, now, 0)

    # Info methods

    def readdir(self, path, fh):
        if path == '/':
            return list(chain(
                ('.', '..'),
                (basename(path) for path in self.fake_files),
                (basename(path) for path in self.temp_files),
            ))
        raise FuseOSError(ENOENT)

    def getattr(self, path, fh=None):
        now = time()
        if path == '/':
            return dict(
                st_mode=S_IFDIR,
                st_ctime=now,
                st_mtime=now,
                st_atime=now,
                st_nlink=2,
            )
        else:
            value = self.get_value(path)
            return dict(
                st_mode=S_IFREG,
                st_ctime=now,
                st_mtime=now,
                st_atime=now,
                st_nlink=1,
                st_size=len(value),
            )

    getxattr = None

    # Open and close files

    def open(self, path, flags):
        if path in self.fake_files or path in self.temp_files:
            with self.file_handles_lock:
                fh = heappop(self.file_handles)
            return fh
        raise FuseOSError(ENOENT)

    def release(self, path, fh):
        with self.file_handles_lock:
            heappush(self.file_handles, fh)

    # Read files

    def read(self, path, size, offset, fh):
        value = self.get_value(path)
        return value[offset:offset + size]

    # Write files

    def write(self, path, data, offset, fh):
        if path in self.temp_files:
            with self.file_locks[path]:
                temp_file = self.temp_files[path]
                temp_file.seek(offset)
                temp_file.write(data)
                if offset == 0:
                    value = data
                else:
                    temp_file.seek(0)
                    value = temp_file.read()
            self.parse_value(path, value)
            return len(data)
        elif path in self.fake_files:
            raise FuseOSError(EPERM)
        else:
            raise FuseOSError(ENOENT)

    def truncate(self, path, size):
        if path in self.temp_files:
            with self.file_locks[path]:
                temp_file = self.temp_files[path]
                temp_file.truncate(size)
        elif path in self.fake_files:
            raise FuseOSError(EPERM)
        else:
            raise FuseOSError(ENOENT)

    # Faketime logic

    def get_value(self, path):

        if path == '/faketimerc':

            ref, time1, time2, rate = self.faketime_control

            if time1 == time2:
                offset = time1 - ref
            else:
                elapsed = time() - ref
                position = time1 + (elapsed * rate) - elapsed
                if position > time2:
                    offset = time2 - ref
                else:
                    offset = position - ref

            if offset >= 0:
                return '+{}'.format(offset)
            else:
                return '{}'.format(offset)

        if path == '/realtime':
            return '{:.22f}'.format(time())

        if path == '/status':

            ref, time1, time2, rate = self.faketime_control

            if time1 == time2:
                return 'IDLE'
            else:
                elapsed = time() - ref
                position = time1 + (elapsed * rate) - elapsed
                if position > time2:
                    return 'IDLE'
                else:
                    return 'MOVING'

        if path in self.temp_files:
            with self.file_locks[path]:
                temp_file = self.temp_files[path]
                temp_file.seek(0)
                return temp_file.read()

        raise FuseOSError(ENOENT)

    def parse_value(self, path, value):

        if path == '/control':
            value = value.strip()
            match = CONTROL_COMMAND.match(value)
            if match:
                ref = int(match.group('ref'))
                time1 = int(match.group('time1'))
                time2 = int(match.group('time2'))
                rate = int(match.group('rate'))
                self.faketime_control = (ref, time1, time2, rate)
                return

        raise FuseOSError(ENOENT)
