import os
import random
from collections import Counter

import torch
import torch.nn as nn
import torch.optim as optim
import torchvision.transforms as transforms
import torchvision.models as models
import torch.nn.functional as F
from PIL import Image

# ======================
# CONFIG
# ======================

DATASET_PATH = "dataset"
BATCH_SIZE = 16
EPOCHS = 10
EMBEDDING_SIZE = 128
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ======================
# TRANSFORM
# ======================

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomHorizontalFlip(),
    transforms.ColorJitter(0.3, 0.3, 0.3),
    transforms.RandomGrayscale(p=0.1),
    transforms.ToTensor(),
    transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225])
])

# ======================
# LOAD DATASET
# ======================

def load_data():
    data = []
    labels = []

    for country in os.listdir(DATASET_PATH):
        path = os.path.join(DATASET_PATH, country)

        if not os.path.isdir(path):
            continue

        images = [f for f in os.listdir(path) if f.endswith(".jpg")]

        # ❌ пропуск пустых
        if len(images) == 0:
            continue

        labels.append(country)

        for file in images:
            data.append((os.path.join(path, file), country))

    print("🌍 Страны:", labels)
    print("📦 Всего:", len(data))

    return data, labels

# ======================
# DATASET (🔥 BALANCED)
# ======================

class GeoDataset(torch.utils.data.Dataset):
    def __init__(self, data, label_to_idx):
        self.data = data
        self.label_to_idx = label_to_idx

        self.label_to_images = {}
        for path, label in data:
            self.label_to_images.setdefault(label, []).append(path)

        self.labels = list(self.label_to_images.keys())

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        # 🔥 баланс по странам
        label = random.choice(self.labels)

        anchor_path = random.choice(self.label_to_images[label])
        pos_path = random.choice(self.label_to_images[label])

        neg_label = random.choice([l for l in self.labels if l != label])
        neg_path = random.choice(self.label_to_images[neg_label])

        anchor = transform(Image.open(anchor_path).convert("RGB"))
        pos = transform(Image.open(pos_path).convert("RGB"))
        neg = transform(Image.open(neg_path).convert("RGB"))

        label_id = self.label_to_idx[label]

        return anchor, pos, neg, label_id

# ======================
# MODEL
# ======================

class GeoModel(nn.Module):
    def __init__(self, num_classes):
        super().__init__()

        base = models.resnet18(weights="DEFAULT")
        self.features = nn.Sequential(*list(base.children())[:-1])

        self.embedding = nn.Linear(512, EMBEDDING_SIZE)
        self.classifier = nn.Linear(EMBEDDING_SIZE, num_classes)

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)

        emb = self.embedding(x)
        emb = F.normalize(emb, p=2, dim=1)

        cls = self.classifier(emb)

        return emb, cls

# ======================
# CLASS WEIGHTS
# ======================

def get_class_weights(data, label_to_idx):
    counts = Counter([label for _, label in data])
    total = sum(counts.values())

    weights = []
    for label in label_to_idx:
        weights.append(total / counts[label])

    return torch.tensor(weights, dtype=torch.float32)

# ======================
# TRAIN
# ======================

def train(model, loader, ce_loss):
    optimizer = optim.Adam(model.parameters(), lr=1e-4)
    triplet = nn.TripletMarginLoss(margin=0.3)

    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0

        for anchor, pos, neg, label in loader:
            anchor = anchor.to(DEVICE)
            pos = pos.to(DEVICE)
            neg = neg.to(DEVICE)
            label = label.to(DEVICE)

            emb_a, cls_a = model(anchor)
            emb_p, _ = model(pos)
            emb_n, _ = model(neg)

            loss_triplet = triplet(emb_a, emb_p, emb_n)
            loss_cls = ce_loss(cls_a, label)

            # 🔥 баланс лоссов
            loss = loss_triplet + 0.3 * loss_cls

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        print(f"Epoch {epoch+1}, Loss: {total_loss / len(loader):.4f}")

    return model

# ======================
# MAIN
# ======================

def main():
    print("📥 Loading dataset...")
    data, labels = load_data()

    if len(data) == 0:
        print("❌ Нет данных")
        return

    label_to_idx = {l:i for i,l in enumerate(labels)}

    dataset = GeoDataset(data, label_to_idx)
    loader = torch.utils.data.DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=4
    )

    print("🧠 Initializing model...")
    model = GeoModel(len(labels)).to(DEVICE)

    # 🔥 веса классов
    weights = get_class_weights(data, label_to_idx).to(DEVICE)
    ce_loss = nn.CrossEntropyLoss(weight=weights)

    print("🚀 Training...")
    model = train(model, loader, ce_loss)

    torch.save(model.state_dict(), "model.pth")
    print("💾 Model saved")

# ======================
# RUN
# ======================

if __name__ == "__main__":
    main()