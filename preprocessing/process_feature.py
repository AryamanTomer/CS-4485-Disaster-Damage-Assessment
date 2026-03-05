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


# Converts POLYGON string from JSON into list of vertices
def polygon_string_to_list(polygon):
    # Remove prefix and suffix so polygon string is only comma-separated list of ordered pairs
    polygon = polygon.removeprefix("POLYGON ((").removesuffix("))")

    # Tokenize polygon: each token is a string representing a ordered pair
    vertex_strings = polygon.split(", ")

    # Convert ordered pair strings to actual ordered pair tuples
    vertices = []
    for string in vertex_strings:
        # Tokenize ordered pair string into x and y strings
        vertex_string_list = string.split(" ")

        # Convert x and y strings to floats and add ordered pair to vertices list
        vertices.append((float(vertex_string_list[0]), float(vertex_string_list[1])))

    # Return list of vertices
    return vertices


# Simplifies feature polygon into smallest axis-aligned bounding box
# Polygon: list of n ordered pairs
# Bounding box: two ordered pairs at opposing corners of box
def simplify_feature_shape(feature):
    # Gets vertices from provided feature
    vertices = polygon_string_to_list(feature["wkt"])

    # Will store vertices of bounding box; initialized to x and y of first vertex
    min_x = max_x = vertices[0][0]  # Min x and max x
    min_y = max_y = vertices[0][1]  # Min y and max y

    # Go through each vertex of polygon to determine bounding box vertices
    for vertex in vertices:
        # Find:
        min_x = vertex[0] if vertex[0] < min_x else min_x   # Min x
        min_y = vertex[1] if vertex[1] < min_y else min_y   # Min y
        max_x = vertex[0] if vertex[0] > max_x else max_x   # Max x
        max_y = vertex[1] if vertex[1] > max_y else max_y   # Max y

    # Return vertices of bounding box as a pair of tuples; min values rounded down and max values rounded up
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
    vertex_1, vertex_2 = simplify_feature_shape(feature)

    # Get damage class
    damage_class = get_damage_class(feature)

    # Return processed feature
    return ProcessedFeature(feature["properties"]["uid"],           # UID
                            feature["properties"]["feature_type"],  # Feature type
                            vertex_1, vertex_2,                     # Bounds
                            damage_class)                           # Damage class
