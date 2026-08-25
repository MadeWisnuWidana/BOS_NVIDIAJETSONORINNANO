import pandas as pd
import os
import glob

download_dir = "/home/brone/Downloads"
csv_files = [f for f in glob.glob(os.path.join(download_dir, "*.csv")) if "refinement" in f.lower()]

if not csv_files:
    print("No CSV files found.")
    exit()

print(f"Found {len(csv_files)} CSV files. Analyzing all...")

total_rows = 0
all_means = []

for f in csv_files:
    df = pd.read_csv(f)
    total_rows += len(df)
    
    # Calculate drift at the end
    end_data = df.tail(10).mean(numeric_only=True)
    drift = abs(end_data.get('Pose_X_Partikel', 0) - end_data.get('Posisi_X_Hitung_Baik', 0))
    
    # Calculate means per status
    if 'Status_Robot' in df.columns:
        grouped = df.groupby('Status_Robot').agg({
            'CPU_Usage(%)': 'mean',
            'Suhu_CPU(C)': 'mean' if 'Suhu_CPU(C)' in df.columns else 'count',
        }).reset_index()
        grouped['File'] = os.path.basename(f)
        grouped['Drift_Akhir'] = drift
        all_means.append(grouped)

if all_means:
    final_df = pd.concat(all_means)
    
    print("\n--- ANALISIS KESELURUHAN (RATA-RATA DARI 3 PENGUJIAN) ---")
    
    overall_mean = final_df.groupby('Status_Robot').agg({
        'CPU_Usage(%)': 'mean',
        'Suhu_CPU(C)': 'mean',
    })
    print("\nRata-Rata CPU dan Suhu Berdasarkan Status (3 Trial):")
    print(overall_mean)
    
    avg_drift = final_df['Drift_Akhir'].mean()
    print(f"\nRata-Rata Selisih Drift (IMU murni vs SLAM) di akhir lintasan: {avg_drift:.4f} meter")
    
    print("\n--- KESIMPULAN KESTABILAN ---")
    suhu_max = final_df['Suhu_CPU(C)'].max()
    cpu_max = final_df['CPU_Usage(%)'].max()
    print(f"Suhu Maksimum Tercatat di seluruh uji: {suhu_max:.2f}°C")
    print(f"Beban CPU Maksimum rata-rata per status: {cpu_max:.2f}%")
