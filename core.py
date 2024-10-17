import os
import re
import ctypes
import subprocess

power_schemes = {
    "Best power efficiency": "a1841308-3541-4fab-bc81-f71556f20b4a",
    "Balanced": "381b4222-f694-41f0-9685-ff5bb260df2e",
    "Best performance": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
}

CREATE_NO_WINDOW = 0x08000000


def get_power_mode():
    try:
        output = subprocess.check_output(
            ["powercfg", "/getactivescheme"],
            encoding="utf-8",
            creationflags=CREATE_NO_WINDOW,
        )
        for mode, guid in power_schemes.items():
            if guid in output:
                return mode
        return "Unknown"
    except subprocess.CalledProcessError:
        return "Unknown"


def set_power_mode(mode):
    if mode in power_schemes:
        try:
            subprocess.check_call(
                ["powercfg", "/setactive", power_schemes[mode]],
                creationflags=CREATE_NO_WINDOW,
            )
            return f"Power mode set to {mode}"
        except subprocess.CalledProcessError:
            return "Failed to set power mode"
    return "Invalid mode"


def get_powercfg_value(subgroup_guid, setting_guid):
    command = ["powercfg", "/query", "SCHEME_CURRENT", subgroup_guid, setting_guid]
    result = subprocess.run(
        command, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW
    )
    output = result.stdout
    match_ac = re.search(r"Current AC Power Setting Index:\s+0x([0-9a-fA-F]+)", output)
    match_dc = re.search(r"Current DC Power Setting Index:\s+0x([0-9a-fA-F]+)", output)
    ac_value = int(match_ac.group(1), 16) if match_ac else None
    dc_value = int(match_dc.group(1), 16) if match_dc else None
    return ac_value, dc_value


def set_powercfg_value(subgroup_guid, setting_guid, seconds, power_source):
    command = []
    if power_source == "AC":
        command = [
            "powercfg",
            "/setacvalueindex",
            "SCHEME_CURRENT",
            subgroup_guid,
            setting_guid,
            str(seconds),
        ]
    elif power_source == "DC":
        command = [
            "powercfg",
            "/setdcvalueindex",
            "SCHEME_CURRENT",
            subgroup_guid,
            setting_guid,
            str(seconds),
        ]

    subprocess.run(command, creationflags=CREATE_NO_WINDOW)
    subprocess.run(
        ["powercfg", "/setactive", "SCHEME_CURRENT"], creationflags=CREATE_NO_WINDOW
    )


def set_screen_timeout(seconds, power_source):
    set_powercfg_value("SUB_VIDEO", "VIDEOIDLE", seconds, power_source)


def set_sleep_timeout(seconds, power_source):
    set_powercfg_value("SUB_SLEEP", "STANDBYIDLE", seconds, power_source)


def reset_timeouts():
    set_screen_timeout(600, "AC")
    set_sleep_timeout(1200, "AC")
    set_screen_timeout(600, "DC")
    set_sleep_timeout(1200, "DC")


def get_timeouts():
    def pretty(value):
        if value is None:
            return "Never (Couldn't fetch)"
        rounded_value = round(value / 60, 1)
        return "Never" if rounded_value == 0 else f"{rounded_value}m"


    sleep = get_powercfg_value("SUB_SLEEP", "STANDBYIDLE")
    screen = get_powercfg_value("SUB_VIDEO", "VIDEOIDLE")

    return {
        "screen_ac": pretty(screen[0]),
        "screen_dc": pretty(screen[1]),
        "sleep_ac": pretty(sleep[0]),
        "sleep_dc": pretty(sleep[1]),
    }


def enable_hibernation():
    try:
        subprocess.check_call(
            ["powercfg", "/hibernate", "on"], creationflags=CREATE_NO_WINDOW
        )
        return "Hibernation enabled"
    except subprocess.CalledProcessError:
        return "Failed to enable hibernation"


def disable_hibernation():
    try:
        subprocess.check_call(
            ["powercfg", "/hibernate", "off"], creationflags=CREATE_NO_WINDOW
        )
        return "Hibernation disabled"
    except subprocess.CalledProcessError:
        return "Failed to disable hibernation"


def get_hibernation():
    try:
        output = subprocess.check_output(
            ["powercfg", "/a"], encoding="utf-8", creationflags=CREATE_NO_WINDOW
        )
        return (
            "Hibernate" in output and "Hibernation has not been enabled." not in output
        )
    except subprocess.CalledProcessError:
        return False


def generate_battery_report():
    try:
        subprocess.check_call(
            ["powercfg", "/batteryreport"], creationflags=CREATE_NO_WINDOW
        )
        return True
    except subprocess.CalledProcessError:
        return False


def generate_sleepstudy_report():
    try:
        subprocess.check_call(
            ["powercfg", "/sleepstudy"], creationflags=CREATE_NO_WINDOW
        )
        return True
    except subprocess.CalledProcessError:
        return False


def get_brightness():
    try:
        cmd = [
            "powershell",
            "-Command",
            "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness).CurrentBrightness",
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW
        )

        if result.returncode != 0:
            raise Exception(result.stderr.strip())

        brightness = int(result.stdout.strip())
        return brightness

    except Exception as e:
        return None


def set_brightness(brightness_value):
    try:
        if brightness_value < 0 or brightness_value > 100:
            raise ValueError("Brightness value must be between 0 and 100")

        cmd = [
            "powershell",
            "-Command",
            f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{brightness_value})",
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW
        )

        if result.returncode != 0:
            raise Exception(result.stderr.strip())

    except Exception as e:
        pass


def set_mouse_speed(speed):
    ctypes.windll.user32.SystemParametersInfoA(113, 0, speed, 0)


def get_mouse_speed():
    speed = ctypes.c_int()
    ctypes.windll.user32.SystemParametersInfoA(112, 0, ctypes.byref(speed), 0)

    return speed.value


def lock_device():
    ctypes.windll.user32.LockWorkStation()


def restart_device():
    os.system("shutdown /r /t 0")


def shutdown_device():
    os.system("shutdown /s /t 0")
