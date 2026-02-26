import numpy as np

def worldToScreen(viewmatrix, worldPos, windowsSize):
    """
    Convert 3D world position to 2D screen coordinates using view matrix.
    
    Args:
        viewmatrix: Tuple of 16 floats (4x4 matrix)
        worldPos: Tuple of (x, y, z) world coordinates
        windowsSize: Tuple of (height, width) screen dimensions
    
    Returns:
        Tuple of (screen_x, screen_y) or (0, 0) if behind camera
    """
    # Reshape viewmatrix to 4x4
    mat = np.array(viewmatrix).reshape(4, 4)
    
    # Convert worldPos to homogeneous coordinates (x, y, z, 1)
    pos = np.array([worldPos[0], worldPos[1], worldPos[2], 1.0])
    
    # Matrix multiplication: clipSpace = mat @ pos
    clipSpace = mat @ pos
    
    # Unpack clip space coordinates
    x, y, z, w = clipSpace
    
    # Check if point is in front of camera
    if w > 0.001:
        # Normalize device coordinates (NDC) - map to -1 to 1
        ndc_x = x / w
        ndc_y = y / w
        
        # Get screen dimensions
        height, width = windowsSize
        
        # Map NDC (-1 to 1) to screen space
        # X: -1 (left) -> 0, 1 (right) -> width
        # Y: -1 (bottom) -> height, 1 (top) -> 0 (inverted Y)
        screen_x = (width / 2) + (width / 2) * ndc_x
        screen_y = (height / 2) - (height / 2) * ndc_y
        
        return (screen_x, screen_y)
    
    # Point is behind camera
    return (0, 0)


def calculate_distance(pos1, pos2):
    """Calculate Euclidean distance between two 3D points"""
    return np.sqrt((pos1[0] - pos2[0])**2 + 
                   (pos1[1] - pos2[1])**2 + 
                   (pos1[2] - pos2[2])**2)


def is_point_in_screen(screen_pos, screen_size):
    """Check if screen position is within screen bounds"""
    height, width = screen_size
    x, y = screen_pos
    return 0 <= x <= width and 0 <= y <= height
