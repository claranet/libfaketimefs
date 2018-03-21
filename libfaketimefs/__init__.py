from __future__ import print_function

import re

from collections import defaultdict, namedtuple
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

Command = namedtuple('Command', 'ref, time1, time2, rate')


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
        self.faketime_control = Command(
            ref=now,
            time1=now,
            time2=now,
            rate=1,
        )

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
                st_mode=S_IFDIR | 0o755,
                st_ctime=now,
                st_mtime=now,
                st_atime=now,
                st_nlink=2,
            )
        else:
            value = self.get_value(path)
            if path in self.temp_files:
                mode = 0o666
            else:
                mode = 0o444
            return dict(
                st_mode=S_IFREG | mode,
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

            command = self.faketime_control
            offset = calculate_offset(command)
            return '{:+f}'.format(offset)

        if path == '/realtime':

            return '{:.22f}'.format(time())

        if path == '/status':

            command = self.faketime_control
            fake_time = calculate_fake_time(command)

            if fake_time > command.time2:
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
                self.faketime_control = Command(
                    ref=int(match.group('ref')),
                    time1=int(match.group('time1')),
                    time2=int(match.group('time2')),
                    rate=int(match.group('rate')),
                )
                return

        raise FuseOSError(ENOENT)


def calculate_fake_time(command, now=None):
    """
    Calculates the fake time from a command and the real time.

    >>> cmd = (0, 0, 10, 2)
    >>> calculate_fake_time(cmd, now=0)
    0
    >>> calculate_fake_time(cmd, now=1)
    2
    >>> calculate_fake_time(cmd, now=5)
    10
    >>> calculate_fake_time(cmd, now=6)
    11.0

    >>> cmd = (0, 10, 20, 2)
    >>> calculate_fake_time(cmd, now=0)
    10
    >>> calculate_fake_time(cmd, now=1)
    12
    >>> calculate_fake_time(cmd, now=5)
    20
    >>> calculate_fake_time(cmd, now=6)
    21.0

    """

    if now is None:
        now = time()

    offset = calculate_offset(command, now)

    return now + offset


def calculate_offset(command, now=None):
    """
    Calculates the offset from a command and the real time.

    >>> cmd = (0, 0, 10, 2)
    >>> calculate_offset(cmd, now=0)
    0
    >>> calculate_offset(cmd, now=1)
    1
    >>> calculate_offset(cmd, now=5)
    5
    >>> calculate_offset(cmd, now=6)
    5.0

    >>> cmd = (0, 10, 20, 2)
    >>> calculate_offset(cmd, now=0)
    10
    >>> calculate_offset(cmd, now=1)
    11
    >>> calculate_offset(cmd, now=5)
    15
    >>> calculate_offset(cmd, now=6)
    15.0

    """

    ref, time1, time2, rate = command

    # The starting point of fast forwarding is already in the future
    # if time1 is ahead of when the command was issued (ref time).
    initial_offset = time1 - ref

    # There is a window of time where it will be fast forwarding.
    # Calculate that and also how much real time that would take.
    window_fast = time2 - time1
    window_real = window_fast / float(rate)

    # Get how much real time has passed since the command was issued.
    if now is None:
        now = time()
    elapsed = now - ref

    # Discard any time elapsed after the fast forwarding end point,
    # because the offset should stop increasing at that point.
    if elapsed > window_real:
        elapsed = window_real

    # Now calculate the offset. Use the intial offset and the fast
    # forwaded time. Subtract the amount of time it has been fast
    # forwarding because that is already included in the fast amount.
    elapsed_fast = elapsed * rate
    return initial_offset + elapsed_fast - elapsed
