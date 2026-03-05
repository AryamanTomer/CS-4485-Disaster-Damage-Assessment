import math
from enum import Enum


# Enum that represents damage classes
class DamageClass(Enum):
    # Damage classes:
    PRE_DISASTER = 0    # N/A: pre-disaster
    NO_DAMAGE = 1       # No damage
    MINOR_DAMAGE = 2    # Minor damage
    MAJOR_DAMAGE = 3    # Major damage
    DESTROYED = 4       # Destroyed


# Dictionary mapping JSON damage subtype strings to DamageClass enums
DAMAGE_CLASS_MAP = {
    # Damage classes:
    None: DamageClass.PRE_DISASTER,             # None (pre-disaster)
    "no-damage": DamageClass.NO_DAMAGE,         # No damage
    "minor-damage": DamageClass.MINOR_DAMAGE,   # Minor damage
    "major-damage": DamageClass.MAJOR_DAMAGE,   # Major damage
    "destroyed": DamageClass.DESTROYED          # Destroyed
}


# Defines "processed features": features from the JSON files processed for maximum utility in program
class ProcessedFeature:
    # ProcessedFeature constructor
    def __init__(self, uid, feature_type, vertex_1, vertex_2, damage_class):
        # Attributes:
        self.uid = uid                      # UID
        self.feature_type = feature_type    # Type
        self.vertex_1 = vertex_1            # Vertex 1
        self.vertex_2 = vertex_2            # Vertex 2
        self.damage_class = damage_class    # Damage class

        # Unprocessed features have polygonal shapes with n vertices
        # To aid in generating images of features, processed features are rectangular
        # Shapes of processed features are defined by opposing vertices: vertex 1 and vertex 2


# Simplifies feature polygon into smallest axis-aligned bounding box
def polygon_to_bbox(polygon):
    # Reduce polygon string to comma-separated list of ordered pairs
    polygon = polygon.removeprefix("POLYGON ((").removesuffix("))")

    # Vertices of bounding box:
    min_x = min_y = float("inf")    # Min vertex
    max_x = max_y = float("-inf")   # Max vertex

    # For each vertex in polygon string:
    for vertex in polygon.split(","):
        # Maps vertex x and y from string to float
        x, y = map(float, vertex.split())

        # Updates bounding box vertices:
        min_x = min(min_x, x)   # Min x
        min_y = min(min_y, y)   # Min y
        max_x = max(max_x, x)   # Max x
        max_y = max(max_y, y)   # Max y

    # Returns vertices of bounding box
    return (math.floor(min_x), math.floor(min_y)), (math.ceil(max_x), math.ceil(max_y))


# Gets damage class from JSON feature
def get_damage_class(feature):
    # Gets subtype string (not defined if pre-disaster)
    subtype = feature["properties"].get("subtype")

    try:
        # If damage subtype string is valid, returns corresponding damage class enum
        return DAMAGE_CLASS_MAP[subtype]
    except KeyError:
        # If damage subtype string is invalid, raises value error
        raise ValueError(f"Unknown damage subtype: {subtype}")


# Process a feature so it is easier to work with
def process_feature(feature):
    # Get vertices of bounding box from polygon vertices of feature
    vertex_1, vertex_2 = polygon_to_bbox(feature["wkt"])

    # Get damage class
    damage_class = get_damage_class(feature)

    # Return processed feature
    return ProcessedFeature(feature["properties"]["uid"],           # UID
                            feature["properties"]["feature_type"],  # Feature type
                            vertex_1, vertex_2,                     # Bounds
                            damage_class)                           # Damage class
