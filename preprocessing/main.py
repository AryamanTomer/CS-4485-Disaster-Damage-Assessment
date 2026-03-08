from PIL import Image
import json
from pathlib import Path
from feature import process_raw_feature, DamageClass


# Saves cropped images of features
def save_feature_images(feature_images, features, save_directory, disaster, image_pair_num):
    # Go through each pair of feature image + feature
    for i in range(len(feature_images)):
        # Get feature and feature image:
        feature = features[i]       # Feature
        image = feature_images[i]   # Feature image

        # Stem of image filename: [disaster]_[image pair number]_[feature type]_[feature UID]
        filename_stem = f"{disaster}_{image_pair_num}_{feature.feature_type}_{feature.uid}"

        # Filename suffix depends on whether image is pre- or post-disaster:
        match feature.damage_class:
            # For pre-disaster images, suffix is "pre_disaster"
            case DamageClass.PRE_DISASTER:
                filename_suffix = "pre_disaster"

            # For post-disaster images, suffix is "post_disaster"
            case _:
                filename_suffix = "post_disaster"

        # Save feature image as [filename stem]_[filename suffix].png
        image.save(
            save_directory /
            f"{filename_stem}_{filename_suffix}.png"
        )


# Main function
def main():
    # Directories for:
    root = Path(__file__).parent.parent     # Project root
    images_dir = root / "data/images/"      # Images from dataset
    labels_dir = root / "data/labels/"      # Labels from dataset
    feature_images_dir = root / "bin/"      # Cropped feature images

    # Disaster
    disaster = "socal-fire"

    # Iterate through every file in labels directory:
    for file_path in labels_dir.iterdir():
        # Verify that file is JSON of correct disaster
        if file_path.name.endswith(".json") and file_path.name.startswith(disaster):
            # Open JSON label
            label = json.load(open(file_path, 'r'))

            # Get features
            features = [process_raw_feature(raw_feature) for raw_feature in label["features"]["xy"]]

            # Open image specified in JSON label
            image = Image.open(images_dir / label["metadata"]["img_name"])

            # Crop features from image
            feature_images = [
                # Add feature image cropped according to feature's bounding box
                image.crop((feature.min_x(), feature.min_y(), feature.max_x(), feature.max_y()))
                for feature in features
            ]

            # Save feature images:
            save_feature_images(
                feature_images, features, feature_images_dir,
                label["metadata"]["disaster"],  # Disaster as specified in JSON
                file_path.name.split('_')[1]    # Image pair number from filename
            )

            # Close image file
            image.close()


# Calls main()
if __name__ == "__main__":
    main()
