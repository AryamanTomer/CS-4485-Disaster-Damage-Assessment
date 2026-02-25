import base64
import os
from dotenv import load_dotenv
from pathlib import Path
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent / ".env")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def assess_damage(pre_image_path, post_image_path):
    pre_b64 = encode_image(pre_image_path)
    post_b64 = encode_image(post_image_path)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": """You are a disaster damage assessment expert analyzing aerial satellite imagery.
Compare the PRE-disaster (first image) and POST-disaster (second image).
Focus ONLY on buildings and structures.

Damage levels:
- no-damage: buildings identical in both images, no visible changes
- minor-damage: slight debris, discoloration, or minor roof damage on 1-2 buildings
- major-damage: clearly collapsed walls, missing roofs, or heavy debris on multiple buildings
- destroyed: buildings completely flattened, foundations only, or entirely gone

IMPORTANT: If you see flooding around intact buildings, that is minor-damage not major-damage.
IMPORTANT: If roofs are visibly missing or walls collapsed, that is major-damage.
IMPORTANT: Only classify as destroyed if the building footprint is gone entirely.

Respond with ONLY one label: no-damage, minor-damage, major-damage, or destroyed"""},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{pre_b64}"}},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{post_b64}"}}
            ]
        }],
        max_tokens=50
    )

    return response.choices[0].message.content.strip().lower()

if __name__ == "__main__":
    images_dir = Path("data/train/images")
    pre = images_dir / "hurricane-michael_00000239_pre_disaster.png"
    post = images_dir / "hurricane-michael_00000239_post_disaster.png"
    result = assess_damage(pre, post)
    print(result)