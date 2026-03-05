import math


# Defines "processed features": features from the JSON files processed for maximum utility in program
class ProcessedFeature:
    # ProcessedFeature constructor
    def __init__(self, uid, feature_type, vertex_1, vertex_2):
        # Attributes:
        self.uid = uid                      # UID
        self.feature_type = feature_type    # Type
        self.vertex_1 = vertex_1            # Vertex 1
        self.vertex_2 = vertex_2            # Vertex 2

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


# Simplifies polygon into smallest axis-aligned bounding box
# Polygon: list of n ordered pairs
# Bounding box: two ordered pairs at opposing corners of box
def simplify_feature_shape(vertices):
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


# Process a feature so it is easier to work with
def process_feature(feature):
    # Get vertices of bounding box from polygon vertices
    vertex_1, vertex_2 = simplify_feature_shape(polygon_string_to_list(feature["wkt"]))

    # Return processed feature
    return ProcessedFeature(feature["properties"]["uid"], feature["properties"]["feature_type"], vertex_1, vertex_2)
