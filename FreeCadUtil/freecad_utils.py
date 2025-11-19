# Tube generator module
# -*- coding: utf-8 -*-
import FreeCAD as App
import Part
import math
import sys
import os

# Add sheetmetal directory to path
sheetmetal_path = os.path.join(os.path.dirname(__file__), 'sheetmetal')
if sheetmetal_path not in sys.path:
    sys.path.insert(0, sheetmetal_path)

from sheetmetal import SheetMetalCmd, SheetMetalBaseShapeCmd
import SheetMetalTools

def taskRestoreDefaults(obj, default_vars):
    pass
SheetMetalTools.taskRestoreDefaults = taskRestoreDefaults

def create_square_tube_angled_cuts(tube_shape, length, outer_width, outer_height, left_cut_angle=45.0, right_cut_angle=60.0):
    """
    Apply angled cuts to both ends of the tube.

    Args:
        tube_shape (Part.Shape): The tube shape to cut
        length (float): Length of the tube
        outer_width (float): Outer width of the tube
        outer_height (float): Outer height of the tube
        left_cut_angle (float): Cut angle at the beginning (left end) in degrees (default: 45.0)
        right_cut_angle (float): Cut angle at the end (right end) in degrees (default: 60.0)

    Returns:
        Part.Shape: The tube shape with angled cuts applied
    """
    # Convert angles to radians
    left_cut_angle_rad = math.radians(left_cut_angle)
    right_cut_angle_rad = math.radians(right_cut_angle)

    # Skip 0-degree and 90-degree cuts to avoid division by zero (tan(0°) = 0, tan(90°) = infinity)
    if abs(left_cut_angle) < 0.001:
        print(f"Skipping left cut: angle {left_cut_angle}° is too close to 0°")
        left_cut_enabled = False
    elif abs(left_cut_angle - 90.0) < 0.001:
        print(f"Skipping left cut: angle {left_cut_angle}° is too close to 90°")
        left_cut_enabled = False
    else:
        left_cut_length_offset = outer_height / math.tan(left_cut_angle_rad)
        left_cut_enabled = True

    if abs(right_cut_angle) < 0.001:
        print(f"Skipping right cut: angle {right_cut_angle}° is too close to 0°")
        right_cut_enabled = False
    elif abs(right_cut_angle - 90.0) < 0.001:
        print(f"Skipping right cut: angle {right_cut_angle}° is too close to 90°")
        right_cut_enabled = False
    else:
        right_cut_length_offset = outer_height / math.tan(right_cut_angle_rad)
        right_cut_enabled = True

    # Create cutting plane at the left end (x=0) if enabled
    if left_cut_enabled:
        # Left end: cut from bottom-left to top-right
        left_cut_points = [
            App.Vector(0, 0, 0),                                    # Bottom-left-front
            App.Vector(0, outer_width, 0),                          # Bottom-left-back
            App.Vector(left_cut_length_offset, outer_width, outer_height), # Top-left-back
            App.Vector(left_cut_length_offset, 0, outer_height)          # Top-left-front
        ]

    # Create cutting plane at the right end (x=length) if enabled
    if right_cut_enabled:
        # Right end: cut from top-left to bottom-right (opposite direction)
        right_cut_points = [
            App.Vector(length - right_cut_length_offset, 0, outer_height), # Top-right-front
            App.Vector(length - right_cut_length_offset, outer_width, outer_height), # Top-right-back
            App.Vector(length, outer_width, 0),                     # Bottom-right-back
            App.Vector(length, 0, 0)                                # Bottom-right-front
        ]

    # Create cutting solids using extrusion
    if left_cut_enabled:
        # Left cutting solid - extrude backwards to cut the left end
        left_cut_face = Part.Face(Part.makePolygon(left_cut_points + [left_cut_points[0]]))
        left_cut_solid = left_cut_face.extrude(App.Vector(-left_cut_length_offset - 5, 0, 0))

    if right_cut_enabled:
        # Right cutting solid - extrude forwards to cut the right end
        right_cut_face = Part.Face(Part.makePolygon(right_cut_points + [right_cut_points[0]]))
        right_cut_solid = right_cut_face.extrude(App.Vector(right_cut_length_offset + 5, 0, 0))

    # Apply the angled cuts to the tube
    try:
        if left_cut_enabled:
            # Cut the left end
            tube_shape = tube_shape.cut(left_cut_solid)
        if right_cut_enabled:
            # Cut the right end
            tube_shape = tube_shape.cut(right_cut_solid)
    except Exception as e:
        print(f"Warning: Could not apply angled cuts: {e}")

    return tube_shape

def create_circular_tube_angled_cuts(tube_shape, length, outer_diameter, cut_angle_1_deg=60.0, cut_angle_2_deg=80.0):
    """
    Apply angled cuts to both ends of a circular tube.

    Args:
        tube_shape (Part.Shape): The tube shape to cut
        length (float): Length of the tube
        outer_diameter (float): Outer diameter of the tube
        cut_angle_1_deg (float): Cut angle at the first end in degrees (default: 60.0)
        cut_angle_2_deg (float): Cut angle at the second end in degrees (default: 80.0)

    Returns:
        Part.Shape: The tube shape with angled cuts applied
    """
    # Convert angles to radians
    cut_angle_1_rad = math.radians(cut_angle_1_deg)
    cut_angle_2_rad = math.radians(cut_angle_2_deg)

    # Calculate the length of the bevel based on tube radius and angle for each end
    tube_radius = outer_diameter / 2

    # Skip 0-degree and 90-degree cuts to avoid division by zero (tan(0°) = 0, tan(90°) = infinity)
    if abs(cut_angle_1_deg) < 0.001:
        print(f"Skipping first cut: angle {cut_angle_1_deg}° is too close to 0°")
        cut_1_enabled = False
    elif abs(cut_angle_1_deg - 90.0) < 0.001:
        print(f"Skipping first cut: angle {cut_angle_1_deg}° is too close to 90°")
        cut_1_enabled = False
    else:
        bevel_length_1 = tube_radius / math.tan(cut_angle_1_rad)
        cut_1_enabled = True

    if abs(cut_angle_2_deg) < 0.001:
        print(f"Skipping second cut: angle {cut_angle_2_deg}° is too close to 0°")
        cut_2_enabled = False
    elif abs(cut_angle_2_deg - 90.0) < 0.001:
        print(f"Skipping second cut: angle {cut_angle_2_deg}° is too close to 90°")
        cut_2_enabled = False
    else:
        bevel_length_2 = tube_radius / math.tan(cut_angle_2_rad)
        cut_2_enabled = True

    # Create cutting boxes that will create the beveled ends
    box_size = outer_diameter * 3

    # First bevel cut at the start (z=0) - first angle cut
    if cut_1_enabled:
        cutter1 = Part.makeBox(box_size, box_size, bevel_length_1 * 2)
        # Position it so it cuts from negative Z into the tube
        cutter1.translate(App.Vector(-box_size/2, -box_size/2, -bevel_length_1))
        # Rotate around the X-axis to create the bevel angle
        # The rotation point should be at the tube's front edge
        cutter1.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 90 - cut_angle_1_deg)

    # Second bevel cut at the end (z=length) - second angle cut
    if cut_2_enabled:
        cutter2 = Part.makeBox(box_size, box_size, bevel_length_2 * 2)
        # Position it at the end of the tube
        cutter2.translate(App.Vector(-box_size/2, -box_size/2, length - bevel_length_2))
        # Rotate in the opposite direction for the other end
        cutter2.rotate(App.Vector(0, 0, length), App.Vector(1, 0, 0), -(90 - cut_angle_2_deg))

    # Apply the cuts to create beveled ends
    try:
        if cut_1_enabled:
            tube_shape = tube_shape.cut(cutter1)
        if cut_2_enabled:
            tube_shape = tube_shape.cut(cutter2)
    except Exception as e:
        print(f"Warning: Could not apply circular angled cuts: {e}")

    return tube_shape

def create_rectangular_tab(tube_shape, tab_length, tab_width, tube_length, tube_width, tube_height, tube_thickness):
    """
    Create rectangular tabs on top and bottom of the tube

    Parameters:
    - tube_shape: The existing tube shape
    - tab_width: Width of the tab
    - tab_length: Length of the tab extending from tube
    - tube_length: Length of the tube
    - tube_width: Width of the tube
    - tube_height: Height of the tube
    - tube_thickness: Wall thickness of the tube

    Returns:
    - Combined shape with tabs
    """

    tab_x = tube_length  # Position at the end of tube
    tab_y = (tube_width - tab_length) / 2    # Center the tab
    tab_z_top = tube_height - tube_thickness     # Top tab position
    tab_z_bottom = 0  # Bottom tab position

    # Create rectangular tabs for start of tube
    tab_box_start_top = Part.makeBox(tab_width, tab_length, tube_thickness, App.Vector(-tab_width, tab_y, tab_z_top))
    tab_box_start_bottom = Part.makeBox(tab_width, tab_length, tube_thickness, App.Vector(-tab_width, tab_y, tab_z_bottom))

    # Create rectangular tabs for end of tube
    tab_box_end_top = Part.makeBox(tab_width, tab_length, tube_thickness, App.Vector(tab_x, tab_y, tab_z_top))
    tab_box_end_bottom = Part.makeBox(tab_width, tab_length, tube_thickness, App.Vector(tab_x, tab_y, tab_z_bottom))

    # Combine tube and tabs using union
    combined_shape = tube_shape.fuse(tab_box_start_top).fuse(tab_box_start_bottom).fuse(tab_box_end_top).fuse(tab_box_end_bottom)

    return combined_shape

def add_hole_leg1(bracket_shape, hole_radius, hole_center_x, hole_center_y, extrude_length, thickness, leg1_length):
    """
    Add hole on leg1 face of L-bracket (horizontal base face)

    Parameters:
    - bracket_shape: Current bracket shape
    - hole_radius: Hole radius
    - hole_center_x: Hole center position along X axis (from 0 to leg1_length)
    - hole_center_y: Hole center position along Y axis (from 0 to extrude_length)
    - extrude_length: Extrude length
    - thickness: Sheet thickness
    - leg1_length: Length of leg1
    """

    # Find leg1 face (horizontal base face)
    leg1_face = None
    max_area = 0
    best_match_score = float('inf')

    # For leg1, we expect a horizontal face with normal pointing up (positive Z) or down (negative Z)
    expected_normal_x = 0.0
    expected_normal_y = 0.0
    expected_normal_z = 1.0  # Pointing up

    print(f"Looking for leg1 face with expected normal: ({expected_normal_x:.3f}, {expected_normal_y:.3f}, {expected_normal_z:.3f})")

    for face in bracket_shape.Faces:
        # Get face normal at center
        u_mid = (face.ParameterRange[0] + face.ParameterRange[1]) / 2
        v_mid = (face.ParameterRange[2] + face.ParameterRange[3]) / 2
        normal = face.normalAt(u_mid, v_mid)

        # Calculate match score (distance from expected normal)
        normal_diff_x = abs(normal.x - expected_normal_x)
        normal_diff_y = abs(normal.y - expected_normal_y)
        normal_diff_z = abs(normal.z - expected_normal_z)
        match_score = normal_diff_x + normal_diff_y + normal_diff_z

        # Also try the opposite normal direction (faces can have flipped normals)
        normal_diff_x_flip = abs(normal.x - expected_normal_x)
        normal_diff_y_flip = abs(normal.y - expected_normal_y)
        normal_diff_z_flip = abs(normal.z + expected_normal_z)  # Try negative Z
        match_score_flip = normal_diff_x_flip + normal_diff_y_flip + normal_diff_z_flip

        final_match_score = min(match_score, match_score_flip)

        # Consider faces with reasonable area and good normal match
        tolerance = 0.3
        expected_area = leg1_length * extrude_length
        if final_match_score < tolerance and face.Area > expected_area * 0.5:
            if final_match_score < best_match_score:
                best_match_score = final_match_score
                leg1_face = face
                print(f"Found potential leg1 face: area={face.Area:.1f}, normal=({normal.x:.3f}, {normal.y:.3f}, {normal.z:.3f}), score={final_match_score:.3f}")

    # Fallback: find largest horizontal face
    if leg1_face is None:
        print("Could not find leg1 face by normal vector, using fallback method")
        for face in bracket_shape.Faces:
            normal = face.normalAt(0, 0)
            # Look for horizontal faces (high Z component in normal)
            if (abs(normal.z) > 0.7 and
                face.Area > max_area and face.Area > leg1_length * extrude_length * 0.3):
                max_area = face.Area
                leg1_face = face
                print(f"Fallback: selected face with area={face.Area:.1f}, normal=({normal.x:.3f}, {normal.y:.3f}, {normal.z:.3f})")

    if leg1_face is None:
        print("Could not find suitable leg1 face")
        return bracket_shape

    print(f"Found leg1 face with area: {leg1_face.Area}")

    # Find center point of leg1 face for reference
    u_mid = (leg1_face.ParameterRange[0] + leg1_face.ParameterRange[1]) / 2
    v_mid = (leg1_face.ParameterRange[2] + leg1_face.ParameterRange[3]) / 2
    face_center = leg1_face.valueAt(u_mid, v_mid)
    normal = leg1_face.normalAt(u_mid, v_mid)

    print(f"Center point of leg1: {face_center}")
    print(f"Normal vector of leg1: {normal}")

    # Calculate hole position directly on the leg1 face surface
    # Use the face's parameter space to find the correct position

    # Get face bounds in parameter space
    u_min, u_max, v_min, v_max = leg1_face.ParameterRange

    # Test corner points to understand face parameter mapping
    corner_points = [
        leg1_face.valueAt(u_min, v_min),
        leg1_face.valueAt(u_max, v_min),
        leg1_face.valueAt(u_min, v_max),
        leg1_face.valueAt(u_max, v_max)
    ]

    print(f"Face corner points:")
    print(f"  (u_min, v_min): {corner_points[0]}")
    print(f"  (u_max, v_min): {corner_points[1]}")
    print(f"  (u_min, v_max): {corner_points[2]}")
    print(f"  (u_max, v_max): {corner_points[3]}")

    # Determine which parameter direction corresponds to X (leg1 length) and Y (extrude length)
    # Check variation in X direction between corner points
    x_variation_u = abs(corner_points[1].x - corner_points[0].x)  # u_max vs u_min at v_min
    x_variation_v = abs(corner_points[2].x - corner_points[0].x)  # v_max vs v_min at u_min

    # Check variation in Y direction between corner points
    y_variation_u = abs(corner_points[1].y - corner_points[0].y)  # u_max vs u_min at v_min
    y_variation_v = abs(corner_points[2].y - corner_points[0].y)  # v_max vs v_min at u_min

    print(f"Parameter variations: X_u={x_variation_u:.3f}, X_v={x_variation_v:.3f}, Y_u={y_variation_u:.3f}, Y_v={y_variation_v:.3f}")

    # Determine correct parameter mapping
    if x_variation_u > x_variation_v:
        # U parameter corresponds to X direction (leg1 length)
        # V parameter corresponds to Y direction (extrude length)
        u_normalized = hole_center_x / leg1_length
        v_normalized = hole_center_y / extrude_length
        print("Mapping: U->X (leg1 length), V->Y (extrude length)")
    else:
        # V parameter corresponds to X direction (leg1 length)
        # U parameter corresponds to Y direction (extrude length)
        u_normalized = hole_center_y / extrude_length
        v_normalized = hole_center_x / leg1_length
        print("Mapping: U->Y (extrude length), V->X (leg1 length)")

    # Map to face parameter range
    u_param = u_min + u_normalized * (u_max - u_min)
    v_param = v_min + v_normalized * (v_max - v_min)

    # Get the actual 3D position on the face surface
    hole_position = leg1_face.valueAt(u_param, v_param)

    print(f"Face parameter range: U({u_min:.3f}, {u_max:.3f}), V({v_min:.3f}, {v_max:.3f})")
    print(f"Normalized position: U={u_normalized:.3f}, V={v_normalized:.3f}")
    print(f"Face parameters: U={u_param:.3f}, V={v_param:.3f}")
    print(f"Hole position on face: {hole_position}")

    # Get the normal at this position for cylinder direction
    normal = leg1_face.normalAt(u_param, v_param)

    # Create cylinder for hole with extra height to ensure complete cut
    cylinder_height = thickness * 1.5  # Add 1mm extra to ensure complete cut

    # Position cylinder to start below the face surface to ensure complete cut
    cylinder_start = hole_position - normal * (thickness)

    hole_cylinder = Part.makeCylinder(
        hole_radius,
        cylinder_height,
        cylinder_start,
        normal  # Direction perpendicular to leg1 face
    )

    # Create cylinder object for debugging (optional)
    if App.ActiveDocument:
        hole_obj = App.ActiveDocument.addObject("Part::Feature", "HoleLeg1Debug")
        hole_obj.Shape = hole_cylinder
        hole_obj.Label = "Hole Cylinder Leg1"
        print(f"Created cylinder with thickness: {cylinder_height}")
        print(f"Cylinder start position: {cylinder_start}")
        print(f"Cylinder direction (normal): {normal}")

    try:
        # Cut cylinder from bracket
        result_shape = bracket_shape.cut(hole_cylinder)
        print("Successfully created hole on leg1")
        return result_shape
    except Exception as e:
        print(f"Error creating hole on leg1: {e}")
        return bracket_shape


def add_countersink_leg2(bracket_shape, hole_radius, cs_radius, cs_angle, hole_center_y, hole_center_z, angle_deg, extrude_length, thickness, leg2_length):
    """
    Add countersink hole on leg2 face of L-bracket with any angle

    Parameters:
    - bracket_shape: Current bracket shape
    - hole_radius: Hole radius
    - cs_radius: Countersink radius (larger than hole_radius)
    - cs_angle: Countersink angle in degrees (typical range: 60-120)
    - hole_center_y: Hole center position along Y axis (from 0 to extrude_length)
    - hole_center_z: Hole center position along Z axis on leg2 (from 0 to leg2 height)
    - angle_deg: L-bracket angle
    - extrude_length: Extrude length
    - thickness: Sheet thickness
    - leg2_length: Length of leg2
    """

    # Find leg2 face (angled face) - same logic as add_hole_leg2
    leg2_face = None
    max_area = 0
    best_match_score = float('inf')

    # Calculate expected normal vector for leg2 face
    angle_rad = math.radians(angle_deg)
    # For an L-bracket, leg2 normal should point outward from the angled surface
    # The normal direction depends on how the SheetMetal bend is oriented
    expected_normal_x = -math.sin(angle_rad)  # Negative because it points outward
    expected_normal_z = math.cos(angle_rad)
    expected_normal_y = 0.0

    print(f"Looking for leg2 face with expected normal: ({expected_normal_x:.3f}, {expected_normal_y:.3f}, {expected_normal_z:.3f})")

    for face in bracket_shape.Faces:
        # Get face normal at center
        u_mid = (face.ParameterRange[0] + face.ParameterRange[1]) / 2
        v_mid = (face.ParameterRange[2] + face.ParameterRange[3]) / 2
        normal = face.normalAt(u_mid, v_mid)

        # Calculate match score (distance from expected normal)
        normal_diff_x = abs(normal.x - expected_normal_x)
        normal_diff_y = abs(normal.y - expected_normal_y)
        normal_diff_z = abs(normal.z - expected_normal_z)
        match_score = normal_diff_x + normal_diff_y + normal_diff_z

        # Also try the opposite normal direction (faces can have flipped normals)
        normal_diff_x_flip = abs(normal.x + expected_normal_x)
        normal_diff_y_flip = abs(normal.y + expected_normal_y)
        normal_diff_z_flip = abs(normal.z + expected_normal_z)
        match_score_flip = normal_diff_x_flip + normal_diff_y_flip + normal_diff_z_flip

        final_match_score = min(match_score, match_score_flip)

        # Consider faces with reasonable area and good normal match
        tolerance = 0.3  # Increased tolerance for better matching
        if final_match_score < tolerance and face.Area > leg2_length * extrude_length * 0.5:
            if final_match_score < best_match_score:
                best_match_score = final_match_score
                leg2_face = face
                print(f"Found potential leg2 face: area={face.Area:.1f}, normal=({normal.x:.3f}, {normal.y:.3f}, {normal.z:.3f}), score={final_match_score:.3f}")

    # Fallback: find largest face that is not horizontal (base) or vertical (sides)
    if leg2_face is None:
        print("Could not find leg2 face by normal vector, using fallback method")
        for face in bracket_shape.Faces:
            normal = face.normalAt(0, 0)
            # Skip horizontal faces (base/top) and purely vertical faces (sides)
            if (abs(normal.z) < 0.9 and abs(normal.x) > 0.1 and
                face.Area > max_area and face.Area > leg2_length * extrude_length * 0.3):
                max_area = face.Area
                leg2_face = face
                print(f"Fallback: selected face with area={face.Area:.1f}, normal=({normal.x:.3f}, {normal.y:.3f}, {normal.z:.3f})")

    if leg2_face is None:
        print("Could not find suitable leg2 face")
        return bracket_shape

    print(f"Found leg2 face with area: {leg2_face.Area}")

    # Find center point of leg2 face for reference
    u_mid = (leg2_face.ParameterRange[0] + leg2_face.ParameterRange[1]) / 2
    v_mid = (leg2_face.ParameterRange[2] + leg2_face.ParameterRange[3]) / 2
    face_center = leg2_face.valueAt(u_mid, v_mid)
    normal = leg2_face.normalAt(u_mid, v_mid)

    print(f"Center point of leg2: {face_center}")
    print(f"Normal vector of leg2: {normal}")

    # Calculate hole position directly on the leg2 face surface
    # Use the face's parameter space to find the correct position

    # Get face bounds in parameter space
    u_min, u_max, v_min, v_max = leg2_face.ParameterRange

    # Test corner points to understand face parameter mapping
    corner_points = [
        leg2_face.valueAt(u_min, v_min),
        leg2_face.valueAt(u_max, v_min),
        leg2_face.valueAt(u_min, v_max),
        leg2_face.valueAt(u_max, v_max)
    ]

    print(f"Face corner points:")
    print(f"  (u_min, v_min): {corner_points[0]}")
    print(f"  (u_max, v_min): {corner_points[1]}")
    print(f"  (u_min, v_max): {corner_points[2]}")
    print(f"  (u_max, v_max): {corner_points[3]}")

    # Determine which parameter direction corresponds to Y (length) and Z (height)
    # Check variation in Y direction between corner points
    y_variation_u = abs(corner_points[1].y - corner_points[0].y)  # u_max vs u_min at v_min
    y_variation_v = abs(corner_points[2].y - corner_points[0].y)  # v_max vs v_min at u_min

    # Check variation in Z direction between corner points
    z_variation_u = abs(corner_points[1].z - corner_points[0].z)  # u_max vs u_min at v_min
    z_variation_v = abs(corner_points[2].z - corner_points[0].z)  # v_max vs v_min at u_min

    print(f"Parameter variations: Y_u={y_variation_u:.3f}, Y_v={y_variation_v:.3f}, Z_u={z_variation_u:.3f}, Z_v={z_variation_v:.3f}")

    # Determine correct parameter mapping
    if y_variation_u > y_variation_v:
        # U parameter corresponds to Y direction (length)
        # V parameter corresponds to Z direction (height on leg2)
        u_normalized = hole_center_y / extrude_length
        v_normalized = hole_center_z / leg2_length
        print("Mapping: U->Y (length), V->Z (height)")
    else:
        # V parameter corresponds to Y direction (length)
        # U parameter corresponds to Z direction (height on leg2)
        u_normalized = hole_center_z / leg2_length
        v_normalized = hole_center_y / extrude_length
        print("Mapping: U->Z (height), V->Y (length)")

    # Map to face parameter range
    u_param = u_min + u_normalized * (u_max - u_min)
    v_param = v_min + v_normalized * (v_max - v_min)

    # Get the actual 3D position on the face surface
    hole_position = leg2_face.valueAt(u_param, v_param)

    print(f"Face parameter range: U({u_min:.3f}, {u_max:.3f}), V({v_min:.3f}, {v_max:.3f})")
    print(f"Normalized position: U={u_normalized:.3f}, V={v_normalized:.3f}")
    print(f"Face parameters: U={u_param:.3f}, V={v_param:.3f}")
    print(f"Hole position on face: {hole_position}")

    # Get the normal at this position for cylinder direction
    normal = leg2_face.normalAt(u_param, v_param)

    # Create main hole cylinder
    cylinder_height = thickness  # Make it a bit longer to ensure complete cut
    cylinder_start = hole_position - normal * (cylinder_height)

    hole_cylinder = Part.makeCylinder(
        hole_radius,
        cylinder_height,
        cylinder_start,
        normal  # Direction perpendicular to leg2 face
    )

    # Create countersink cone
    # Calculate countersink depth based on cs_angle and radius difference
    # For a countersink, the depth is determined by: depth = (cs_radius - hole_radius) / tan(cs_angle/2)
    # cs_angle is the full cone angle, so half-angle is used for the calculation

    if cs_angle <= 0 or cs_angle >= 180:
        print(f"Warning: Invalid cs_angle {cs_angle}°. Using default 90°")
        cs_angle = 90.0

    half_angle_rad = math.radians(cs_angle / 2.0)
    radius_diff = cs_radius - hole_radius

    if radius_diff <= 0:
        print(f"Warning: cs_radius ({cs_radius}) must be larger than hole_radius ({hole_radius})")
        return bracket_shape

    # Calculate depth based on countersink angle
    cs_depth = radius_diff / math.tan(half_angle_rad)

    # Limit depth to reasonable values (not more than thickness)
    max_depth = thickness * 0.8  # Maximum 80% of thickness
    if cs_depth > max_depth:
        cs_depth = max_depth
        print(f"Warning: Calculated cs_depth ({cs_depth:.2f}) limited to {max_depth:.2f} (80% of thickness)")

    # Position countersink on the outer surface of leg2
    # The cone should start from the surface and go inward
    cs_start = hole_position

    # Create cone for countersink
    # For countersink, we want larger radius at the surface (top) and smaller at depth (bottom)
    # But Part.makeCone parameters are (radius1, radius2, height, pnt, dir)
    # where radius1 is at pnt, radius2 is at pnt + height*dir
    # So we need to position it correctly
    cs_cone = Part.makeCone(
        cs_radius,        # radius at the start position (surface - larger)
        hole_radius,      # radius at the end position (depth - smaller)
        cs_depth,         # height of cone (calculated from angle)
        cs_start,         # start position (on surface)
        -normal           # direction going INTO the material (opposite to normal)
    )

    # Create separate debug objects to see what's happening
    if App.ActiveDocument:
        # Debug hole cylinder
        hole_debug = App.ActiveDocument.addObject("Part::Feature", "HoleDebug")
        hole_debug.Shape = hole_cylinder
        hole_debug.Label = "Hole Cylinder Debug"

        # Debug countersink cone
        cs_debug = App.ActiveDocument.addObject("Part::Feature", "CountersinkDebug")
        cs_debug.Shape = cs_cone
        cs_debug.Label = "Countersink Cone Debug"

        print(f"Created countersink hole: radius={hole_radius}, cs_radius={cs_radius}, cs_depth={cs_depth:.2f}, cs_angle={cs_angle}°")
        print(f"Hole position: {hole_position}")
        print(f"Normal direction: {normal}")
        print(f"Countersink start: {cs_start}")

    # Combine hole and countersink
    try:
        combined_cut = hole_cylinder.fuse(cs_cone)

        # Create combined debug object
        if App.ActiveDocument:
            combined_debug = App.ActiveDocument.addObject("Part::Feature", "CombinedCutDebug")
            combined_debug.Shape = combined_cut
            combined_debug.Label = "Combined Cut Debug"

        # Cut the combined shape from the bracket
        result_shape = bracket_shape.cut(combined_cut)
        print("Successfully created countersink hole on leg2")
        return result_shape

    except Exception as e:
        print(f"Error creating countersink hole: {e}")
        return bracket_shape

def add_hole_leg2(bracket_shape, hole_radius, hole_center_y, hole_center_z, angle_deg, extrude_length, thickness, leg2_length):
    """
    Add hole on leg2 face of L-bracket with any angle

    Parameters:
    - bracket_shape: Current bracket shape
    - hole_radius: Hole radius
    - hole_center_y: Hole center position along Y axis (from 0 to extrude_length)
    - hole_center_z: Hole center position along Z axis on leg2 (from 0 to leg2 height)
    - angle_deg: L-bracket angle
    - extrude_length: Extrude length
    - thickness: Sheet thickness
    - leg2_length: Length of leg2

    Returns:
    - Modified bracket shape with hole cut from leg2
    """

    # Find leg2 face (angled face) - same logic as add_countersink_leg2
    leg2_face = None
    max_area = 0
    best_match_score = float('inf')

    # Calculate expected normal vector for leg2 face
    angle_rad = math.radians(angle_deg)
    # For an L-bracket, leg2 normal should point outward from the angled surface
    # The normal direction depends on how the SheetMetal bend is oriented
    expected_normal_x = -math.sin(angle_rad)  # Negative because it points outward
    expected_normal_z = math.cos(angle_rad)
    expected_normal_y = 0.0

    print(f"Looking for leg2 face with expected normal: ({expected_normal_x:.3f}, {expected_normal_y:.3f}, {expected_normal_z:.3f})")

    for face in bracket_shape.Faces:
        # Get face normal at center
        u_mid = (face.ParameterRange[0] + face.ParameterRange[1]) / 2
        v_mid = (face.ParameterRange[2] + face.ParameterRange[3]) / 2
        normal = face.normalAt(u_mid, v_mid)

        # Calculate match score (distance from expected normal)
        normal_diff_x = abs(normal.x - expected_normal_x)
        normal_diff_y = abs(normal.y - expected_normal_y)
        normal_diff_z = abs(normal.z - expected_normal_z)
        match_score = normal_diff_x + normal_diff_y + normal_diff_z

        # Also try the opposite normal direction (faces can have flipped normals)
        normal_diff_x_flip = abs(normal.x + expected_normal_x)
        normal_diff_y_flip = abs(normal.y + expected_normal_y)
        normal_diff_z_flip = abs(normal.z + expected_normal_z)
        match_score_flip = normal_diff_x_flip + normal_diff_y_flip + normal_diff_z_flip

        final_match_score = min(match_score, match_score_flip)

        # Consider faces with reasonable area and good normal match
        tolerance = 0.3  # Increased tolerance for better matching
        if final_match_score < tolerance and face.Area > leg2_length * extrude_length * 0.5:
            if final_match_score < best_match_score:
                best_match_score = final_match_score
                leg2_face = face
                print(f"Found potential leg2 face: area={face.Area:.1f}, normal=({normal.x:.3f}, {normal.y:.3f}, {normal.z:.3f}), score={final_match_score:.3f}")

    # Fallback: find largest face that is not horizontal (base) or vertical (sides)
    if leg2_face is None:
        print("Could not find leg2 face by normal vector, using fallback method")
        for face in bracket_shape.Faces:
            normal = face.normalAt(0, 0)
            # Skip horizontal faces (base/top) and purely vertical faces (sides)
            if (abs(normal.z) < 0.9 and abs(normal.x) > 0.1 and
                face.Area > max_area and face.Area > leg2_length * extrude_length * 0.3):
                max_area = face.Area
                leg2_face = face
                print(f"Fallback: selected face with area={face.Area:.1f}, normal=({normal.x:.3f}, {normal.y:.3f}, {normal.z:.3f})")

    if leg2_face is None:
        print("Could not find suitable leg2 face")
        return bracket_shape

    print(f"Found leg2 face with area: {leg2_face.Area}")

    # Find center point of leg2 face for reference
    u_mid = (leg2_face.ParameterRange[0] + leg2_face.ParameterRange[1]) / 2
    v_mid = (leg2_face.ParameterRange[2] + leg2_face.ParameterRange[3]) / 2
    face_center = leg2_face.valueAt(u_mid, v_mid)
    normal = leg2_face.normalAt(u_mid, v_mid)

    print(f"Center point of leg2: {face_center}")
    print(f"Normal vector of leg2: {normal}")

    # Calculate hole position directly on the leg2 face surface
    # Use the face's parameter space to find the correct position

    # Get face bounds in parameter space
    u_min, u_max, v_min, v_max = leg2_face.ParameterRange

    # Test corner points to understand face parameter mapping
    corner_points = [
        leg2_face.valueAt(u_min, v_min),
        leg2_face.valueAt(u_max, v_min),
        leg2_face.valueAt(u_min, v_max),
        leg2_face.valueAt(u_max, v_max)
    ]

    print(f"Face corner points:")
    print(f"  (u_min, v_min): {corner_points[0]}")
    print(f"  (u_max, v_min): {corner_points[1]}")
    print(f"  (u_min, v_max): {corner_points[2]}")
    print(f"  (u_max, v_max): {corner_points[3]}")

    # Determine which parameter direction corresponds to Y (length) and Z (height)
    # Check variation in Y direction between corner points
    y_variation_u = abs(corner_points[1].y - corner_points[0].y)  # u_max vs u_min at v_min
    y_variation_v = abs(corner_points[2].y - corner_points[0].y)  # v_max vs v_min at u_min

    # Check variation in Z direction between corner points
    z_variation_u = abs(corner_points[1].z - corner_points[0].z)  # u_max vs u_min at v_min
    z_variation_v = abs(corner_points[2].z - corner_points[0].z)  # v_max vs v_min at u_min

    print(f"Parameter variations: Y_u={y_variation_u:.3f}, Y_v={y_variation_v:.3f}, Z_u={z_variation_u:.3f}, Z_v={z_variation_v:.3f}")

    # Determine correct parameter mapping
    if y_variation_u > y_variation_v:
        # U parameter corresponds to Y direction (length)
        # V parameter corresponds to Z direction (height on leg2)
        u_normalized = hole_center_y / extrude_length
        v_normalized = hole_center_z / leg2_length
        print("Mapping: U->Y (length), V->Z (height)")
    else:
        # V parameter corresponds to Y direction (length)
        # U parameter corresponds to Z direction (height on leg2)
        u_normalized = hole_center_z / leg2_length
        v_normalized = hole_center_y / extrude_length
        print("Mapping: U->Z (height), V->Y (length)")

    # Map to face parameter range
    u_param = u_min + u_normalized * (u_max - u_min)
    v_param = v_min + v_normalized * (v_max - v_min)

    # Get the actual 3D position on the face surface
    hole_position = leg2_face.valueAt(u_param, v_param)

    print(f"Face parameter range: U({u_min:.3f}, {u_max:.3f}), V({v_min:.3f}, {v_max:.3f})")
    print(f"Normalized position: U={u_normalized:.3f}, V={v_normalized:.3f}")
    print(f"Face parameters: U={u_param:.3f}, V={v_param:.3f}")
    print(f"Hole position on face: {hole_position}")

    # Get the normal at this position for cylinder direction
    normal = leg2_face.normalAt(u_param, v_param)

    # Create hole cylinder with exact thickness
    cylinder_height = thickness

    # Position cylinder to start at the face surface
    cylinder_start = hole_position - normal * (thickness)

    hole_cylinder = Part.makeCylinder(
        hole_radius,
        cylinder_height,
        cylinder_start,
        normal  # Direction perpendicular to leg2 face
    )

    # Create cylinder object for debugging (optional)
    if App.ActiveDocument:
        hole_obj = App.ActiveDocument.addObject("Part::Feature", "HoleLeg2Debug")
        hole_obj.Shape = hole_cylinder
        hole_obj.Label = "Hole Cylinder Leg2"
        print(f"Created cylinder with thickness: {cylinder_height}")
        print(f"Cylinder start position: {cylinder_start}")
        print(f"Cylinder direction (normal): {normal}")

    try:
        # Cut cylinder from bracket
        result_shape = bracket_shape.cut(hole_cylinder)
        print("Successfully created hole on leg2")
        return result_shape
    except Exception as e:
        print(f"Error creating hole on leg2: {e}")
        return bracket_shape

def create_holes_on_flange_capot(width, length, bend_radius, additional_bend_length, edge_distance=10, hole_radius=5.0, hole_height=300.0, tub_obj=None):
    """
    Create 4 cylindrical holes on flange at calculated positions

    Parameters:
    - width: Capot width (mm)
    - length: Capot length (mm)
    - bend_radius: Bend radius (mm)
    - additional_bend_length: Additional bend length (mm)
    - edge_distance: Distance from edge (mm) - default 10
    - hole_radius: Hole radius (mm) - default 5.0
    - hole_height: Hole height (mm) - default 300.0
    - tub_obj: Capot object to cut holes in

    Returns:
    - FreeCAD object (capot with holes cut on flange)
    """

    if tub_obj is None:
        raise ValueError("tub_obj cannot be empty")

    # Calculate X and Y coordinates for holes
    x_coord = length/2 + bend_radius + additional_bend_length - edge_distance
    y_coord = width/2 - edge_distance

    # Coordinates of 4 holes: (+X,+Y), (+X,-Y), (-X,+Y), (-X,-Y)
    hole_positions = [
        (x_coord, y_coord, 0),      # Hole 1: +X, +Y (starting from Z=0)
        (x_coord, -y_coord, 0),     # Hole 2: +X, -Y
        (-x_coord, y_coord, 0),     # Hole 3: -X, +Y
        (-x_coord, -y_coord, 0)     # Hole 4: -X, -Y
    ]

    cutting_cylinders = []

    for i, (x, y, z) in enumerate(hole_positions):
        # Create cylinder to cut hole
        cylinder = Part.makeCylinder(hole_radius, hole_height)
        # Move cylinder to position
        cylinder = cylinder.translate(App.Vector(x, y, z))
        cutting_cylinders.append(cylinder)

    # Cut holes in tub
    modified_tub_shape = tub_obj.Shape

    # Cut each hole sequentially
    for i, cutting_cylinder in enumerate(cutting_cylinders):
        try:
            modified_tub_shape = modified_tub_shape.cut(cutting_cylinder)
            print(f"Created hole {i+1} at position ({hole_positions[i][0]:.1f}, {hole_positions[i][1]:.1f})")
        except Exception as e:
            print(f"Error cutting hole {i+1}: {e}")

    # Update tub shape
    tub_obj.Shape = modified_tub_shape
    App.ActiveDocument.recompute()

    return tub_obj

def create_capot(thickness, bend_radius, width, length, height, fillet=0, additional_bend_length=50.0, additional_bend_angle=90.0):
    """
    Create Capot with additional bends and optional fillet

    Parameters:
    - thickness: Sheet thickness (mm)
    - bend_radius: Bend radius (mm)
    - width: Width (mm)
    - length: Length (mm)
    - height: Height (mm)
    - fillet: Fillet radius (mm) - 0 = no fillet
    - additional_bend_length: Additional bend length (mm)
    - additional_bend_angle: Additional bend angle (degrees)

    Returns:
    - FreeCAD object (final shape with bends and fillet)
    """


    tub_shape = SheetMetalBaseShapeCmd.smCreateBaseShape(
        type="Tub",
        thickness=thickness,
        radius=bend_radius,
        width=width + 2*bend_radius,
        length=length + 2*bend_radius,
        height=height,
        flangeWidth=0,
        fillGaps=True,
        origin="0,0"
    )

    tub_obj = App.ActiveDocument.addObject("Part::Feature", "Tub_Base")
    tub_obj.Shape = tub_shape
    tub_obj.Label = "Tub_Base"
    App.ActiveDocument.recompute()

    edge_candidates = ["Edge46", "Edge26"]
    wall_objects = []

    for i, edge in enumerate(edge_candidates):
        try:
            wall_obj = App.ActiveDocument.addObject("Part::FeaturePython", f"SMBendWall_{i+1}")
            SheetMetalCmd.SMBendWall(wall_obj, tub_obj, [edge])

            wall_obj.length = additional_bend_length - bend_radius
            wall_obj.angle = (180 - additional_bend_angle)
            wall_obj.radius = bend_radius
            App.ActiveDocument.recompute()

            wall_objects.append(wall_obj)
        except:
            pass

    if len(wall_objects) > 0:
        fused_shape = tub_obj.Shape

        for wall_obj in wall_objects:
            fused_shape = fused_shape.fuse(wall_obj.Shape)

        fused_obj = App.ActiveDocument.addObject("Part::Feature", "Tub_With_Bends")
        fused_obj.Shape = fused_shape
        fused_obj.Label = "Tub_With_Bends"
        App.ActiveDocument.recompute()

        current_obj = fused_obj
    else:
        current_obj = tub_obj

    if fillet <= 0:
        return current_obj

    edges_to_fillet = []
    thickness_tolerance = 1e-3
    z_direction_tolerance = 1e-3

    for edge in current_obj.Shape.Edges:
        if abs(edge.Length - thickness) <= thickness_tolerance:
            if hasattr(edge, 'Vertexes') and len(edge.Vertexes) >= 2:
                v1 = edge.Vertexes[0].Point
                v2 = edge.Vertexes[1].Point
                direction = v2.sub(v1)

                if direction.Length > 1e-6:
                    normalized_direction = direction.normalize()
                    is_parallel_to_z = (abs(normalized_direction.x) <= z_direction_tolerance and
                                       abs(normalized_direction.y) <= z_direction_tolerance and
                                       abs(abs(normalized_direction.z) - 1.0) <= z_direction_tolerance)

                    if is_parallel_to_z:
                        edges_to_fillet.append(edge)

    if len(edges_to_fillet) == 0:
        return current_obj

    filleted_shape = None
    successful_fillets = 0
    temp_shape = current_obj.Shape

    try:
        filleted_shape = current_obj.Shape.makeFillet(fillet, edges_to_fillet)
        successful_fillets = len(edges_to_fillet)
    except:
        batch_size = 5
        for i in range(0, len(edges_to_fillet), batch_size):
            batch_edges = edges_to_fillet[i:i+batch_size]
            try:
                temp_shape = temp_shape.makeFillet(fillet, batch_edges)
                successful_fillets += len(batch_edges)
            except:
                for edge in batch_edges:
                    try:
                        temp_shape = temp_shape.makeFillet(fillet, [edge])
                        successful_fillets += 1
                    except:
                        pass

        if successful_fillets > 0:
            filleted_shape = temp_shape

    if filleted_shape is not None and successful_fillets > 0:
        filleted_obj = App.ActiveDocument.addObject("Part::Feature", f"Tub_Final_R{fillet}")
        filleted_obj.Shape = filleted_shape
        filleted_obj.Label = f"Tub with {successful_fillets} Fillets (R{fillet})"
        App.ActiveDocument.recompute()
        return filleted_obj
    else:
        return current_obj

def create_u_shaped_plate(
    plate_length=60.0,
    plate_width=120.0,
    thickness=2.0,
    flange_height=20.0,
    bend_angle_deg=90.0,
    bend_radius=2.0,
    bend_axis="Y"  # "X" or "Y" - which axis to bend along
):
    """
    Create a U-shaped plate with configurable bend axis.

    Parameters:
    - plate_length: Length of the plate (X dimension)
    - plate_width: Width of the plate (Y dimension)
    - thickness: Plate thickness (Z dimension)
    - flange_height: Height of the bent flanges
    - bend_angle_deg: Bend angle in degrees (90° for perpendicular flanges)
    - bend_radius: Bend radius
    - bend_axis: "X" to bend along X-axis edges, "Y" to bend along Y-axis edges

    Returns:
    - final_obj: The final FreeCAD object with the U-shaped plate
    """

    # Create document with auto-generated name
    doc_name = f"U_Shaped_Plate_{bend_axis.upper()}_Axis"
    doc = App.newDocument(doc_name)

    # Create base plate
    base_shape = Part.makeBox(plate_length, plate_width, thickness)
    base_obj = doc.addObject("Part::Feature", "BasePlate")
    base_obj.Shape = base_shape
    doc.recompute()

    # Determine edges based on bend axis
    if bend_axis.upper() == "X":
        # Bend along X-axis (flanges on Y=0 and Y=plate_width edges)
        edge1 = "Edge10"  # Front edge (Y=0)
        edge2 = "Edge12"  # Back edge (Y=plate_width)
        axis_description = "X-axis"
    elif bend_axis.upper() == "Y":
        # Bend along Y-axis (flanges on X=0 and X=plate_length edges)
        edge1 = "Edge2"   # Left edge (X=0)
        edge2 = "Edge6"   # Right edge (X=plate_length)
        axis_description = "Y-axis"
    else:
        raise ValueError("bend_axis must be 'X' or 'Y'")

    print(f"Creating U-shaped plate with flanges along {axis_description}")

    # Create first flange
    flange1_obj = doc.addObject("Part::FeaturePython", "SMBendWall1")
    SheetMetalCmd.SMBendWall(flange1_obj, base_obj, [edge1])
    flange1_obj.length = flange_height
    flange1_obj.angle = 180 - bend_angle_deg  # SheetMetal uses supplementary angle
    flange1_obj.radius = bend_radius

    # Create second flange
    flange2_obj = doc.addObject("Part::FeaturePython", "SMBendWall2")
    SheetMetalCmd.SMBendWall(flange2_obj, base_obj, [edge2])
    flange2_obj.length = flange_height
    flange2_obj.angle = 180 - bend_angle_deg
    flange2_obj.radius = bend_radius

    doc.recompute()

    # Fuse plate + flanges
    try:
        fused_shape = base_obj.Shape.fuse(flange1_obj.Shape).fuse(flange2_obj.Shape)
        final_obj = doc.addObject("Part::Feature", "U_Shaped_Plate")
        final_obj.Shape = fused_shape
        doc.recompute()
    except Exception as e:
        print(f"Warning: fusing failed - using compound. Reason: {e}")
        compound_shape = Part.makeCompound([base_obj.Shape,
                                            flange1_obj.Shape,
                                            flange2_obj.Shape])
        final_obj = doc.addObject("Part::Feature", "U_Shaped_Plate")
        final_obj.Shape = compound_shape
        doc.recompute()

    return final_obj.Shape

def create_l_shaped_plate(plate_length, plate_width, thickness, flange_height, bend_angle_deg, bend_radius, fillet_corner=0):
    """
    Creates an L-shaped plate using SheetMetal workbench.

    Args:
        plate_length: X dimension - Length of the base plate
        plate_width: Y dimension - Width of the plate
        thickness: Sheet thickness
        flange_height: Flange / wing height
        bend_angle_deg: 90deg bend angle in degrees
        bend_radius: Radius of the bend
        fillet_corner: Fillet radius for corner edges (0 = no fillet)

    Returns:
        FreeCAD object containing the L-shaped plate
    """
    # Create document
    doc = App.newDocument("L_Shape_Bracket")

    # Create base box (base plate)
    base_box = Part.makeBox(plate_length, plate_width, thickness)
    base_obj = doc.addObject("Part::Feature", "BaseBox")
    base_obj.Shape = base_box
    base_obj.Label = "Base Box"
    doc.recompute()

    # Create SMBendWall (flange)
    wall_obj = doc.addObject("Part::FeaturePython", "SMBendWall")
    edge = "Edge2"
    wall_feature = SheetMetalCmd.SMBendWall(wall_obj, base_obj, [edge])

    # Set properties for the bend
    wall_obj.length = flange_height
    wall_obj.angle = (180 - bend_angle_deg)
    wall_obj.radius = bend_radius
    doc.recompute()

    # Create final L-bracket by fusing base and wall
    try:
        fused_shape = base_obj.Shape.fuse(wall_obj.Shape)
        final_bracket_obj = doc.addObject("Part::Feature", "L_Bracket")
        final_bracket_obj.Shape = fused_shape
        final_bracket_obj.Label = "L-Bracket"
        doc.recompute()
        print("Successfully created L-shaped bracket")

        # Apply fillet to corner edges if requested
        if fillet_corner > 0:
            try:
                # Find vertical edges (edges with length equal to thickness)
                edges_to_fillet = []
                for edge in final_bracket_obj.Shape.Edges:
                    if abs(edge.Length - thickness) < 1e-6:
                        edges_to_fillet.append(edge)

                if len(edges_to_fillet) >= 4:
                    filleted_shape = final_bracket_obj.Shape.makeFillet(fillet_corner, edges_to_fillet)
                    filleted_obj = doc.addObject("Part::Feature", "FilletedBracket")
                    filleted_obj.Shape = filleted_shape
                    filleted_obj.Label = "L-Bracket with Fillets"
                    doc.recompute()
                    print(f"Successfully applied fillets with radius {fillet_corner}mm to {len(edges_to_fillet)} edges")
                    return filleted_obj
                else:
                    print(f"Warning: Found {len(edges_to_fillet)} vertical edges, expected 4. Skipping fillets.")
            except Exception as e:
                print(f"Warning: Could not create fillets: {e}")
                print("Continuing with unfilleted bracket...")

        return final_bracket_obj
    except Exception as e:
        print(f"Warning: Could not fuse shapes: {e}")
        # Fallback to compound shape
        bracket_shape = Part.makeCompound([base_obj.Shape, wall_obj.Shape])
        final_bracket_obj = doc.addObject("Part::Feature", "L_Bracket")
        final_bracket_obj.Shape = bracket_shape
        final_bracket_obj.Label = "L-Bracket"
        doc.recompute()
        print("Created L-shaped bracket as compound shape")
        return final_bracket_obj

