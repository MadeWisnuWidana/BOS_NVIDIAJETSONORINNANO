import paramiko
import os
import re

# ============================================================
# KONFIGURASI KONEKSI
# ============================================================
hostname  = "192.168.1.117"
username  = "robotis"
password  = "111111"

# Folder tujuan di laptop
local_base = os.path.expanduser("~/Downloads/Hasil Pengujian Lokalisasi")

# Direktori CSV di NUC (berdasarkan SOP)
remote_dir = "/home/robotis/robotis_ws/src/Lokalisasi/"

# ============================================================
# KRITERIA PENCARIAN UNTUK SETIAP SKENARIO
# Berdasarkan format prefix Compute.py:
#   {prefix}_compute_imu_pose_{timestamp}.csv
# ============================================================
SKENARIO_A_PREFIX = "Skenario_A_DeadReckoning"   # Murni Dead Reckoning
SKENARIO_B_PREFIX = "Skenario_B_Alvin"           # VIO Konvensional Alvin
SKENARIO_C_PREFIX = "Skenario_C_VIO_Poligon"     # Proposed Method

# Regex untuk mendeteksi nomor akhiran skenario C (21, 22, 23, ...)
# Skenario C diketahui berakhiran angka >= 21
SKENARIO_C_SUFFIX_RE = re.compile(r'_(\d+)_compute_imu_pose_')

def get_scenario_folder(prefix):
    """Buat subfolder per skenario."""
    mapping = {
        SKENARIO_A_PREFIX: "Skenario_A_DeadReckoning",
        SKENARIO_B_PREFIX: "Skenario_B_Alvin",
        SKENARIO_C_PREFIX: "Skenario_C_VIO_Poligon",
    }
    return mapping.get(prefix, prefix)

def classify_file(filename):
    """
    Kembalikan label skenario berdasarkan nama file.
    Urutan pengecekan: A → B → C (agar tidak salah tangkap)
    """
    f = filename.lower()
    if SKENARIO_A_PREFIX.lower() in f:
        return "A"
    if SKENARIO_B_PREFIX.lower() in f:
        return "B"
    if SKENARIO_C_PREFIX.lower() in f:
        return "C"
    # Fallback: coba deteksi pola akhiran angka >= 21
    # (cadangan jika penamaan sedikit berbeda)
    match = SKENARIO_C_SUFFIX_RE.search(filename)
    if match and int(match.group(1)) >= 21:
        return "C_maybe"
    return None

def download_all():
    print("=" * 60)
    print("  DOWNLOADER HASIL PENGUJIAN SAR — ROBOTIS OP3")
    print("=" * 60)
    print(f"  Host   : {hostname}")
    print(f"  User   : {username}")
    print(f"  Target : {local_base}")
    print("=" * 60)

    # Buat folder utama
    os.makedirs(local_base, exist_ok=True)
    subfolders = {
        "A": os.path.join(local_base, "Skenario_A_DeadReckoning"),
        "B": os.path.join(local_base, "Skenario_B_Alvin"),
        "C": os.path.join(local_base, "Skenario_C_VIO_Poligon"),
        "C_maybe": os.path.join(local_base, "Skenario_C_VIO_Poligon"),
    }
    for path in set(subfolders.values()):
        os.makedirs(path, exist_ok=True)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print("\n🔌 Menghubungkan ke NUC robot...")
        ssh.connect(hostname, username=username, password=password, timeout=15)
        print("✅ Koneksi SSH berhasil!\n")

        sftp = ssh.open_sftp()

        # --------------------------------------------------------
        # 1. List semua file CSV di direktori utama Lokalisasi
        # --------------------------------------------------------
        print(f"📂 Membaca direktori: {remote_dir}")
        try:
            all_files = sftp.listdir(remote_dir)
        except Exception as e:
            print(f"❌ Gagal membaca direktori {remote_dir}: {e}")
            return

        csv_files = [f for f in all_files if f.endswith(".csv")]
        print(f"   Ditemukan {len(csv_files)} file CSV total di NUC.\n")

        # --------------------------------------------------------
        # 2. Kelompokkan file per skenario
        # --------------------------------------------------------
        grouped = {"A": [], "B": [], "C": [], "C_maybe": []}
        unclassified = []

        for f in csv_files:
            label = classify_file(f)
            if label:
                grouped[label].append(f)
            else:
                unclassified.append(f)

        # Sort tiap grup berdasarkan timestamp di nama file
        for key in grouped:
            grouped[key].sort()

        print("📊 Hasil Klasifikasi File:")
        print(f"   Skenario A (Dead Reckoning) : {len(grouped['A'])} file")
        print(f"   Skenario B (Alvin)          : {len(grouped['B'])} file")
        print(f"   Skenario C (VIO Poligon)    : {len(grouped['C']) + len(grouped['C_maybe'])} file")
        if unclassified:
            print(f"   Tidak terklasifikasi        : {len(unclassified)} file")
        print()

        # --------------------------------------------------------
        # 3. Download per skenario
        # --------------------------------------------------------
        total_downloaded = 0
        total_failed = 0

        for label, display_name in [
            ("A", "🔴 SKENARIO A — Dead Reckoning"),
            ("B", "🟡 SKENARIO B — VIO Alvin"),
            ("C", "🟢 SKENARIO C — VIO Poligon (Proposed)"),
        ]:
            files_in_group = grouped[label]
            if label == "C":
                files_in_group = grouped["C"] + grouped["C_maybe"]
                files_in_group.sort()

            print(f"{display_name}")
            print(f"   {'-'*50}")

            if not files_in_group:
                print("   ⚠️  Tidak ada file ditemukan untuk skenario ini.\n")
                continue

            dest_folder = subfolders[label]

            for i, fname in enumerate(files_in_group, 1):
                remote_path = remote_dir + fname
                local_path  = os.path.join(dest_folder, fname)

                # Skip jika sudah ada dan ukurannya sama
                try:
                    remote_size = sftp.stat(remote_path).st_size
                    if os.path.exists(local_path) and os.path.getsize(local_path) == remote_size:
                        print(f"   [{i:02d}] ⏭  SKIP (sudah ada): {fname}")
                        total_downloaded += 1
                        continue
                except Exception:
                    pass

                try:
                    sftp.get(remote_path, local_path)
                    size_kb = os.path.getsize(local_path) / 1024
                    print(f"   [{i:02d}] ✅  {fname}  ({size_kb:.1f} KB)")
                    total_downloaded += 1
                except Exception as e:
                    print(f"   [{i:02d}] ❌  GAGAL: {fname} → {e}")
                    total_failed += 1
            print()

        # --------------------------------------------------------
        # 4. Cek juga di subdirektori Lokalisasi/ jika ada
        # --------------------------------------------------------
        sub_lokalisasi = remote_dir + "Lokalisasi/"
        try:
            sub_files = sftp.listdir(sub_lokalisasi)
            sub_csvs = [f for f in sub_files if f.endswith(".csv")]
            if sub_csvs:
                print(f"🔍 Ditemukan {len(sub_csvs)} CSV tambahan di subdirektori Lokalisasi/")
                for f in sub_csvs:
                    label = classify_file(f)
                    dest_folder = subfolders.get(label, local_base)
                    remote_path = sub_lokalisasi + f
                    local_path  = os.path.join(dest_folder, f)
                    try:
                        sftp.get(remote_path, local_path)
                        size_kb = os.path.getsize(local_path) / 1024
                        print(f"   ✅  {f}  ({size_kb:.1f} KB) → {label or 'uncategorized'}")
                        total_downloaded += 1
                    except Exception as e:
                        print(f"   ❌  GAGAL: {f} → {e}")
                        total_failed += 1
                print()
        except Exception:
            pass  # Subdirektori tidak ada, lanjut

        sftp.close()

        # --------------------------------------------------------
        # 5. Ringkasan Akhir
        # --------------------------------------------------------
        print("=" * 60)
        print("  RINGKASAN DOWNLOAD")
        print("=" * 60)
        print(f"  ✅ Berhasil : {total_downloaded} file")
        print(f"  ❌ Gagal    : {total_failed} file")
        print(f"\n  📁 Lokasi penyimpanan:")
        print(f"     {local_base}/")
        for name in ["Skenario_A_DeadReckoning", "Skenario_B_Alvin", "Skenario_C_VIO_Poligon"]:
            folder = os.path.join(local_base, name)
            if os.path.exists(folder):
                count = len([x for x in os.listdir(folder) if x.endswith(".csv")])
                print(f"     ├── {name}/  ({count} file CSV)")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error koneksi SSH: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    download_all()
