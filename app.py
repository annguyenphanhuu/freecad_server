import uuid
import os
import tempfile
import shutil
from datetime import datetime, timezone
import time
from flask import Flask, request, jsonify, send_file
from flask_restx import Api, Resource, fields, Namespace
from redis import Redis
from rq import Queue
from rq.job import Job
from dotenv import load_dotenv
from werkzeug.datastructures import FileStorage
import threading

import config
from mqtt_client import get_mqtt_manager

load_dotenv()

app = Flask(__name__)
api = Api(app, 
          title='FreeCAD Model Generator API',
          version='1.0',
          description='API to create FreeCAD models through worker queue with scalability',
          doc='/swagger/')

redis_conn = Redis.from_url(config.REDIS_URL)
queue = Queue(
    config.QUEUE_NAME,
    connection=redis_conn,
    default_timeout=config.JOB_TIMEOUT,
    result_ttl=config.RESULT_TTL,
    failure_ttl=config.FAILURE_TTL,
)

# Initialize MQTT manager
mqtt_manager = get_mqtt_manager()

# Swagger models
freecad_ns = Namespace('freecad', description='FreeCAD model generation operations')
api.add_namespace(freecad_ns)

# API Models
upload_parser = api.parser()
upload_parser.add_argument('file', location='files', type=FileStorage, required=True, help='FreeCAD Python script file (.py)')
upload_parser.add_argument('user_id', location='form', type=str, required=True, help='User ID for job management')
upload_parser.add_argument('auto_download', location='form', type=bool, required=False, help='If true, API will wait and return files immediately')

# Result parser with auto_download parameter
result_parser = api.parser()
result_parser.add_argument('auto_download', location='query', type=bool, required=False, help='If true, copy files to outputs/code/cad_outputs_generated/ and return download links. If false or not set, only return file information without copying.')

generate_request = api.model('GenerateRequest', {
    'user_id': fields.String(required=True, description='User ID', example='user123'),
    'script_name': fields.String(description='FreeCAD script name', example='oblong.py')
})

job_response = api.model('JobResponse', {
    'user_id': fields.String(description='User ID'),
    'status': fields.String(description='Job status', enum=['queued', 'started', 'finished', 'failed']),
    'message': fields.String(description='Message'),
    'created_at': fields.String(description='Creation time')
})

status_response = api.model('StatusResponse', {
    'user_id': fields.String(description='User ID'),
    'job_id': fields.String(description='Job ID', required=False),
    'status': fields.String(description='Job status'),
    'progress': fields.Integer(description='Completion percentage (0-100)'),
    'message': fields.String(description='Detailed message'),
    'error': fields.String(description='Error message (if any)'),
    'updated_at': fields.String(description='Update time'),
    'data_source': fields.String(description='Data source: "mqtt" or "redis"', required=False),
    'mqtt_connected': fields.Boolean(description='MQTT connection status', required=False)
})

file_info = api.model('FileInfo', {
    'type': fields.String(description='File type', enum=['step', 'obj', 'pdf', 'json']),
    'path': fields.String(description='File path'),
    'filename': fields.String(description='File name'),
    'download_url': fields.String(description='Download URL (if auto_download is enabled)', required=False),
    'local_path': fields.String(description='Local path (if auto_download is enabled)', required=False)
})

result_response = api.model('ResultResponse', {
    'user_id': fields.String(description='User ID'),
    'job_id': fields.String(description='Job ID', required=False),
    'status': fields.String(description='Job status'),
    'message': fields.String(description='Message', required=False),
    'files': fields.List(fields.Nested(file_info), description='List of generated files'),
    'output_directory': fields.String(description='Output directory (if auto_download is enabled)', required=False),
    'completed_at': fields.String(description='Completion time')
})


def iso_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _prepare_download_files(files, user_id):
    """Copy files to outputs directory and create download links"""
    if not files:
        return []
    
    # Always use default output directory (absolute path in container)
    output_dir_absolute = os.path.join("/app", "outputs", "code", "cad_outputs_generated")
    os.makedirs(output_dir_absolute, exist_ok=True)
    
    # Relative path from source (workspace root)
    output_dir_relative = "outputs/code/cad_outputs_generated"
    
    # Copy files to outputs directory and create download links
    download_links = []
    for f in files:
        src_path = f.get('path')
        filename = f.get('filename')
        if src_path and os.path.exists(src_path):
            dst_path_absolute = os.path.join(output_dir_absolute, filename)
            dst_path_relative = os.path.join(output_dir_relative, filename)
            shutil.copy2(src_path, dst_path_absolute)
            
            # Create download link
            base_url = os.getenv('API_BASE_URL', f'http://{config.API_HOST}:{config.API_PORT}')
            download_url = f"{base_url}/freecad/download/{user_id}/{filename}"
            download_links.append({
                "type": f.get('type'),
                "filename": filename,
                "download_url": download_url,
                "local_path": dst_path_relative,  # Return relative path from source
                "path": dst_path_relative  # Return relative path from source
            })
    
    return download_links


@api.route('/health')
class Health(Resource):
    @api.doc('health_check')
    def get(self):
        """Health check endpoint"""
        return {"status": "ok", "time": iso_now()}


@freecad_ns.route('/generate')
class GenerateModel(Resource):
    @api.expect(upload_parser)
    @api.doc('generate_model')
    def post(self):
        """Create FreeCAD model from script file"""
        try:
            # Check file upload
            if 'file' not in request.files:
                api.abort(400, "No file uploaded")
            
            file = request.files['file']
            if file.filename == '':
                api.abort(400, "No file selected")
            
            if not file.filename.endswith('.py'):
                api.abort(400, "File must be a Python script (.py)")
            
            # Get user_id from form data
            user_id = request.form.get('user_id')
            if not user_id:
                api.abort(400, "user_id is required")
            auto_download_raw = request.form.get('auto_download', '')
            auto_download = str(auto_download_raw).lower() in ['1', 'true', 'yes', 'on']
            
            # Save file in storage directory with user_id
            script_path = os.path.join(config.STORAGE_PATH, f"script_{user_id}_{file.filename}")
            file.save(script_path)
            
            # Put job into queue with user_id
            job = queue.enqueue(
                "worker.execute_freecad_script",
                script_path,
                user_id=user_id,
                meta={"created_at": iso_now(), "script_name": file.filename, "user_id": user_id},
                job_timeout=config.JOB_TIMEOUT
            )
            
            # Publish initial status to MQTT when job is queued
            mqtt_published = False
            try:
                if mqtt_manager.connected:
                    mqtt_manager.publish_status(
                        user_id,
                        "queued",
                        f"Job {job.id} queued for script {file.filename}"
                    )
                    mqtt_manager.publish_progress(
                        user_id,
                        0,
                        "queued",
                        f"Job queued. Waiting for worker to start processing..."
                    )
                    mqtt_published = True
                    print(f"✓ Published initial MQTT status for user {user_id}, job {job.id}")
                else:
                    print(f"⚠️ MQTT not connected, cannot publish for user {user_id}")
            except Exception as e:
                print(f"⚠️ Warning: Failed to publish initial MQTT status: {e}")
                import traceback
                traceback.print_exc()
                # Don't fail the request if MQTT publish fails
            
            # Always return immediately (no waiting) to avoid timeout for long-running jobs
            # Use /freecad/status/{user_id} to check progress via MQTT in real-time
            # Use /freecad/result/{user_id} to get results when job is finished
            return {
                "user_id": user_id,
                "status": "queued",
                "message": f"Script {file.filename} has been queued for processing. Use /freecad/status/{user_id} to check progress via MQTT, or /freecad/result/{user_id} to get results when finished.",
                "created_at": job.meta.get("created_at"),
                "job_id": job.id,
                "check_status_url": f"/freecad/status/{user_id}",
                "check_result_url": f"/freecad/result/{user_id}",
                "mqtt_published": mqtt_published
            }
            
        except Exception as exc:
            api.abort(500, f"Failed to process file: {exc}")


@freecad_ns.route('/status/<string:user_id>')
class JobStatus(Resource):
    @api.marshal_with(status_response)
    @api.doc('get_job_status')
    def get(self, user_id):
        """Check job status by user_id with progress from MQTT"""
        try:
            # Check MQTT progress first
            mqtt_progress = mqtt_manager.get_progress(user_id)
            mqtt_connected = mqtt_manager.connected if hasattr(mqtt_manager, 'connected') else False
            
            if mqtt_progress:
                # Try to find the job in RQ to get job_id if not present in MQTT meta
                job_id = None
                try:
                    def _find_job_for_user():
                        registries = [
                            queue.finished_job_registry.get_job_ids(),
                            queue.started_job_registry.get_job_ids(),
                            queue.get_job_ids(),
                        ]
                        for job_ids in registries:
                            for jid in job_ids:
                                try:
                                    j = Job.fetch(jid, connection=redis_conn)
                                    if j.meta and j.meta.get("user_id") == user_id:
                                        return j
                                except Exception:
                                    continue
                        return None
                    job = _find_job_for_user()
                    if job:
                        job_id = job.id
                except Exception:
                    pass
                
                return {
                    "user_id": user_id,
                    "job_id": job_id,
                    "status": mqtt_progress.get("status", "unknown"),
                    "progress": mqtt_progress.get("progress", 0),
                    "message": mqtt_progress.get("message", ""),
                    "error": mqtt_progress.get("error"),
                    "updated_at": mqtt_progress.get("updated_at", iso_now()),
                    "data_source": "mqtt",
                    "mqtt_connected": mqtt_connected
                }
            
            def _find_job_for_user():
                registries = [
                    queue.finished_job_registry.get_job_ids(),
                    queue.started_job_registry.get_job_ids(),
                    queue.get_job_ids(),
                ]
                for job_ids in registries:
                    for job_id in job_ids:
                        try:
                            job = Job.fetch(job_id, connection=redis_conn)
                        except Exception:
                            continue
                        if job.meta and job.meta.get("user_id") == user_id:
                            return job
                return None

            # Fallback to Redis if no MQTT data
            job = _find_job_for_user()
            
            if job:
                status = job.get_status()
                updated_at = iso_now()
                if job.ended_at:
                    updated_at = job.ended_at.replace(tzinfo=timezone.utc).isoformat()
                progress = 0
                if status == "started":
                    progress = 50
                elif status == "finished":
                    progress = 100
                return {
                    "user_id": user_id,
                    "job_id": job.id,
                    "status": status,
                    "progress": progress,
                    "message": f"Job {status} (from Redis queue)",
                    "error": None,
                    "updated_at": updated_at,
                    "data_source": "redis",
                    "mqtt_connected": mqtt_connected
                }
            
            api.abort(
                404,
                {
                    "message": "Job not found. It may still be initializing or has already expired.",
                    "user_id": user_id,
                },
            )
        except Exception as e:
            api.abort(
                404,
                {
                    "message": f"Job not found: {str(e)}",
                    "user_id": user_id,
                },
            )


@freecad_ns.route('/result/<string:user_id>')
class JobResult(Resource):
    @api.expect(result_parser)
    @api.marshal_with(result_response)
    @api.doc('get_job_result')
    def get(self, user_id):
        """Get job result by user_id. Use auto_download=true to copy files to outputs/code/cad_outputs_generated/ and get download links."""
        try:
            # Check if auto_download is requested (only check auto_download, not download alias)
            auto_download_raw = request.args.get('auto_download', '')
            auto_download = str(auto_download_raw).lower() in ['1', 'true', 'yes', 'on']
            
            # Helper function to return result
            def _return_result(job, files):
                if auto_download and files:
                    # Copy files to outputs directory and create download links
                    download_links = _prepare_download_files(files, user_id)
                    
                    # Return relative path from source (workspace root)
                    output_dir = "outputs/code/cad_outputs_generated"
                    
                    return {
                        "user_id": user_id,
                        "job_id": job.id if job else None,
                        "status": "success",
                        "message": f"Files generated and saved to {output_dir}/",
                        "files": download_links,
                        "output_directory": output_dir,
                        "completed_at": job.ended_at.replace(tzinfo=timezone.utc).isoformat()
                        if job and job.ended_at
                        else iso_now(),
                    }
                else:
                    return {
                        "user_id": user_id,
                        "job_id": job.id if job else None,
                        "status": "success",
                        "files": files,
                        "completed_at": job.ended_at.replace(tzinfo=timezone.utc).isoformat()
                        if job and job.ended_at
                        else iso_now(),
                    }
            
            # Find job by user_id in meta
            # Try to find in finished jobs first
            finished_jobs = queue.finished_job_registry.get_job_ids()
            for job_id in finished_jobs:
                try:
                    job = Job.fetch(job_id, connection=redis_conn)
                    if job.meta and job.meta.get('user_id') == user_id:
                        status = job.get_status()
                        if status != "finished":
                            return {
                                "user_id": user_id,
                                "job_id": job.id,
                                "status": status,
                                "message": "Result not ready yet. Job is still running.",
                                "files": [],
                                "completed_at": None,
                            }, 202

                        result = job.result or {}
                        files = result.get("files", [])
                        return _return_result(job, files)
                except:
                    continue
            
            # Find in running jobs
            started_jobs = queue.started_job_registry.get_job_ids()
            for job_id in started_jobs:
                try:
                    job = Job.fetch(job_id, connection=redis_conn)
                    if job.meta and job.meta.get('user_id') == user_id:
                        status = job.get_status()
                        if status != "finished":
                            return {
                                "user_id": user_id,
                                "job_id": job.id,
                                "status": status,
                                "message": "Result not ready yet. Job is still running.",
                                "files": [],
                                "completed_at": None,
                            }, 202

                        result = job.result or {}
                        files = result.get("files", [])
                        return _return_result(job, files)
                except:
                    continue
            
            # Find in queue
            queued_jobs = queue.get_job_ids()
            for job_id in queued_jobs:
                try:
                    job = Job.fetch(job_id, connection=redis_conn)
                    if job.meta and job.meta.get('user_id') == user_id:
                        status = job.get_status()
                        if status != "finished":
                            return {
                                "user_id": user_id,
                                "job_id": job.id,
                                "status": status,
                                "message": "Result not ready yet. Job is still running.",
                                "files": [],
                                "completed_at": None,
                            }, 202

                        result = job.result or {}
                        files = result.get("files", [])
                        return _return_result(job, files)
                except:
                    continue
            
            api.abort(
                404,
                {
                    "message": "Result not found. The job may still be running or the result has expired.",
                    "user_id": user_id,
                },
            )
        except Exception as e:
            api.abort(
                404,
                {
                    "message": f"Result not available: {str(e)}",
                    "user_id": user_id,
                },
            )


@freecad_ns.route('/download/<string:user_id>/<string:filename>')
class DownloadFile(Resource):
    @api.doc('download_file')
    def get(self, user_id, filename):
        """Download file by user_id and filename"""
        try:
            # Check in default outputs directory first (for auto_download files)
            output_dir = os.path.join("/app", "outputs", "code", "cad_outputs_generated")
            file_path = os.path.join(output_dir, filename)
            
            # If not found, search in all subdirectories of /app/outputs/
            if not os.path.exists(file_path):
                outputs_base = "/app/outputs"
                if os.path.exists(outputs_base):
                    for root, dirs, files in os.walk(outputs_base):
                        if filename in files:
                            file_path = os.path.join(root, filename)
                            break
            
            # If still not found, check in storage directory
            if not os.path.exists(file_path):
                file_path = os.path.join(config.STORAGE_PATH, filename)
            
            if not os.path.exists(file_path):
                api.abort(404, f"File not found: {filename}")
            
            # Check if file belongs to this user (filename contains user_id)
            if user_id not in filename:
                api.abort(403, f"Access denied: File does not belong to user {user_id}")
            
            # Return file
            return send_file(
                file_path,
                as_attachment=True,
                download_name=filename,
                mimetype='application/octet-stream'
            )
            
        except Exception as e:
            api.abort(500, f"Download failed: {str(e)}")


@freecad_ns.route('/template/oblong')
class OblongTemplate(Resource):
    @api.doc('get_oblong_template')
    def get(self):
        """Get oblong.py template script"""
        return {
            "script_name": "oblong.py",
            "description": "Oblong plate generator script",
            "usage": "Upload this script file to /freecad/generate endpoint"
        }


@freecad_ns.route('/workers/status')
class AllWorkersStatus(Resource):
    @api.doc('get_all_workers_status')
    def get(self):
        """Get status of all workers"""
        try:
            all_progress = mqtt_manager.get_all_progress()
            return {
                "workers": all_progress,
                "total_workers": len(all_progress),
                "updated_at": iso_now()
            }
        except Exception as e:
            api.abort(500, f"Failed to get workers status: {str(e)}")


if __name__ == "__main__":
    app.run(host=config.API_HOST, port=config.API_PORT, debug=True)
