#!/usr/bin/env python

import argparse
import os
import subprocess
import time
import yaml
from datetime import datetime


def load_config(config_path):
    global config
    with open(config_path, "r") as config_file:
        config = yaml.safe_load(config_file)

    if config is None:
        raise Exception("Unable to load config file")


def take_photo(device="/dev/video0", resolution="1920x1080", filename=None):

    if filename is None:
        filename = tempfile.mktemp(".jpg")

    result = subprocess.run(
        [
            "fswebcam",
            "--no-banner",
            "-sFocus, Auto=False",
            "-sExposure, Auto=Manual Mode",
            "-sWhite Balance Temperature, Auto=False",
            "-S5",
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
    if "Error" in rval and "Error querying menu" not in rval:
        print(rval)
        return None

    isodate = datetime.now().isoformat()

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


last_photo_time = 0


def time_for_photo():
    global last_photo_time

    if time.time() >= (last_photo_time + config["interval_s"]):
        last_photo_time = time.time()
        return True
    else:
        return False


parser = argparse.ArgumentParser()
parser.add_argument("config", help="Config file location")
parser.add_argument("--overwrite", action="store_true", help="Overwrite images if necessary")
args = parser.parse_args()

if not os.path.exists(args.config):
    raise Exception("Config file not found.")

load_config(args.config)

if not os.path.exists(config["out_dir"]):
    print("{} not found. Creating".format(config["out_dir"]))
    os.makedirs(config["out_dir"], exist_ok=True)

index = 0

while True:

    if time_for_photo():
        filename = os.path.join(
            config["out_dir"], "{}{:05d}.jpg".format(config["prefix"], index)
        )

        if os.path.exists(filename) and args.overwrite:
            print("Overwriting file {}".format(filename))
        elif os.path.exists(filename):
            print("Error: File exists - {}".format(filename))
            filename = None

        if filename:
            res = take_photo(config["device"], config["resolution"], filename)
            if res == filename:
                print("Saving photo to ", filename)
            else:
                print("Error taking photo")

        index += 1

    time.sleep(1)
