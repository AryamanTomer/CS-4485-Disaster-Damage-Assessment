from PIL import Image
import json
from pathlib import Path
from process_features import ProcessedFeature, process_feature

# Project root
root = Path(__file__).parent.parent

# Image pair name (root of image and label filenames)
image_pair = "socal-fire_00000031_"

# Directories for:
images = root / "test_images_labels_targets/test/images/"   # Images
labels = root / "test_images_labels_targets/test/labels/"   # Labels

# Open image files:
img_pre_disaster = Image.open(images / (image_pair + "pre_disaster.png"))       # Pre-disaster
img_post_disaster = Image.open(images / (image_pair + "post_disaster.png"))     # Post-disaster

# Open label files:
label_pre_disaster_file = open(labels / (image_pair + "pre_disaster.json"), 'r')    # Pre-disaster
label_post_disaster_file = open(labels / (image_pair + "post_disaster.json"), 'r')  # Post-disaster

# Load label JSONs:
label_pre_disaster = json.load(label_pre_disaster_file)     # Pre-disaster
label_post_disaster = json.load(label_post_disaster_file)   # Post-disaster

# Store lists of features from JSONS:
features_pre_disaster = label_pre_disaster["features"]["xy"]    # Pre-disaster
features_post_disaster = label_post_disaster["features"]["xy"]  # Post-disaster

# Store lists of processed features:
# ("Processed features" are features from the JSON files processed so they are convenient to work with)
processed_features_pre_disaster = [process_feature(feature) for feature in features_pre_disaster]       # Pre-disaster
processed_features_post_disaster = [process_feature(feature) for feature in features_post_disaster]     # Post-disaster
