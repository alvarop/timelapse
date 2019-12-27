#!/usr/bin/env python

import argparse
import os
import subprocess
import time
import yaml
from datetime import datetime


class Timelapse:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self.load_config(config_path)

        self.start_timelapse()

    def start_timelapse(self):
        self.last_photo_time = 0
        self.index = 0

        # Use start time of timelapse as a tag
        self.photo_prefix = "{}{}_".format(
            self.config["prefix"], datetime.now().replace(microsecond=0).isoformat()
        )

        if not os.path.exists(self.config["out_dir"]):
            print("{} not found. Creating".format(self.config["out_dir"]))
            os.makedirs(self.config["out_dir"], exist_ok=True)

    def load_config(self, config_path):
        with open(config_path, "r") as config_file:
            config = yaml.safe_load(config_file)

        if config is None:
            raise Exception("Unable to load config file")

        return config

    def time_for_photo(self):
        if time.time() >= (self.last_photo_time + self.config["interval_s"]):
            self.last_photo_time = time.time()
            return True
        else:
            return False

    def take_photo(self, device="/dev/video0", resolution="1920x1080", filename=None):

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

    def run(self):
        while True:

            # TODO - setup watchdog to watch config file for changes
            new_config = self.load_config(args.config)
            if new_config != self.config:
                print("Config changed. Starting new timelapse with new settings.")
                self.start_timelapse()
            self.config = new_config

            if self.time_for_photo():
                filename = os.path.join(
                    self.config["out_dir"],
                    "{}{:06d}.jpg".format(self.photo_prefix, self.index),
                )

                res = self.take_photo(
                    self.config["device"], self.config["resolution"], filename
                )
                if res == filename:
                    print("Saving photo to ", filename)
                else:
                    print("Error taking photo")

                self.index += 1

            time.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="Config file location")
    args = parser.parse_args()

    if not os.path.exists(args.config):
        raise Exception("Config file not found.")

    timelapse = Timelapse(args.config)

    timelapse.run()
