import json
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T
from torch.utils.data import Dataset, DataLoader
from PIL import Image
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
IMAGES_DIR  = Path("data/train/images")
LABELS_DIR  = Path("data/train/labels")
WEIGHTS_OUT = Path("backend/weights/resnet18_damage.pth")
WEIGHTS_OUT.parent.mkdir(exist_ok=True)

LABELS    = ["no-damage", "minor-damage", "major-damage", "destroyed"]
LABEL2IDX = {l: i for i, l in enumerate(LABELS)}
SEVERITY  = {"no-damage": 0, "minor-damage": 1,
             "major-damage": 2, "destroyed": 3}

EPOCHS     = 1
BATCH_SIZE = 16
LR         = 1e-4
IMG_SIZE   = 224
DEVICE     = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ── Transform (3-channel only — applied to each image separately) ─────────────
transform = T.Compose([
    T.Resize((IMG_SIZE, IMG_SIZE)),
    T.RandomHorizontalFlip(),
    T.RandomVerticalFlip(),
    T.ColorJitter(brightness=0.2, contrast=0.2),
    T.ToTensor(),
    T.Normalize([0.485, 0.456, 0.406],   # 3-channel mean
                [0.229, 0.224, 0.225]),   # 3-channel std
])

val_transform = T.Compose([
    T.Resize((IMG_SIZE, IMG_SIZE)),
    T.ToTensor(),
    T.Normalize([0.485, 0.456, 0.406],
                [0.229, 0.224, 0.225]),
])

# ── Dataset ───────────────────────────────────────────────────────────────────

class DisasterDataset(Dataset):
    def __init__(self, transform=None):
        self.samples   = []
        self.transform = transform

        post_images = sorted(IMAGES_DIR.glob("*_post_disaster.png"))
        for post_path in post_images:
            pre_path   = IMAGES_DIR / post_path.name.replace("_post_", "_pre_")
            label_path = LABELS_DIR / post_path.name.replace(".png", ".json")

            if not pre_path.exists() or not label_path.exists():
                continue

            with open(label_path) as f:
                data = json.load(f)

            subtypes = [feat["properties"]["subtype"]
                        for feat in data["features"]["lng_lat"]]
            subtypes_valid = [s for s in subtypes if s in SEVERITY]

            if not subtypes_valid:
                continue

            label = max(set(subtypes_valid), key=subtypes_valid.count)
            if label not in LABEL2IDX:
                continue

            self.samples.append((pre_path, post_path, LABEL2IDX[label]))

        print(f"Dataset: {len(self.samples)} samples loaded")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        pre_path, post_path, label = self.samples[idx]

        pre  = Image.open(pre_path).convert("RGB")
        post = Image.open(post_path).convert("RGB")

        # Apply 3-channel transform to each image SEPARATELY, then concatenate
        # This avoids the 6-channel normalization error
        if self.transform:
            pre  = self.transform(pre)   # → [3, H, W]
            post = self.transform(post)  # → [3, H, W]

        combined = torch.cat([pre, post], dim=0)  # → [6, H, W]
        return combined, label

# ── Model ─────────────────────────────────────────────────────────────────────

def build_model():
    """
    ResNet-18 modified to accept 6-channel input (pre + post concatenated).
    First conv layer expanded from 3 to 6 channels.
    Pretrained ImageNet weights averaged across the extra channels.
    """
    model    = models.resnet18(weights="IMAGENET1K_V1")
    old_conv = model.conv1

    model.conv1 = nn.Conv2d(
        6, 64,
        kernel_size=old_conv.kernel_size,
        stride=old_conv.stride,
        padding=old_conv.padding,
        bias=False
    )

    # Initialize new conv by averaging pretrained weights across 6 channels
    with torch.no_grad():
        model.conv1.weight = nn.Parameter(
            old_conv.weight.repeat(1, 2, 1, 1) / 2.0
        )

    # 4-class output head
    model.fc = nn.Linear(model.fc.in_features, 4)
    return model

# ── Training ──────────────────────────────────────────────────────────────────

def train():
    full_dataset = DisasterDataset(transform=None)  # load paths first

    train_size = int(0.8 * len(full_dataset))
    val_size   = len(full_dataset) - train_size
    train_ds, val_ds = torch.utils.data.random_split(
        full_dataset, [train_size, val_size],
        generator=torch.Generator().manual_seed(42)
    )

    # Apply different transforms to train vs val
    train_ds.dataset.transform = transform
    val_ds.dataset.transform   = val_transform

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE,
                              shuffle=True,  num_workers=0)
    val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE,
                              shuffle=False, num_workers=0)

    model     = build_model().to(DEVICE)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    scheduler = torch.optim.lr_scheduler.StepLR(
        optimizer, step_size=3, gamma=0.5
    )

    best_val_acc = 0.0

    for epoch in range(EPOCHS):
        # ── Train ──
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total   = 0

        for imgs, labels in train_loader:
            imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
            optimizer.zero_grad()
            outputs = model(imgs)
            loss    = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            train_loss    += loss.item()
            preds          = outputs.argmax(dim=1)
            train_correct += (preds == labels).sum().item()
            train_total   += labels.size(0)

        # ── Validate ──
        model.eval()
        val_correct = 0
        val_total   = 0

        with torch.no_grad():
            for imgs, labels in val_loader:
                imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
                outputs      = model(imgs)
                preds        = outputs.argmax(dim=1)
                val_correct += (preds == labels).sum().item()
                val_total   += labels.size(0)

        train_acc = train_correct / train_total
        val_acc   = val_correct   / val_total
        scheduler.step()

        print(f"Epoch {epoch+1}/{EPOCHS} | "
              f"Loss: {train_loss/len(train_loader):.4f} | "
              f"Train Acc: {train_acc:.1%} | "
              f"Val Acc: {val_acc:.1%}")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), WEIGHTS_OUT)
            print(f"  ✓ Saved best model (val_acc={val_acc:.1%})")

    print(f"\nTraining complete. Best val accuracy: {best_val_acc:.1%}")
    print(f"Weights saved to: {WEIGHTS_OUT}")

if __name__ == "__main__":
    print(f"Training on: {DEVICE}")
    train()