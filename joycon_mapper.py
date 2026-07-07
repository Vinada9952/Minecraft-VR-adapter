import threading
import time
import pyautogui

from pynput.keyboard import Controller as KeyboardController, Key
from pynput.mouse import Controller as MouseController, Button

try:
    import vgamepad
except ImportError:
    vgamepad = None

from pyjoycon import (
    get_L_ids,
    get_R_ids,
    ButtonEventJoyCon
)


# =======================================================
# Clavier / souris
# =======================================================

keyboard = KeyboardController()
mouse = MouseController()


# =======================================================
# États
# =======================================================

mouse_left = False
mouse_right = False
b_toggle = False

last_scroll = 0
SCROLL_DELAY = 0.1

stick_calibration = None
left_stick_state = {
    "raw_x": 0.0,
    "raw_y": 0.0,
    "x": 0.0,
    "y": 0.0,
}
virtual_gamepad = None


# =======================================================
# Raccourcis clavier
# =======================================================

def hotkey(*keys):

    for key in keys:
        keyboard.press(key)

    for key in reversed(keys):
        keyboard.release(key)



# =======================================================
# Boutons pressés
# =======================================================

def button_pressed(name):

    global mouse_left
    global mouse_right
    global last_scroll
    global b_toggle

    print("PRESS :", name)


    # Joy-Con droit

    if name == "a":

        keyboard.press(Key.space)
        # keyboard.release(Key.space)


    elif name == "b":

        if not b_toggle:
            keyboard.press(Key.shift)
            b_toggle = True
        else:
            keyboard.release(Key.shift)
            b_toggle = False


    elif name == "x":

        hotkey(Key.ctrl, Key.cmd, "o")
        pyautogui.moveTo(1400, 575)
        time.sleep( 1 )
        pyautogui.click()

    
    elif name == "y":

        hotkey(Key.ctrl)


    elif name == "plus":

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


    elif name == "zl":

        if not mouse_right:
            mouse.press(Button.right)
            mouse_right = True


    # Scroll

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



# =======================================================
# Boutons relâchés
# =======================================================

def button_released(name):

    global mouse_left
    global mouse_right

    print("RELEASE :", name)


    if name == "zr":

        if mouse_left:
            mouse.release(Button.left)
            mouse_left = False


    elif name == "zl":

        if mouse_right:
            mouse.release(Button.right)
            mouse_right = False
    
    elif name == "a":

        # keyboard.press(Key.space)
        keyboard.release(Key.space)



# =======================================================
# Traitement événements Joy-Con
# =======================================================

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
    """Échantillonne le stick gauche plusieurs fois pour lisser la mesure."""
    total_x = 0.0
    total_y = 0.0

    for _ in range(samples):
        total_x += controller.get_stick_left_horizontal()
        total_y += controller.get_stick_left_vertical()
        time.sleep(delay)

    return total_x / samples, total_y / samples


def prompt_stick_position(controller, prompt, samples=20, delay=0.01):
    input(prompt)
    raw_x, raw_y = sample_left_stick(controller, samples=samples, delay=delay)
    print(f"  Mesure : X={raw_x:.4f}, Y={raw_y:.4f}")
    return raw_x, raw_y


def calibrate_left_stick(controller):
    """Calibre le stick gauche position par position et confirme avec Enter."""
    print("Calibration interactive du joystick gauche.")
    print("Pour chaque étape, positionnez le stick puis appuyez sur Entrée.")

    center_x, center_y = prompt_stick_position(
        controller,
        "1) Placez le stick au centre puis appuyez sur Entrée : ",
    )

    left_x, _ = prompt_stick_position(
        controller,
        "2) Poussez le stick complètement à gauche puis appuyez sur Entrée : ",
    )

    right_x, _ = prompt_stick_position(
        controller,
        "3) Poussez le stick complètement à droite puis appuyez sur Entrée : ",
    )

    _, top_y = prompt_stick_position(
        controller,
        "4) Poussez le stick complètement vers le haut puis appuyez sur Entrée : ",
    )

    _, bottom_y = prompt_stick_position(
        controller,
        "5) Poussez le stick complètement vers le bas puis appuyez sur Entrée : ",
    )

    calibration = {
        "center_x": center_x,
        "center_y": center_y,
        "min_x": min(left_x, center_x, right_x),
        "max_x": max(left_x, center_x, right_x),
        "min_y": min(top_y, center_y, bottom_y),
        "max_y": max(top_y, center_y, bottom_y),
    }

    print("Calibration terminée :")
    print(f"  centre X={center_x:.4f}, Y={center_y:.4f}")
    print(f"  min X={calibration['min_x']:.4f}, max X={calibration['max_x']:.4f}")
    print(f"  min Y={calibration['min_y']:.4f}, max Y={calibration['max_y']:.4f}")

    return calibration


def normalize_left_stick(raw_x, raw_y, calibration):
    """Normalise les valeurs brutes du stick gauche en [-1.0, 1.0]."""
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

    x = max(-1.0, min(1.0, x))
    y = max(-1.0, min(1.0, y))

    return x, y


def update_left_stick_state():
    global left_stick_state, virtual_gamepad
    if stick_calibration is None:
        return

    raw_x = left.get_stick_left_horizontal()
    raw_y = left.get_stick_left_vertical()
    normalized_x, normalized_y = normalize_left_stick(raw_x, raw_y, stick_calibration)

    left_stick_state["raw_x"] = raw_x
    left_stick_state["raw_y"] = raw_y
    left_stick_state["x"] = normalized_x
    left_stick_state["y"] = normalized_y

    if virtual_gamepad is not None:
        virtual_gamepad.left_joystick_float(normalized_x, normalized_y)
        virtual_gamepad.update()



# =======================================================
# Boucles Joy-Con
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



# =======================================================
# Connexion Joy-Con
# =======================================================

print("Recherche Joy-Con...")


left_id = get_L_ids()[0]
right_id = get_R_ids()[0]


print("Joy-Con gauche :", left_id)
print("Joy-Con droit :", right_id)


left = ButtonEventJoyCon(*left_id)
right = ButtonEventJoyCon(*right_id)

if vgamepad is None:
    raise ImportError("Le module vgamepad est requis pour le joystick virtuel. Installez-le avec 'pip install vgamepad'.")

virtual_gamepad = vgamepad.VX360Gamepad()

print("Connecté !")

# Calibration du stick gauche
stick_calibration = calibrate_left_stick(left)

print("Calibration enregistrée. Lecture du stick gauche en cours...")

# =======================================================
# Threads
# =======================================================

threading.Thread(
    target=left_loop,
    daemon=True
).start()

threading.Thread(
    target=right_loop,
    daemon=True
).start()

threading.Thread(
    target=left_stick_loop,
    daemon=True
).start()



# =======================================================
# Boucle principale
# =======================================================

try:

    while True:

        time.sleep(0.01)



except KeyboardInterrupt:

    print("Arrêt")

    if mouse_left:
        mouse.release(Button.left)

    if mouse_right:
        mouse.release(Button.right)