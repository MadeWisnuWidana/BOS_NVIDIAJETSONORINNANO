import paramiko
import os

hostname = "192.168.1.117"
username = "robotis"
password = "111111"

files_to_upload = [
    ("/home/brone/brone_vision_ws/remote_files/Lokalisasi.py", "/home/robotis/robotis_ws/src/Lokalisasi/Lokalisasi/Lokalisasi.py"),
    ("/home/brone/brone_vision_ws/remote_files/Compute.py", "/home/robotis/robotis_ws/src/Lokalisasi/Compute.py")
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(hostname, username=username, password=password, timeout=10)
    sftp = ssh.open_sftp()
    
    for local_file, remote_file in files_to_upload:
        sftp.put(local_file, remote_file)
        print(f"Successfully uploaded {local_file} to {remote_file}")
            
    sftp.close()
except Exception as e:
    print(f"SSH connection failed: {e}")
finally:
    ssh.close()
