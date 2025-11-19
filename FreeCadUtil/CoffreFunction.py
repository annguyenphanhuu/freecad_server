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

def makeTub(thickness, bend_radius, length, width, height):
    """
    Create Capot - simplified version that only returns the base tub shape

    Parameters:
    - thickness: Sheet thickness (mm)
    - bend_radius: Bend radius (mm)
    - length: Length (mm)
    - width: Width (mm)
    - height: Height (mm)

    Returns:
    - Base tub shape
    """

    tub_shape = SheetMetalBaseShapeCmd.smCreateBaseShape(
        type="Tub",
        thickness=thickness,
        radius=bend_radius,
        width=width,
        length=length,
        height=height,
        flangeWidth=0,
        fillGaps=True,
        origin="0,0"
    )

    tub_obj = App.ActiveDocument.addObject("Part::Feature", "Capot")
    tub_obj.Shape = tub_shape
    tub_obj.Label = "Capot"
    App.ActiveDocument.recompute()

    return tub_obj

Part.makeTub = makeTub

def AddOutwardBend(shape, bend_length, bend_angle, bend_radius, axis="Y", fillet=0.0, thickness=1.5):
    """
    Add outward bends to specific edges of a shape (bending away from the shape)

    Args:
        shape: The base shape object to add bends to
        bend_length: Length of the bend
        bend_angle: Angle of the bend in degrees
        bend_radius: Radius of the bend
        axis: Axis direction ("X" or "Y") to determine which edges to use
        fillet: Fillet radius to apply to edges parallel to Z-axis with length equal to thickness
        thickness: Sheet thickness to identify edges for filleting

    Returns:
        The shape with outward bends applied, or original shape if bending fails
    """
    # Select edges based on axis
    if axis.upper() == "X":
        edge_candidates = ["Edge36", "Edge55"]
    elif axis.upper() == "Y":
        edge_candidates = ["Edge46", "Edge26"]
    else:
        print(f"Warning: Invalid axis '{axis}'. Using default Y axis.")
        edge_candidates = ["Edge46", "Edge26"]

    wall_objects = []

    for i, edge in enumerate(edge_candidates):
        try:
            wall_obj = App.ActiveDocument.addObject("Part::FeaturePython", f"SMBendWall_Outward_{axis}_{i+1}")
            SheetMetalCmd.SMBendWall(wall_obj, shape, [edge])

            wall_obj.length = bend_length - bend_radius
            wall_obj.angle = (180 - bend_angle)
            wall_obj.radius = bend_radius
            App.ActiveDocument.recompute()

            wall_objects.append(wall_obj)
        except:
            pass

    if len(wall_objects) > 0:
        fused_shape = shape.Shape

        for wall_obj in wall_objects:
            fused_shape = fused_shape.fuse(wall_obj.Shape)

        # Apply fillet if specified
        if fillet > 0.0:
            try:
                # Find edges that are parallel to Z-axis and have length equal to thickness
                edges_to_fillet = []
                for i, edge in enumerate(fused_shape.Edges):
                    try:
                        # Check if edge is parallel to Z-axis (direction vector close to (0,0,1) or (0,0,-1))
                        edge_vector = edge.lastVertex().Point.sub(edge.firstVertex().Point)
                        if edge_vector.Length < 0.001:  # Skip degenerate edges
                            continue

                        edge_vector_normalized = edge_vector.normalize()

                        # Check if edge is parallel to Z-axis (dot product with Z-axis close to ±1)
                        z_axis = App.Vector(0, 0, 1)
                        dot_product = abs(edge_vector_normalized.dot(z_axis))

                        # Check if edge length is approximately equal to thickness
                        edge_length = edge.Length

                        if dot_product > 0.99 and abs(edge_length - thickness) < 0.1:  # Relaxed tolerance
                            edges_to_fillet.append(edge)
                    except Exception:
                        continue  # Skip problematic edges

                if edges_to_fillet:
                    print(f"Found {len(edges_to_fillet)} edges parallel to Z-axis with thickness {thickness}")

                    # Try to apply fillet with the requested radius first, then progressively smaller radii
                    fillet_applied = False

                    # Start with the exact requested fillet radius
                    fillet_radius = fillet

                    # Try applying fillet to all edges first with requested radius
                    try:
                        fused_shape = fused_shape.makeFillet(fillet_radius, edges_to_fillet)
                        print(f"Successfully applied fillet radius {fillet_radius} to {len(edges_to_fillet)} edges")
                        fillet_applied = True
                    except Exception as e:
                        print(f"Failed to apply fillet radius {fillet_radius} to all edges: {e}")

                        # Try with half the requested radius
                        fillet_radius = fillet * 0.5
                        try:
                            fused_shape = fused_shape.makeFillet(fillet_radius, edges_to_fillet)
                            print(f"Applied reduced fillet radius {fillet_radius} to {len(edges_to_fillet)} edges")
                            fillet_applied = True
                        except Exception as e2:
                            print(f"Failed with half radius {fillet_radius}: {e2}")

                            # Try applying fillet to edges one by one with progressively smaller radii
                            successful_fillets = 0

                            # Try different fillet radii for individual edges, starting with requested radius
                            radii_to_try = [
                                fillet,  # Start with requested radius
                                fillet * 0.75,  # 75% of requested
                                fillet * 0.5,   # 50% of requested
                                fillet * 0.25,  # 25% of requested
                                min(thickness * 0.3, 1.0),  # Conservative fallback
                                0.1  # Very small fallback radius
                            ]

                            radius_usage = {}  # Track which radii were successfully used

                            for edge in edges_to_fillet:
                                edge_filleted = False
                                for fillet_radius in radii_to_try:
                                    try:
                                        fused_shape = fused_shape.makeFillet(fillet_radius, [edge])
                                        successful_fillets += 1
                                        edge_filleted = True

                                        # Track radius usage
                                        if fillet_radius not in radius_usage:
                                            radius_usage[fillet_radius] = 0
                                        radius_usage[fillet_radius] += 1

                                        break  # Success, move to next edge
                                    except Exception:
                                        continue  # Try next smaller radius

                                if not edge_filleted:
                                    continue  # Skip this edge completely

                            if successful_fillets > 0:
                                # Report which radii were actually used
                                radius_report = ", ".join([f"{r}mm({c} edges)" for r, c in radius_usage.items()])
                                print(f"Applied individual fillets to {successful_fillets}/{len(edges_to_fillet)} edges with radii: {radius_report}")
                                fillet_applied = True
                            else:
                                print("Could not apply fillet to any edges individually")

                    if not fillet_applied:
                        print("Fillet operation failed completely - continuing without fillet")
                else:
                    print(f"No edges found parallel to Z-axis with length ~{thickness} for filleting")

            except Exception as e:
                print(f"Warning: Could not apply fillet: {e}")

        fused_obj = App.ActiveDocument.addObject("Part::Feature", f"Tub_With_Outward_Bends_{axis}")
        fused_obj.Shape = fused_shape
        fused_obj.Label = f"Tub_With_Outward_Bends_{axis}"
        App.ActiveDocument.recompute()

        return fused_obj
    else:
        return shape

def AddHoleOutwardBend(tub_obj, length, width, height, bend_radius, additional_bend_length, edge_distance=10, hole_radius=5.0, hole_height=300.0, axis="Y"):
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
    - axis: Bend axis direction ("X" or "Y") - default "Y"

    Returns:
    - FreeCAD object (capot with holes cut on flange)
    """

    if tub_obj is None:
        raise ValueError("tub_obj cannot be empty")

    z_coord = bend_radius + height 
    # Calculate hole positions based on axis direction
    if axis.upper() == "Y":
        # For Y-axis bends: holes are on flanges extending in X direction
        x_coord = length/2 + bend_radius + additional_bend_length - edge_distance
        y_coord = width/2 - edge_distance

        # Coordinates of 4 holes: (+X,+Y), (+X,-Y), (-X,+Y), (-X,-Y)
        hole_positions = [
            (x_coord, y_coord, z_coord),      # Hole 1: +X, +Y (starting from Z=z_coord)
            (x_coord, -y_coord, z_coord),     # Hole 2: +X, -Y
            (-x_coord, y_coord, z_coord),     # Hole 3: -X, +Y
            (-x_coord, -y_coord, z_coord)     # Hole 4: -X, -Y
        ]
    elif axis.upper() == "X":
        # For X-axis bends: holes are on flanges extending in Y direction
        x_coord = length/2 - edge_distance
        y_coord = width/2 + bend_radius + additional_bend_length - edge_distance

        # Coordinates of 4 holes: (+X,+Y), (+X,-Y), (-X,+Y), (-X,-Y)
        hole_positions = [
            (x_coord, y_coord, z_coord),      # Hole 1: +X, +Y (starting from Z=z_coord)
            (x_coord, -y_coord, z_coord),     # Hole 2: +X, -Y
            (-x_coord, y_coord, z_coord),     # Hole 3: -X, +Y
            (-x_coord, -y_coord, z_coord)     # Hole 4: -X, -Y
        ]
    else:
        raise ValueError(f"Invalid axis '{axis}'. Must be 'X' or 'Y'.")

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

def AddInwardBend(shape, bend_length, bend_angle, bend_radius, axis="X"):
    """
    Add inward bends to specific edges of a shape (bending toward the shape)

    Args:
        shape: The base shape object to add bends to
        bend_length: Length of the bend
        bend_angle: Angle of the bend in degrees
        bend_radius: Radius of the bend
        axis: Axis direction ("X" or "Y") to determine which edges to use

    Returns:
        The shape with inward bends applied, or original shape if bending fails
    """
    # Select edges based on axis
    if axis.upper() == "X":
        edge_candidates = ["Edge77", "Edge99"]
    elif axis.upper() == "Y":
        edge_candidates = ["Edge66", "Edge88"]
    else:
        print(f"Warning: Invalid axis '{axis}'. Using default X axis.")
        edge_candidates = ["Edge66", "Edge88"]

    try:
        # Create a single wall object with all edges at once
        wall_obj = App.ActiveDocument.addObject("Part::FeaturePython", f"SMBendWall_Inward_{axis}")
        SheetMetalCmd.SMBendWall(wall_obj, shape, edge_candidates)

        wall_obj.length = bend_length - bend_radius
        # For inward bending, we use the bend_angle directly instead of (180 - bend_angle)
        wall_obj.angle = bend_angle
        wall_obj.radius = bend_radius
        App.ActiveDocument.recompute()

        # Create the final fused object
        fused_obj = App.ActiveDocument.addObject("Part::Feature", f"Tub_With_Inward_Bends_{axis}")
        fused_obj.Shape = wall_obj.Shape
        fused_obj.Label = f"Tub_With_Inward_Bends_{axis}"
        App.ActiveDocument.recompute()

        return fused_obj
    except Exception as e:
        print(f"Warning: Could not apply inward bends on axis {axis}: {e}")
        return shape


def AddInwardBendExtended(shape, bend_length, bend_angle, bend_radius):
    """
    Add inward bends to extended set of edges of a shape (bending toward the shape)

    Args:
        shape: The base shape object to add bends to
        bend_length: Length of the bend
        bend_angle: Angle of the bend in degrees
        bend_radius: Radius of the bend

    Returns:
        The shape with inward bends applied, or original shape if bending fails
    """
    edge_candidates = ["Edge66", "Edge88", "Edge77", "Edge99"]

    try:
        # Create a single wall object with all edges at once
        wall_obj = App.ActiveDocument.addObject("Part::FeaturePython", "SMBendWall_InwardExt_All")
        SheetMetalCmd.SMBendWall(wall_obj, shape, edge_candidates)

        wall_obj.length = bend_length - bend_radius
        # For inward bending, we use the bend_angle directly instead of (180 - bend_angle)
        wall_obj.angle = bend_angle
        wall_obj.radius = bend_radius
        App.ActiveDocument.recompute()

        # Create the final fused object
        fused_obj = App.ActiveDocument.addObject("Part::Feature", "Tub_With_Extended_Inward_Bends")
        fused_obj.Shape = wall_obj.Shape
        fused_obj.Label = "Tub_With_Extended_Inward_Bends"
        App.ActiveDocument.recompute()

        return fused_obj
    except Exception as e:
        print(f"Warning: Could not apply extended inward bends: {e}")
        return shape


def find_edge_by_coordinates(shape, target_point1, target_point2, tolerance=0.1):
    """
    Find an edge that has vertices matching the target coordinates within tolerance

    Args:
        shape: The shape to analyze
        target_point1: First target point [x, y, z]
        target_point2: Second target point [x, y, z]
        tolerance: Coordinate matching tolerance

    Returns:
        Tuple of (edge_name, edge_object) or (None, None) if not found
    """
    target1 = App.Vector(target_point1[0], target_point1[1], target_point1[2])
    target2 = App.Vector(target_point2[0], target_point2[1], target_point2[2])

    for i, edge in enumerate(shape.Edges):
        # Get the two vertices of the edge
        vertices = edge.Vertexes
        if len(vertices) == 2:
            v1 = vertices[0].Point
            v2 = vertices[1].Point

            # Check if vertices match target points (in either order)
            match1 = (v1.distanceToPoint(target1) < tolerance and v2.distanceToPoint(target2) < tolerance)
            match2 = (v1.distanceToPoint(target2) < tolerance and v2.distanceToPoint(target1) < tolerance)

            if match1 or match2:
                edge_name = f"Edge{i+1}"
                print(f"Found matching edge: {edge_name}")
                print(f"  Vertex 1: X={v1.x:.2f}, Y={v1.y:.2f}, Z={v1.z:.2f}")
                print(f"  Vertex 2: X={v2.x:.2f}, Y={v2.y:.2f}, Z={v2.z:.2f}")
                return edge_name, edge

    return None, None
