import os
import time
import tempfile
import subprocess
from datetime import datetime, timedelta
from flask import Flask, request, g, render_template, send_file, redirect
from v4l2 import v4l2

app = Flask(__name__)


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
