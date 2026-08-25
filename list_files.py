import paramiko
import os

hostname = "192.168.1.117"
username = "robotis"
password = "111111"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(hostname, username=username, password=password, timeout=10)
    stdin, stdout, stderr = ssh.exec_command("find ~/robotis_ws/src/Lokalisasi -type f -name '*.py'")
    print(stdout.read().decode())
    ssh.close()
except Exception as e:
    print(f"SSH connection failed: {e}")
