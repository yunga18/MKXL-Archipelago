"""Avisos en pantalla encima de Mortal Kombat XL.

Ventana transparente, siempre encima y que deja pasar los clics, dibujada con tkinter en su
propio hilo. Solo se ve si el juego está en modo Ventana o Ventana sin bordes (no en
Pantalla completa exclusiva).
"""
from __future__ import annotations

import ctypes
import queue
import threading
import time

SHOW_SECONDS = 6.0
MAX_LINES = 5
FONT = ("Segoe UI", 16, "bold")
KEY_COLOR = "#010101"          # color que se vuelve transparente
COLORS = {"item": "#7CFC9A", "trap": "#FF6B6B", "check": "#9AD0FF", "death": "#FF3030", "info": "#FFFFFF"}

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000


class Overlay:
    def __init__(self):
        self.q: queue.Queue = queue.Queue()
        self.enabled = True
        self._thread: threading.Thread | None = None
        self._lines: list[tuple[float, str, str]] = []

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="MKXL overlay", daemon=True)
            self._thread.start()

    def show(self, text: str, kind: str = "info"):
        if self.enabled:
            self.start()
            self.q.put((text, kind))

    def stop(self):
        self.q.put(None)

    # ---------- hilo de tkinter ----------
    def _run(self):
        try:
            import tkinter as tk
        except Exception:
            return
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=KEY_COLOR)
        try:
            root.attributes("-transparentcolor", KEY_COLOR)
        except tk.TclError:
            pass
        w, h = 760, 40 * MAX_LINES + 20
        root.geometry(f"{w}x{h}+{root.winfo_screenwidth() - w - 20}+{60}")
        canvas = tk.Canvas(root, bg=KEY_COLOR, highlightthickness=0, width=w, height=h)
        canvas.pack()
        root.update_idletasks()
        try:  # que los clics atraviesen la ventana y no robe el foco al juego
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT
                                                | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        except Exception:
            pass
        root.withdraw()

        def tick():
            stop = False
            while True:
                try:
                    msg = self.q.get_nowait()
                except queue.Empty:
                    break
                if msg is None:
                    stop = True
                    break
                text, kind = msg
                self._lines.append((time.monotonic() + SHOW_SECONDS, text, kind))
            if stop:
                root.destroy()
                return
            now = time.monotonic()
            self._lines = [l for l in self._lines if l[0] > now][-MAX_LINES:]
            canvas.delete("all")
            if self._lines:
                y = 10
                for _, text, kind in self._lines:
                    x = w - 10
                    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (2, 2)):   # contorno negro legible
                        canvas.create_text(x + dx, y + dy, text=text, anchor="ne", font=FONT, fill="#000000")
                    canvas.create_text(x, y, text=text, anchor="ne", font=FONT, fill=COLORS.get(kind, "#FFFFFF"))
                    y += 40
                if root.state() == "withdrawn":
                    root.deiconify()
                root.attributes("-topmost", True)
            elif root.state() != "withdrawn":
                root.withdraw()
            root.after(150, tick)

        root.after(150, tick)
        root.mainloop()
