#!/usr/bin/env python

import datetime
import subprocess
import tempfile
from v4l2 import v4l2


def take_photo(device="/dev/video0", resolution="1920x1080", filename=None):

    if filename is None:
        filename = tempfile.mktemp(".jpg")

    result = subprocess.run(
        [
            "fswebcam",
            "--no-banner",
            "-d",
            "v4l2:{}".format(device),
            "-r",
            resolution,
            filename,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # fswebcam seems to use stderr instead of stdout
    rval = result.stderr.decode("utf-8")
    if "Error" in rval:
        print(rval)
        return None

    isodate = datetime.datetime.now().isoformat()

    result = subprocess.run(
        [
            "exiftool",
            "-overwrite_original",
            "-DateTimeOriginal='{}'".format(isodate),
            filename,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return filename


result = take_photo("/dev/video0", "640x480")
print(result)
