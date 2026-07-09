"""
server.py
---------
Serveur Flask + Socket.IO qui tourne en LOCAL sur ton PC Windows 11.

Fonctionnement :
  1. Capture en continu l'écran principal (via mss).
  2. Redimensionne et compresse l'image en JPEG, envoyée en BINAIRE
     (pas de base64) pour réduire la latence et la bande passante.
  3. Envoie l'image au client (iPhone) via WebSocket (Socket.IO),
     qui l'affiche en double (oeil gauche / oeil droit) pour un effet "VR".
  4. Reçoit du téléphone les données du gyroscope (deviceorientation)
     et déplace la souris du PC en fonction de la VITESSE de rotation
     (angle / temps), ce qui permet de viser dans un jeu en bougeant
     la tête à une vitesse qui correspond à celle du curseur.

Installation des dépendances (à faire une seule fois) :
    pip install flask flask-socketio mss opencv-python numpy pywin32

Lancement :
    python server.py

Puis sur l'iPhone (connecté au MEME réseau Wi-Fi que le PC) :
    - aller sur https://192.168.0.120:5000/
      (HTTPS est nécessaire pour que le gyroscope fonctionne sur iOS ;
      le certificat est généré via mkcert, voir CERT_FILE / KEY_FILE ci-dessous)

Remarque : si rien ne se passe depuis le téléphone, vérifie que le
pare-feu Windows autorise Python/le port 5000 en connexions entrantes.
"""

import ctypes
import os
import time

import cv2
import mss
import numpy as np
import win32api
import win32con
import win32gui
import win32ui
from flask import Flask, Response, request
from flask_socketio import SocketIO
import threading

joycon = threading.Thread( target=os.system, args=("python3 joycon_mapper.py",) )
joycon.start()

# ---------- SendInput (mouvement souris relatif bas niveau) ----------
PUL = ctypes.POINTER(ctypes.c_ulong)


class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL),
    ]


class Input_I(ctypes.Union):
    _fields_ = [("mi", MouseInput)]


class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ii", Input_I)]


MOUSEEVENTF_MOVE = 0x0001
INPUT_MOUSE = 0


def send_mouse_relative(dx, dy):
    """Déplace la souris de façon relative via SendInput (bas niveau)."""
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.mi = MouseInput(dx, dy, 0, MOUSEEVENTF_MOVE, 0, ctypes.pointer(extra))
    command = Input(ctypes.c_ulong(INPUT_MOUSE), ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(command), ctypes.sizeof(command))

# ---------- Configuration ----------
JPEG_QUALITY = 60
TARGET_WIDTH = 1280
FPS_TARGET = 60
# MONITOR_INDEX = 3
MONITOR_INDEX = 1

MOUSE_SENSITIVITY = 25.0

HOST = "0.0.0.0"
PORT = 5000

CERT_FILE = "192.168.0.120+2.pem"
KEY_FILE = "192.168.0.120+2-key.pem"

app = Flask(__name__)
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PAGE_HTML_PATH = os.path.join(BASE_DIR, "page.html")
SETTINGS_HTML_PATH = os.path.join(BASE_DIR, "settings.html")

settings = {
    "mouseSensitivityX": 0.6666666666,
    "mouseSensitivityY": 1,
    "warpTL": 0.0,
    "warpTR": 0.0,
    "warpBL": 0.0,
    "warpBR": 0.0,
    "eyeGap": -65,
    "eyeZoom": 0.9,
}

sct = mss.MSS()

print("Écrans détectés (mss.monitors) :")
for i, m in enumerate(sct.monitors):
    print(f"  [{i}] {m}")

monitor = sct.monitors[MONITOR_INDEX]
print(f"-> Capture de l'écran index {MONITOR_INDEX} : {monitor}")

streaming = False
stream_clients = set()

ENCODE_PARAMS = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY, int(cv2.IMWRITE_JPEG_OPTIMIZE), 0]


def get_cursor_overlay():
    try:
        flags, hcursor, (x, y) = win32gui.GetCursorInfo()
        if flags != win32con.CURSOR_SHOWING:
            return None

        hicon_info = win32gui.GetIconInfo(hcursor)
        hotspot_x, hotspot_y = hicon_info[1], hicon_info[2]
        hbm_mask, hbm_color = hicon_info[3], hicon_info[4]

        size = 32

        hdc_screen = win32gui.GetDC(0)
        hdc_mem = win32ui.CreateDCFromHandle(hdc_screen)
        hdc_compat = hdc_mem.CreateCompatibleDC()

        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(hdc_mem, size, size)
        hdc_compat.SelectObject(bmp)

        win32gui.DrawIconEx(
            hdc_compat.GetSafeHdc(), 0, 0, hcursor, size, size, 0, None, win32con.DI_NORMAL
        )

        bmp_info = bmp.GetInfo()
        bmp_bits = bmp.GetBitmapBits(True)
        cursor_img = np.frombuffer(bmp_bits, dtype=np.uint8).reshape(
            (bmp_info["bmHeight"], bmp_info["bmWidth"], 4)
        )

        win32gui.DeleteObject(bmp.GetHandle())
        hdc_compat.DeleteDC()
        hdc_mem.DeleteDC()
        win32gui.ReleaseDC(0, hdc_screen)
        win32gui.DeleteObject(hbm_mask)
        win32gui.DeleteObject(hbm_color)

        return cursor_img, hotspot_x, hotspot_y, x, y
    except Exception:
        return None


def draw_cursor_on_image(img, monitor_left, monitor_top):
    overlay = get_cursor_overlay()
    if overlay is None:
        return

    cursor_img, hotspot_x, hotspot_y, screen_x, screen_y = overlay

    px = screen_x - monitor_left - hotspot_x
    py = screen_y - monitor_top - hotspot_y

    ch, cw = cursor_img.shape[:2]
    h, w = img.shape[:2]

    x0, y0 = max(px, 0), max(py, 0)
    x1, y1 = min(px + cw, w), min(py + ch, h)
    if x0 >= x1 or y0 >= y1:
        return

    cx0, cy0 = x0 - px, y0 - py
    cx1, cy1 = cx0 + (x1 - x0), cy0 + (y1 - y0)

    cursor_crop = cursor_img[cy0:cy1, cx0:cx1]
    alpha = cursor_crop[:, :, 3:4].astype(np.float32) / 255.0
    cursor_bgr = cursor_crop[:, :, :3].astype(np.float32)

    region = img[y0:y1, x0:x1].astype(np.float32)
    blended = cursor_bgr * alpha + region * (1 - alpha)
    img[y0:y1, x0:x1] = blended.astype(np.uint8)


def capture_loop():
    global streaming
    frame_interval = 1.0 / FPS_TARGET

    while streaming:
        t0 = time.time()

        raw = np.array(sct.grab(monitor))
        img = raw[:, :, :3].copy()

        draw_cursor_on_image(img, monitor["left"], monitor["top"])

        h, w = img.shape[:2]
        scale = TARGET_WIDTH / w
        resized = cv2.resize(
            img, (TARGET_WIDTH, int(h * scale)), interpolation=cv2.INTER_NEAREST
        )

        ok, buffer = cv2.imencode(".jpg", resized, ENCODE_PARAMS)
        if ok:
            for sid in list(stream_clients):
                socketio.emit("frame", buffer.tobytes(), to=sid)

        elapsed = time.time() - t0
        sleep_time = frame_interval - elapsed
        if sleep_time > 0:
            socketio.sleep(sleep_time)
        else:
            socketio.sleep(0)


@app.route("/")
def index():
    with open(PAGE_HTML_PATH, "r", encoding="utf-8") as f:
        return Response(f.read(), mimetype="text/html")


@app.route("/settings")
def pc_settings():
    with open(SETTINGS_HTML_PATH, "r", encoding="utf-8") as f:
        return Response(f.read(), mimetype="text/html")


@socketio.on("connect")
def on_connect():
    print("[+] Client connecté.")
    socketio.emit("settings", settings)


@socketio.on("start_stream")
def on_start_stream():
    global streaming
    stream_clients.add(request.sid)
    print("[+] Client VR connecté, démarrage du flux écran...")
    if not streaming:
        streaming = True
        socketio.start_background_task(capture_loop)


@socketio.on("disconnect")
def on_disconnect():
    global streaming
    stream_clients.discard(request.sid)
    print("[-] Client déconnecté.")
    if not stream_clients:
        print("[-] Aucun client VR, arrêt du flux écran.")
        streaming = False


# ---------- Gyroscope -> Souris ----------
last_gyro_time = None
mouse_remainder = {"x": 0.0, "y": 0.0}
GYRO_DEADZONE_DPS = 0.8


def move_mouse_relative(dx, dy):
    global mouse_remainder

    mouse_remainder["x"] += dx
    mouse_remainder["y"] += dy

    send_dx = int(round(mouse_remainder["x"]))
    send_dy = int(round(mouse_remainder["y"]))
    if send_dx == 0 and send_dy == 0:
        return

    mouse_remainder["x"] -= send_dx
    mouse_remainder["y"] -= send_dy
    send_mouse_relative(send_dx, send_dy)


@socketio.on("get_settings")
def on_get_settings():
    socketio.emit("settings", settings)


@socketio.on("update_settings")
def on_update_settings(data):
    if "mouseSensitivity" in data:
        try:
            legacy_value = float(data["mouseSensitivity"])
            settings["mouseSensitivityX"] = legacy_value
            settings["mouseSensitivityY"] = legacy_value
        except (TypeError, ValueError):
            pass

    for key in settings:
        if key in data:
            try:
                settings[key] = float(data[key])
            except (TypeError, ValueError):
                pass

    print(f"[settings] {settings}")
    socketio.emit("settings", settings)


@socketio.on("gyro")
def on_gyro(data):
    """Reçoit les vitesses de rotation déjà projetées dans le repère de la
    tête par le client (voir page.html : la rotation par le roulis y est
    appliquée avant l'envoi), donc rien à faire de spécial ici pour le
    roulis - le serveur reste inchangé."""
    global last_gyro_time

    yaw_rate = data.get("gamma")
    pitch_rate = data.get("beta")
    if yaw_rate is None:
        yaw_rate = data.get("alpha")
    if yaw_rate is None or pitch_rate is None:
        print(f"[gyro] reçu mais incomplet : {data}")
        return

    try:
        yaw_rate = float(yaw_rate)
        pitch_rate = float(pitch_rate)
        sensitivity_multiplier = float(data.get("sensitivity", 1.0))
    except (TypeError, ValueError):
        return

    now = time.time()
    if last_gyro_time is None:
        last_gyro_time = now
        return

    dt = now - last_gyro_time
    last_gyro_time = now
    if dt <= 0:
        dt = 1.0 / 60.0
    dt = min(dt, 0.05)

    if abs(yaw_rate) < GYRO_DEADZONE_DPS:
        yaw_rate = 0.0
    if abs(pitch_rate) < GYRO_DEADZONE_DPS:
        pitch_rate = 0.0

    sensitivity_x = MOUSE_SENSITIVITY * settings["mouseSensitivityX"] * sensitivity_multiplier
    sensitivity_y = MOUSE_SENSITIVITY * settings["mouseSensitivityY"] * sensitivity_multiplier

    dx = yaw_rate * sensitivity_x * dt
    dy = -pitch_rate * sensitivity_y * dt

    print(
        f"[gyro] yaw={yaw_rate:6.1f} pitch={pitch_rate:6.1f} "
        f"dt={dt*1000:5.1f}ms  dx={dx:6.2f} dy={dy:6.2f} "
        f"sensX={sensitivity_x:.1f} sensY={sensitivity_y:.1f}"
    )

    move_mouse_relative(dx, dy)

if __name__ == "__main__":
    cert_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CERT_FILE)
    key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), KEY_FILE)

    if os.path.exists(cert_path) and os.path.exists(key_path):
        print(f"Serveur démarré : https://{HOST}:{PORT}  (utilise ton IP locale depuis l'iPhone)")
        socketio.run(app, host=HOST, port=PORT, ssl_context=(cert_path, key_path))
    else:
        print(
            f"[!] Certificat mkcert introuvable ({CERT_FILE} / {KEY_FILE}).\n"
            f"    Démarrage en HTTP -> le gyroscope ne fonctionnera PAS sur iPhone.\n"
            f"    Place les fichiers .pem générés par mkcert à côté de server.py."
        )
        print(f"Serveur démarré : http://{HOST}:{PORT}")
        socketio.run(app, host=HOST, port=PORT)