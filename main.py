import os
import re
import sys
import time
import math
import queue
import ctypes
import sv_ttk
import pystray
import keyword
import threading
import darkdetect
import pywinstyles
import core as core
import tkinter as tk
from PIL import Image
from tkinter import ttk
from pystray import MenuItem as item

ctypes.windll.shcore.SetProcessDpiAwareness(1)
ctypes.windll.kernel32.SetConsoleTitleW("Winpower console")

changes = {}
timer_threads = []
stop_threads = False
update_queue = queue.Queue()
default_options = [
    "5 minutes",
    "10 minutes",
    "15 minutes",
    "1 hour",
    "5 hours",
    "Never",
]


def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    print(f"An error occurred: {exc_value}")


sys.excepthook = global_exception_handler


def titlebar_theme(root):
    version = sys.getwindowsversion()
    if version.major == 10 and version.build >= 22000:
        pywinstyles.change_header_color(
            root, "#1c1c1c" if sv_ttk.get_theme() == "dark" else "#fafafa"
        )
    elif version.major == 10:
        pywinstyles.apply_style(
            root, "dark" if sv_ttk.get_theme() == "dark" else "normal"
        )
        root.wm_attributes("-alpha", 0.99)
        root.wm_attributes("-alpha", 1)


def process_time(value):
    if value.lower() == "never":
        return 0

    value = value.lower().replace(" ", "")
    if not value:
        return 0

    time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    total_seconds = 0
    pattern = re.compile(r"(\d+\.?\d*)([smhd])")
    matches = pattern.findall(value)

    if not matches:
        if value.isdigit() or ("." in value and value.replace(".", "", 1).isdigit()):
            total_seconds += float(value) * time_units["m"]
    else:
        for number, unit in matches:
            if number:
                number = float(number) if "." in number else int(number)
                total_seconds += number * time_units[unit]

    return math.ceil(total_seconds)


def play_sound():
    user32 = ctypes.WinDLL("user32")
    user32.MessageBeep(0x00000040)


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def add_timer(text, duration):
    global stop_threads
    clear_all_timers()

    try:
        duration = int(duration)
    except ValueError:
        return

    row = len(timer_frame.winfo_children())
    timer_label = tk.Label(timer_frame, text=f"{text} - {duration}")
    timer_label.grid(row=row, column=0, padx=10, pady=(8, 10))

    def run_timer():
        global stop_threads
        for i in range(duration, 0, -1):
            if stop_threads:
                return
            timer_label.config(text=f"{text} - {i}")
            time.sleep(1)
        if not stop_threads:
            timer_label.config(text=f"{text} - Done")
            play_sound()
            action = {
                "Shutdown after": core.shutdown_device,
                "Restart after": core.restart_device,
                "Lock after": core.lock_device,
                "Run script after": run_script,
            }.get(text)
            if action:
                action()

    timer_thread = threading.Thread(target=run_timer)
    timer_threads.append(timer_thread)
    timer_thread.start()


def clear_all_timers(reload=False):
    global stop_threads
    stop_threads = True
    for thread in timer_threads:
        thread.join()
    stop_threads = False
    timer_threads.clear()

    for widget in timer_frame.winfo_children():
        widget.destroy()

    if reload:
        tk.Label(timer_frame, text="None").grid(row=0, column=0, padx=10, pady=(8, 10))


def minimize_to_tray(icon, item):
    global tray_icon
    if tray_icon is None:
        setup_tray()
    root.withdraw()
    tray_icon.visible = True


def restore_from_tray(icon, item):
    root.deiconify()
    root.state("normal")
    if icon:
        icon.visible = False


def quit_app(icon, item):
    if icon is not None:
        icon.visible = False
        icon.stop()
    root.quit()
    os._exit(1)


def run_script():
    exec(textarea.get("1.0", "end-1c"))


def setup_tray():
    global tray_icon

    if hasattr(sys, "_MEIPASS"):
        icon_path = os.path.join(sys._MEIPASS, "icon.ico")
    else:
        icon_path = "icon.ico"

    icon_image = Image.open(icon_path)
    tray_icon = pystray.Icon("winpower", icon_image, "Winpower")

    tray_icon.menu = pystray.Menu(
        item("Restore", lambda: restore_from_tray(tray_icon, None), default=True),
        item("Quit", lambda: quit_app(tray_icon, None)),
    )

    tray_icon.run_detached()


def create_window():

    ## ---- Comment this code block when testing (make sure to run terminal with admin perms)
    # if not is_admin():
    #     ctypes.windll.shell32.ShellExecuteW(
    #         None, "runas", sys.executable, os.path.abspath(sys.argv[0]), None, 1
    #     )
    #     sys.exit()

    # hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    # if hwnd:
    #     ctypes.windll.user32.ShowWindow(hwnd, 0)
    ## ----

    global root
    global brightness_slider
    global tray_icon
    global timer_frame
    global textarea
    tray_icon = None
    root = tk.Tk()
    root.title("Winpower")
    root.iconbitmap(os.path.join(os.path.dirname(__file__), "icon.ico"))
    root.resizable(False, False)

    sv_ttk.set_theme(darkdetect.theme())
    titlebar_theme(root)

    # Save changes

    def save_changes():

        def worker():
            global changes
            for key in changes:
                if key == "power_mode":
                    core.set_power_mode(changes["power_mode"])
                    continue
                elif key == "hibernation":
                    if changes["hibernation"]:
                        core.enable_hibernation()
                    else:
                        core.disable_hibernation()
                    continue
                elif key == "brightness":
                    core.set_brightness(int(changes["brightness"]))
                elif key == "mouse_speed":
                    core.set_mouse_speed(int(changes["mouse_speed"]))
                elif key == "timer_event":
                    if "timer_time" in changes:
                        add_timer(
                            changes["timer_event"], process_time(changes["timer_time"])
                        )
                    else:
                        add_timer(changes["timer_event"], 500)
                elif key == "timer_time":
                    if "timer_event" in changes:
                        add_timer(
                            changes["timer_event"], process_time(changes["timer_time"])
                        )
                    else:
                        add_timer("Shutdown after", process_time(changes["timer_time"]))

                value = changes[key]

                if isinstance(value, str):
                    time = process_time(value)
                    if key == "battery_screen":
                        core.set_screen_timeout(time, "DC")
                    elif key == "plugged_screen":
                        core.set_screen_timeout(time, "AC")
                    elif key == "battery_sleep":
                        core.set_sleep_timeout(time, "DC")
                    elif key == "plugged_sleep":
                        core.set_sleep_timeout(time, "AC")

            play_sound()
            timer_time.set("10 minutes")
            changes = {}
            clear_pending()

        threading.Thread(target=worker).start()

    # • Tabs
    notebook = ttk.Notebook(root)
    power_tab = ttk.Frame(notebook)
    timer_tab = ttk.Frame(notebook)
    script_tab = ttk.Frame(notebook)
    other_tab = ttk.Frame(notebook)
    pending_tab = ttk.Frame(notebook)
    info_tab = ttk.Frame(notebook)

    notebook.add(power_tab, text="Power")
    notebook.add(timer_tab, text="Timer")
    notebook.add(script_tab, text="Script")
    notebook.add(other_tab, text="Other")
    notebook.add(pending_tab, text="Pending")
    notebook.add(info_tab, text="Info")
    notebook.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

    # • Pending tab

    def on_frame_configure(canvas):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def on_mousewheel(event, canvas):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    pending_tab.columnconfigure(0, weight=1)
    pending_tab.rowconfigure(0, weight=1)

    canvas = tk.Canvas(pending_tab, highlightthickness=0)
    canvas.grid(row=0, column=0, sticky="nsew")

    scrollbar = ttk.Scrollbar(pending_tab, orient="vertical", command=canvas.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")

    canvas.configure(yscrollcommand=scrollbar.set)

    scrollable_frame = ttk.Frame(canvas)
    scrollable_frame.bind("<Configure>", lambda e: on_frame_configure(canvas))

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

    scrollable_frame.bind("<MouseWheel>", lambda e: on_mousewheel(e, canvas))

    scrollable_frame.columnconfigure(0, weight=0)
    scrollable_frame.columnconfigure(1, weight=1)
    scrollable_frame.columnconfigure(2, weight=0)

    def add_change(text, key, value):
        for widget in scrollable_frame.winfo_children():
            if (
                isinstance(widget, ttk.Frame)
                and widget.winfo_children()[0].cget("text") == text
            ):
                remove_item(widget, key)
                break

        changes[key] = value
        parent = ttk.Frame(scrollable_frame)
        parent.grid(sticky="ew", padx=10, pady=5)

        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=0)

        tk.Label(parent, text=text).grid(row=0, column=0, sticky="w", pady=5)

        ttk.Button(
            parent, text="Remove", command=lambda: remove_item(parent, key)
        ).grid(row=0, column=1, padx=(20, 0), pady=(3, 0), sticky="e")

    def remove_item(parent, key):
        if key in changes:
            del changes[key]
        parent.grid_forget()
        parent.destroy()

    def clear_pending():
        global changes
        changes = {}

        for widget in scrollable_frame.winfo_children():
            widget.grid_forget()
            widget.destroy()

    def bind_combobox(text, combobox, var_name):
        combobox.initial_value = combobox.get()

        combobox.bind(
            "<<ComboboxSelected>>",
            lambda e: [
                add_change(text, var_name, combobox.get()),
                combobox.selection_clear(),
            ],
        )

        combobox.bind(
            "<FocusIn>", lambda e: setattr(combobox, "initial_value", combobox.get())
        )

        combobox.bind(
            "<FocusOut>",
            lambda e: (
                [add_change(text, var_name, combobox.get()), combobox.selection_clear()]
                if combobox.get() != combobox.initial_value
                else None
            ),
        )

    # • Power tab

    power_tab.columnconfigure(0, weight=0)
    power_tab.columnconfigure(1, weight=1)
    power_tab.columnconfigure(2, weight=0)

    # – On Battery Power Section

    battery_frame = ttk.LabelFrame(power_tab, text=" On battery power ")
    battery_frame.grid(
        row=0, column=0, columnspan=3, padx=10, pady=(10, 5), sticky="ew"
    )

    tk.Label(battery_frame, text="Turn off screen after").grid(
        row=0, column=0, padx=10, pady=5, sticky="w"
    )
    global battery_screen
    battery_screen = ttk.Combobox(battery_frame, values=default_options)
    battery_screen.grid(row=0, column=1, padx=(130, 0), pady=5, sticky="e")
    bind_combobox(
        "On battery power, turn off screen after", battery_screen, "battery_screen"
    )

    tk.Label(battery_frame, text="Sleep after").grid(
        row=1, column=0, padx=10, pady=5, sticky="w"
    )
    global battery_sleep
    battery_sleep = ttk.Combobox(battery_frame, values=default_options)
    battery_sleep.grid(row=1, column=1, padx=(130, 0), pady=(5, 15), sticky="e")
    bind_combobox("On battery power, sleep after", battery_sleep, "battery_sleep")

    # – When Plugged In Section

    plugged_frame = ttk.LabelFrame(power_tab, text=" When plugged in ")
    plugged_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=5, sticky="ew")

    tk.Label(plugged_frame, text="Turn off screen after").grid(
        row=0, column=0, padx=10, pady=5, sticky="w"
    )
    global plugged_screen
    plugged_screen = ttk.Combobox(plugged_frame, values=default_options)
    plugged_screen.grid(row=0, column=1, padx=(130, 0), pady=5, sticky="e")
    bind_combobox(
        "When plugged in, turn off screen after", plugged_screen, "plugged_screen"
    )

    tk.Label(plugged_frame, text="Sleep after").grid(
        row=1, column=0, padx=10, pady=5, sticky="w"
    )
    global plugged_sleep
    plugged_sleep = ttk.Combobox(plugged_frame, values=default_options)
    plugged_sleep.grid(row=1, column=1, padx=(130, 0), pady=(5, 15), sticky="e")
    bind_combobox("When plugged in, sleep after", plugged_sleep, "plugged_sleep")

    # – Power Mode

    tk.Label(power_tab, text="Power mode").grid(
        row=2, column=0, padx=10, pady=5, sticky="w"
    )

    global power_mode
    power_mode = ttk.Combobox(
        power_tab,
        values=["Best power efficiency", "Balanced", "Best performance"],
        state="readonly",
    )
    power_mode.grid(row=2, column=1, padx=(50, 22), pady=(5, 10), sticky="e")
    bind_combobox("Power mode", power_mode, "power_mode")

    # – Hibernation

    def toggle_hibernation():
        if hibernation_var.get():
            add_change("Hibernation - Enabled", "hibernation", True)
        else:
            add_change("Hibernation - Disabled", "hibernation", False)

    hibernation_var = tk.BooleanVar()

    tk.Label(power_tab, text="Hibernation").grid(
        row=3, column=0, padx=10, pady=5, sticky="w"
    )
    ttk.Checkbutton(
        power_tab, variable=hibernation_var, command=toggle_hibernation
    ).grid(row=3, column=1, padx=(50, 19), pady=(5, 10), sticky="e")

    # • Timer tab

    timer_tab.columnconfigure(0, weight=0)
    timer_tab.columnconfigure(1, weight=1)
    timer_tab.columnconfigure(2, weight=0)

    global timer_event
    timer_event = ttk.Combobox(
        timer_tab,
        width=12,
        values=["Shutdown after", "Restart after", "Lock after", "Run script after"],
        state="readonly",
    )
    timer_event.grid(row=0, column=0, padx=10, pady=(15, 0), sticky="w")
    timer_event.set("Shutdown after")
    bind_combobox(f"Timer event - {timer_event}", timer_event, "timer_event")

    global timer_time
    timer_time = ttk.Combobox(timer_tab, values=default_options[:-1])
    timer_time.grid(row=0, column=1, padx=(90, 12), pady=(15, 0), sticky="e")
    timer_time.set("10 minutes")
    bind_combobox("Timer time", timer_time, "timer_time")

    timer_info_frame = ttk.LabelFrame(timer_tab, text=" Usage information ")
    timer_info_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=15, sticky="ew")

    tk.Label(
        timer_info_frame,
        text=(
            "You must change any of the above input fields to put timer in pending changes. Click 'Save' to start the timer (also applies all pending changes). Click 'Cancel' to cancel the timer (this also cancels any pending changes)."
        ),
        anchor="w",
        justify="left",
        wraplength=480,
    ).grid(row=0, column=0, padx=10, pady=(8, 10))

    timer_frame = ttk.LabelFrame(timer_tab, text=" Active timer ")
    timer_frame.grid(row=2, column=0, columnspan=3, padx=10, pady=(0, 15), sticky="ew")

    tk.Label(timer_frame, text="None").grid(row=0, column=0, padx=10, pady=(8, 10))

    # • Script tab

    def apply_syntax_highlighting_thread(event=None):
        threading.Thread(target=apply_syntax_highlighting).start()

    def apply_syntax_highlighting():
        text = textarea.get("1.0", "end-1c")

        def highlight():
            textarea.tag_remove("keyword", "1.0", "end")
            textarea.tag_remove("string", "1.0", "end")
            textarea.tag_remove("comment", "1.0", "end")
            textarea.tag_remove("number", "1.0", "end")
            textarea.tag_remove("function", "1.0", "end")
            textarea.tag_remove("operator", "1.0", "end")
            textarea.tag_remove("bracket", "1.0", "end")

            for match in re.finditer(r"#.*", text):
                start_idx = f"1.0+{match.start()}c"
                end_idx = f"1.0+{match.end()}c"
                textarea.tag_add("comment", start_idx, end_idx)

            for match in re.finditer(
                r"(\"\"\".*?\"\"\"|\'\'\'.*?\'\'\'|\".*?\"|\'.*?\')", text, re.DOTALL
            ):
                start_idx = f"1.0+{match.start()}c"
                end_idx = f"1.0+{match.end()}c"
                textarea.tag_add("string", start_idx, end_idx)

            for word in text.split():
                if keyword.iskeyword(word):
                    idx = textarea.search(
                        rf"\b{word}\b", "1.0", stopindex="end", regexp=True
                    )
                    while idx:
                        end_idx = f"{idx}+{len(word)}c"
                        textarea.tag_add("keyword", idx, end_idx)
                        idx = textarea.search(
                            rf"\b{word}\b", end_idx, stopindex="end", regexp=True
                        )

            for match in re.finditer(r"\b\d+(\.\d+)?\b", text):
                start_idx = f"1.0+{match.start()}c"
                end_idx = f"1.0+{match.end()}c"
                textarea.tag_add("number", start_idx, end_idx)

            for match in re.finditer(r"\b(def|class)\s+(\w+)", text):
                start_idx = f"1.0+{match.start(2)}c"
                end_idx = f"1.0+{match.end(2)}c"
                textarea.tag_add("function", start_idx, end_idx)

            for match in re.finditer(r"[\+\-\*/%=<>!&|^~]", text):
                start_idx = f"1.0+{match.start()}c"
                end_idx = f"1.0+{match.end()}c"
                textarea.tag_add("operator", start_idx, end_idx)

            for match in re.finditer(r"[\(\)\[\]\{\}]", text):
                start_idx = f"1.0+{match.start()}c"
                end_idx = f"1.0+{match.end()}c"
                textarea.tag_add("bracket", start_idx, end_idx)

        root.after(0, highlight)

    textarea = tk.Text(
        script_tab,
        wrap="word",
        width=47,
        height=11.4,
        padx=15,
        pady=15,
        fg="#fff",
        bg="#212121",
        bd=0,
        highlightthickness=1,
        highlightcolor="#3d3d3d",
    )
    textarea.grid(row=0, column=0, sticky="nsew", pady=15, padx=15)
    textarea.insert(
        "1.0",
        'ctypes.windll.user32.MessageBoxW(0, "Donate -> https://www.patreon.com/axorax", "Winpower", 0x00000000 | 0x00000040)',
    )

    textarea.tag_configure("keyword", foreground="#66d9ef")
    textarea.tag_configure("string", foreground="#e6db74")
    textarea.tag_configure("comment", foreground="#75715e")
    textarea.tag_configure("number", foreground="#ae81ff")
    textarea.tag_configure("function", foreground="#a6e22e")
    textarea.tag_configure("operator", foreground="#f92672")
    textarea.tag_configure("bracket", foreground="#f8f8f2")

    textarea.bind("<KeyRelease>", apply_syntax_highlighting_thread)

    apply_syntax_highlighting_thread()

    script_button = ttk.Button(script_tab, text="Run Script", command=run_script)
    script_button.grid(row=1, column=0, sticky="ew", padx=15)

    # • Other tab

    other_tab.columnconfigure(0, weight=0)
    other_tab.columnconfigure(1, weight=1)
    other_tab.columnconfigure(2, weight=0)

    # – Brightness

    tk.Label(other_tab, text="Screen brightness").grid(
        row=1, column=0, padx=10, pady=5, sticky="w"
    )
    brightness_slider = ttk.Scale(
        other_tab,
        from_=0,
        to=100,
        orient="horizontal",
        command=lambda value: add_change(
            f"Brightness", "brightness", int(float(value))
        ),
        length=200,
    )
    brightness_slider.grid(row=1, column=1, padx=(50, 10), pady=10, sticky="e")

    # – Mouse speed

    tk.Label(other_tab, text="Mouse pointer speed").grid(
        row=2, column=0, padx=10, pady=5, sticky="w"
    )

    mouse_speed_slider = ttk.Scale(
        other_tab,
        from_=1,
        to=20,
        orient="horizontal",
        command=lambda value: add_change(
            f"Mouse speed", "mouse_speed", int(float(value))
        ),
        length=200,
    )
    mouse_speed_slider.grid(row=2, column=1, padx=(50, 10), pady=10, sticky="e")

    # – Battery report

    tk.Label(other_tab, text="Generate battery report").grid(
        row=3, column=0, padx=10, pady=5, sticky="w"
    )
    ttk.Button(
        other_tab,
        text=" Generate ",
        command=lambda: threading.Thread(
            target=lambda: [core.generate_battery_report(), play_sound()]
        ).start(),
    ).grid(row=3, column=1, padx=(50, 10), pady=10, sticky="e")

    # – Sleepstudy report

    tk.Label(other_tab, text="Generate sleepstudy report").grid(
        row=4, column=0, padx=10, pady=5, sticky="w"
    )
    ttk.Button(
        other_tab,
        text=" Generate ",
        command=lambda: threading.Thread(
            target=lambda: [core.generate_sleepstudy_report(), play_sound()]
        ).start(),
    ).grid(row=4, column=1, padx=(50, 10), pady=10, sticky="e")

    # – Lock device

    tk.Label(other_tab, text="Lock device").grid(
        row=5, column=0, padx=10, pady=5, sticky="w"
    )
    ttk.Button(
        other_tab,
        text="    Lock     ",
        command=lambda: threading.Thread(target=core.lock_device).start(),
    ).grid(row=5, column=1, padx=(50, 10), pady=10, sticky="e")

    # – Restart device

    tk.Label(other_tab, text="Restart device").grid(
        row=6, column=0, padx=10, pady=5, sticky="w"
    )
    ttk.Button(
        other_tab,
        text="  Restart   ",
        command=lambda: threading.Thread(target=core.restart_device).start(),
    ).grid(row=6, column=1, padx=(50, 10), pady=10, sticky="e")

    # – Shutdown device

    tk.Label(other_tab, text="Shutdown device").grid(
        row=7, column=0, padx=10, pady=5, sticky="w"
    )
    ttk.Button(
        other_tab,
        text="Shutdown ",
        command=lambda: threading.Thread(target=core.shutdown_device).start(),
    ).grid(row=7, column=1, padx=(50, 10), pady=10, sticky="e")

    # → Set active values

    def set_active_values():
        t = core.get_timeouts()
        power_mode.set(core.get_power_mode())
        battery_screen.set(t["screen_dc"])
        battery_sleep.set(t["sleep_dc"])
        plugged_screen.set(t["screen_ac"])
        plugged_sleep.set(t["sleep_ac"])
        hibernation_var.set(core.get_hibernation())

        brightness_value = (
            core.get_brightness() if core.get_brightness() is not None else 50
        )
        brightness_slider.set(int(brightness_value))

        mouse_speed_value = (
            core.get_mouse_speed() if core.get_mouse_speed() is not None else 10
        )
        mouse_speed_slider.set(int(mouse_speed_value))

        changes.pop("brightness", None)
        changes.pop("mouse_speed", None)
        changes.pop("timer_event", None)
        clear_pending()

    set_active_values()

    # • Info tab

    def on_mouse_wheel_info(event):
        info_canvas.yview_scroll(-1 * int((event.delta / 120)), "units")

    info_canvas = tk.Canvas(info_tab, height=200)
    info_scrollbar = ttk.Scrollbar(
        info_tab, orient="vertical", command=info_canvas.yview
    )
    info_scrollable_frame = ttk.Frame(info_canvas)

    info_canvas.create_window((0, 0), window=info_scrollable_frame, anchor="nw")
    info_canvas.configure(yscrollcommand=info_scrollbar.set)

    info_label = tk.Label(
        info_scrollable_frame,
        text=(
            "In time input fields, you can use seconds, minutes, hours, and days. "
            "If no unit is specified, it will be treated as minutes. "
            "If a decimal is formed after converting to seconds, it will round up to the nearest integer.\n\nPending tasks will appear in the pending tab.\n\n"
            "s = seconds\nm = minutes\nh = hours\nd = days\n\n"
            "Example times:\n\n"
            "5s 10m 1h\n"
            "5 hours\n"
            "1 minute 3 hours\n"
            "500seconds\n"
            "500\n\n"
            "Scripts use the Python programming language. Some libraries are loaded in the app by default like ctypes, time, tkinter, pywinstyles, darkdetect, pystray, keyword, queue, threading, math, sys, re, os. You can also use any app functions. These include:\n\n"
            "core.get_mouse_speed()\n"
            "core.set_mouse_speed(INT)\n"
            "core.set_brightness(INT)\n"
            "core.get_brightness()\n"
            "core.generate_sleepstudy_report()\n"
            "core.generate_battery_report()\n"
            "core.get_hibernation()\n"
            "core.disable_hibernation()\n"
            "core.enable_hibernation()\n"
            "core.get_timeouts()\n"
            "core.reset_timeouts()\n"
            "core.set_sleep_timeout(INT(in seconds), STR(Power source: 'DC' or 'AC'))\n"
            "core.set_screen_timeout(INT(in seconds), STR(Power source: 'DC' or 'AC'))\n"
            "core.set_power_mode(STR)\n"
            "core.get_power_mode()\n"
            "core.lock_device()\n"
            "core.restart_device()\n"
            "core.shutdown_device()\n"
        ),
        anchor="w",
        justify="left",
        wraplength=480,
    )

    info_label.pack(padx=10, pady=10, anchor="w")

    info_scrollable_frame.bind(
        "<Configure>",
        lambda e: info_canvas.configure(scrollregion=info_canvas.bbox("all")),
    )
    info_canvas.bind_all("<MouseWheel>", on_mouse_wheel_info)

    info_canvas.pack(side="left", fill="both", expand=True)
    info_scrollbar.pack(side="right", fill="y")

    # • Bottom

    bottom_frame = ttk.Frame(root)
    bottom_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

    bottom_frame.columnconfigure(0, weight=0)
    bottom_frame.columnconfigure(1, weight=0)
    bottom_frame.columnconfigure(2, weight=1)
    bottom_frame.columnconfigure(3, weight=0)
    bottom_frame.columnconfigure(4, weight=0)

    dark_mode_var = tk.BooleanVar()
    dark_mode_checkbox = ttk.Checkbutton(
        bottom_frame,
        text="Invert theme",
        variable=dark_mode_var,
        command=sv_ttk.toggle_theme,
    )
    dark_mode_checkbox.grid(row=0, column=0, sticky="w")

    to_tray_button = ttk.Button(
        bottom_frame, text="To Tray", command=lambda: minimize_to_tray(tray_icon, None)
    )
    to_tray_button.grid(row=0, column=1, padx=(10, 0), sticky="w")

    global cancel_button
    cancel_button = ttk.Button(bottom_frame, text=" Cancel ", command=reload_app)
    cancel_button.grid(row=0, column=3, padx=(10, 0), sticky="e")

    save_button = ttk.Button(bottom_frame, text="    Save    ", command=save_changes)
    save_button.grid(row=0, column=4, padx=(10, 0), sticky="e")

    root.protocol("WM_DELETE_WINDOW", lambda: quit_app(tray_icon, None))

    sv_ttk.set_theme(darkdetect.theme())

    root.mainloop()


def reload_app():
    global root
    global changes
    clear_all_timers(True)
    root.destroy()
    changes = {}
    create_window()


if __name__ == "__main__":
    create_window()
