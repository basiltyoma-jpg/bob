import os
import requests
import time
import random
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import json
from shapely.geometry import shape, Point

# ======================
# CONFIG
# ======================
hashes = set()
SAVE_DIR = "dataset"
os.makedirs(SAVE_DIR, exist_ok=True)

THREADS = 20
RADIUS = 0.03
MAX_POINTS = 100

ACCESS_TOKEN = "MLY|26223642377319709|5b9e8aec2d3756e7baf3b7f9c61b9ae4"

# ======================
# LOAD COUNTRIES
# ======================

print("🌍 Загружаем страны...")

with open("countries.geojson", encoding="utf-8") as f:
    geo = json.load(f)

countries = []

for feature in geo["features"]:
    props = feature["properties"]
    name = (
        props.get("ADMIN")
        or props.get("NAME")
        or props.get("name")
    )

    countries.append((name, shape(feature["geometry"])))

print(f"✅ Загружено стран: {len(countries)}")

# ======================
# COUNTRY DETECTION
# ======================

def get_country(lat, lon):
    point = Point(lon, lat)

    for name, poly in countries:
        if poly.contains(point):
            return name.replace(" ", "_")

    return "Unknown"

# ======================
# LOCATIONS (твои страны)
# ======================

LOCATIONS = [

    # Oman
    (23.5880, 58.3829),

    # Israel
    (32.0853, 34.7818),

    # Jordan
    (31.9454, 35.9284),

]

# ======================
# GENERATE POINTS
# ======================

def generate_points(lat, lon):
    STEP = 0.02
    points = []

    for dlat in range(-20, 20):
        for dlon in range(-20, 20):
            new_lat = lat + dlat * STEP
            new_lon = lon + dlon * STEP

            points.append((new_lat, new_lon))

            if len(points) >= MAX_POINTS:
                return points

    return points

# ======================
# MAPILLARY
# ======================

def get_images(lat, lon):
    url = "https://graph.mapillary.com/images"
    params = {
        "access_token": ACCESS_TOKEN,
        "fields": "thumb_1024_url",
        "bbox": f"{lon-RADIUS},{lat-RADIUS},{lon+RADIUS},{lat+RADIUS}",
        "limit": 5
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()

        if "data" not in data:
            return []

        return [img["thumb_1024_url"] for img in data["data"]]

    except:
        return []
import cv2
import numpy as np

def is_valid_image(img):
    if img is None:
        return False

    # --- 1. яркость ---
    mean = img.mean()
    if mean < 40 or mean > 220:
        return False

    # --- 2. размытость ---
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    blur = cv2.Laplacian(gray, cv2.CV_64F).var()
    if blur < 80:
        return False

    # --- 3. слишком мало деталей ---
    edges = cv2.Canny(gray, 100, 200)
    edge_density = edges.mean()
    if edge_density < 5:
        return False

    # --- 4. слишком однотонная картинка ---
    std = img.std()
    if std < 20:
        return False

    return True
# ======================
# DOWNLOAD
# ======================

total_downloaded = 0

def download_image(url, lat, lon, country):
    global total_downloaded

    try:
        r = requests.get(url, timeout=10)

        if r.status_code != 200:
            return

        img_array = np.frombuffer(r.content, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        if img is None:
            return

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # 🔥 ФИЛЬТР
        if not is_valid_image(img):
            return

        folder = os.path.join(SAVE_DIR, country)
        os.makedirs(folder, exist_ok=True)

        filename = f"{lat}_{lon}_{random.randint(0,999999)}.jpg"
        path = os.path.join(folder, filename)

        cv2.imwrite(path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

        total_downloaded += 1
        print(f"📥 {country} | {total_downloaded}")
        import hashlib

        # после img загрузки
        h = hashlib.md5(img.tobytes()).hexdigest()
        if h in hashes:
            return
        hashes.add(h)

    except:
        pass

def download_batch(images, lat, lon, country):
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        for url in images:
            executor.submit(download_image, url, lat, lon, country)

# ======================
# MAIN
# ======================

def main():
    print("🚀 Сбор датасета начался")

    for base_lat, base_lon in LOCATIONS:

        base_country = get_country(base_lat, base_lon)

        print(f"\n🌍 Страна: {base_country}")
        print(f"📍 Центр: {base_lat}, {base_lon}")

        points = generate_points(base_lat, base_lon)

        for lat, lon in tqdm(points):

            country = get_country(lat, lon)

            if country == "Unknown":
                continue

            images = get_images(lat, lon)

            if not images:
                print(f"❌ нет данных: {lat:.4f}, {lon:.4f}")
                continue

            download_batch(images, lat, lon, country)

            time.sleep(0.05)

    print("\n🔥 ГОТОВО")
    print("Всего скачано:", total_downloaded)

# ======================
# RUN
# ======================

if __name__ == "__main__":
    main()






