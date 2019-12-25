import subprocess


class V4L2_Ctrl:
    def __init__(self, control_string, device):
        self.limits = {}
        self.name = None
        self.type = None
        self.value = None
        self.device = device

        description, limits = control_string.split(":")
        description = description.strip()

        self.name, address, data_type = description.split(" ")
        self.type = data_type.strip("()")

        # TODO - list control menu options

        for limit_str in limits.strip().split(" "):
            name, value = limit_str.split("=")
            if name == "value":
                self.value = int(value)
            else:
                try:
                    self.limits[name] = int(value)
                except ValueError:
                    self.limits[name] = value

    def get(self):
        result = subprocess.run(
            ["v4l2-ctl", "-d", str(self.device), "-C", self.name],
            stdout=subprocess.PIPE,
        )
        name, value = result.stdout.decode("utf-8").strip().split(": ")
        if name != self.name:
            raise ValueError("Invalid control name")

        if value is None:
            raise ValueError("Invalid value")
        else:
            self.value = int(value)

        return self.value

    def set(self, value):

        # Make sure value is within limits (if any)
        if "min" in self.limits and value < self.limits["min"]:
            raise ValueError("Invalid value (min)")

        if "max" in self.limits and value > self.limits["max"]:
            raise ValueError("Invalid value (max)")

        # Set limit
        result = subprocess.run(
            [
                "v4l2-ctl",
                "-d",
                str(self.device),
                "-c",
                "{}={}".format(self.name, value),
            ],
            stdout=subprocess.PIPE,
        )
        output = result.stdout.decode("utf-8").strip()

        # OK result means no output. If anything returns we have a problem
        if len(output) > 0:
            print(output)
            raise ValueError("Unable to set value")

        # Verify the new value matches the setting
        if self.get() != value:
            print("WARNING Value does not match. {} {}".format(value, self.value))

        return self.value

    def __repr__(self):
        string = "V4L2_Ctrl({} ({}) value={})[{}]".format(
            self.name, self.type, self.value, self.limits
        )
        return string


class V4L2:
    def __init__(self, device=0):
        self.device = device
        self.controls = {}
        self.get_ctrls(self.device)

    def get_ctrls(self, device):
        result = subprocess.run(
            ["v4l2-ctl", "-d", str(self.device), "-l"], stdout=subprocess.PIPE
        )
        for line in result.stdout.decode("utf-8").split("\n"):
            control_string = line.strip()
            if len(control_string) > 0:
                control = V4L2_Ctrl(control_string, self.device)
                self.controls[control.name] = control


def list_devices():
    """
    Return list of tuples with all available v4l devices.
    Tuple format is: (device_id, device_path, name/description)
    """
    devices = []

    result = subprocess.run(["v4l2-ctl", "--list-devices"], stdout=subprocess.PIPE)
    output_lines = result.stdout.decode("utf-8").replace(":\n\t", "\0")
    for line in output_lines.split("\n"):
        if "\0" in line:
            name, device_path = line.split("\0")
            device_id = int(device_path.replace("/dev/video", ""))
            devices.append((device_id, device_path, name))

    return devices


if __name__ == "__main__":
    v4l2 = V4L2(0)
