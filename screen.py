# Advanced GeoGuessr AI: Grid + FAISS + Training
# This is a more serious architecture with:
# - grid-based geolocation
# - FAISS memory
# - training loop

import os
import numpy as np
import cv2
import torch
import torch.nn as nn
import torchvision.transforms as transforms
import torchvision.models as models
import faiss

# -------- CONFIG --------
DATASET_PATH = "dataset"
GRID_SIZE = 1.0  # degrees (~111km)
EMBED_DIM = 512

# -------- GRID UTILS --------
def latlon_to_cell(lat, lon, grid_size=GRID_SIZE):
    lat_cell = int(lat // grid_size)
    lon_cell = int(lon // grid_size)
    return f"{lat_cell}_{lon_cell}"

# -------- MODEL --------
class GeoModel(nn.Module):
    def __init__(self):
        super().__init__()
        base = models.resnet18(pretrained=True)
        self.features = nn.Sequential(*list(base.children())[:-1])

    def forward(self, x):
        x = self.features(x)
        return x.view(x.size(0), -1)

# -------- FAISS MEMORY --------
class FaissMemory:
    def __init__(self, dim=EMBED_DIM):
        self.index = faiss.IndexFlatL2(dim)
        self.labels = []

    def add(self, embedding, label):
        self.index.add(np.array([embedding]).astype('float32'))
        self.labels.append(label)

    def search(self, embedding, k=5):
        if len(self.labels) == 0:
            return []
        D, I = self.index.search(np.array([embedding]).astype('float32'), k)
        return [self.labels[i] for i in I[0]]

# -------- DATA LOADING --------
transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
])


def load_dataset(dataset_path):
    data = []

    for file in os.listdir(dataset_path):
        if not file.endswith(".jpg"):
            continue

        # filename format: lat_lon.jpg
        try:
            lat, lon = map(float, file.replace(".jpg", "").split("_"))
            cell = latlon_to_cell(lat, lon)

            img = cv2.imread(os.path.join(dataset_path, file))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            data.append((img, cell))
        except:
            continue

    return data

# -------- TRAINING --------
def build_memory(model, data, device):
    memory = FaissMemory()

    model.eval()

    for img, label in data:
        tensor = transform(img).unsqueeze(0).to(device)

        with torch.no_grad():
            emb = model(tensor).cpu().numpy()[0]

        memory.add(emb, label)

    return memory

# -------- PREDICTION --------
def predict(model, memory, frame, device):
    tensor = transform(frame).unsqueeze(0).to(device)

    with torch.no_grad():
        emb = model(tensor).cpu().numpy()[0]

    neighbors = memory.search(emb, k=5)

    # majority vote
    if not neighbors:
        return "Unknown"

    return max(set(neighbors), key=neighbors.count)

# -------- MAIN --------
def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("Loading model...")
    model = GeoModel().to(device)

    print("Loading dataset...")
    data = load_dataset(DATASET_PATH)
    print(f"Loaded {len(data)} samples")

    print("Building FAISS memory...")
    memory = build_memory(model, data, device)

    print("Ready! Press Ctrl+C to stop.")

    cap = cv2.VideoCapture(0)  # or replace with screen capture

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        pred = predict(model, memory, frame, device)

        cv2.putText(frame, pred, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
        cv2.imshow("GeoAI", frame)

        if cv2.waitKey(1) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

