import sqlite3
import pandas as pd
from datetime import datetime
import numpy as np

def handle_duplicate_username(username, existing_usernames):
    """Menangani username duplikat dengan menambahkan counter"""
    original_username = username
    counter = 1
    while username in existing_usernames:
        username = f"{original_username}_{counter}"
        counter += 1
    return username

def migrate_database(old_db_path, new_db_path):
    try:
        # Koneksi ke database lama dan baru
        old_conn = sqlite3.connect(old_db_path)
        new_conn = sqlite3.connect(new_db_path)
        cursor = new_conn.cursor()
        
        # Hapus data yang ada di database baru
        tables = [
            'main_customuser',
            'main_jenjang',
            'main_kelas',
            'main_mata_pelajaran',
            'main_jabatan',
            'Siswa_siswa',
            'Guru_guru',
            'Karyawan_karyawan',
            'main_sakit',
            'main_izin',
            'main_record_absensi',
            'main_tanggal_merah',
            'main_instalasi'
        ]
        
        # Nonaktifkan foreign key constraints sementara
        cursor.execute('PRAGMA foreign_keys=OFF')
        
        # Hapus data dari setiap tabel
        for table in tables:
            try:
                cursor.execute(f'DELETE FROM {table}')
            except sqlite3.OperationalError:
                print(f"Tabel {table} tidak ditemukan atau kosong")
        
        # Aktifkan kembali foreign key constraints
        cursor.execute('PRAGMA foreign_keys=ON')
        new_conn.commit()
        
        # 1. Migrasi data CustomUser
        df_users = pd.read_sql_query("""
            SELECT username, password, last_login, is_superuser, first_name, 
            last_name, email, is_staff, is_active, date_joined, userid 
            FROM main_customuser
        """, old_conn)
        
        # Tangani username duplikat
        existing_usernames = set()
        new_usernames = []
        
        for username in df_users['username']:
            new_username = handle_duplicate_username(username, existing_usernames)
            new_usernames.append(new_username)
            existing_usernames.add(new_username)
        
        df_users['username'] = new_usernames
        df_users.to_sql('main_customuser', new_conn, if_exists='append', index=False)
        
        # 2. Migrasi data jenjang
        df_jenjang = pd.read_sql_query("SELECT nama FROM main_jenjang", old_conn)
        df_jenjang.to_sql('main_jenjang', new_conn, if_exists='append', index=False)
        
        # 3. Migrasi data kelas
        df_kelas = pd.read_sql_query("SELECT nama FROM main_kelas", old_conn)
        df_kelas.to_sql('main_kelas', new_conn, if_exists='append', index=False)
        
        # 4. Migrasi data mata pelajaran
        df_mapel = pd.read_sql_query("SELECT nama FROM main_mata_pelajaran", old_conn)
        df_mapel.to_sql('main_mata_pelajaran', new_conn, if_exists='append', index=False)
        
        # 5. Migrasi data jabatan
        df_jabatan = pd.read_sql_query("SELECT nama FROM main_jabatan", old_conn)
        df_jabatan.to_sql('main_jabatan', new_conn, if_exists='append', index=False)
        
        # 6. Migrasi data siswa
        # Periksa struktur tabel terlebih dahulu
        cursor_old = old_conn.cursor()
        cursor_old.execute("PRAGMA table_info(Siswa_siswa)")
        columns = [column[1] for column in cursor_old.fetchall()]
        
        # Buat query berdasarkan kolom yang ada
        siswa_columns = ["s.nisn", "s.nama", "s.tanggal_lahir", "s.alamat", 
                        "s.telegram_chat_id", "s.notifikasi_telegram"]
        
        if "pin_ortu" in columns:
            siswa_columns.append("s.pin_ortu")
            
        siswa_columns.extend(["u.username as user_username", "s.jenjang_id", "s.kelas_id"])
        
        siswa_query = f"""
            SELECT {', '.join(siswa_columns)}
            FROM Siswa_siswa s
            JOIN main_customuser u ON s.user_id = u.id
        """
        
        df_siswa = pd.read_sql_query(siswa_query, old_conn)
        
        # Set nilai default untuk kolom yang tidak ada
        if "pin_ortu" not in df_siswa.columns:
            df_siswa["pin_ortu"] = None  # atau bisa diisi dengan nilai default lain
            
        # Update user_id berdasarkan username mapping
        df_siswa['user_id'] = df_siswa['user_username'].map(dict(zip(df_users['username'], range(1, len(df_users) + 1))))
        df_siswa = df_siswa.drop('user_username', axis=1)
        df_siswa.to_sql('Siswa_siswa', new_conn, if_exists='append', index=False)
        
        # 7. Migrasi data guru
        # Periksa struktur tabel terlebih dahulu
        cursor_old = old_conn.cursor()
        cursor_old.execute("PRAGMA table_info(Guru_guru)")
        columns = [column[1] for column in cursor_old.fetchall()]
        
        # Buat query berdasarkan kolom yang ada
        guru_columns = ["g.nuptk", "g.nama", "g.tanggal_lahir", "g.alamat", 
                       "g.telegram_chat_id", "g.notifikasi_telegram"]
        
        if "wali_kelas" in columns:
            guru_columns.append("g.wali_kelas")
        if "kepala_sekolah" in columns:
            guru_columns.append("g.kepala_sekolah")
            
        guru_columns.extend(["u.username as user_username", "g.jenjang_id", 
                           "g.kelas_id", "g.mata_pelajaran_id"])
        
        guru_query = f"""
            SELECT {', '.join(guru_columns)}
            FROM Guru_guru g
            JOIN main_customuser u ON g.user_id = u.id
        """
        
        df_guru = pd.read_sql_query(guru_query, old_conn)
        
        # Set nilai default untuk kolom yang tidak ada
        if "wali_kelas" not in df_guru.columns:
            df_guru["wali_kelas"] = False
        if "kepala_sekolah" not in df_guru.columns:
            df_guru["kepala_sekolah"] = False
            
        # Update user_id
        df_guru['user_id'] = df_guru['user_username'].map(dict(zip(df_users['username'], range(1, len(df_users) + 1))))
        df_guru = df_guru.drop('user_username', axis=1)
        df_guru.to_sql('Guru_guru', new_conn, if_exists='append', index=False)
        
        # 8. Migrasi data karyawan
        df_karyawan = pd.read_sql_query("""
            SELECT k.nip, k.nama, k.tanggal_lahir, k.alamat, k.telegram_chat_id, 
            k.notifikasi_telegram, u.username as user_username, k.jabatan_id 
            FROM Karyawan_karyawan k
            JOIN main_customuser u ON k.user_id = u.id
        """, old_conn)
        
        df_karyawan['user_id'] = df_karyawan['user_username'].map(dict(zip(df_users['username'], range(1, len(df_users) + 1))))
        df_karyawan = df_karyawan.drop('user_username', axis=1)
        df_karyawan.to_sql('Karyawan_karyawan', new_conn, if_exists='append', index=False)
        
        # 9. Migrasi data record_absensi
        record_query = """
            SELECT r.checktime, r.status, r.status_verifikasi, r.tipe_absensi, 
                   r.terlambat, r.mesin, u.username as user_username,
                   r.id_izin_id, r.id_sakit_id
            FROM main_record_absensi r
            JOIN main_customuser u ON r.user_id = u.id
        """
        
        try:
            df_record = pd.read_sql_query(record_query, old_conn)
            
            # Update user_id berdasarkan username mapping
            df_record['user_id'] = df_record['user_username'].map(dict(zip(df_users['username'], range(1, len(df_users) + 1))))
            df_record = df_record.drop('user_username', axis=1)
            
            # Tangani format datetime dengan lebih baik
            def clean_datetime(dt_str):
                try:
                    # Hapus microseconds jika ada
                    if '.' in str(dt_str):
                        dt_str = str(dt_str).split('.')[0]
                    return dt_str
                except:
                    return dt_str
            
            # Terapkan clean_datetime ke kolom checktime
            df_record['checktime'] = df_record['checktime'].apply(clean_datetime)
            
            # Tangani nilai NULL untuk setiap kolom secara terpisah
            for col in df_record.columns:
                if col == 'status':
                    df_record[col] = df_record[col].replace({np.nan: 'hadir', None: 'hadir'})
                elif col == 'status_verifikasi':
                    df_record[col] = df_record[col].replace({np.nan: 'menunggu', None: 'menunggu'})
                elif col == 'tipe_absensi':
                    df_record[col] = df_record[col].replace({np.nan: 'masuk', None: 'masuk'})
                elif col == 'terlambat':
                    df_record[col] = df_record[col].replace({np.nan: 0, None: 0})
                elif col == 'mesin':
                    df_record[col] = df_record[col].replace({np.nan: '', None: ''})
                elif col in ['id_izin_id', 'id_sakit_id']:
                    df_record[col] = df_record[col].replace({np.nan: None, None: None})
            
            # Pastikan tipe data sesuai
            df_record['terlambat'] = df_record['terlambat'].astype(int)
            
            # Migrasi data record_absensi
            df_record.to_sql('main_record_absensi', new_conn, if_exists='append', index=False)
            print(f"Berhasil memindahkan {len(df_record)} record absensi")
            
        except Exception as e:
            print(f"Error saat memindahkan record absensi: {str(e)}")
            print("Detail DataFrame record_absensi:")
            if 'df_record' in locals():
                print("\nSampel data checktime:")
                print(df_record['checktime'].head())
                print("\nTipe data kolom:")
                print(df_record.dtypes)
                print("\nNilai unik di kolom status:")
                print(df_record['status'].unique())
                print("\nNilai unik di kolom status_verifikasi:")
                print(df_record['status_verifikasi'].unique())
                print("\nNilai unik di kolom tipe_absensi:")
                print(df_record['tipe_absensi'].unique())

        # 10. Migrasi data izin
        izin_query = """
            SELECT i.keterangan, u.username as user_username
            FROM main_izin i
            JOIN main_customuser u ON i.user_id = u.id
        """
        
        try:
            df_izin = pd.read_sql_query(izin_query, old_conn)
            df_izin['user_id'] = df_izin['user_username'].map(dict(zip(df_users['username'], range(1, len(df_users) + 1))))
            df_izin = df_izin.drop('user_username', axis=1)
            df_izin.to_sql('main_izin', new_conn, if_exists='append', index=False)
            print(f"Berhasil memindahkan {len(df_izin)} data izin")
        except Exception as e:
            print(f"Error saat memindahkan data izin: {str(e)}")

        # 11. Migrasi data sakit
        sakit_query = """
            SELECT s.keterangan, s.surat_sakit, u.username as user_username
            FROM main_sakit s
            JOIN main_customuser u ON s.user_id = u.id
        """
        
        try:
            df_sakit = pd.read_sql_query(sakit_query, old_conn)
            df_sakit['user_id'] = df_sakit['user_username'].map(dict(zip(df_users['username'], range(1, len(df_users) + 1))))
            df_sakit = df_sakit.drop('user_username', axis=1)
            df_sakit.to_sql('main_sakit', new_conn, if_exists='append', index=False)
            print(f"Berhasil memindahkan {len(df_sakit)} data sakit")
        except Exception as e:
            print(f"Error saat memindahkan data sakit: {str(e)}")

        # Commit dan tutup koneksi
        new_conn.commit()
        old_conn.close()
        new_conn.close()
        
        print("Migrasi database berhasil!")
        return True
        
    except Exception as e:
        print(f"Terjadi kesalahan: {str(e)}")
        return False

if __name__ == "__main__":
    OLD_DB_PATH = "/Users/liarandawydia/Downloads/db.sqlite3"  # Sesuaikan dengan path database lama
    NEW_DB_PATH = "/Users/liarandawydia/MyProjects/Absensi-Update/db.sqlite3"  # Sesuaikan dengan path database baru
    
    migrate_database(OLD_DB_PATH, NEW_DB_PATH) 