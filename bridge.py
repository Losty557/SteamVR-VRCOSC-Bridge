"""
SteamVR + XSOverlay -> VRChat OSC bridge
Prototype for Windows / SteamVR.

- Reads OpenVR DashboardActivated / DashboardDeactivated events.
- Receives XSOverlay OSC on UDP 9002.
- Forwards all other XSOverlay OSC packets to VRChat UDP 9000.
- Combines XSOverlay isOverlayOpen with SteamVR dashboard state using OR.
"""
import ctypes
import logging
import socket
import struct
import threading
import time

import openvr

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 9002          # Set XSOverlay's OSC Send Port to this
VRCHAT_HOST = "127.0.0.1"
VRCHAT_PORT = 9000
DASHBOARD_ON = 502           # VREvent_DashboardActivated
DASHBOARD_OFF = 503          # VREvent_DashboardDeactivated

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def osc_string(data, offset):
    end = data.find(b"\0", offset)
    if end < 0:
        raise ValueError("Malformed OSC string")
    value = data[offset:end].decode("utf-8", errors="replace")
    next_offset = (end + 4) & ~3
    return value, next_offset

def read_overlay_bool(packet):
    """Return True/False for /avatar/parameters/isOverlayOpen, else None."""
    try:
        address, pos = osc_string(packet, 0)
        if address != "/avatar/parameters/isOverlayOpen":
            return None
        tags, pos = osc_string(packet, pos)
        if tags == ",T":
            return True
        if tags == ",F":
            return False
        # Also accept integer/float encodings as a defensive fallback.
        if tags == ",i" and len(packet) >= pos + 4:
            return struct.unpack(">i", packet[pos:pos+4])[0] != 0
        if tags == ",f" and len(packet) >= pos + 4:
            return struct.unpack(">f", packet[pos:pos+4])[0] != 0.0
    except Exception:
        pass
    return None

def make_osc_bool(address, value):
    def pad(s):
        raw = s.encode("utf-8") + b"\0"
        return raw + b"\0" * ((-len(raw)) % 4)
    return pad(address) + pad(",T" if value else ",F")

class Bridge:
    def __init__(self):
        self.lock = threading.Lock()
        self.xso_open = False
        self.dashboard_open = False
        self.last_sent = None
        self.out_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.in_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.in_sock.bind((LISTEN_HOST, LISTEN_PORT))
        self.in_sock.settimeout(1.0)

    def combined(self):
        return self.xso_open or self.dashboard_open

    def publish(self, force=False):
        with self.lock:
            value = self.combined()
            if not force and value == self.last_sent:
                return
            self.last_sent = value
        packet = make_osc_bool("/avatar/parameters/isOverlayOpen", value)
        self.out_sock.sendto(packet, (VRCHAT_HOST, VRCHAT_PORT))
        logging.info("isOverlayOpen -> %s (XSOverlay=%s, Dashboard=%s)",
                     value, self.xso_open, self.dashboard_open)

    def set_dashboard(self, value):
        with self.lock:
            self.dashboard_open = value
        self.publish()

    def osc_loop(self):
        logging.info("OSC relay listening on %s:%s", LISTEN_HOST, LISTEN_PORT)
        # Send a safe initial false. XSOverlay will update the state when it next reports.
        self.publish(force=True)
        while True:
            try:
                packet, _addr = self.in_sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                return

            state = read_overlay_bool(packet)
            if state is not None:
                with self.lock:
                    self.xso_open = state
                # Do not forward the original value: publish the combined state instead.
                self.publish()
            else:
                # Preserve every other XSOverlay OSC message unchanged.
                self.out_sock.sendto(packet, (VRCHAT_HOST, VRCHAT_PORT))

    def openvr_loop(self):
        initialized = False
        try:
            logging.info("Connecting to SteamVR through OpenVR...")
            system = openvr.init(openvr.VRApplication_Background)
            initialized = True
            event = openvr.VREvent_t()
            event_size = ctypes.sizeof(event)
            logging.info("OpenVR connected; waiting for dashboard events.")
            while True:
                got_event = False
                while system.pollNextEvent(event):
                    got_event = True
                    if event.eventType == DASHBOARD_ON:
                        self.set_dashboard(True)
                    elif event.eventType == DASHBOARD_OFF:
                        self.set_dashboard(False)
                time.sleep(0.01 if got_event else 0.03)
        except Exception:
            logging.exception("OpenVR event monitor stopped.")
            logging.error("Check that SteamVR is running and the 'openvr' Python package is installed.")
        finally:
            if initialized:
                try:
                    openvr.shutdown()
                except Exception:
                    pass

    def run(self):
        threading.Thread(target=self.openvr_loop, daemon=True).start()
        self.osc_loop()

if __name__ == "__main__":
    logging.info("SteamVR / XSOverlay OSC Bridge starting.")
    Bridge().run()
