import tkinter as tk
import math


class MapOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        self.root.configure(bg='black')
        self.root.wm_attributes("-transparentcolor", "black")

        # ⚠️ НАСТРОЙ ПОД СВОЙ ЭКРАН
        self.MAP_X = 1000
        self.MAP_Y = 200
        self.MAP_W = 800
        self.MAP_H = 600

        self.canvas = tk.Canvas(
            self.root,
            width=self.MAP_W,
            height=self.MAP_H,
            bg="black",
            highlightthickness=0
        )
        self.canvas.pack()

        self.root.geometry(f"{self.MAP_W}x{self.MAP_H}+{self.MAP_X}+{self.MAP_Y}")

    # ======================
    # ПРОЕКЦИЯ (ВАЖНО)
    # ======================

    def latlon_to_pixel(self, lat, lon):
        # X — линейно
        x = (lon + 180) / 360 * self.MAP_W

        # Y — Web Mercator
        lat_rad = math.radians(lat)
        merc = math.log(math.tan(math.pi/4 + lat_rad/2))

        y = (1 - merc / math.pi) / 2 * self.MAP_H

        return int(x), int(y)

    # ======================
    # UPDATE
    # ======================

    def update(self, lat, lon, conf):
        self.canvas.delete("all")

        x, y = self.latlon_to_pixel(lat, lon)

        # 🎯 точка
        self.canvas.create_oval(
            x-6, y-6, x+6, y+6,
            fill="red"
        )

        # 🔥 кольцо точности
        radius = int((1 - conf) * 50)

        self.canvas.create_oval(
            x-radius, y-radius,
            x+radius, y+radius,
            outline="yellow"
        )

        # 📊 текст
        self.canvas.create_text(
            x, y-20,
            text=f"{conf:.2f}",
            fill="white"
        )

        self.root.update()