import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T
from PIL import Image
from pathlib import Path

LABELS    = ["no-damage", "minor-damage", "major-damage", "destroyed"]
WEIGHTS   = Path("backend/weights/resnet18_damage.pth")
DEVICE    = torch.device("cuda" if torch.cuda.is_available() else "cpu")
IMG_SIZE  = 224

transform = T.Compose([
    T.Resize((IMG_SIZE, IMG_SIZE)),
    T.ToTensor(),
    T.Normalize([0.485, 0.456, 0.406, 0.485, 0.456, 0.406],
                [0.229, 0.224, 0.225, 0.229, 0.224, 0.225]),
])

def build_model():
    model    = models.resnet18(weights=None)
    old_conv = model.conv1
    model.conv1 = nn.Conv2d(
        6, 64,
        kernel_size=old_conv.kernel_size,
        stride=old_conv.stride,
        padding=old_conv.padding,
        bias=False
    )
    model.fc = nn.Linear(model.fc.in_features, 4)
    return model

def load_model():
    model = build_model()
    model.load_state_dict(torch.load(WEIGHTS, map_location=DEVICE))
    model.eval().to(DEVICE)
    return model

def predict(model, pre_path: Path, post_path: Path) -> str:
    pre  = Image.open(pre_path).convert("RGB")
    post = Image.open(post_path).convert("RGB")
    pre  = transform(pre)
    post = transform(post)
    inp  = torch.cat([pre, post], dim=0).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        logits = model(inp)
        idx    = logits.argmax(dim=1).item()

    return LABELS[idx]

if __name__ == "__main__":
    model = load_model()
    images_dir = Path("data/train/images")
    pre  = images_dir / "hurricane-michael_00000239_pre_disaster.png"
    post = images_dir / "hurricane-michael_00000239_post_disaster.png"
    print(predict(model, pre, post))