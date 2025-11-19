#!/usr/bin/env python3
"""
FreeCAD API Client - User-based Script Processor
Equivalent to: freecadcmd <script.py> with user management
"""

import requests
import time
import sys
import os
import tarfile

API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000')

def check_health():
    """Check API health"""
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print(f"✅ API Health: {response.json()['status']} at {response.json()['time']}")
            return True
        else:
            print(f"❌ API Health check failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ API Health check error: {e}")
        return False

def upload_script(script_file, user_id, auto_download=False):
    """Upload script file with user_id"""
    try:
        if not os.path.exists(script_file):
            print(f"❌ Script file not found: {script_file}")
            return None
        
        with open(script_file, 'rb') as f:
            files = {'file': (os.path.basename(script_file), f, 'text/x-python')}
            data = {'user_id': user_id}
            if auto_download:
                data['auto_download'] = 'true'
            
            print(f"📤 Uploading {script_file} for user: {user_id}")
            if auto_download:
                print(f"🔄 Auto-download enabled - will wait for completion and download files")
            
            response = requests.post(f"{API_BASE_URL}/freecad/generate", files=files, data=data)
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    result = response.json()
                    
                    if 'files' in result and result['files']:
                        print(f"✅ Job completed for user: {result['user_id']}")
                        print(f"📁 Files saved to: {result.get('output_directory', 'N/A')}")
                        
                        downloaded_files = []
                        for file_info in result['files']:
                            file_type = file_info.get('type', '').upper()
                            filename = file_info.get('filename', '')
                            download_url = file_info.get('download_url', '')
                            local_path = file_info.get('local_path', '')
                            
                            print(f"📥 Downloading {file_type}: {filename}")
                            
                            try:
                                file_response = requests.get(download_url)
                                if file_response.status_code == 200:
                                    output_dir = "outputs/code/cad_outputs_generated"
                                    os.makedirs(output_dir, exist_ok=True)
                                    file_path = os.path.join(output_dir, filename)
                                    
                                    with open(file_path, 'wb') as f:
                                        f.write(file_response.content)
                                    
                                    print(f"✅ Downloaded: {file_path}")
                                    downloaded_files.append(file_path)
                                else:
                                    print(f"❌ Download failed: {file_response.status_code}")
                            except Exception as e:
                                print(f"❌ Download error: {e}")
                        
                        if downloaded_files:
                            print(f"\n📁 All files saved to: outputs/code/cad_outputs_generated/")
                            for file_path in downloaded_files:
                                print(f"   📄 {os.path.basename(file_path)}")
                        
                        return user_id
                    else:
                        print(f"✅ Job created for user: {result['user_id']}")
                        print(f"📋 Status: {result['status']}")
                        if 'created_at' in result:
                            print(f"⏰ Created at: {result['created_at']}")
                        return result['user_id']
                else:
                    print(f"❌ Unexpected response type: {content_type}")
                    return None
            else:
                print(f"❌ Upload failed: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return None

def check_status(user_id):
    """Check job status"""
    try:
        response = requests.get(f"{API_BASE_URL}/freecad/status/{user_id}")
        if response.status_code == 200:
            return response.json()['status']
        elif response.status_code == 202:
            return response.json()['status']
        else:
            print(f"❌ Status check failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Status check error: {e}")
        return None

def get_result(user_id):
    """Get job result"""
    try:
        response = requests.get(f"{API_BASE_URL}/freecad/result/{user_id}")
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 202:
            data = response.json()
            print(f"⏳ Job not finished yet: {data['status']}")
            return None
        else:
            print(f"❌ Result check failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Result check error: {e}")
        return None

def download_file(user_id, filename, local_path=None):
    """Download file from server"""
    try:
        if local_path is None:
            local_path = filename
        
        print(f"📥 Downloading {filename}...")
        response = requests.get(f"{API_BASE_URL}/freecad/download/{user_id}/{filename}")
        
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                f.write(response.content)
            print(f"✅ Downloaded: {local_path}")
            return True
        else:
            print(f"❌ Download failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False

def wait_for_completion(user_id, max_wait=60):
    """Wait for job to complete"""
    print(f"⏳ Waiting for job {user_id} to complete...")
    start_time = time.time()
    while time.time() - start_time < max_wait:
        status = check_status(user_id)
        if status == 'finished':
            print("\n✅ Job completed successfully!")
            return status
        elif status == 'failed':
            print("\n❌ Job failed!")
            return status
        elif status is None:
            # Error already printed by check_status
            return None
        print(f"📊 Status: {status}")
        time.sleep(2)
    
    print(f"⏰ Timeout after {max_wait} seconds")
    return None

def main():
    if len(sys.argv) < 3:
        print("Usage: python client_user_upload.py <script_file> <user_id> [--auto-download]")
        print("Example: python client_user_upload.py oblong.py user123")
        print("Example: python client_user_upload.py oblong.py user123 --auto-download")
        sys.exit(1)
    
    script_file = sys.argv[1]
    user_id = sys.argv[2]
    auto_download = '--auto-download' in sys.argv
    
    print("FreeCAD API Client - User-based Script Processor")
    print("Equivalent to: freecadcmd <script.py> with user management")
    if auto_download:
        print("🔄 Auto-download mode: Will wait and download files immediately")
    print("=" * 50)
    
    if not check_health():
        sys.exit(1)
    
    uploaded_user_id = upload_script(script_file, user_id, auto_download=auto_download)
    if not uploaded_user_id:
        sys.exit(1)
    
    if auto_download:
        print(f"\n✅ Process completed successfully!")
        print(f"🎯 Equivalent to: freecadcmd {script_file} (managed by user: {user_id})")
        print(f"📁 Files saved to: outputs/code/cad_outputs_generated/")
        return
    
    final_status = wait_for_completion(uploaded_user_id)
    if not final_status:
        sys.exit(1)
    
    if final_status == 'failed':
        print("❌ Job failed!")
        sys.exit(1)
    
    result = get_result(uploaded_user_id)
    if result:
        print("\n🎉 Job completed successfully!")
        print(f"📁 Files generated:")
        
        downloaded_files = []
        for file_info in result['files']:
            file_type = file_info['type'].upper()
            filename = file_info['filename']
            path = file_info['path']
            print(f"   📄 {file_type}: {filename}")
            print(f"      Path: {path}")
            
            if download_file(uploaded_user_id, filename):
                downloaded_files.append(filename)
        
        print(f"\n⏰ Completed at: {result['completed_at']}")
        
        if downloaded_files:
            print(f"\n📥 Downloaded files:")
            for filename in downloaded_files:
                print(f"   ✅ {filename}")
            print(f"\n💡 Files are now available in current directory")
        else:
            print(f"\n💡 Files are available in ./storage/ directory")
        
        print(f"\n✅ Process completed successfully!")
        print(f"🎯 Equivalent to: freecadcmd {script_file} (managed by user: {user_id})")
    else:
        print("❌ Failed to get results")
        sys.exit(1)

if __name__ == "__main__":
    main()
