import os
import time
import math
import torch
import torch.nn as nn
import torchvision.transforms as transforms
import torchvision.models as models
import torch.nn.functional as F
from PIL import Image
import numpy as np
import faiss
import cv2
import mss
import easyocr
import keyboard
import pyautogui

# ======================
# CONFIG
# ======================

MODEL_PATH = "model.pth"
INDEX_PATH = "index.faiss"
COORDS_PATH = "coords.npy"
DATASET_PATH = "dataset"

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ======================
# SCREENSHOT
# ======================

def grab_screen():
    with mss.mss() as sct:
        img = sct.grab(sct.monitors[1])
        img = np.array(img)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
        return img

# ======================
# MODEL
# ======================

class GeoModel(nn.Module):
    def __init__(self, num_classes):
        super().__init__()

        base = models.resnet18(weights="DEFAULT")
        self.features = nn.Sequential(*list(base.children())[:-1])

        self.embedding = nn.Linear(512, 128)
        self.classifier = nn.Linear(128, num_classes)

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)

        emb = F.normalize(self.embedding(x), p=2, dim=1)
        cls = self.classifier(emb)

        return emb, cls

# ======================
# TRANSFORM
# ======================

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.CenterCrop(180),
    transforms.ToTensor(),
    transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225])
])

# ======================
# OVERLAY
# ======================

import tkinter as tk

class MapOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        self.root.configure(bg='black')
        self.root.wm_attributes("-transparentcolor", "black")

        self.MAP_X = 1300
        self.MAP_Y = 650
        self.MAP_W = 100
        self.MAP_H = 100

        self.canvas = tk.Canvas(
            self.root,
            width=self.MAP_W,
            height=self.MAP_H,
            bg="black",
            highlightthickness=0
        )
        self.canvas.pack()

        self.root.geometry(f"{self.MAP_W}x{self.MAP_H}+{self.MAP_X}+{self.MAP_Y}")

    def latlon_to_pixel(self, lat, lon):
        x = (lon + 180) / 360 * self.MAP_W

        lat_rad = math.radians(lat)
        merc = math.log(math.tan(math.pi/4 + lat_rad/2))
        y = (1 - merc / math.pi) / 2 * self.MAP_H

        return int(x), int(y)

    def update(self, country, lat, lon, conf):
        self.canvas.delete("all")

        x, y = self.latlon_to_pixel(lat, lon)

        # точка
        self.canvas.create_oval(x-6, y-6, x+6, y+6, fill="red")

        # радиус ошибки
        r = int((1 - conf) * 80)
        self.canvas.create_oval(x-r, y-r, x+r, y+r, outline="yellow")

        # текст
        self.canvas.create_text(x, y-35, text=country, fill="white")
        self.canvas.create_text(x, y-20, text=f"{conf:.2f}", fill="white")

        self.root.update()

# ======================
# LOAD
# ======================

def load_labels():
    return [d for d in os.listdir(DATASET_PATH) if os.path.isdir(os.path.join(DATASET_PATH, d))]

def load_all():
    labels = load_labels()

    model = GeoModel(len(labels)).to(DEVICE)

    state_dict = torch.load(MODEL_PATH, map_location=DEVICE)
    state_dict.pop("classifier.weight", None)
    state_dict.pop("classifier.bias", None)
    model.load_state_dict(state_dict, strict=False)

    model.eval()

    index = faiss.read_index(INDEX_PATH)
    coords = np.load(COORDS_PATH, allow_pickle=True)

    reader = easyocr.Reader(['en'], gpu=False)

    return model, index, coords, labels, reader

# ======================
# BRAINS
# ======================

def brain_cnn(img, model, labels):
    img_pil = Image.fromarray(img)
    img_t = transform(img_pil).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        emb, logits = model(img_t)

    probs = torch.softmax(logits, dim=1)
    conf, pred = torch.max(probs, dim=1)

    return emb.cpu().numpy(), labels[pred.item()], conf.item()

def brain_faiss(emb, index, coords):
    D, I = index.search(emb, k=5)

    lats = [coords[i][0] for i in I[0]]
    lons = [coords[i][1] for i in I[0]]

    return np.mean(lats), np.mean(lons)

def brain_ocr(img, reader):
    res = reader.readtext(img)
    text = " ".join([r[1] for r in res])

    if "USA" in text: return "USA"
    if "BR" in text: return "Brazil"
    if "MX" in text: return "Mexico"

    return None

def voting(cnn_label, lat, lon, ocr):
    votes = [cnn_label]

    if -140 < lon < -50:
        votes.append("USA")
    elif -30 < lon < 60:
        votes.append("Europe")
    elif 60 < lon < 150:
        votes.append("Asia")

    if ocr:
        votes += [ocr, ocr]

    return max(set(votes), key=votes.count)

# ======================
# MAIN
# ======================

def main():
    print("🔄 Loading...")
    model, index, coords, labels, reader = load_all()

    overlay = MapOverlay()

    print("🎮 Нажми F9")

    while True:
        if keyboard.is_pressed("F9"):

            print("📸 Capture...")

            img = grab_screen()

            emb, cnn_label, conf = brain_cnn(img, model, labels)
            lat, lon = brain_faiss(emb, index, coords)
            ocr = brain_ocr(img, reader)

            final = voting(cnn_label, lat, lon, ocr)

            print(f"\n🌍 {final}")
            print(f"📍 {lat:.4f}, {lon:.4f}")
            print(f"📊 {conf:.2f}")

            overlay.update(final, lat, lon, conf)

            time.sleep(1)

# ======================

if __name__ == "__main__":
    main()