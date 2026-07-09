import threading
import time
import math
import queue
import tkinter as tk

import pyautogui
from pynput.keyboard import Controller as KeyboardController, Key
from pynput.mouse import Controller as MouseController, Button

from PIL import Image, ImageDraw, ImageTk

try:
    import vgamepad
except ImportError:
    vgamepad = None

try:
    from plyer import notification as plyer_notification
except ImportError:
    plyer_notification = None

from pyjoycon import (
    get_L_ids,
    get_R_ids,
    ButtonEventJoyCon
)


# =======================================================
# Thème visuel (sombre, dégradés, coins ronds)
# =======================================================

THEME = {
    "bg_top":       "#15122b",
    "bg_bottom":    "#1c1740",
    "panel_top":    "#2a2352",
    "panel_bottom": "#181430",
    "panel_border": "#3d3670",
    "accent":       "#8b5cf6",
    "accent_dark":  "#5b3fb0",
    "success":      "#2cd3a8",
    "success_dark": "#1a8c6f",
    "danger":       "#ff5d73",
    "danger_dark":  "#a83349",
    "text":         "#f4f2ff",
    "muted":        "#9089b5",
}

FONT_FAMILY = "Segoe UI"


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def make_rounded_gradient(width, height, radius, top_color, bottom_color,
                           border_color=None, border_width=0, horizontal=False):
    """Crée une image RGBA : rectangle à coins arrondis rempli d'un dégradé."""

    width = max(2, int(width))
    height = max(2, int(height))
    radius = max(0, min(radius, width // 2, height // 2))

    gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    top = hex_to_rgb(top_color)
    bottom = hex_to_rgb(bottom_color)
    draw = ImageDraw.Draw(gradient)

    if horizontal:
        for x in range(width):
            ratio = x / max(1, width - 1)
            r = int(top[0] + (bottom[0] - top[0]) * ratio)
            g = int(top[1] + (bottom[1] - top[1]) * ratio)
            b = int(top[2] + (bottom[2] - top[2]) * ratio)
            draw.line([(x, 0), (x, height)], fill=(r, g, b, 255))
    else:
        for y in range(height):
            ratio = y / max(1, height - 1)
            r = int(top[0] + (bottom[0] - top[0]) * ratio)
            g = int(top[1] + (bottom[1] - top[1]) * ratio)
            b = int(top[2] + (bottom[2] - top[2]) * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, width - 1, height - 1], radius=radius, fill=255
    )

    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    out.paste(gradient, (0, 0), mask)

    if border_color and border_width > 0:
        ImageDraw.Draw(out).rounded_rectangle(
            [border_width / 2, border_width / 2, width - 1 - border_width / 2, height - 1 - border_width / 2],
            radius=radius, outline=border_color, width=border_width
        )

    return out


# =======================================================
# Contrôleurs clavier / souris
# =======================================================

keyboard = KeyboardController()
mouse = MouseController()


# =======================================================
# États partagés
# =======================================================

mouse_left = False
mouse_right = False
b_toggle = False

last_scroll = 0
SCROLL_DELAY = 0.1

stick_calibration = None
left_stick_state = {"raw_x": 0.0, "raw_y": 0.0, "x": 0.0, "y": 0.0}
virtual_gamepad = None

left = None
right = None

home_held = False
GYRO_MOUSE_SENSITIVITY = 0.05  # à ajuster selon la sensibilité souhaitée

ui_queue = queue.Queue()

BUTTON_LAYOUT = [
    ["a", "b", "x", "y"],
    ["plus", "minus", "capture", "home"],
    ["zr", "zl", "right_sr", "left_sl"],
    ["left", "right", "up", "down"],
    ["l", "left_sr", "right_sl"]
]


# =======================================================
# Raccourcis clavier
# =======================================================

def hotkey(*keys):
    for key in keys:
        keyboard.press(key)
    for key in reversed(keys):
        keyboard.release(key)


# =======================================================
# Boutons pressés / relâchés (logique inchangée + notif UI)
# =======================================================

def button_pressed(name):
    global mouse_left, mouse_right, last_scroll, b_toggle, home_held

    ui_queue.put(("button", name, True))
    print( f"Button pressed: {name}" )

    if name == "a":
        keyboard.press(Key.space)

    elif name == "b":
        if not b_toggle:
            keyboard.press(Key.shift)
            b_toggle = True
        else:
            keyboard.release(Key.shift)
            b_toggle = False

    elif name == "plus":
        hotkey(Key.ctrl, Key.cmd, "o")
        pyautogui.moveTo(1400, 575)
        time.sleep(1)
        pyautogui.click()

    elif name == "y":
        hotkey(Key.ctrl)

    elif name == "x":
        keyboard.press("e")
        keyboard.release("e")

    elif name == "minus":
        keyboard.press(Key.esc)
        keyboard.release(Key.esc)

    elif name == "capture":
        hotkey(Key.alt, Key.cmd, "g")

    elif name == "zr":
        if not mouse_left:
            mouse.press(Button.left)
            mouse_left = True
        ui_queue.put(("mouse", "left", True))

    elif name == "zl":
        if not mouse_right:
            mouse.press(Button.right)
            mouse_right = True
        ui_queue.put(("mouse", "right", True))

    elif name == "right_sr":
        now = time.time()
        if now - last_scroll > SCROLL_DELAY:
            mouse.scroll(0, -1)
            last_scroll = now

    elif name == "left_sl":
        now = time.time()
        if now - last_scroll > SCROLL_DELAY:
            mouse.scroll(0, 1)
            last_scroll = now

    elif name == "home":
        home_held = True
    
    elif name == "left":
        keyboard.press( "1" )
        keyboard.release( "1" )
    
    elif name == "down":
        keyboard.press( "v" )
        keyboard.release( "v" )
    
    elif name == "up":
        keyboard.press( "f" )
        keyboard.release( "f" )
    
    elif name == "right":
        keyboard.press( "j" )
        keyboard.release( "j" )
    
    elif name == "l":
        hotkey( Key.alt, 'i' )
    
    elif name == "left_sr":
        hotkey( Key.alt, '8' )
    
    elif name == "right_sl":
        hotkey( Key.alt, '9' )


def button_released(name):
    global mouse_left, mouse_right, home_held

    ui_queue.put(("button", name, False))
    print( f"Button released: {name}" )
    if name == "zr":
        if mouse_left:
            mouse.release(Button.left)
            mouse_left = False
        ui_queue.put(("mouse", "left", False))

    elif name == "zl":
        if mouse_right:
            mouse.release(Button.right)
            mouse_right = False
        ui_queue.put(("mouse", "right", False))

    elif name == "a":
        keyboard.release(Key.space)

    elif name == "home":
        home_held = False


def process_events(events):
    for event in events:
        if not isinstance(event, tuple):
            continue
        name, state = event
        if state == 1:
            button_pressed(name)
        elif state == 0:
            button_released(name)


# =======================================================
# Calibration et lecture du stick gauche
# =======================================================

def sample_left_stick(controller, samples=20, delay=0.01):
    total_x = 0.0
    total_y = 0.0
    for _ in range(samples):
        total_x += controller.get_stick_left_horizontal()
        total_y += controller.get_stick_left_vertical()
        time.sleep(delay)
    return total_x / samples, total_y / samples


def normalize_left_stick(raw_x, raw_y, calibration):
    center_x = calibration["center_x"]
    center_y = calibration["center_y"]
    min_x = calibration["min_x"]
    max_x = calibration["max_x"]
    min_y = calibration["min_y"]
    max_y = calibration["max_y"]

    if raw_x >= center_x:
        x = (raw_x - center_x) / max(1e-6, max_x - center_x)
    else:
        x = (raw_x - center_x) / max(1e-6, center_x - min_x)

    if raw_y >= center_y:
        y = (raw_y - center_y) / max(1e-6, max_y - center_y)
    else:
        y = (raw_y - center_y) / max(1e-6, center_y - min_y)

    return max(-1.0, min(1.0, x)), max(-1.0, min(1.0, y))


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _encode_rumble_amplitude(amp):
    """Encode une amplitude 0.0-1.0 selon le format HD Rumble du Joy-Con."""
    amp = _clamp(amp, 0.0, 1.0)
    if amp <= 0.0:
        return 0
    if amp < 0.12:
        amp = 0.12  # plage basse non documentée : on remonte au minimum exploitable
    return int(round(math.log2(amp * 8.7) * 32.0))


def encode_rumble(freq_low=160.0, amp_low=0.6, freq_high=320.0, amp_high=0.6):
    """
    Construit les 8 octets de vibration HD Rumble attendus par le Joy-Con,
    d'après le protocole documenté par la communauté (dekuNukem/Nintendo_Switch_Reverse_Engineering).
    Le même motif de 4 octets est dupliqué pour les deux canaux (gauche/droite).
    """
    freq_low = _clamp(freq_low, 40.875, 626.286)
    freq_high = _clamp(freq_high, 81.751, 1252.572)

    enc_low = round(math.log2(freq_low / 10.0) * 32.0)
    enc_high = round(math.log2(freq_high / 10.0) * 32.0)

    hf = (enc_high - 0x60) * 4
    lf = enc_low - 0x40

    amp_h = _encode_rumble_amplitude(amp_high) * 2
    amp_l = _encode_rumble_amplitude(amp_low) // 2 + 0x40

    amp_h = _clamp(amp_h, 0, 0xFE)
    amp_l = _clamp(amp_l, 0x40, 0xFF)

    byte0 = hf & 0xFF
    byte1 = (amp_h + ((hf >> 8) & 0x01)) & 0xFF
    byte2 = lf & 0xFF
    byte3 = amp_l & 0xFF

    quarter = bytes([byte0, byte1, byte2, byte3])
    return quarter * 2


NEUTRAL_RUMBLE = b'\x00\x01\x40\x40\x00\x01\x40\x40'


def enable_vibration(joycon):
    """Active la vibration (sous-commande 0x48) avant de pouvoir envoyer un rumble."""
    if joycon is None:
        return
    try:
        joycon._write_output_report(b'\x01', b'\x48', b'\x01')
    except Exception as exc:
        print("Vibration : impossible de l'activer :", exc)


def send_rumble(joycon, freq_low=160.0, amp_low=0.6, freq_high=320.0, amp_high=0.6, duration=0.35):
    """
    Fait vibrer un Joy-Con pendant `duration` secondes.
    NOTE : la bibliothèque pyjoycon ne fournit pas d'API officielle de vibration ;
    ceci s'appuie sur le protocole HD Rumble documenté par la communauté et reste
    expérimental selon la version de la bibliothèque / du firmware du Joy-Con.
    """
    if joycon is None:
        return
    try:
        rumble_bytes = encode_rumble(freq_low, amp_low, freq_high, amp_high)
        joycon._RUMBLE_DATA = rumble_bytes
        end_time = time.time() + duration
        while time.time() < end_time:
            joycon._write_output_report(b'\x10', b'', b'')
            time.sleep(0.05)
    except Exception as exc:
        print("Vibration non disponible sur ce Joy-Con :", exc)
    finally:
        try:
            joycon._RUMBLE_DATA = NEUTRAL_RUMBLE
            joycon._write_output_report(b'\x10', b'', b'')
        except Exception:
            pass


def light_up_players(joycon, pattern=0x0F):
    """Allume les 4 lumières joueur du Joy-Con (best-effort, pattern 0x0F = toutes allumées)."""
    if joycon is None:
        return
    try:
        joycon.set_player_lamp_on(pattern)
    except AttributeError:
        try:
            joycon._write_output_report(b'\x01', b'\x30', bytes([pattern]))
        except Exception as exc:
            print("Lumières joueur non disponibles :", exc)
    except Exception as exc:
        print("Lumières joueur non disponibles :", exc)


def vibrate_low_battery_alert(joycon):
    """Fait vibrer le Joy-Con 5 fois de suite pour signaler une batterie faible."""
    if joycon is None:
        return
    for _ in range(5):
        send_rumble(joycon, duration=0.15)
        time.sleep(0.15)


def notify_low_battery(side_label):
    """Envoie une notification système via plyer."""
    if plyer_notification is None:
        print("plyer n'est pas installé (pip install plyer) : notification ignorée.")
        return
    try:
        plyer_notification.notify(
            title="Batterie Joy-Con faible",
            message=f"Le Joy-Con {side_label} est presque déchargé, pensez à le recharger.",
            timeout=10,
        )
    except Exception as exc:
        print("Notification impossible :", exc)


BATTERY_LOW_THRESHOLD = 1  # niveau pyjoycon : 0=vide, 1=critique, 2=faible, 3=moyenne, 4=pleine
_battery_alert_sent = {"left": False, "right": False}


def battery_loop():
    """Interroge périodiquement le niveau de batterie des deux Joy-Con."""
    while True:
        for side, joycon, label in (("left", left, "gauche"), ("right", right, "droit")):
            if joycon is None:
                continue
            try:
                status = joycon.get_status()
                battery = status.get("battery", {})
                level = battery.get("level")
                charging = bool(battery.get("charging"))
            except Exception:
                continue

            if level is None:
                continue

            ui_queue.put(("battery", side, level, charging))

            if charging or level > BATTERY_LOW_THRESHOLD:
                _battery_alert_sent[side] = False
            elif not _battery_alert_sent[side]:
                _battery_alert_sent[side] = True
                threading.Thread(target=vibrate_low_battery_alert, args=(joycon,), daemon=True).start()
                threading.Thread(target=notify_low_battery, args=(label,), daemon=True).start()

        time.sleep(15)


def update_left_stick_state():
    global left_stick_state, virtual_gamepad

    if stick_calibration is None or left is None:
        return

    raw_x = left.get_stick_left_horizontal()
    raw_y = left.get_stick_left_vertical()
    nx, ny = normalize_left_stick(raw_x, raw_y, stick_calibration)

    left_stick_state.update({"raw_x": raw_x, "raw_y": raw_y, "x": nx, "y": ny})
    ui_queue.put(("stick", nx, ny, raw_x, raw_y))

    if virtual_gamepad is not None:
        virtual_gamepad.left_joystick_float(nx, ny)
        virtual_gamepad.update()


# =======================================================
# Boucles Joy-Con (threads d'arrière-plan)
# =======================================================

def left_loop():
    while True:
        events = left.events()
        if events:
            process_events(events)
        time.sleep(0.001)


def right_loop():
    while True:
        events = right.events()
        if events:
            process_events(events)
        time.sleep(0.001)


def left_stick_loop():
    while True:
        update_left_stick_state()
        time.sleep(0.01)


def right_gyro_mouse_loop():
    """
    Déplace la souris avec le gyroscope de la manette droite, mais UNIQUEMENT
    tant que le bouton HOME est maintenu enfoncé. Dès qu'il est relâché,
    la souris ne bouge plus.
    """
    while True:
        if home_held and right is not None:
            try:
                gx = right.get_gyro_y()
                gy = right.get_gyro_z()
            except Exception:
                gx = gy = 0

            # Sens/axes à ajuster selon l'orientation de tenue de la manette.
            dx = int(gy * GYRO_MOUSE_SENSITIVITY)
            dy = int(-gx * GYRO_MOUSE_SENSITIVITY)

            if dx or dy:
                cx, cy = mouse.position
                mouse.position = (cx + dx, cy + dy)

        time.sleep(0.01)


# =======================================================
# Interface graphique
# =======================================================

class RoundedPanel:
    """Un panneau (carte) à coins ronds avec fond dégradé, dessiné sur un canvas."""

    def __init__(self, canvas, x, y, w, h, top_color, bottom_color,
                 border_color=None, radius=22, horizontal=False):
        self.canvas = canvas
        self.x, self.y, self.w, self.h = x, y, w, h
        img = make_rounded_gradient(
            w, h, radius, top_color, bottom_color,
            border_color=border_color, border_width=2, horizontal=horizontal
        )
        self.photo = ImageTk.PhotoImage(img)
        self.image_id = canvas.create_image(x, y, image=self.photo, anchor="nw")


class ButtonChip:
    """Un 'chip' rond représentant un bouton du Joy-Con, avec deux états visuels."""

    def __init__(self, canvas, x, y, w, h, label):
        self.canvas = canvas
        self.x, self.y, self.w, self.h = x, y, w, h
        self.label = label

        img_off = make_rounded_gradient(w, h, h // 2, THEME["panel_top"], THEME["panel_bottom"],
                                         border_color=THEME["panel_border"], border_width=2)
        img_on = make_rounded_gradient(w, h, h // 2, THEME["accent"], THEME["accent_dark"],
                                        border_color=THEME["text"], border_width=2)

        self.photo_off = ImageTk.PhotoImage(img_off)
        self.photo_on = ImageTk.PhotoImage(img_on)

        self.image_id = canvas.create_image(x, y, image=self.photo_off, anchor="nw")
        self.text_id = canvas.create_text(
            x + w / 2, y + h / 2, text=label.upper(),
            fill=THEME["muted"], font=(FONT_FAMILY, 11, "bold")
        )

    def set_active(self, active):
        self.canvas.itemconfig(self.image_id, image=self.photo_on if active else self.photo_off)
        self.canvas.itemconfig(self.text_id, fill=THEME["text"] if active else THEME["muted"])


class JoyConApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Joy-Con Controller")
        self.root.geometry("1000x660")
        self.root.configure(bg=THEME["bg_top"])
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(root, width=1000, height=660, highlightthickness=0,
                                 bg=THEME["bg_top"])
        self.canvas.pack(fill="both", expand=True)

        self.chips = {}
        self.dot_id = None
        self.connection_dots = {}
        self.mouse_dots = {}
        self.battery_text_ids = {}
        self.value_text_id = None

        self.build_ui()
        self.poll_queue()

    # ---------------------------------------------------
    def build_ui(self):
        bg = make_rounded_gradient(1000, 660, 0, THEME["bg_top"], THEME["bg_bottom"])
        self.bg_photo = ImageTk.PhotoImage(bg)
        self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw")

        self.canvas.create_text(
            40, 34, text="JOY-CON CONTROLLER", anchor="w",
            fill=THEME["text"], font=(FONT_FAMILY, 22, "bold")
        )
        self.canvas.create_text(
            40, 62, text="Panneau de contrôle en temps réel", anchor="w",
            fill=THEME["muted"], font=(FONT_FAMILY, 11)
        )

        # --- Carte connexion ---
        RoundedPanel(self.canvas, 40, 100, 280, 160,
                     THEME["panel_top"], THEME["panel_bottom"], THEME["panel_border"])
        self.canvas.create_text(60, 122, text="CONNEXION", anchor="w",
                                 fill=THEME["muted"], font=(FONT_FAMILY, 10, "bold"))

        self.connection_dots["left"] = self._make_status_row(60, 152, "Joy-Con gauche")
        self.battery_text_ids["left"] = self._make_battery_label(60, 170)

        self.connection_dots["right"] = self._make_status_row(60, 198, "Joy-Con droit")
        self.battery_text_ids["right"] = self._make_battery_label(60, 216)

        self.connection_dots["gamepad"] = self._make_status_row(60, 240, "Manette virtuelle")

        # --- Carte stick ---
        RoundedPanel(self.canvas, 340, 100, 300, 260,
                     THEME["panel_top"], THEME["panel_bottom"], THEME["panel_border"])
        self.canvas.create_text(360, 122, text="STICK GAUCHE", anchor="w",
                                 fill=THEME["muted"], font=(FONT_FAMILY, 10, "bold"))

        cx, cy, r = 490, 250, 85
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                 outline=THEME["accent"], width=2, fill=THEME["bg_bottom"])
        self.canvas.create_line(cx - r, cy, cx + r, cy, fill=THEME["panel_border"])
        self.canvas.create_line(cx, cy - r, cx, cy + r, fill=THEME["panel_border"])
        self.stick_center = (cx, cy, r)

        dr = 10
        self.dot_id = self.canvas.create_oval(cx - dr, cy - dr, cx + dr, cy + dr,
                                               fill=THEME["success"], outline=THEME["text"], width=2)

        self.value_text_id = self.canvas.create_text(
            490, 355, text="x: 0.00   y: 0.00", fill=THEME["text"],
            font=(FONT_FAMILY, 11)
        )

        # --- Carte souris ---
        RoundedPanel(self.canvas, 660, 100, 300, 160,
                     THEME["panel_top"], THEME["panel_bottom"], THEME["panel_border"])
        self.canvas.create_text(680, 122, text="SOURIS", anchor="w",
                                 fill=THEME["muted"], font=(FONT_FAMILY, 10, "bold"))
        self.mouse_dots["left"] = self._make_status_row(680, 155, "Clic gauche (ZR)")
        self.mouse_dots["right"] = self._make_status_row(680, 190, "Clic droit (ZL)")
        self.mouse_dots["shift"] = self._make_status_row(680, 225, "Maj. maintenue (B)")

        # --- Carte boutons ---
        RoundedPanel(self.canvas, 40, 380, 920, 240,
                     THEME["panel_top"], THEME["panel_bottom"], THEME["panel_border"])
        self.canvas.create_text(60, 402, text="BOUTONS", anchor="w",
                                 fill=THEME["muted"], font=(FONT_FAMILY, 10, "bold"))

        chip_w, chip_h = 130, 46
        start_x, start_y = 60, 440
        gap_x, gap_y = 20, 20

        for row_idx, row in enumerate(BUTTON_LAYOUT):
            for col_idx, name in enumerate(row):
                x = start_x + col_idx * (chip_w + gap_x)
                y = start_y + row_idx * (chip_h + gap_y)
                self.chips[name] = ButtonChip(self.canvas, x, y, chip_w, chip_h, name)

        # --- Bouton recalibrer ---
        self.recalib_panel = RoundedPanel(self.canvas, 770, 440, 150, 46,
                                           THEME["accent"], THEME["accent_dark"], THEME["text"])
        self.canvas.create_text(845, 463, text="RECALIBRER", fill=THEME["text"],
                                 font=(FONT_FAMILY, 11, "bold"))
        self.canvas.tag_bind(self.recalib_panel.image_id, "<Button-1>",
                              lambda e: self.open_calibration_wizard())

    def _make_status_row(self, x, y, label):
        dot = self.canvas.create_oval(x, y, x + 12, y + 12, fill=THEME["danger"], outline="")
        self.canvas.create_text(x + 22, y + 6, text=label, anchor="w",
                                 fill=THEME["text"], font=(FONT_FAMILY, 11))
        return dot

    def _make_battery_label(self, x, y):
        return self.canvas.create_text(
            x + 22, y + 6, text="Batterie : —", anchor="w",
            fill=THEME["muted"], font=(FONT_FAMILY, 10)
        )

    # ---------------------------------------------------
    def set_dot(self, dot_id, ok):
        self.canvas.itemconfig(dot_id, fill=THEME["success"] if ok else THEME["danger"])

    BATTERY_LABELS = {0: "Vide", 1: "Critique", 2: "Faible", 3: "Moyenne", 4: "Pleine"}

    def set_battery(self, side, level, charging):
        if side not in self.battery_text_ids:
            return

        label = self.BATTERY_LABELS.get(level, f"{level}")
        text = f"Batterie : {label}" + (" (en charge)" if charging else "")

        if charging or level > BATTERY_LOW_THRESHOLD:
            color = THEME["muted"]
        else:
            color = THEME["danger"]

        self.canvas.itemconfig(self.battery_text_ids[side], text=text, fill=color)

    def poll_queue(self):
        try:
            while True:
                item = ui_queue.get_nowait()
                kind = item[0]

                if kind == "button":
                    _, name, active = item
                    if name in self.chips:
                        self.chips[name].set_active(active)
                    if name == "b":
                        self.set_dot(self.mouse_dots["shift"], active)

                elif kind == "mouse":
                    _, side, active = item
                    self.set_dot(self.mouse_dots[side], active)

                elif kind == "stick":
                    _, nx, ny, raw_x, raw_y = item
                    cx, cy, r = self.stick_center
                    px = cx + nx * (r - 12)
                    py = cy - ny * (r - 12)
                    self.canvas.coords(self.dot_id, px - 10, py - 10, px + 10, py + 10)
                    self.canvas.itemconfig(
                        self.value_text_id,
                        text=f"x: {nx:.2f}   y: {ny:.2f}"
                    )

                elif kind == "battery":
                    _, side, level, charging = item
                    self.set_battery(side, level, charging)
        except queue.Empty:
            pass

        self.root.after(20, self.poll_queue)

    # ---------------------------------------------------
    def set_connection_status(self, left_ok, right_ok, gamepad_ok):
        self.set_dot(self.connection_dots["left"], left_ok)
        self.set_dot(self.connection_dots["right"], right_ok)
        self.set_dot(self.connection_dots["gamepad"], gamepad_ok)

    # ---------------------------------------------------
    def open_calibration_wizard(self):
        CalibrationWizard(self.root, on_done=self.apply_calibration)

    def apply_calibration(self, calibration):
        global stick_calibration
        stick_calibration = calibration


class CalibrationWizard(tk.Toplevel):
    """
    Fenêtre modale sombre guidant l'utilisateur en 2 étapes :
      1) Centre : une mesure au repos pour définir le point zéro.
      2) Rotation : l'utilisateur fait tourner le stick sur son bord au moins
         5 fois de suite, pendant que min/max x et y sont capturés en continu.
    """

    ROTATIONS_TARGET = 5

    def __init__(self, master, on_done):
        super().__init__(master)
        self.on_done = on_done
        self.phase = "center"
        self.busy = False

        self.center_x = 0.0
        self.center_y = 0.0
        self.min_x = 0.0
        self.max_x = 0.0
        self.min_y = 0.0
        self.max_y = 0.0

        self.rotation_running = False
        self.rotation_queue = queue.Queue()

        self.title("Calibration du stick gauche")
        self.geometry("520x300")
        self.configure(bg=THEME["bg_top"])
        self.resizable(False, False)
        self.grab_set()

        self.canvas = tk.Canvas(self, width=520, height=300, highlightthickness=0,
                                 bg=THEME["bg_top"])
        self.canvas.pack(fill="both", expand=True)

        bg = make_rounded_gradient(520, 300, 0, THEME["bg_top"], THEME["bg_bottom"])
        self.bg_photo = ImageTk.PhotoImage(bg)
        self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw")

        RoundedPanel(self.canvas, 24, 24, 472, 252,
                     THEME["panel_top"], THEME["panel_bottom"], THEME["panel_border"])

        self.title_id = self.canvas.create_text(
            260, 58, text="Calibration", fill=THEME["text"],
            font=(FONT_FAMILY, 16, "bold")
        )
        self.instruction_id = self.canvas.create_text(
            260, 100, text="", fill=THEME["text"], width=420,
            font=(FONT_FAMILY, 12), justify="center"
        )
        self.measure_id = self.canvas.create_text(
            260, 145, text="", fill=THEME["muted"], width=420,
            font=(FONT_FAMILY, 11), justify="center"
        )
        self.progress_id = self.canvas.create_text(
            260, 175, text="", fill=THEME["accent"],
            font=(FONT_FAMILY, 12, "bold")
        )

        self.action_btn = RoundedPanel(self.canvas, 190, 215, 140, 42,
                                        THEME["accent"], THEME["accent_dark"], THEME["text"])
        self.action_label = self.canvas.create_text(
            260, 236, text="VALIDER", fill=THEME["text"], font=(FONT_FAMILY, 11, "bold")
        )
        self.canvas.tag_bind(self.action_btn.image_id, "<Button-1>", lambda e: self.on_action_click())
        self.canvas.tag_bind(self.action_label, "<Button-1>", lambda e: self.on_action_click())

        self.show_center_phase()

    # ---------------------------------------------------
    def set_action_label(self, text):
        self.canvas.itemconfig(self.action_label, text=text)

    def show_center_phase(self):
        self.phase = "center"
        self.canvas.itemconfig(
            self.instruction_id,
            text="1) Placez le stick bien au CENTRE, sans le toucher, puis validez."
        )
        self.canvas.itemconfig(self.measure_id, text="En attente de validation...")
        self.canvas.itemconfig(self.progress_id, text="")
        self.set_action_label("VALIDER")

    def show_rotation_phase(self):
        self.phase = "rotation"
        self.canvas.itemconfig(
            self.instruction_id,
            text=("2) Tournez le stick tout autour, jusqu'au bord, "
                  f"au moins {self.ROTATIONS_TARGET} fois de suite.")
        )
        self.canvas.itemconfig(self.measure_id, text="Cliquez sur Démarrer puis faites tourner le stick.")
        self.canvas.itemconfig(self.progress_id, text=f"Tours effectués : 0.00 / {self.ROTATIONS_TARGET}")
        self.set_action_label("DÉMARRER")

    # ---------------------------------------------------
    def on_action_click(self):
        if self.busy:
            return

        if self.phase == "center":
            self.measure_center()
        elif self.phase == "rotation":
            if not self.rotation_running:
                self.start_rotation()
            else:
                self.stop_rotation()

    # ---------------------------------------------------
    def measure_center(self):
        if left is None:
            return
        self.busy = True
        self.canvas.itemconfig(self.measure_id, text="Mesure en cours...")

        def sample():
            raw_x, raw_y = sample_left_stick(left, samples=20, delay=0.01)
            self.after(0, lambda: self.on_center_sampled(raw_x, raw_y))

        threading.Thread(target=sample, daemon=True).start()

    def on_center_sampled(self, raw_x, raw_y):
        self.center_x = raw_x
        self.center_y = raw_y
        self.min_x = self.max_x = raw_x
        self.min_y = self.max_y = raw_y

        self.canvas.itemconfig(self.measure_id, text=f"Centre mesuré : x={raw_x:.3f}  y={raw_y:.3f}")
        self.busy = False
        self.after(500, self.show_rotation_phase)

    # ---------------------------------------------------
    def start_rotation(self):
        if left is None:
            return
        self.rotation_running = True
        self.set_action_label("TERMINER")
        self.canvas.itemconfig(self.measure_id, text="Faites tourner le stick sur son bord...")

        threading.Thread(target=self.rotation_worker, daemon=True).start()
        self.poll_rotation()

    def stop_rotation(self):
        self.rotation_running = False
        self.after(150, self.finish)

    def rotation_worker(self):
        prev_angle = None
        total_rotation = 0.0

        while self.rotation_running:
            raw_x = left.get_stick_left_horizontal()
            raw_y = left.get_stick_left_vertical()

            self.min_x = min(self.min_x, raw_x)
            self.max_x = max(self.max_x, raw_x)
            self.min_y = min(self.min_y, raw_y)
            self.max_y = max(self.max_y, raw_y)

            dx = raw_x - self.center_x
            dy = raw_y - self.center_y

            if dx * dx + dy * dy > 1e-6:
                angle = math.atan2(dy, dx)
                if prev_angle is not None:
                    delta = angle - prev_angle
                    while delta > math.pi:
                        delta -= 2 * math.pi
                    while delta < -math.pi:
                        delta += 2 * math.pi
                    total_rotation += abs(delta)
                prev_angle = angle

            revolutions = total_rotation / (2 * math.pi)
            self.rotation_queue.put(revolutions)

            time.sleep(0.015)

    def poll_rotation(self):
        if not self.rotation_running:
            return

        revolutions = None
        try:
            while True:
                revolutions = self.rotation_queue.get_nowait()
        except queue.Empty:
            pass

        if revolutions is not None:
            done = revolutions >= self.ROTATIONS_TARGET
            self.canvas.itemconfig(
                self.progress_id,
                text=f"Tours effectués : {revolutions:.2f} / {self.ROTATIONS_TARGET}"
            )
            self.canvas.itemconfig(
                self.measure_id,
                text=(f"x: [{self.min_x:.0f}, {self.max_x:.0f}]   "
                      f"y: [{self.min_y:.0f}, {self.max_y:.0f}]")
            )
            if done:
                self.canvas.itemconfig(
                    self.measure_id,
                    text="Objectif atteint ! Vous pouvez cliquer sur Terminer."
                )

        self.after(30, self.poll_rotation)

    # ---------------------------------------------------
    def finish(self):
        calibration = {
            "center_x": self.center_x,
            "center_y": self.center_y,
            "min_x": self.min_x,
            "max_x": self.max_x,
            "min_y": self.min_y,
            "max_y": self.max_y,
        }

        self.canvas.itemconfig(self.instruction_id, text="Calibration terminée !")
        self.canvas.itemconfig(self.measure_id, text="")
        self.canvas.itemconfig(self.progress_id, text="")
        self.on_done(calibration)

        # Vibration de confirmation + toutes les lumières joueur allumées (best-effort)
        for joycon in (left, right):
            threading.Thread(target=send_rumble, args=(joycon,), daemon=True).start()
            threading.Thread(target=light_up_players, args=(joycon,), daemon=True).start()

        self.after(600, self.destroy)


# =======================================================
# Connexion Joy-Con + lancement de l'application
# =======================================================

def connect_and_run():
    global left, right, virtual_gamepad

    root = tk.Tk()
    app = JoyConApp(root)

    def background_setup():
        global left, right, virtual_gamepad

        left_id = get_L_ids()[0]
        right_id = get_R_ids()[0]

        left = ButtonEventJoyCon(*left_id)
        right = ButtonEventJoyCon(*right_id)

        gamepad_ok = vgamepad is not None
        if gamepad_ok:
            virtual_gamepad = vgamepad.VX360Gamepad()

        root.after(0, lambda: app.set_connection_status(True, True, gamepad_ok))

        # Petite vibration de confirmation au démarrage (best-effort, voir send_rumble)
        enable_vibration(left)
        enable_vibration(right)
        threading.Thread(target=send_rumble, args=(left,), daemon=True).start()
        threading.Thread(target=send_rumble, args=(right,), daemon=True).start()

        threading.Thread(target=left_loop, daemon=True).start()
        threading.Thread(target=right_loop, daemon=True).start()
        threading.Thread(target=left_stick_loop, daemon=True).start()
        threading.Thread(target=right_gyro_mouse_loop, daemon=True).start()
        threading.Thread(target=battery_loop, daemon=True).start()

        root.after(0, app.open_calibration_wizard)

    threading.Thread(target=background_setup, daemon=True).start()

    root.mainloop()


if __name__ == "__main__":
    connect_and_run()