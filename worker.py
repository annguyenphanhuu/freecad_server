import os
import sys
import tempfile
import shutil
import subprocess
import uuid
import threading
import time
import json
from typing import Dict, Any
from pathlib import Path
from mqtt_client import get_mqtt_manager

STORAGE_PATH = os.getenv("STORAGE_PATH", "/app/storage")
os.makedirs(STORAGE_PATH, exist_ok=True)

# Add src/utils and src/core to Python path for technical drawing generator and step converter
sys.path.append('/app/src/utils')
sys.path.append('/app/src/core')


def generate_pdf_from_step(step_file_path: str, user_id: str) -> Dict[str, Any]:
    """
    Generate PDF from STEP file using technical_drawing_generator
    """
    try:
        from technical_drawing_generator import generate_technical_drawing_from_step
        
        print(f"Generating PDF from STEP file: {step_file_path} for user: {user_id}")
        
        # Create output directory for PDF
        pdf_output_dir = Path(STORAGE_PATH) / f"pdf_user_{user_id}"
        pdf_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create base filename from step file
        step_path = Path(step_file_path)
        base_filename = f"{step_path.stem}_{user_id}"
        
        # Call technical drawing generator
        result = generate_technical_drawing_from_step(
            step_path, 
            pdf_output_dir, 
            base_filename
        )
        
        if result["success"] and result["pdf_path"]:
            # Copy PDF to main storage
            pdf_source = Path(result["pdf_path"])
            pdf_dest = Path(STORAGE_PATH) / f"{base_filename}.pdf"
            shutil.copy2(pdf_source, pdf_dest)
            
            # Cleanup temp directory
            shutil.rmtree(pdf_output_dir, ignore_errors=True)
            
            return {
                "status": "success",
                "pdf_path": str(pdf_dest),
                "filename": pdf_dest.name,
                "message": result["message"]
            }
        else:
            return {
                "status": "failed",
                "error": result["message"]
            }
            
    except ImportError as e:
        print(f"Warning: Technical drawing generator not available: {e}")
        return {
            "status": "failed", 
            "error": "PDF generation not available - technical_drawing_generator not found"
        }
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return {
            "status": "failed",
            "error": f"PDF generation failed: {str(e)}"
        }


def generate_json_from_step(step_file_path: str, user_id: str) -> Dict[str, Any]:
    """
    Generate JSON from STEP file using step_converter
    """
    try:
        print(f"Generating JSON from STEP file: {step_file_path} for user: {user_id}")
        
        # Create base filename from step file
        step_path = Path(step_file_path)
        base_filename = f"{step_path.stem}_{user_id}"
        json_dest = Path(STORAGE_PATH) / f"{base_filename}.json"
        
        # Create script to run step_converter
        converter_script = f"""
import sys
sys.path.append('/app/src/core')
from step_converter import OnShapeJSONConverter

converter = OnShapeJSONConverter()
success = converter.convert('{step_file_path}', '{json_dest}')
if success:
    print("JSON conversion completed successfully!")
else:
    print("JSON conversion failed!")
    sys.exit(1)
"""
        
        # Save temporary script
        script_path = Path(STORAGE_PATH) / f"converter_{user_id}.py"
        with open(script_path, 'w') as f:
            f.write(converter_script)
        
        # Run script with freecadcmd (increased timeout for heavy files)
        print(f"Running JSON converter script: {script_path}")
        result = subprocess.run(
            ["freecadcmd", str(script_path)],
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout for heavy files
        )
        
        # Cleanup script
        try:
            os.remove(script_path)
        except:
            pass
        
        if result.returncode != 0:
            error_msg = f"FreeCAD command failed with return code {result.returncode}"
            if result.stderr:
                error_msg += f": {result.stderr[:500]}"  # Limit error message length
            print(f"JSON generation failed: {error_msg}")
            print(f"FreeCAD stdout: {result.stdout[:500] if result.stdout else 'No output'}")
            return {
                "status": "failed",
                "error": error_msg,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        
        if json_dest.exists():
            print(f"JSON file created successfully: {json_dest}")
            return {
                "status": "success",
                "json_path": str(json_dest),
                "filename": json_dest.name,
                "message": "JSON conversion completed successfully"
            }
        else:
            error_msg = f"JSON file was not created at {json_dest}"
            print(f"JSON generation failed: {error_msg}")
            if result.stdout:
                print(f"FreeCAD stdout: {result.stdout[:500]}")
            if result.stderr:
                print(f"FreeCAD stderr: {result.stderr[:500]}")
            return {
                "status": "failed",
                "error": error_msg,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
            
    except ImportError as e:
        print(f"Warning: Step converter not available: {e}")
        return {
            "status": "failed", 
            "error": "JSON generation not available - step_converter not found"
        }
    except subprocess.TimeoutExpired as e:
        error_msg = "JSON generation timed out after 1 hour. This may happen with very large/complex STEP files."
        print(f"Error generating JSON: {error_msg}")
        print(f"Exception: {e}")
        # Cleanup script on timeout
        try:
            script_path = Path(STORAGE_PATH) / f"converter_{user_id}.py"
            if script_path.exists():
                os.remove(script_path)
        except:
            pass
        return {
            "status": "failed",
            "error": error_msg,
            "exception": str(e),
        }
    except Exception as e:
        error_msg = f"JSON generation failed: {str(e)}"
        print(f"Error generating JSON: {error_msg}")
        import traceback
        tb = traceback.format_exc()
        print(f"Traceback: {tb}")
        return {
            "status": "failed",
            "error": error_msg,
            "traceback": tb,
        }


def execute_freecad_script(script_path: str, user_id: str = None) -> Dict[str, Any]:
    """
    Execute FreeCAD script using freecadcmd
    """
    mqtt_manager = get_mqtt_manager()
    
    try:
        if user_id is None:
            user_id = str(uuid.uuid4())
        
        print(f"Processing script: {script_path} for user: {user_id}")
        
        # Publish initial status
        mqtt_manager.publish_status(user_id, "started", "Starting FreeCAD script execution")
        mqtt_manager.publish_progress(user_id, 0, "started", "Initializing...")
        
        # Create output directory for this user
        user_output_dir = os.path.join(STORAGE_PATH, f"user_{user_id}")
        os.makedirs(user_output_dir, exist_ok=True)
        
        # Update progress
        mqtt_manager.publish_progress(user_id, 10, "running", "Setting up output directory...")
        
        # Run script using Python with FreeCAD modules
        cmd = ["freecadcmd", script_path]
        print(f"Executing command: {' '.join(cmd)}")
        
        # Update progress
        mqtt_manager.publish_progress(user_id, 20, "running", "Executing FreeCAD script...")
        
        # Start heartbeat thread to publish progress updates while FreeCAD is running
        heartbeat_stop = threading.Event()
        heartbeat_progress = {"value": 25}  # Start at 25%
        
        def heartbeat_worker():
            """Publish progress updates every 5 seconds while FreeCAD is running"""
            while not heartbeat_stop.is_set():
                heartbeat_progress["value"] = min(heartbeat_progress["value"] + 2, 35)  # Gradually increase to 35%
                mqtt_manager.publish_progress(
                    user_id, 
                    heartbeat_progress["value"], 
                    "running", 
                    f"FreeCAD script is running... (progress: {heartbeat_progress['value']}%)"
                )
                if heartbeat_stop.wait(timeout=5):  # Wait 5 seconds or until stop event
                    break
        
        heartbeat_thread = threading.Thread(target=heartbeat_worker, daemon=True)
        heartbeat_thread.start()
        
        try:
            # Use Popen to allow monitoring, but still wait for completion
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            text=True,
            cwd=user_output_dir,
            env={**os.environ, "PYTHONPATH": "/app:/usr/lib/freecad/lib:/usr/lib/python3/dist-packages"}
        )
            
            # Wait for process with timeout (increased for heavy files)
            try:
                stdout, stderr = process.communicate(timeout=3600)  # 1 hour timeout for heavy files
                returncode = process.returncode
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                returncode = -1
                error_msg = "FreeCAD command timed out after 1 hour"
                heartbeat_stop.set()
                mqtt_manager.publish_status(user_id, "failed", error_msg, None)
                mqtt_manager.publish_progress(user_id, 0, "failed", error_msg, None)
                return {
                    "status": "failed",
                    "error": error_msg
                }
            
            result = type('obj', (object,), {
                'returncode': returncode,
                'stdout': stdout,
                'stderr': stderr
            })()
            
        finally:
            # Stop heartbeat
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=1)
        
        print(f"FreeCAD command exit code: {result.returncode}")
        print(f"FreeCAD stdout: {result.stdout}")
        if result.stderr:
            print(f"FreeCAD stderr: {result.stderr}")
        
        if result.returncode != 0:
            error_msg = f"FreeCAD command failed with exit code {result.returncode}"
            # Include helpful diagnostics
            stdout_tail = (result.stdout or "").splitlines()[-50:]
            stderr_tail = (result.stderr or "").splitlines()[-50:]
            error_hint = _extract_error_hint("\n".join(stdout_tail), "\n".join(stderr_tail))
            details = {
                "error_hint": error_hint,
                "stdout_tail": stdout_tail,
                "stderr_tail": stderr_tail,
            }
            mqtt_manager.publish_status(user_id, "failed", error_msg, str(details))
            mqtt_manager.publish_progress(user_id, 0, "failed", error_msg, str(details))
            return {
                "status": "failed",
                "error": error_msg,
                "details": details
            }
        
        # Update progress after successful execution
        mqtt_manager.publish_progress(user_id, 40, "running", "FreeCAD script executed successfully, searching for generated files...")
        
        # Find generated files
        generated_files = []
        
        # Update progress
        mqtt_manager.publish_progress(user_id, 50, "running", "Searching for generated files...")
        
        # Find files in user output directory
        for root, dirs, files in os.walk(user_output_dir):
            for file in files:
                if file.endswith(('.step', '.obj')):
                    file_path = os.path.join(root, file)
                    # Copy file to main storage with filename containing user_id
                    new_filename = f"{os.path.splitext(file)[0]}_{user_id}{os.path.splitext(file)[1]}"
                    new_path = os.path.join(STORAGE_PATH, new_filename)
                    shutil.copy2(file_path, new_path)
                    
                    file_type = "step" if file.endswith('.step') else "obj"
                    generated_files.append({
                        "type": file_type,
                        "path": new_path,
                        "filename": new_filename
                    })
        
        # If no files found in job directory, search in cad_outputs_generated
        if not generated_files:
            mqtt_manager.publish_progress(user_id, 60, "running", "Searching in cad_outputs_generated directory...")
            cad_output_dir = "/app/cad_outputs_generated"
            if os.path.exists(cad_output_dir):
                for root, dirs, files in os.walk(cad_output_dir):
                    for file in files:
                        if file.endswith(('.step', '.obj')):
                            file_path = os.path.join(root, file)
                            # Copy file to main storage with filename containing user_id
                            new_filename = f"{os.path.splitext(file)[0]}_{user_id}{os.path.splitext(file)[1]}"
                            new_path = os.path.join(STORAGE_PATH, new_filename)
                            shutil.copy2(file_path, new_path)
                            
                            file_type = "step" if file.endswith('.step') else "obj"
                            generated_files.append({
                                "type": file_type,
                                "path": new_path,
                                "filename": new_filename
                            })
                            
                            # Cleanup original file
                            try:
                                os.remove(file_path)
                            except:
                                pass
        
        # Cleanup temp directory
        shutil.rmtree(user_output_dir, ignore_errors=True)
        
        if not generated_files:
            error_msg = "No STEP or OBJ files were generated"
            # Provide diagnostics from the FreeCAD run output
            stdout_tail = (result.stdout or "").splitlines()[-50:]
            stderr_tail = (result.stderr or "").splitlines()[-50:]
            error_hint = _extract_error_hint("\n".join(stdout_tail), "\n".join(stderr_tail))
            details = {
                "error_hint": error_hint,
                "stdout_tail": stdout_tail,
                "stderr_tail": stderr_tail,
            }
            mqtt_manager.publish_status(user_id, "failed", error_msg, str(details))
            mqtt_manager.publish_progress(user_id, 0, "failed", error_msg, str(details))
            return {
                "status": "failed",
                "error": error_msg,
                "details": details
            }
        
        # Update progress
        mqtt_manager.publish_progress(user_id, 70, "running", f"Found {len(generated_files)} files, generating PDF and JSON...")
        
        # Generate PDF and JSON from STEP files (if any)
        pdf_files = []
        json_files = []
        for i, file_info in enumerate(generated_files):
            if file_info["type"] == "step":
                # Update progress for each file
                progress = 70 + int((i + 1) * 20 / len(generated_files))
                mqtt_manager.publish_progress(user_id, progress, "running", f"Processing file {i+1}/{len(generated_files)}: {file_info['filename']}")
                
                print(f"Generating PDF from STEP file: {file_info['path']}")
                pdf_result = generate_pdf_from_step(file_info["path"], user_id)
                if pdf_result["status"] == "success":
                    pdf_files.append({
                        "type": "pdf",
                        "path": pdf_result["pdf_path"],
                        "filename": pdf_result["filename"]
                    })
                    print(f"PDF generated successfully: {pdf_result['filename']}")
                else:
                    print(f"PDF generation failed: {pdf_result['error']}")
                
                print(f"Generating JSON from STEP file: {file_info['path']}")
                json_result = generate_json_from_step(file_info["path"], user_id)
                if json_result["status"] == "success":
                    json_files.append({
                        "type": "json",
                        "path": json_result["json_path"],
                        "filename": json_result["filename"]
                    })
                    print(f"✅ JSON generated successfully: {json_result['filename']}")
                else:
                    error_msg = json_result.get("error", "Unknown error during JSON generation")
                    details_payload = {
                        "error": error_msg,
                        "result": json_result,
                        "step_file": file_info["path"],
                    }
                    print(f"⚠️ JSON generation failed for {file_info['filename']}: {error_msg}")
                    mqtt_manager.publish_status(
                        user_id,
                        "failed",
                        error_msg,
                        json.dumps(details_payload),
                    )
                    mqtt_manager.publish_progress(
                        user_id,
                        0,
                        "failed",
                        error_msg,
                        json.dumps(details_payload),
                    )
                    return {
                        "status": "failed",
                        "error": error_msg,
                        "details": details_payload,
                    }
        
        # Combine all files (STEP, OBJ, PDF, JSON)
        all_files = generated_files + pdf_files + json_files
        print(f"✅ All generated files ({len(all_files)}): {[f['filename'] for f in all_files]}")
        
        # Final progress update
        mqtt_manager.publish_progress(user_id, 100, "finished", f"Successfully generated {len(all_files)} files")
        mqtt_manager.publish_status(user_id, "finished", f"Job completed successfully with {len(all_files)} files")
        
        return {
            "status": "success",
            "files": all_files
        }
        
    except subprocess.TimeoutExpired:
        error_msg = "FreeCAD command timed out after 5 minutes"
        mqtt_manager.publish_status(user_id, "failed", error_msg, None)
        mqtt_manager.publish_progress(user_id, 0, "failed", error_msg, None)
        return {
            "status": "failed",
            "error": error_msg
        }
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        mqtt_manager.publish_status(user_id, "failed", error_msg, None)
        mqtt_manager.publish_progress(user_id, 0, "failed", error_msg, None)
        return {
            "status": "failed",
            "error": error_msg
        }
    finally:
        # Cleanup script file
        try:
            if os.path.exists(script_path):
                os.remove(script_path)
                # Remove parent directory if empty
                parent_dir = os.path.dirname(script_path)
                if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                    os.rmdir(parent_dir)
        except Exception as e:
            print(f"Warning: Could not cleanup script file: {e}")


# Legacy function for backward compatibility (if needed)
def generate_freecad_job(model_type: str, parameters: dict, job_id: str) -> Dict[str, Any]:
    """
    Legacy function - redirects to script execution
    """
    return {
        "status": "failed",
        "error": "This endpoint is deprecated. Please use file upload instead."
    }


def _extract_error_hint(stdout_text: str, stderr_text: str) -> str:
    """Try to infer a helpful error hint from FreeCAD outputs."""
    text = f"{stdout_text}\n{stderr_text}".lower()
    if "modulenotfounderror" in text or "no module named" in text:
        return "ImportError: missing module. Verify FreeCadUtil and workbench imports, or sys.path."
    if "attributeerror" in text and "maketub" in text:
        return "AttributeError: Part.makeTub missing. Ensure FreeCadUtil monkey patch is loaded."
    if "permission denied" in text:
        return "Permission issue writing outputs. Verify container paths and permissions."
    if "traceback" in text and "export" in text and ".step" in text:
        return "STEP export failed. Ensure shapes are valid solids and export path exists."
    if "wkhtmltopdf" in text and "not found" in text:
        return "wkhtmltopdf missing. PDF generation may fail; check worker image deps."
    if "precision" in text and "approximation" in text:
        return "FreeCAD Precision API mismatch. Ensure FreeCAD 0.21+/1.0 compatibility fixes are applied."
    return "See stdout_tail/stderr_tail for details."