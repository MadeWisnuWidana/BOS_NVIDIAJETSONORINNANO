import paramiko
import os

hostname = "192.168.1.117"
username = "robotis"
password = "111111"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(hostname, username=username, password=password, timeout=10)
    print("Connected successfully!")
    
    # We can run a find command via SSH to list all CSV files in /home/robotis
    stdin, stdout, stderr = ssh.exec_command("find /home/robotis -name '*.csv'")
    files = stdout.read().decode().splitlines()
    
    print(f"Found {len(files)} CSV files:")
    for f in sorted(files):
        print(f)
        
except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
