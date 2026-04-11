import os
import cv2
import random
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as transforms
import faiss
from tqdm import tqdm

# -------- CONFIG --------
DATASET_PATH = "dataset"
GRID_SIZE = 1.0  # degrees (~111km)
EMBED_DIM = 512
EPOCHS = 5
BATCH_SIZE = 16

# -------- GRID UTILS --------
def latlon_to_cell(lat, lon, grid_size=GRID_SIZE):
    lat_cell = int(lat // grid_size)
    lon_cell = int(lon // grid_size)
    return f"{lat_cell}_{lon_cell}"

# -------- IMAGE FILTER --------
def is_valid(img):
    if img is None:
        return False

    if img.mean() < 40 or img.mean() > 220:
        return False

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    if cv2.Laplacian(gray, cv2.CV_64F).var() < 100:
        return False

    return True

# -------- LOAD DATASET --------
def load_dataset(dataset_path):
    data = []

    for file in os.listdir(dataset_path):
        if not file.endswith(".jpg"):
            continue

        try:
            lat, lon = map(float, file.replace(".jpg", "").split("_"))
            cell = latlon_to_cell(lat, lon)

            img = cv2.imread(os.path.join(dataset_path, file))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            if not is_valid(img):
                continue

            data.append((img, cell))

        except:
            continue

    print(f"Loaded {len(data)} images")
    return data

# -------- MODEL --------
class GeoModel(nn.Module):
    def __init__(self):
        super().__init__()
        base = models.resnet18(pretrained=True)
        self.features = nn.Sequential(*list(base.children())[:-1])

    def forward(self, x):
        x = self.features(x)
        return x.view(x.size(0), -1)

# -------- TRIPLET DATASET --------
transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
])

class TripletDataset(torch.utils.data.Dataset):
    def __init__(self, data):
        self.data = data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        anchor_img, anchor_label = self.data[idx]

        pos = random.choice([x for x in self.data if x[1] == anchor_label])
        neg = random.choice([x for x in self.data if x[1] != anchor_label])

        return (
            transform(anchor_img),
            transform(pos[0]),
            transform(neg[0]),
        )

# -------- TRAINING --------
def train(model, data, device, epochs=EPOCHS):
    dataset = TripletDataset(data)
    loader = torch.utils.data.DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
    criterion = nn.TripletMarginLoss(margin=1.0)

    model.train()

    for epoch in range(epochs):
        total_loss = 0
        for anchor, positive, negative in loader:
            anchor = anchor.to(device)
            positive = positive.to(device)
            negative = negative.to(device)

            emb_a = model(anchor)
            emb_p = model(positive)
            emb_n = model(negative)

            loss = criterion(emb_a, emb_p, emb_n)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        print(f"Epoch {epoch+1}, Loss: {total_loss:.4f}")

    return model

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

def build_memory(model, data, device):
    memory = FaissMemory()
    model.eval()
    with torch.no_grad():
        for img, label in data:
            tensor = transform(img).unsqueeze(0).to(device)
            emb = model(tensor).cpu().numpy()[0]
            memory.add(emb, label)
    return memory

# -------- PREDICTION --------
def predict(model, memory, frame, device):
    tensor = transform(frame).unsqueeze(0).to(device)
    with torch.no_grad():
        emb = model(tensor).cpu().numpy()[0]
    neighbors = memory.search(emb, k=5)
    if not neighbors:
        return "Unknown"
    return max(set(neighbors), key=neighbors.count)

# -------- MAIN --------
def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("Loading dataset...")
    data = load_dataset(DATASET_PATH)

    print("Initializing model...")
    model = GeoModel().to(device)

    print("Training model...")
    model = train(model, data, device, epochs=EPOCHS)

    print("Building FAISS memory...")
    memory = build_memory(model, data, device)

    print("Ready for prediction!")

if __name__ == "__main__":
    main()
