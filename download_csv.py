import paramiko
import os

hostname = "192.168.1.117"
username = "robotis"
password = "111111"

local_dir = "/home/brone/Downloads"
os.makedirs(local_dir, exist_ok=True)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(hostname, username=username, password=password, timeout=10)
    sftp = ssh.open_sftp()
    
    remote_dir = "/home/robotis/robotis_ws/src/Lokalisasi/"
    files = sftp.listdir(remote_dir)
    
    # Ambil semua file berakhiran .csv yang mengandung kata "refinement" atau "Refinement"
    csv_files = [f for f in files if f.endswith(".csv") and "refinement" in f.lower()]
    
    # Sort files by name (which contains timestamp) to get the latest 3
    csv_files.sort(reverse=True)
    latest_3_csv = csv_files[:3]
    
    print(f"Found {len(latest_3_csv)} CSV files to download:")
    
    for file_name in latest_3_csv:
        remote_path = os.path.join(remote_dir, file_name)
        local_path = os.path.join(local_dir, file_name)
        try:
            sftp.get(remote_path, local_path)
            print(f"Downloaded {file_name} to {local_path}")
        except Exception as e:
            print(f"Failed to fetch {file_name}: {e}")
            
    sftp.close()
except Exception as e:
    print(f"SSH connection failed: {e}")
finally:
    ssh.close()
