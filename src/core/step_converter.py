#!/usr/bin/env python3
"""
Reusable STEP to OnShape JSON Converter for FreeCAD

This script is designed to be executed by freecadcmd.exe and converts a
STEP file into an OnShape-compatible JSON format.

Usage:
freecadcmd.exe <path_to_script> <input_step_path> <output_json_path>
"""

import os
import json
import sys
from pathlib import Path
from typing import Dict, Any, List

# Try to import FreeCAD modules. This will only work when run with freecadcmd.
try:
    import FreeCAD
    import Part
    import Mesh
    import MeshPart
    import Import
except ImportError:
    print("[ERROR] FreeCAD modules not found. This script must be run via freecadcmd.exe.")
    sys.exit(1)

# --- Configuration ---
FREECAD_MESH_CONFIG = {
    "LINEAR_DEFLECTION": 0.1,
    "ANGULAR_DEFLECTION": 0.1,
    "RELATIVE": False
}
EDGE_PROCESSING_CONFIG = {
    "POINTS_PER_EDGE": 10
}

# --- Utility Classes ---
class FreeCADUtils:
    """Utility class for FreeCAD operations"""
    @staticmethod
    def import_step_file(step_path: str, doc_name: str = "TempDoc"):
        try:
            doc = FreeCAD.newDocument(doc_name)
            Import.insert(step_path, doc.Name)
            return doc
        except Exception as e:
            print(f"[ERROR] Failed to import STEP file: {e}")
            return None

    @staticmethod
    def create_mesh_from_shape(shape, linear_deflection: float = None, angular_deflection: float = None):
        try:
            mesh = MeshPart.meshFromShape(
                Shape=shape,
                LinearDeflection=linear_deflection or FREECAD_MESH_CONFIG["LINEAR_DEFLECTION"],
                AngularDeflection=angular_deflection or FREECAD_MESH_CONFIG["ANGULAR_DEFLECTION"],
                Relative=FREECAD_MESH_CONFIG["RELATIVE"]
            )
            return mesh
        except Exception as e:
            print(f"[ERROR] Failed to create mesh: {e}")
            return None

    @staticmethod
    def extract_individual_faces(shape) -> List:
        try:
            return list(shape.Faces)
        except Exception as e:
            print(f"[ERROR] Failed to extract individual faces: {e}")
            return []

    @staticmethod
    def extract_edges_data(shape, edge_id_prefix: str = "Edge") -> List[Dict[str, Any]]:
        edges_data = []
        try:
            for i, edge in enumerate(shape.Edges):
                vertices = []
                try:
                    curve = edge.Curve
                    params = [edge.FirstParameter + (edge.LastParameter - edge.FirstParameter) * j / EDGE_PROCESSING_CONFIG["POINTS_PER_EDGE"] for j in range(EDGE_PROCESSING_CONFIG["POINTS_PER_EDGE"] + 1)]
                    points = [curve.value(param) for param in params]
                    vertices = [{
                        "btType": "BTVector3d-389",
                        "x": float(p.x), "y": float(p.y), "z": float(p.z)
                    } for p in points]
                except Exception:
                    start_point = edge.firstVertex().Point
                    end_point = edge.lastVertex().Point
                    vertices = [
                        {"btType": "BTVector3d-389", "x": float(start_point.x), "y": float(start_point.y), "z": float(start_point.z)},
                        {"btType": "BTVector3d-389", "x": float(end_point.x), "y": float(end_point.y), "z": float(end_point.z)}
                    ]
                
                edges_data.append({
                    "btType": "BTExportTessellatedEdgesEdge-1364",
                    "id": f"{edge_id_prefix}_{i}",
                    "vertices": vertices
                })
            return edges_data
        except Exception as e:
            print(f"[ERROR] Failed to extract edges data: {e}")
            return []

    @staticmethod
    def cleanup_document(doc):
        if doc:
            try:
                FreeCAD.closeDocument(doc.Name)
            except Exception as e:
                print(f"[WARNING] Failed to cleanup document: {e}")

    @staticmethod
    def get_shape_objects(doc) -> List:
        try:
            return [obj for obj in doc.Objects if hasattr(obj, 'Shape') and not obj.Shape.isNull()]
        except Exception as e:
            print(f"[ERROR] Failed to get shape objects: {e}")
            return []

class OnShapeJSONConverter:
    """Converter for OnShape JSON format"""
    def convert(self, step_path: str, json_path: str) -> bool:
        if not os.path.exists(step_path):
            print(f"[ERROR] STEP file not found: {step_path}")
            return False

        doc = FreeCADUtils.import_step_file(step_path)
        if not doc:
            return False

        try:
            shape_objects = FreeCADUtils.get_shape_objects(doc)
            if not shape_objects:
                print(f"[ERROR] No shape objects found in STEP file")
                return False
            print(f"[OK] Found {len(shape_objects)} shape objects")

            all_faces = []
            all_edges = []

            for obj in shape_objects:
                shape = obj.Shape
                individual_faces = FreeCADUtils.extract_individual_faces(shape)
                for i, face_shape in enumerate(individual_faces):
                    mesh = FreeCADUtils.create_mesh_from_shape(face_shape)
                    if not mesh: continue
                    
                    facets = []
                    for facet in mesh.Facets:
                        vertices = [{
                            "btType": "BTVector3d-389",
                            "x": p.x, "y": p.y, "z": p.z
                        } for p in (mesh.Points[idx] for idx in facet.PointIndices)]
                        facets.append({
                            "btType": "BTExportTessellatedFacesFacet-1417",
                            "vertices": vertices, "indices": [], "normals": [], "textureCoordinates": []
                        })
                    all_faces.append({
                        "btType": "BTExportTessellatedFacesFace-1192",
                        "id": f"Jf{chr(65 + i)}",
                        "facets": facets
                    })
                all_edges.extend(FreeCADUtils.extract_edges_data(shape, obj.Name))

            json_data = {
                "faces": {
                    "btType": "BTExportTessellatedFacesResponse-898",
                    "bodies": [{
                        "btType": "BTExportTessellatedFacesBody-1321",
                        "facetPoints": [],
                        "faces": all_faces
                    }]
                },
                "edges": {
                    "btType": "BTExportTessellatedEdgesResponse-327",
                    "bodies": [{
                        "btType": "BTExportTessellatedEdgesBody-1324",
                        "edges": all_edges
                    }] if all_edges else []
                }
            }

            with open(json_path, 'w') as f:
                json.dump(json_data, f, indent=2)
            
            print(f"[OK] OnShape JSON exported to: {json_path}")
            return True

        except Exception as e:
            print(f"[ERROR] OnShape JSON conversion failed: {e}")
            return False
        finally:
            FreeCADUtils.cleanup_document(doc)

def main():
    """Main execution function"""
    # We expect sys.argv to be [script_path, input_step, output_json]
    if len(sys.argv) != 3:
        print(f"[ERROR] Invalid arguments. Usage: <script> <input_step> <output_json>")
        print(f"[DEBUG] Received arguments ({len(sys.argv)}): {sys.argv}")
        sys.exit(1)

    input_step = sys.argv[1]
    output_json = sys.argv[2]

    print("--- Starting STEP to OnShape JSON Conversion ---")
    print(f"Input: {input_step}")
    print(f"Output: {output_json}")

    converter = OnShapeJSONConverter()
    success = converter.convert(input_step, output_json)

    if success:
        print("--- Conversion successful ---")
        sys.exit(0)
    else:
        print("--- Conversion failed ---")
        sys.exit(1)

if __name__ == "__main__":
    main()

