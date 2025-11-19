# TubeFunction.py - Functions related to tube/cylinder operations
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

def makeRectangularTube(length, outer_width, outer_height, thickness,
                       outer_fillet_radius=0.0, inner_fillet_radius=0.0):
    """
    Create a basic rectangular tube with optional fillets.

    Args:
        length (float): Length of the tube along X-axis
        outer_width (float): Outer width of the tube (Y dimension)
        outer_height (float): Outer height of the tube (Z dimension)
        thickness (float): Wall thickness of the tube
        outer_fillet_radius (float): Fillet radius for outer edges (default: 0.0)
        inner_fillet_radius (float): Fillet radius for inner edges (default: 0.0)

    Returns:
        Part.Shape: The basic rectangular tube shape
    """
    # Calculate inner dimensions
    inner_width = outer_width - 2 * thickness
    inner_height = outer_height - 2 * thickness

    # Validate dimensions
    if inner_width <= 0 or inner_height <= 0:
        raise ValueError("Wall thickness is too large for the given outer dimensions")

    # Create outer box
    outer_box = Part.makeBox(length, outer_width, outer_height, App.Vector(0, 0, 0))

    # Apply fillet to outer box edges if specified
    if outer_fillet_radius > 0:
        try:
            outer_edges = []
            for edge in outer_box.Edges:
                # Find edges parallel to the length (X-axis)
                if abs(edge.Length - length) < 0.001:
                    outer_edges.append(edge)

            if outer_edges:
                outer_box_filleted = outer_box.makeFillet(outer_fillet_radius, outer_edges)
            else:
                outer_box_filleted = outer_box
                print("Warning: No suitable edges found for outer fillet")
        except Exception as e:
            print(f"Warning: Could not apply outer fillet: {e}")
            outer_box_filleted = outer_box
    else:
        outer_box_filleted = outer_box

    # Create inner box positioned centrally to achieve uniform wall thickness
    inner_box = Part.makeBox(length, inner_width, inner_height,
                           App.Vector(0, thickness, thickness))

    # Apply fillet to inner box edges if specified
    if inner_fillet_radius > 0:
        try:
            inner_edges = []
            for edge in inner_box.Edges:
                # Find edges parallel to the length (X-axis)
                if abs(edge.Length - length) < 0.001:
                    inner_edges.append(edge)

            if inner_edges:
                inner_box_filleted = inner_box.makeFillet(inner_fillet_radius, inner_edges)
            else:
                inner_box_filleted = inner_box
                print("Warning: No suitable edges found for inner fillet")
        except Exception as e:
            print(f"Warning: Could not apply inner fillet: {e}")
            inner_box_filleted = inner_box
    else:
        inner_box_filleted = inner_box

    # Boolean cut to form the tube
    tube_shape = outer_box_filleted.cut(inner_box_filleted)

    return tube_shape
Part.makeRectangularTube = makeRectangularTube


def makeCircularTube(length, outer_diameter, thickness):
    """
    Create a basic circular tube (hollow cylinder).

    Args:
        length (float): Length of the tube along X-axis
        outer_diameter (float): Outer diameter of the tube
        thickness (float): Wall thickness of the tube

    Returns:
        Part.Shape: The basic circular tube shape
    """
    # Calculate inner diameter
    inner_diameter = outer_diameter - 2 * thickness

    # Validate dimensions
    if inner_diameter <= 0:
        raise ValueError("Wall thickness is too large for the given outer diameter")

    # Calculate radii
    outer_radius = outer_diameter / 2
    inner_radius = inner_diameter / 2

    # Create outer cylinder along X-axis
    outer_cylinder = Part.makeCylinder(outer_radius, length, App.Vector(0, 0, 0), App.Vector(1, 0, 0))

    # Create inner cylinder (hollow part) along X-axis
    inner_cylinder = Part.makeCylinder(inner_radius, length, App.Vector(0, 0, 0), App.Vector(1, 0, 0))

    # Boolean cut to form the tube
    tube_shape = outer_cylinder.cut(inner_cylinder)

    return tube_shape

Part.makeCircularTube = makeCircularTube


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
    Apply angled cuts to both ends of a circular tube (tube oriented along X-axis).
    This version uses rotated cutting boxes for correct angle geometry on circular surfaces.

    Args:
        tube_shape (Part.Shape): The tube shape to cut
        length (float): Length of the tube along X-axis
        outer_diameter (float): Outer diameter of the tube
        cut_angle_1_deg (float): Cut angle at the first end in degrees (default: 60.0)
        cut_angle_2_deg (float): Cut angle at the second end in degrees (default: 80.0)

    Returns:
        Part.Shape: The tube shape with angled cuts applied
    """
    # Convert angles to radians
    cut_angle_1_rad = math.radians(cut_angle_1_deg)
    cut_angle_2_rad = math.radians(cut_angle_2_deg)

    # Calculate the tube radius
    tube_radius = outer_diameter / 2

    # Skip 0-degree and 90-degree cuts to avoid division by zero or no-op
    if abs(cut_angle_1_deg) < 0.001 or abs(cut_angle_1_deg - 90.0) < 0.001:
        print(f"Skipping first cut: angle {cut_angle_1_deg}° is a straight cut or invalid.")
        cut_1_enabled = False
    else:
        bevel_length_1 = tube_radius / math.tan(cut_angle_1_rad)
        cut_1_enabled = True

    if abs(cut_angle_2_deg) < 0.001 or abs(cut_angle_2_deg - 90.0) < 0.001:
        print(f"Skipping second cut: angle {cut_angle_2_deg}° is a straight cut or invalid.")
        cut_2_enabled = False
    else:
        bevel_length_2 = tube_radius / math.tan(cut_angle_2_rad)
        cut_2_enabled = True

    # Create a sufficiently large cutting box to ensure it covers the entire tube diameter
    box_size = outer_diameter * 3

    # First bevel cut at the start (x=0)
    if cut_1_enabled:
        cutter1 = Part.makeBox(abs(bevel_length_1) * 2, box_size, box_size)
        # Position the box so its front face is at the tube end before rotation
        cutter1.translate(App.Vector(-abs(bevel_length_1), -box_size/2, -box_size/2))
        # Rotate the box around the Y-axis to create the angled cut
        cutter1.rotate(App.Vector(0, 0, 0), App.Vector(0, 1, 0), 90 - cut_angle_1_deg)

    # Second bevel cut at the end (x=length)
    if cut_2_enabled:
        cutter2 = Part.makeBox(abs(bevel_length_2) * 2, box_size, box_size)
        # Position the box so its front face is at the tube end before rotation
        cutter2.translate(App.Vector(length - abs(bevel_length_2), -box_size/2, -box_size/2))
        # Rotate in the opposite direction for the other end
        cutter2.rotate(App.Vector(length, 0, 0), App.Vector(0, 1, 0), -(90 - cut_angle_2_deg))

    # Apply the cuts to the tube shape
    try:
        if cut_1_enabled:
            tube_shape = tube_shape.cut(cutter1)
        if cut_2_enabled:
            tube_shape = tube_shape.cut(cutter2)
    except Exception as e:
        print(f"Warning: Could not apply circular angled cuts: {e}")

    return tube_shape

def create_rectangular_tab(tube_shape, tab_length, tab_width, tube_length, tube_width, tube_height, tube_thickness,
                          add_start_tab=True, add_end_tab=True):
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
    - add_start_tab: Whether to add tabs at the start of the tube (default: True)
    - add_end_tab: Whether to add tabs at the end of the tube (default: True)

    Returns:
    - Combined shape with tabs
    """

    tab_x = tube_length  # Position at the end of tube
    tab_y = (tube_width - tab_length) / 2    # Center the tab
    tab_z_top = tube_height - tube_thickness     # Top tab position
    tab_z_bottom = 0  # Bottom tab position

    # Start with the original tube shape
    combined_shape = tube_shape

    # Create rectangular tabs for start of tube (if enabled)
    if add_start_tab:
        tab_box_start_top = Part.makeBox(tab_width, tab_length, tube_thickness, App.Vector(-tab_width, tab_y, tab_z_top))
        tab_box_start_bottom = Part.makeBox(tab_width, tab_length, tube_thickness, App.Vector(-tab_width, tab_y, tab_z_bottom))
        combined_shape = combined_shape.fuse(tab_box_start_top).fuse(tab_box_start_bottom)

    # Create rectangular tabs for end of tube (if enabled)
    if add_end_tab:
        tab_box_end_top = Part.makeBox(tab_width, tab_length, tube_thickness, App.Vector(tab_x, tab_y, tab_z_top))
        tab_box_end_bottom = Part.makeBox(tab_width, tab_length, tube_thickness, App.Vector(tab_x, tab_y, tab_z_bottom))
        combined_shape = combined_shape.fuse(tab_box_end_top).fuse(tab_box_end_bottom)

    return combined_shape
