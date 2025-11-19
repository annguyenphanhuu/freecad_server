# PlateFunction.py - Functions related to plate operations
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

def makeUShape(
    dim_x=60.0,
    dim_y=120.0,
    thickness=2.0,
    flange_height=20.0,
    bend_angle_deg=90.0,
    bend_radius=2.0
):
    """
    Create a U-shaped plate with flanges along Y-axis (on X=0 and X=dim_x edges).

    Parameters:
    - dim_x: Dimension of the plate along X-axis
    - dim_y: Dimension of the plate along Y-axis
    - thickness: Plate thickness (Z dimension)
    - flange_height: Height of the bent flanges
    - bend_angle_deg: Bend angle in degrees (90° for perpendicular flanges)
    - bend_radius: Bend radius

    Returns:
    - final_obj: The final FreeCAD object with the U-shaped plate
    """

    # Create document with auto-generated name
    doc_name = "U_Shaped_Plate_Y_Axis"
    doc = App.newDocument(doc_name)

    # Create base plate
    base_shape = Part.makeBox(dim_x, dim_y, thickness)
    base_obj = doc.addObject("Part::Feature", "BasePlate")
    base_obj.Shape = base_shape
    doc.recompute()

    # Bend along Y-axis (flanges on X=0 and X=dim_x edges)
    edge1 = "Edge2"   # Left edge (X=0)
    edge2 = "Edge6"   # Right edge (X=dim_x)

    print("Creating U-shaped plate with flanges along Y-axis")

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

Part.makeUShape = makeUShape

def makeLShape(dim_x, dim_y, thickness, flange_height, bend_angle_deg, bend_radius, fillet_corner=0):
    """
    Creates an L-shaped plate using SheetMetal workbench.

    Args:
        dim_x: X dimension - Length of the base plate
        dim_y: Y dimension - Width of the plate
        thickness: Sheet thickness
        flange_height: Flange / wing height
        bend_angle_deg: 90deg bend angle in degrees
        bend_radius: Radius of the bend
        fillet_corner: Fillet radius for corner edges (0 = no fillet)

    Returns:
        Part.Shape - The L-shaped plate geometry
    """
    # Create document
    doc = App.newDocument("L_Shape_Bracket")

    # Create base box (base plate)
    base_box = Part.makeBox(dim_x, dim_y, thickness, App.Vector(2 * bend_radius, 0, 0))
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
                    return filleted_obj.Shape
                else:
                    print(f"Warning: Found {len(edges_to_fillet)} vertical edges, expected 4. Skipping fillets.")
            except Exception as e:
                print(f"Warning: Could not create fillets: {e}")
                print("Continuing with unfilleted bracket...")

        return final_bracket_obj.Shape
    except Exception as e:
        print(f"Warning: Could not fuse shapes: {e}")
        # Fallback to compound shape
        bracket_shape = Part.makeCompound([base_obj.Shape, wall_obj.Shape])
        final_bracket_obj = doc.addObject("Part::Feature", "L_Bracket")
        final_bracket_obj.Shape = bracket_shape
        final_bracket_obj.Label = "L-Bracket"
        doc.recompute()
        print("Created L-shaped bracket as compound shape")
        return final_bracket_obj.Shape
Part.makeLShape = makeLShape

def makeZShape(
    dim_x=60.0,
    dim_y=120.0,
    thickness=2.0,
    top_flange_height=20.0,
    bottom_flange_height=20.0,
    bend_angle_deg=90.0,
    bend_radius=2.0
):
    """
    Create a Z-shaped plate with flanges of potentially different heights.

    Parameters:
    - dim_x: Dimension of the plate along X-axis
    - dim_y: Dimension of the plate along Y-axis
    - thickness: Plate thickness (Z dimension)
    - top_flange_height: Height of the top flange (bent upwards)
    - bottom_flange_height: Height of the bottom flange (bent downwards)
    - bend_angle_deg: Bend angle in degrees (90° for perpendicular flanges)
    - bend_radius: Bend radius

    Returns:
    - final_obj: The final FreeCAD object with the Z-shaped plate
    """

    # Create document with auto-generated name
    doc_name = "Z_Shaped_Plate_Y_Axis"
    doc = App.newDocument(doc_name)

    # Create base plate
    base_shape = Part.makeBox(dim_x, dim_y, thickness)
    base_obj = doc.addObject("Part::Feature", "BasePlate")
    base_obj.Shape = base_shape
    doc.recompute()

    # Bend along Y-axis (flanges on X=0 and X=dim_x edges)
    edge1 = "Edge2"   # Left edge (X=0) - bottom flange
    edge2 = "Edge6"   # Right edge (X=dim_x) - top flange

    print("Creating Z-shaped plate with flanges along Y-axis")

    # Create bottom flange (bends down)
    flange1_obj = doc.addObject("Part::FeaturePython", "SMBendWall1")
    SheetMetalCmd.SMBendWall(flange1_obj, base_obj, [edge1])
    flange1_obj.length = bottom_flange_height
    flange1_obj.angle = 180 - bend_angle_deg  # SheetMetal uses supplementary angle
    flange1_obj.radius = bend_radius
    flange1_obj.invert = False

    # Create top flange (bends up)
    flange2_obj = doc.addObject("Part::FeaturePython", "SMBendWall2")
    SheetMetalCmd.SMBendWall(flange2_obj, base_obj, [edge2])
    flange2_obj.length = top_flange_height
    flange2_obj.angle = 180 - bend_angle_deg
    flange2_obj.radius = bend_radius
    flange2_obj.invert = True # Invert the direction of the bend

    doc.recompute()

    # Fuse plate + flanges
    try:
        fused_shape = base_obj.Shape.fuse(flange1_obj.Shape).fuse(flange2_obj.Shape)
        final_obj = doc.addObject("Part::Feature", "Z_Shaped_Plate")
        final_obj.Shape = fused_shape
        doc.recompute()
    except Exception as e:
        print(f"Warning: fusing failed - using compound. Reason: {e}")
        compound_shape = Part.makeCompound([base_obj.Shape,
                                            flange1_obj.Shape,
                                            flange2_obj.Shape])
        final_obj = doc.addObject("Part::Feature", "Z_Shaped_Plate")
        final_obj.Shape = compound_shape
        doc.recompute()

    return final_obj.Shape

Part.makeZShape = makeZShape


def makeOblong(length, width, height, pnt=None, dir=None):
    """
    Create an oblong shape by combining a rectangular box in the middle with two cylinders at the ends.
    The oblong starts from origin (0,0,0) and extends in the direction specified by dir parameter.

    Parameters:
    - length: Total length of the oblong (including the two cylinder ends)
    - width: Width of the oblong (also diameter of the cylinders)
    - height: Height of the oblong
    - pnt: Position vector (optional, default Vector(0,0,0))
    - dir: Direction vector (optional, default Vector(1,0,0) for X-axis)
           Supported directions:
           Vector(1,0,0) = along positive X-axis
           Vector(-1,0,0) = along negative X-axis
           Vector(0,1,0) = along positive Y-axis
           Vector(0,-1,0) = along negative Y-axis
           Vector(0,0,1) = along positive Z-axis
           Vector(0,0,-1) = along negative Z-axis

    Returns: Part.Shape - the created oblong shape starting from origin
    """
    if pnt is None:
        pnt = App.Vector(0, 0, 0)

    if dir is None:
        dir = App.Vector(1, 0, 0)  # Default to positive X-axis

    # Normalize direction vector
    dir = dir.normalize()

    cylinder_radius = width / 2

    # Determine orientation based on direction vector
    if abs(dir.x) > abs(dir.y) and abs(dir.x) > abs(dir.z):
        # Create oblong along X-axis (positive or negative)
        rect_length = length - 2 * cylinder_radius

        if rect_length <= 0:
            # Just a cylinder when length is too small
            oblong = Part.makeCylinder(cylinder_radius, height, App.Vector(cylinder_radius, cylinder_radius, 0))
        else:
            if dir.x > 0:
                # Positive X direction
                rectangle = Part.makeBox(rect_length, width, height,
                                       App.Vector(cylinder_radius, 0, 0))
                left_cylinder = Part.makeCylinder(cylinder_radius, height,
                                                App.Vector(cylinder_radius, cylinder_radius, 0))
                right_cylinder = Part.makeCylinder(cylinder_radius, height,
                                                 App.Vector(cylinder_radius + rect_length, cylinder_radius, 0))
            else:
                # Negative X direction
                rectangle = Part.makeBox(rect_length, width, height,
                                       App.Vector(-cylinder_radius - rect_length, 0, 0))
                left_cylinder = Part.makeCylinder(cylinder_radius, height,
                                                App.Vector(-cylinder_radius - rect_length, cylinder_radius, 0))
                right_cylinder = Part.makeCylinder(cylinder_radius, height,
                                                 App.Vector(-cylinder_radius, cylinder_radius, 0))
            oblong = rectangle.fuse([left_cylinder, right_cylinder])

    elif abs(dir.y) > abs(dir.x) and abs(dir.y) > abs(dir.z):
        # Create oblong along Y-axis (positive or negative)
        rect_width = length - 2 * cylinder_radius

        if rect_width <= 0:
            # Just a cylinder when length is too small
            oblong = Part.makeCylinder(cylinder_radius, height, App.Vector(cylinder_radius, cylinder_radius, 0))
        else:
            if dir.y > 0:
                # Positive Y direction
                rectangle = Part.makeBox(width, rect_width, height,
                                       App.Vector(0, cylinder_radius, 0))
                bottom_cylinder = Part.makeCylinder(cylinder_radius, height,
                                                  App.Vector(cylinder_radius, cylinder_radius, 0))
                top_cylinder = Part.makeCylinder(cylinder_radius, height,
                                               App.Vector(cylinder_radius, cylinder_radius + rect_width, 0))
            else:
                # Negative Y direction
                rectangle = Part.makeBox(width, rect_width, height,
                                       App.Vector(0, -cylinder_radius - rect_width, 0))
                bottom_cylinder = Part.makeCylinder(cylinder_radius, height,
                                                  App.Vector(cylinder_radius, -cylinder_radius - rect_width, 0))
                top_cylinder = Part.makeCylinder(cylinder_radius, height,
                                               App.Vector(cylinder_radius, -cylinder_radius, 0))
            oblong = rectangle.fuse([bottom_cylinder, top_cylinder])

    else:  # Z-axis (positive or negative) or default
        # Create oblong along Z-axis
        rect_height = length - 2 * cylinder_radius

        if rect_height <= 0:
            # Just a cylinder when length is too small
            oblong = Part.makeCylinder(cylinder_radius, height, App.Vector(cylinder_radius, cylinder_radius, 0))
        else:
            if dir.z > 0:
                # Positive Z direction
                rectangle = Part.makeBox(width, height, rect_height,
                                       App.Vector(0, 0, cylinder_radius))
                bottom_cylinder = Part.makeCylinder(cylinder_radius, height,
                                                  App.Vector(cylinder_radius, cylinder_radius, 0))
                top_cylinder = Part.makeCylinder(cylinder_radius, height,
                                               App.Vector(cylinder_radius, cylinder_radius, cylinder_radius + rect_height))
            else:
                # Negative Z direction
                rectangle = Part.makeBox(width, height, rect_height,
                                       App.Vector(0, 0, -cylinder_radius - rect_height))
                bottom_cylinder = Part.makeCylinder(cylinder_radius, height,
                                                  App.Vector(cylinder_radius, cylinder_radius, -cylinder_radius - rect_height))
                top_cylinder = Part.makeCylinder(cylinder_radius, height,
                                               App.Vector(cylinder_radius, cylinder_radius, -cylinder_radius))
            oblong = rectangle.fuse([bottom_cylinder, top_cylinder])

    # Apply transformation if needed
    if pnt != App.Vector(0, 0, 0):
        oblong.translate(pnt)

    return oblong

# Add makeOblong to Part module for convenience
Part.makeOblong = makeOblong

def makeHalfCylinder(radius, height, pnt=None, dir=None):
    """
    Create a half-cylinder shape.
    The flat face is oriented along the XY plane by default if dir is along Z.

    Parameters:
    - radius: The radius of the half-cylinder.
    - height: The height of the half-cylinder.
    - pnt: Position vector (optional, default Vector(0,0,0)).
    - dir: Direction vector for the axis of the half-cylinder (optional, default Vector(0,0,1)).

    Returns: Part.Shape - the created half-cylinder shape.
    """
    if pnt is None:
        pnt = App.Vector(0, 0, 0)
    if dir is None:
        dir = App.Vector(0, 0, 1) # Default to Z-axis for height

    # Create a full cylinder
    full_cylinder = Part.makeCylinder(radius, height, pnt, dir)

    # Create a cutting box to make it a half-cylinder
    # The box should be large enough to cut the cylinder in half
    # We'll place the box to cut along the cylinder's length

    # Calculate the rotation from the default Z-axis to the target direction
    z_axis = App.Vector(0, 0, 1)
    rotation = App.Rotation(z_axis, dir)

    # Define the cutting box in a standard orientation (e.g., cutting the positive Y part)
    box_size = 2 * radius
    box_pnt = App.Vector(-radius, 0, 0) + pnt # Start from the center plane
    cutter = Part.makeBox(box_size, radius, height)
    cutter.translate(App.Vector(-radius, 0, 0)) # Center the box for the cut

    # Apply the same placement as the cylinder
    cutter.rotate(pnt, rotation.Axis, rotation.Angle)
    cutter.translate(pnt)

    # Perform the cut
    half_cylinder = full_cylinder.cut(cutter)

    return half_cylinder

# Add makeHalfCylinder to Part module for convenience
Part.makeHalfCylinder = makeHalfCylinder
