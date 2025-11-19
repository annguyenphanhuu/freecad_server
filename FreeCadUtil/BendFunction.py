# BendFunction.py - Functions related to bend/bracket/plate operations
# -*- coding: utf-8 -*-
import FreeCAD as App
import Part
import math
import sys
import os

# Add sheetmetal directory to path (it's at project root level)
sheetmetal_path = os.path.join(os.path.dirname(__file__), '..', 'sheetmetal')
if sheetmetal_path not in sys.path:
    sys.path.insert(0, sheetmetal_path)

from sheetmetal import SheetMetalCmd, SheetMetalBaseShapeCmd
import SheetMetalTools

def taskRestoreDefaults(obj, default_vars):
    pass
SheetMetalTools.taskRestoreDefaults = taskRestoreDefaults

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
        # For countersink, we need to FUSE the hole cylinder and cone to create the complete cut shape
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
