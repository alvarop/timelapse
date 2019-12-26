import os
import time
import tempfile
import subprocess
import yaml
from datetime import datetime, timedelta
from flask import Flask, request, g, render_template, send_file, redirect
from v4l2 import v4l2


app = Flask(__name__)
app.config.from_pyfile("default_config")
app.config.from_envvar("TIMELAPSE_UI_SETTINGS", silent=True)


def load_config(config_path):
    with open(config_path, "r") as config_file:
        config = yaml.safe_load(config_file)

    if config is None:
        raise Exception("Unable to load config file")

    return config


gen_config = load_config(app.config["TIMELAPSE_GEN_CONFIG"])


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


@app.route("/")
def root():
    cam_control = v4l2.V4L2()
    return render_template("preview.html", controls=cam_control.controls)


@app.route("/update_settings", methods=["POST"])
def update_settings():
    cam_control = v4l2.V4L2()
    for item, value in request.form.items():
        control = cam_control.controls[item]
        if control.limits.get("flags") != "inactive" and control.get() != int(value):
            print("updating", item, value)
            control.set(int(value))
    return "OK"


@app.route("/default_settings", methods=["GET", "POST"])
def default_settings():
    cam_control = v4l2.V4L2()
    for name, control in cam_control.controls.items():
        if control.limits.get("flags") != "inactive":
            control.set(control.limits["default"])
            print("updating", name, control.limits["default"])
    return redirect("/")


@app.route("/preview_photo")
def preview_photo():
    filename = take_photo()
    if filename is None:
        return "Error"

    response = send_file(
        filename, mimetype="image/jpeg", attachment_filename="preview.jpg"
    )
    response.headers["Content-Disposition"] = 'inline; filename="preview.jpg"'
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Cache-Control"] = "public, max-age=0"

    return response


@app.route("/videos")
def videos():

    videos = []
    for config in gen_config["timelapses"]:

        video_path = os.path.join(config["out_dir"], "{}.mp4".format(config["name"]))
        if os.path.exists(video_path):
            videos.append({"name": config["name"], "resolution": config["resolution"]})

    return render_template("videos.html", videos=videos)


@app.route("/video/<name>")
def video(name):

    video = None
    for config in gen_config["timelapses"]:
        if name != config["name"]:
            continue
        video_path = os.path.join(config["out_dir"], "{}.mp4".format(config["name"]))
        if os.path.exists:
            video = video_path
            break

    video_filename = os.path.split(video_path)[1]

    response = send_file(
        video_path, mimetype="video/mp4", attachment_filename=video_filename
    )
    response.headers["Content-Disposition"] = 'inline; filename="{}"'.format(
        video_filename
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Cache-Control"] = "public, max-age=0"

    return response
