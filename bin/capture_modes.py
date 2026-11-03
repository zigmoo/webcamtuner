"""Read capture formats using V4L2 enumeration ioctls; never negotiate or stream."""
import errno
import fcntl
import os
import struct


def enumerate_values(fd, request, size, fields):
    for index in range(256):
        value = bytearray(size)
        struct.pack_into('=' + 'I' * (len(fields) + 1), value, 0, index, *fields)
        try:
            fcntl.ioctl(fd, request, value, True)
        except OSError as error:
            if error.errno == errno.EINVAL:
                return
            raise
        yield value


def modes(camera):
    # Structures/requests from linux/videodev2.h; see kernel.org userspace V4L2
    # VIDIOC_ENUM_FMT, VIDIOC_ENUM_FRAMESIZES and VIDIOC_ENUM_FRAMEINTERVALS.
    fd = os.open(camera, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    result = []
    try:
        for fmt in enumerate_values(fd, 0xc0405602, 64, [1]):
            fourcc = bytes(fmt[44:48]).decode('ascii', errors='replace')
            if fourcc not in ('MJPG', 'YUYV', 'NV12'):
                continue
            pixel = struct.unpack_from('=I', fmt, 44)[0]
            for size in enumerate_values(fd, 0xc02c564a, 44, [pixel]):
                kind, width, height = struct.unpack_from('=III', size, 8)
                if kind != 1:
                    # Common UVC cameras enumerate discrete modes. Do not invent
                    # a mode for a continuous/stepwise device.
                    continue
                for interval in enumerate_values(fd, 0xc034564b, 52, [pixel, width, height]):
                    kind, numerator, denominator = struct.unpack_from('=III', interval, 16)
                    if numerator and denominator:
                        result.append({'width': width, 'height': height, 'fps': denominator / numerator, 'fourcc': fourcc})
                    if kind != 1:
                        break
    finally:
        os.close(fd)
    return result
