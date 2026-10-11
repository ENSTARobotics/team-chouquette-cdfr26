"""
serial_link.py
----------------
Couche de communication série entre la Raspberry Pi et l'ESP32.

Format du protocole (texte, terminé par '\n', 115200 bauds) :

  ESP32 -> Pi :
    POS:<x>,<y>,<theta>
    SONAR:<d1>,<d2>,<d3>,<d4>
    EVT:START | EVT:STOP
    EVT:READY | EVT:RESET

  Pi -> ESP32 :
    MOT:<dm1>,<pm1>,<dm2>,<pm2>
    SRV:<id>,<angle>
    SRVALL:<a1>,<a2>,<a3>,<a4>,<a5>
    STOP
    RESET
    SETPOS:<x>,<y>,<theta>

Utilisation typique :

    link = SerialLink("/dev/serial0", 115200)
    link.start()
    while True:
        state = link.state              # snapshot thread-safe
        link.set_motors(1, 180, 0, 180) # avancer
"""

import threading
import time
import serial
from dataclasses import dataclass, field
from typing import Optional, Callable


@dataclass
class RobotState:
    """Snapshot de l'état physique du robot vu par l'ESP32."""
    x: float = 0.0           # position X (mm)
    y: float = 0.0           # position Y (mm)
    theta: float = 0.0       # cap (rad)
    sonars: list = field(default_factory=lambda: [9999, 9999, 9999, 9999])
    match_started: bool = False
    last_pos_update: float = 0.0
    last_sonar_update: float = 0.0


class SerialLink:
    """
    Lien série non-bloquant avec l'ESP32.

    Un thread de fond lit en permanence les trames montantes (POS, SONAR, EVT).
    Les méthodes set_motors / set_servo / ... sont thread-safe et écrivent
    immédiatement sur le port série.
    """

    def __init__(self, port: str = "/dev/serial0", baud: int = 115200,
                 timeout: float = 0.1):
        self.port_name = port
        self.baud = baud
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None
        self.state = RobotState()
        self._lock = threading.Lock()         # protège l'écriture série
        self._stop_evt = threading.Event()
        self._reader: Optional[threading.Thread] = None
        self.on_event: Optional[Callable[[str], None]] = None  # callback EVT:*

    # ------------------------------------------------------------------ start/stop
    def start(self):
        self.ser = serial.Serial(self.port_name, self.baud, timeout=self.timeout)
        time.sleep(0.2)
        self.ser.reset_input_buffer()
        self._stop_evt.clear()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def close(self):
        self._stop_evt.set()
        if self._reader:
            self._reader.join(timeout=1.0)
        if self.ser and self.ser.is_open:
            try:
                self._write_raw("STOP")
            except Exception:
                pass
            self.ser.close()

    # ------------------------------------------------------------------ écriture
    def _write_raw(self, cmd: str):
        if not self.ser:
            return
        with self._lock:
            self.ser.write((cmd + "\n").encode("ascii", errors="ignore"))

    def set_motors(self, dir1: int, pwm1: int, dir2: int, pwm2: int):
        """Pilote les 2 moteurs DC. dir = 0/1, pwm = 0..255."""
        pwm1 = max(0, min(255, int(pwm1)))
        pwm2 = max(0, min(255, int(pwm2)))
        self._write_raw(f"MOT:{int(dir1)},{pwm1},{int(dir2)},{pwm2}")

    def stop_motors(self):
        self._write_raw("STOP")

    def set_servo(self, servo_id: int, angle: int):
        """Règle un servo individuel (id 1..5, angle 0..180°)."""
        angle = max(0, min(180, int(angle)))
        self._write_raw(f"SRV:{servo_id},{angle}")
        
    def set_all_front_servos(self, a1: int, a2: int, a3: int, a4: int):
        vals = [max(0, min(180, int(a))) for a in (a1, a2, a3, a4)]
        self._write_raw("SRVALL:" + ",".join(str(v) for v in vals))

    def set_all_servos(self, a1: int, a2: int, a3: int, a4: int, a5: int):
        """Règle les 5 servos d'un coup (utile pour les changements d'état)."""
        vals = [max(0, min(180, int(a))) for a in (a1, a2, a3, a4, a5)]
        self._write_raw("SRVALL:" + ",".join(str(v) for v in vals))

    def reset_odometry(self):
        self._write_raw("RESET")

    def set_position(self, x: float, y: float, theta: float):
        """Force la position de l'ESP32 (calibration de départ)."""
        self._write_raw(f"SETPOS:{x:.1f},{y:.1f},{theta:.4f}")

    # ------------------------------------------------------------------ lecture
    def _read_loop(self):
        buf = b""
        while not self._stop_evt.is_set():
            try:
                data = self.ser.read(128)
            except Exception:
                time.sleep(0.05)
                continue

            if not data:
                continue

            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    msg = line.decode("ascii", errors="ignore").strip()
                except Exception:
                    continue
                if msg:
                    self._handle_line(msg)

    def _handle_line(self, msg: str):
        if msg.startswith("POS:"):
            try:
                x, y, theta = msg[4:].split(",")
                self.state.x = float(x)
                self.state.y = float(y)
                self.state.theta = float(theta)
                self.state.last_pos_update = time.time()
            except ValueError:
                pass

        elif msg.startswith("SONAR:"):
            try:
                parts = msg[6:].split(",")
                self.state.sonars = [int(p) for p in parts]
                self.state.last_sonar_update = time.time()
            except ValueError:
                pass

        elif msg.startswith("EVT:"):
            evt = msg[4:]
            if evt == "START":
                self.state.match_started = True
                    
            elif evt == "RESET" or evt == "READY":
                self.state.match_started = False
            
            if self.on_event:
                self.on_event(evt)
            
            
            
            
            
            
            
            
            
            
