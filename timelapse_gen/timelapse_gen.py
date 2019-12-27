#!/usr/bin/env python

import argparse
import glob
import os
import shutil
import subprocess
import tempfile
import time
import yaml
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


def load_config(config_path):
    with open(config_path, "r") as config_file:
        config = yaml.safe_load(config_file)

    if config is None:
        raise Exception("Unable to load config file")

    return config


def resize_and_move(file_path, out_dir, resolution, prefix):
    result = subprocess.run(
        [
            "convert",
            file_path,
            "-resize",
            "{}^".format(resolution),
            "-gravity",
            "center",
            "-extent",
            resolution,
            os.path.join(out_dir, "{}_{}".format(prefix, os.path.split(file_path)[1])),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if result.returncode:
        print("Error resizing {}".format(file_path))


def create_tmp_video(config):
    photo_list = glob.glob(
        os.path.join(config["out_tmp_dir"], "{}_*.jpg".format(config["name"]))
    )
    if len(photo_list) < config["fps"]:
        return

    photo_files_path = os.path.join(
        config["out_tmp_dir"], "{}_photo_files.txt".format(config["name"])
    )

    with open(photo_files_path, "w") as outfile:
        print("Writing to {}".format(photo_files_path))
        for photo_path in sorted(photo_list):
            outfile.write("file '{}'\n".format(photo_path))

    outfile = create_timelapse(config, photo_files_path)
    os.remove(photo_files_path)

    if outfile is not None:
        for photo in sorted(photo_list):
            os.remove(photo)

    return outfile


def create_timelapse(config, photo_files_path):
    print("Creating timelapse for {}".format(photo_files_path))

    outfile = os.path.join(config["out_tmp_dir"], "{}_tmp.mp4".format(config["name"]))

    result = subprocess.run(
        [
            "ffmpeg",
            "-f",
            "concat",
            "-r",
            str(config["fps"]),
            "-safe",
            "0",
            "-y",
            "-i",
            photo_files_path,
            "-vcodec",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            outfile,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if result.returncode:
        print(result.stdout.decode("utf-8"))
        print(result.stderr.decode("utf-8"))
        print("Error creating {}".format(outfile))
        return None
    else:
        return outfile


def concat_videos(config, files, outfile):

    if len(files) < 2:
        return None

    concat_files_path = os.path.join(
        config["out_tmp_dir"], "{}_concat.txt".format(config["name"])
    )

    with open(concat_files_path, "w") as concat_file:
        print("Writing to {}".format(concat_files_path))
        for file in files:
            concat_file.write("file '{}'\n".format(file))

    start_time = time.time()
    result = subprocess.run(
        [
            "ffmpeg",
            "-f",
            "concat",
            "-r",
            str(config["fps"]),
            "-safe",
            "0",
            "-y",
            "-i",
            concat_files_path,
            "-vcodec",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c",
            "copy",
            outfile,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    print("Concat duration: {}".format(time.time() - start_time))

    os.remove(concat_files_path)

    if result.returncode:
        print(result.stdout.decode("utf-8"))
        print(result.stderr.decode("utf-8"))
        print("Error creating {}".format(outfile))
        return None
    else:
        return outfile


def process_photo(config, photo_path):
    # Don't mess with other files
    if ".jpg" in photo_path:
        resize_and_move(
            photo_path, config["out_tmp_dir"], config["resolution"], config["name"]
        )

    tmp_video_filename = create_tmp_video(config)
    main_video_filename = os.path.join(
        config["out_dir"], "{}.mp4".format(config["name"])
    )
    if tmp_video_filename:
        if os.path.exists(main_video_filename):
            print("Joining videos", main_video_filename, tmp_video_filename)
            concat_outfile = tempfile.mktemp(".mp4")
            concat_file = concat_videos(
                config, [main_video_filename, tmp_video_filename], concat_outfile
            )
            if concat_file is not None:
                os.replace(concat_outfile, main_video_filename)
                os.remove(tmp_video_filename)
        else:
            print("Moving video", tmp_video_filename, main_video_filename)
            shutil.move(tmp_video_filename, main_video_filename)


class FSChangeHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config

    def on_moved(self, event):
        print(self.config["name"], event.dest_path)
        process_photo(self.config, event.dest_path)


parser = argparse.ArgumentParser()
parser.add_argument("config", help="Config file location")
parser.add_argument(
    "--test", action="store_true", help="Test mode. Run on all files from source dir"
)

args = parser.parse_args()

if not os.path.exists(args.config):
    raise Exception("Config file not found.")

config = load_config(args.config)

observer = Observer()
for timelapse in config["timelapses"]:
    if not os.path.exists(timelapse["src_dir"]):
        print("{} not found. Creating".format(timelapse["src_dir"]))
        os.makedirs(timelapse["src_dir"], exist_ok=True)

    if not os.path.exists(timelapse["out_dir"]):
        print("{} not found. Creating".format(timelapse["out_dir"]))
        os.makedirs(timelapse["out_dir"], exist_ok=True)

    if not os.path.exists(timelapse["out_tmp_dir"]):
        print("{} not found. Creating".format(timelapse["out_tmp_dir"]))
        os.makedirs(timelapse["out_tmp_dir"], exist_ok=True)

    if args.test:
        for photo in sorted(glob.glob(os.path.join(timelapse["src_dir"], "*.jpg"))):
            process_photo(timelapse, photo)
    else:
        event_handler = FSChangeHandler(timelapse)
        observer.schedule(event_handler, timelapse["src_dir"])

if not args.test:
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
