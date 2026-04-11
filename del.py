import os
import shutil
import json
from shapely.geometry import shape, Point

DATASET = "dataset"

# ❗ папки, которые надо удалить
OLD_FOLDERS = [
    "Europe", "USA", "Asia", "LATAM", "Africa", "Other"
]

# ======================
# DELETE OLD STRUCTURE
# ======================

import stat

def handle_remove_error(func, path, exc):
    # снимаем readonly и пробуем снова
    os.chmod(path, stat.S_IWRITE)
    func(path)

def delete_old():
    print("🧹 Удаляем старые папки...")

    for folder in OLD_FOLDERS:
        path = os.path.join(DATASET, folder)

        if os.path.exists(path):
            try:
                shutil.rmtree(path, onerror=handle_remove_error)
                print(f"❌ Удалено: {folder}")
            except Exception as e:
                print(f"⚠️ Не удалось удалить: {folder} ({e})")

# ======================
# LOAD COUNTRIES
# ======================

print("🌍 Загружаем границы стран...")

with open("countries.geojson", encoding="utf-8") as f:
    geo = json.load(f)

countries = []

for feature in geo["features"]:
    props = feature["properties"]

    name = (
        props.get("ADMIN") or
        props.get("NAME") or
        props.get("name") or
        props.get("COUNTRY") or
        "Unknown"
    )

    polygon = shape(feature["geometry"])
    countries.append((name, polygon))

print(f"✅ Стран загружено: {len(countries)}")

# ======================
# NORMALIZE NAMES
# ======================

RENAME = {
    "United States of America": "USA",
    "United Kingdom": "UK",
    "Russian Federation": "Russia",
    "Korea, Republic of": "SouthKorea",
    "Korea, Democratic People's Republic of": "NorthKorea"
}

# ======================
# FIND COUNTRY
# ======================

def get_country(lat, lon):
    point = Point(lon, lat)

    for name, poly in countries:
        if poly.contains(point):
            return RENAME.get(name, name.replace(" ", "_"))

    return "Unknown"

# ======================
# MOVE ALL IMAGES
# ======================

def organize():
    print("📦 Начинаем распределение по странам...")

    moved = 0

    for root, _, files in os.walk(DATASET):
        for file in files:

            if not file.lower().endswith((".jpg", ".jpeg", ".png")):
                continue

            try:
                name = file.replace(".jpg", "").replace(".png", "").replace(".jpeg", "")
                parts = name.split("_")

                lat = float(parts[-2])
                lon = float(parts[-1])

                country = get_country(lat, lon)

                if country == "Unknown":
                    continue

                src = os.path.join(root, file)
                dst_dir = os.path.join(DATASET, country)

                os.makedirs(dst_dir, exist_ok=True)
                dst = os.path.join(dst_dir, file)

                if src == dst:
                    continue

                shutil.move(src, dst)
                moved += 1

                if moved % 100 == 0:
                    print(f"📊 Перемещено: {moved}")

            except Exception as e:
                print("❌ Ошибка:", file)

    print(f"\n✅ ГОТОВО! Всего перемещено: {moved}")

# ======================
# MAIN
# ======================

if __name__ == "__main__":
    delete_old()
    organize()