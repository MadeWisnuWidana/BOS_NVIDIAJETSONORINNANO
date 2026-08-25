import paramiko
import os

hostname = "192.168.1.117"
username = "robotis"
password = "111111"

local_dir = "/home/brone/brone_vision_ws/remote_files"
os.makedirs(local_dir, exist_ok=True)

files_to_fetch = [
    "robotis_ws/src/Lokalisasi/Lokalisasi/Lokalisasi.py",
    "robotis_ws/src/Lokalisasi/Lokalisasi/Visual.py"
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(hostname, username=username, password=password, timeout=10)
    sftp = ssh.open_sftp()
    
    for file_path in files_to_fetch:
        remote_path = f"/home/robotis/{file_path}"
        local_path = os.path.join(local_dir, os.path.basename(file_path))
        try:
            sftp.get(remote_path, local_path)
            print(f"Fetched {remote_path} to {local_path}")
        except Exception as e:
            print(f"Failed to fetch {remote_path}: {e}")
            
    sftp.close()
except Exception as e:
    print(f"SSH connection failed: {e}")
finally:
    ssh.close()
