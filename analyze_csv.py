import pandas as pd
import os
import glob

download_dir = "/home/brone/Downloads"
csv_files = glob.glob(os.path.join(download_dir, "Uji_Refinement_compute_imu_pose_*.csv"))

if not csv_files:
    print("No CSV files found.")
    exit()

latest_csv = max(csv_files, key=os.path.getctime)
print(f"Analyzing {latest_csv}...\n")

df = pd.read_csv(latest_csv)

print("--- ANALISIS STATISTIK DASAR ---")
print(f"Total baris data: {len(df)}")
print(f"Durasi total: {df['Waktu_Elapsed(s)'].max()} detik")
print(f"Rata-rata CPU Usage: {df['CPU_Usage(%)'].mean():.2f}%")
if 'Suhu_CPU(C)' in df.columns:
    print(f"Rata-rata Suhu CPU: {df['Suhu_CPU(C)'].mean():.2f}°C")
    print(f"Suhu Maksimum CPU: {df['Suhu_CPU(C)'].max():.2f}°C")

print("\n--- ANALISIS BERDASARKAN STATUS ---")
if 'Status_Robot' in df.columns:
    grouped = df.groupby('Status_Robot').agg({
        'CPU_Usage(%)': 'mean',
        'Suhu_CPU(C)': 'mean' if 'Suhu_CPU(C)' in df.columns else 'count',
        'Pose_X_Partikel': ['min', 'max']
    })
    print(grouped)
    
print("\n--- ANALISIS DRIFT (POSISI BAIK VS PARTIKEL) ---")
# Cek perbedaan di akhir lintasan
end_data = df.tail(10).mean()
drift = abs(end_data['Pose_X_Partikel'] - end_data['Posisi_X_Hitung_Baik'])
print(f"Selisih Pose X (IMU Baik vs SLAM Partikel) di akhir lintasan: {drift:.4f} meter")
