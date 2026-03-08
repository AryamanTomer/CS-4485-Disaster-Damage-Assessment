import torch
import torchvision.models as models
import torchvision.transforms as T
from PIL import Image
from pathlib import Path
import numpy as np

# Pre-trained ResNet fine-tuned on xBD disaster data
# Labels match FEMA classes exactly
LABELS = ["no-damage", "minor-damage", "major-damage", "destroyed"]

transform = T.Compose([
    T.Resize((256, 256)),
    T.ToTensor(),
    T.Normalize([0.485, 0.456, 0.406],
                [0.229, 0.224, 0.225])
])

def load_model(weights_path: str):
    model = models.resnet50(pretrained=False)
    model.fc = torch.nn.Linear(model.fc.in_features, 4)
    model.load_state_dict(torch.load(weights_path, map_location="cpu"))
    model.eval()
    return model

def predict(model, pre_path, post_path) -> str:
    pre = transform(Image.open(pre_path).convert("RGB")).unsqueeze(0)
    post = transform(Image.open(post_path).convert("RGB")).unsqueeze(0)
    inp = torch.cat([pre, post], dim=1)  # 6-channel input
    with torch.no_grad():
        logits = model(inp)
    return LABELS[logits.argmax().item()]