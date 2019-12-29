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


def save_config(config, config_path):
    with open(config_path, "w") as config_file:
        yaml.dump(config, config_file, default_flow_style=False)


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
    return redirect("/preview")


@app.route("/timelapse")
def timelapse():
    timelapse_settings = load_config(app.config["TIMELAPSE_CONFIG"])
    cam_ctrl = v4l2.V4L2(timelapse_settings["device"])
    resolutions = cam_ctrl.get_resolutions()
    resolutions_str = []
    for resolution in resolutions:
        resolutions_str.append("{}x{}".format(resolution[0], resolution[1]))

    if timelapse_settings["start_time"] is not None:
        localtime = time.localtime(int(timelapse_settings["start_time"]))
        start_day = time.strftime("%Y-%m-%d", localtime)
        start_time = time.strftime("%H:%M", localtime)
        timelapse_settings["start_time"] = (start_day, start_time)

    return render_template(
        "timelapse.html", settings=timelapse_settings, resolutions=resolutions_str
    )


INTEGER_SETTINGS = ["interval", "start_time", "duration"]
REQUIRED_SETTINGS = ["interval", "resolution", "out_dir", "prefix", "device"]


@app.route("/save_timelapse_settings", methods=["POST"])
def save_timelapse_settings():
    timelapse_settings = load_config(app.config["TIMELAPSE_CONFIG"])
    new_settings = timelapse_settings

    for item, value in request.form.items():
        if item == "start_date" or item == "start_time":
            continue
        elif item in INTEGER_SETTINGS:
            try:
                new_settings[item] = int(value)
            except ValueError:
                new_settings[item] = None
        else:
            new_settings[item] = value

    if request.form["start_date"] is not "" and request.form["start_date"] is not "":
        start_str = "{} {}".format(
            request.form["start_date"], request.form["start_time"]
        )
        new_settings["start_time"] = int(
            datetime.strptime(start_str, "%Y-%m-%d %H:%M").timestamp()
        )
    else:
        new_settings["start_time"] = None

    error_message = ""
    for key in REQUIRED_SETTINGS:
        if new_settings[key] is None or new_settings[key] is "":
            error_message += "Error: {} is required!<br />\n".format(key)

    if error_message is not "":
        return error_message
    else:
        save_config(new_settings, app.config["TIMELAPSE_CONFIG"])
        return "Settings Saved"


@app.route("/preview")
def preview():
    cam_control = v4l2.V4L2()
    return render_template("preview.html", controls=cam_control.controls)


@app.route("/update_settings", methods=["POST"])
def update_settings():

    cam_control = v4l2.V4L2()
    for item, value in request.form.items():
        control = cam_control.controls[item]
        print(item, value, control.limits.get("flags"), control.get(), int(value))
        if control.limits.get("flags") != "inactive" and control.get() != int(value):
            print("updating", item, value)
            control.set(int(value))
            control.set(int(value))
            control.set(int(value))

    camera_settings = {}
    for control_name, control in cam_control.controls.items():
        camera_settings[control_name] = control.value

    timelapse_settings = load_config(app.config["TIMELAPSE_CONFIG"])
    timelapse_settings["z_camera_settings"] = camera_settings
    save_config(timelapse_settings, app.config["TIMELAPSE_CONFIG"])

    return "OK"


@app.route("/default_settings", methods=["GET", "POST"])
def default_settings():
    cam_control = v4l2.V4L2()
    for name, control in cam_control.controls.items():
        if control.limits.get("flags") != "inactive":
            try:
                control.set(control.limits["default"])
            except ValueError:
                pass
            print("updating", name, control.limits["default"])

    # Read settings in again before saving
    cam_control = v4l2.V4L2()
    camera_settings = {}
    for control_name, control in cam_control.controls.items():
        camera_settings[control_name] = control.value

    timelapse_settings = load_config(app.config["TIMELAPSE_CONFIG"])
    timelapse_settings["z_camera_settings"] = camera_settings
    save_config(timelapse_settings, app.config["TIMELAPSE_CONFIG"])

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


@app.route("/video/<filename>")
def video(filename):
    name = filename.replace(".mp4", "")

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
