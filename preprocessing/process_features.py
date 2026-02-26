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


# Simplifies polygon into smallest axis-aligned bounding box
# Polygon: list of n ordered pairs
# Bounding box: two ordered pairs at opposing corners of box
def simplify_feature_shape(vertices):
    # Will store vertices of bounding box
    min_x = 0   # Min x
    min_y = 0   # Min y
    max_x = 0   # Max x
    max_y = 0   # Max y

    # Go through each vertex of polygon to determine bounding box vertices
    for vertex in vertices:
        # Find:
        min_x = vertex[0] if vertex[0] < min_x else min_x   # Min x
        min_y = vertex[1] if vertex[1] < min_y else min_y   # Min y
        max_x = vertex[0] if vertex[0] > max_x else max_x   # Max x
        max_y = vertex[1] if vertex[1] > max_y else max_y   # Max y

    # Return vertices of bounding box as a pair of tuples
    return (min_x, min_y), (max_x, max_y)
