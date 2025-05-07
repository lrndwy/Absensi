import os
import sys
import django
import pandas as pd
from django.db.models import Count
from django.db.models.functions import ExtractYear, ExtractMonth, ExtractDay
from django.db.models import Q

# Tambahkan path proyek ke PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Konfigurasi Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# Import model setelah konfigurasi Django
from apps.main.models import record_absensi, CustomUser
from apps.Siswa.models import Siswa
from apps.Guru.models import Guru 
from apps.Karyawan.models import Karyawan

def generate_attendance_report():
    # Fungsi helper untuk mendapatkan data per tipe user
    def get_attendance_data(user_type_model, user_type_name):
        print(f"\nMemproses data {user_type_name}...")
        
        # Dapatkan semua user ID untuk tipe tersebut
        user_ids = user_type_model.objects.values_list('user_id', flat=True)
        print(f"Jumlah {user_type_name}: {len(user_ids)}")
        
        # Query untuk mendapatkan data absensi
        attendance_data = (
            record_absensi.objects.filter(
                user_id__in=user_ids,
                status='hadir',
                status_verifikasi='diterima'  # Tambahan filter untuk memastikan data valid
            ).annotate(
                tahun=ExtractYear('checktime'),
                bulan=ExtractMonth('checktime'),
                tanggal=ExtractDay('checktime')
            ).values(
                'tahun', 'bulan', 'tanggal', 'tipe_absensi'
            ).annotate(
                jumlah=Count('id')
            ).order_by('tahun', 'bulan', 'tanggal')
        )
        
        print(f"Jumlah record absensi: {attendance_data.count()}")
        
        # Konversi ke DataFrame
        df_records = pd.DataFrame(list(attendance_data))
        
        if df_records.empty:
            print(f"Tidak ada data absensi untuk {user_type_name}")
            return pd.DataFrame(columns=['Tahun', 'Bulan', 'Tanggal', 'Jumlah Log Masuk', 'Jumlah Log Keluar'])
        
        print("Data sebelum pivot:")
        print(df_records.head())
        
        # Pivot data untuk memisahkan masuk dan pulang
        df_pivot = df_records.pivot_table(
            index=['tahun', 'bulan', 'tanggal'],
            columns='tipe_absensi',
            values='jumlah',
            fill_value=0,
            aggfunc='sum'  # Tambahan untuk memastikan agregasi yang benar
        ).reset_index()
        
        # Rename kolom
        df_pivot.columns.name = None
        
        # Pastikan kolom masuk dan pulang ada
        if 'masuk' not in df_pivot.columns:
            df_pivot['masuk'] = 0
        if 'pulang' not in df_pivot.columns:
            df_pivot['pulang'] = 0
            
        df_pivot = df_pivot.rename(columns={
            'tahun': 'Tahun',
            'bulan': 'Bulan',
            'tanggal': 'Tanggal',
            'masuk': 'Jumlah Log Masuk',
            'pulang': 'Jumlah Log Keluar'
        })
        
        print("\nData setelah pivot:")
        print(df_pivot.head())
        
        return df_pivot[['Tahun', 'Bulan', 'Tanggal', 'Jumlah Log Masuk', 'Jumlah Log Keluar']]

    # Ambil data untuk setiap tipe user
    df_siswa = get_attendance_data(Siswa, 'Siswa')
    df_guru = get_attendance_data(Guru, 'Guru')
    df_karyawan = get_attendance_data(Karyawan, 'Karyawan')

    # Buat Excel writer
    with pd.ExcelWriter('laporan_absensi.xlsx', engine='xlsxwriter') as writer:
        # Tulis setiap DataFrame ke sheet yang berbeda
        df_siswa.to_excel(writer, sheet_name='Siswa', index=False)
        df_guru.to_excel(writer, sheet_name='Guru', index=False)
        df_karyawan.to_excel(writer, sheet_name='Karyawan', index=False)
        
        # Dapatkan workbook dan worksheet objects
        workbook = writer.book
        
        # Format untuk header
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'bg_color': '#D3D3D3'
        })
        
        # Format untuk angka
        number_format = workbook.add_format({
            'align': 'center',
            'num_format': '0'
        })
        
        # Aplikasikan format untuk setiap sheet
        for sheet_name in ['Siswa', 'Guru', 'Karyawan']:
            worksheet = writer.sheets[sheet_name]
            
            # Format header
            for col_num, value in enumerate(df_siswa.columns.values):
                worksheet.write(0, col_num, value, header_format)
                
            # Format kolom
            worksheet.set_column('A:C', 12)  # Tahun, Bulan, Tanggal
            worksheet.set_column('D:E', 15, number_format)  # Jumlah Log

def debug_query(user_type_model, user_type_name):
    user_ids = user_type_model.objects.values_list('user_id', flat=True)
    print(f"\nDebug {user_type_name}:")
    print(f"User IDs: {list(user_ids)}")
    
    records = record_absensi.objects.filter(
        user_id__in=user_ids,
        status='hadir',
        status_verifikasi='diterima'
    )
    print(f"Total records: {records.count()}")
    print("Sample records:")
    for record in records[:5]:
        print(f"ID: {record.id}, User: {record.user}, Time: {record.checktime}, Type: {record.tipe_absensi}")

def check_data():
    print("\nPengecekan Data:")
    print(f"Total Siswa: {Siswa.objects.count()}")
    print(f"Total Guru: {Guru.objects.count()}")
    print(f"Total Karyawan: {Karyawan.objects.count()}")
    print(f"Total Record Absensi: {record_absensi.objects.count()}")
    print("\nSampel Record Absensi:")
    for record in record_absensi.objects.all()[:5]:
        print(f"User: {record.user}, Status: {record.status}, Tipe: {record.tipe_absensi}, Waktu: {record.checktime}")

if __name__ == "__main__":
    try:
        check_data()
        generate_attendance_report()
    except Exception as e:
        print(f"\nTerjadi kesalahan: {str(e)}")