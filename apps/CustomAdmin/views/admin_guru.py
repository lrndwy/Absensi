from datetime import date, datetime
import pandas as pd

from django.contrib import messages
from django.db.models import OuterRef, Subquery
from django.shortcuts import redirect, render
from django.utils import timezone
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from django.db.models.functions import Coalesce, TruncDate

from apps.CustomAdmin.functions import *

from apps.Guru.models import *
from apps.Karyawan.models import *
from apps.main.instalasi import cek_instalasi, get_context
from apps.main.models import *
from apps.main.models import CustomUser, izin, jenjang, kelas
from apps.Siswa.models import *


@cek_instalasi
@superuser_required
def admin_guru(request):
    try:
        today = timezone.localtime(timezone.now()).date()
        jenjang_filter = request.GET.get('jenjang')
        kelas_filter = request.GET.get('kelas')
        mata_pelajaran_filter = request.GET.get('mata_pelajaran')
        
        edit_data_guru = []
        edit_id = request.GET.get('id')
        if edit_id:
            for data_guru in Guru.objects.filter(id=edit_id):
                data_edit = {
                    'idguru': data_guru.id,
                    'iduser': data_guru.user.id if data_guru.user else None,
                    'username': data_guru.user.username if data_guru.user else None,
                    'email': data_guru.user.email if data_guru.user else None,
                    'nama': data_guru.nama,
                    'nuptk': data_guru.nuptk,
                    'tanggal_lahir': data_guru.tanggal_lahir,
                    'jenjang': data_guru.jenjang.nama if data_guru.jenjang else None,
                    'kelas': data_guru.kelas.nama if data_guru.kelas else None,
                    'mata_pelajaran': data_guru.mata_pelajaran if data_guru else None,
                    'alamat': data_guru.alamat if data_guru else None,
                    'userid': data_guru.user.userid if data_guru.user else None,
                    'telegram_chat_id': data_guru.telegram_chat_id if data_guru else None,
                    'is_wali_kelas': data_guru.wali_kelas if data_guru else False,
                    'is_kepsek': data_guru.kepala_sekolah if data_guru else False,
                }
                edit_data_guru.append(data_edit)
                
        guru_filter = Guru.objects.all()
        if jenjang_filter:
            guru_filter = guru_filter.filter(jenjang__nama=jenjang_filter)
        if kelas_filter:
            guru_filter = guru_filter.filter(kelas__nama=kelas_filter)
        if mata_pelajaran_filter:
            guru_filter = guru_filter.filter(mata_pelajaran__nama=mata_pelajaran_filter)
            
        # IF PRINT
        print_id = request.GET.get('print')
        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        
        if print_id and start_date and end_date:
            try:
                guru = Guru.objects.get(id=print_id)
                
                # Konversi string tanggal ke datetime
                tanggal_awal = timezone.datetime.strptime(start_date, '%Y-%m-%d')
                tanggal_akhir = timezone.datetime.strptime(end_date, '%Y-%m-%d')
                
                # Buat list semua hari dalam rentang tanggal
                jumlah_hari = (tanggal_akhir - tanggal_awal).days + 1
                semua_hari = []
                
                # Ambil jam masuk dari instalasi
                instalasi = Instalasi.objects.first()
                jam_masuk = instalasi.jam_masuk_guru if instalasi else None

                for i in range(jumlah_hari):
                    tanggal = tanggal_awal + timezone.timedelta(days=i)
                    
                    # Cek apakah tanggal tersebut adalah tanggal merah
                    tanggal_merah_obj = tanggal_merah.objects.filter(
                        tanggal=tanggal.date(),
                        kategori__in=['guru', 'semua']
                    ).first()
                    
                    if tanggal_merah_obj:
                        # Jika tanggal merah, set status dan keterangan sesuai tanggal merah
                        hari_data = {
                            'tanggal': f"{tanggal.strftime('%A')}, {tanggal.strftime('%d %B %Y')}",
                            'jam_masuk': '-',
                            'mesin_masuk': '-',
                            'jam_pulang': '-',
                            'mesin_pulang': '-',
                            'status': f"Tanggal Merah: {tanggal_merah_obj.nama_acara}",
                            'keterangan': tanggal_merah_obj.keterangan,
                            'keterlambatan': None,
                            'is_terlambat': False
                        }
                    else:
                        # Jika bukan tanggal merah, proses seperti biasa
                        absensi_masuk = record_absensi.objects.filter(
                            user=guru.user,
                            checktime__date=tanggal.date(),
                            tipe_absensi='masuk',
                            status_verifikasi='diterima'
                        ).first()
                        
                        absensi_pulang = record_absensi.objects.filter(
                            user=guru.user,
                            checktime__date=tanggal.date(),
                            tipe_absensi='pulang',
                            status_verifikasi='diterima'
                        ).first()
                        
                        # Cek ketidakhadiran (sakit/izin)
                        ketidakhadiran = record_absensi.objects.filter(
                            user=guru.user,
                            checktime__date=tanggal.date(),
                            status__in=['sakit', 'izin'],
                            status_verifikasi='diterima'
                        ).first()

                        # Hitung keterlambatan berdasarkan jam masuk guru dari instalasi
                        keterlambatan = absensi_masuk.terlambat if absensi_masuk else None

                        # Hitung durasi kerja jika ada absensi masuk dan pulang
                        durasi_kerja = None
                        if absensi_masuk and absensi_pulang:
                            durasi = absensi_pulang.checktime - absensi_masuk.checktime
                            durasi_kerja = durasi.total_seconds() / 3600  # Konversi ke jam

                        hari_data = {
                            'tanggal': f"{tanggal.strftime('%A')}, {tanggal.strftime('%d %B %Y')}",
                            'jam_masuk': timezone.localtime(absensi_masuk.checktime).strftime('%H:%M') if absensi_masuk else '-',
                            'mesin_masuk': absensi_masuk.mesin if absensi_masuk else '-',
                            'jam_pulang': timezone.localtime(absensi_pulang.checktime).strftime('%H:%M') if absensi_pulang else '-',
                            'mesin_pulang': absensi_pulang.mesin if absensi_pulang else '-',
                            'status': ketidakhadiran.status if ketidakhadiran else ('Hadir' if absensi_masuk else 'Tidak Hadir'),
                            'keterlambatan': keterlambatan,
                            'durasi_kerja': f"{durasi_kerja:.2f} jam" if durasi_kerja else '-',
                            'is_terlambat': keterlambatan > 0 if keterlambatan is not None else False,
                            'keterangan': ketidakhadiran.id_sakit.keterangan if ketidakhadiran and ketidakhadiran.status == 'sakit' and ketidakhadiran.id_sakit
                                        else ketidakhadiran.id_izin.keterangan if ketidakhadiran and ketidakhadiran.status == 'izin' and ketidakhadiran.id_izin
                                        else f"Terlambat {keterlambatan} menit" if keterlambatan and keterlambatan > 0
                                        else '-' if not absensi_masuk
                                        else 'Tepat Waktu'
                        }
                    
                    semua_hari.append(hari_data)
                
                # Hitung total keseluruhan
                total_hari = len(semua_hari)
                total_hadir = sum(1 for hari in semua_hari if hari['status'] == 'Hadir')
                total_sakit = sum(1 for hari in semua_hari if hari['status'] == 'sakit')
                total_izin = sum(1 for hari in semua_hari if hari['status'] == 'izin')
                total_tidak_hadir = sum(1 for hari in semua_hari if hari['status'] == 'Tidak Hadir')
                total_tanggal_merah = sum(1 for hari in semua_hari if 'Tanggal Merah' in hari['status'])
                total_weekend = sum(1 for hari in semua_hari if 'Saturday' in hari['tanggal'] or 'Sunday' in hari['tanggal'])

                # Hitung total tepat waktu dan terlambat
                total_tepat_waktu = sum(1 for hari in semua_hari 
                    if hari['status'] == 'Hadir' and not hari['keterlambatan'])
                total_terlambat = sum(1 for hari in semua_hari 
                    if hari['status'] == 'Hadir' and hari['keterlambatan'])
                total_menit_terlambat = sum(
                    hari['keterlambatan'] 
                    for hari in semua_hari 
                    if hari['status'] == 'Hadir' and hari['is_terlambat']
                )

                # Hitung untuk hari kerja (tidak termasuk tanggal merah dan weekend)
                hari_kerja = [hari for hari in semua_hari 
                            if 'Tanggal Merah' not in hari['status'] 
                            and not ('Saturday' in hari['tanggal'] or 'Sunday' in hari['tanggal'])]
                
                total_hari_kerja = len(hari_kerja)
                total_hadir_kerja = sum(1 for hari in hari_kerja if hari['status'] == 'Hadir')
                total_sakit_kerja = sum(1 for hari in hari_kerja if hari['status'] == 'sakit')
                total_izin_kerja = sum(1 for hari in hari_kerja if hari['status'] == 'izin')
                total_tidak_hadir_kerja = sum(1 for hari in hari_kerja if hari['status'] == 'Tidak Hadir')
                
                total_tepat_waktu_kerja = sum(1 for hari in hari_kerja 
                    if hari['status'] == 'Hadir' and not hari['keterlambatan'])
                total_terlambat_kerja = sum(1 for hari in hari_kerja 
                    if hari['status'] == 'Hadir' and hari['keterlambatan'])
                total_menit_terlambat_kerja = sum(
                    hari['keterlambatan']
                    for hari in hari_kerja 
                    if hari['status'] == 'Hadir' and hari['is_terlambat']
                )

                context = {
                    'guru': guru,
                    'periode': f"{tanggal_awal.strftime('%d %B %Y')} - {tanggal_akhir.strftime('%d %B %Y')}",
                    'hari_records': semua_hari,
                    # Data sekolah
                    'nama_sekolah': instalasi.nama_sekolah if instalasi else '',
                    'logo_sekolah': instalasi.logo if instalasi else None,
                    'deskripsi_sekolah': instalasi.deskripsi if instalasi else '',
                    'alamat_sekolah': instalasi.alamat if instalasi else '',
                    # Total keseluruhan
                    'total_hari': total_hari,
                    'total_hadir': total_hadir,
                    'total_sakit': total_sakit,
                    'total_izin': total_izin,
                    'total_tidak_hadir': total_tidak_hadir,
                    'total_tanggal_merah': total_tanggal_merah,
                    'total_weekend': total_weekend,
                    'total_tepat_waktu': total_tepat_waktu,
                    'total_terlambat': total_terlambat,
                    'total_menit_terlambat': total_menit_terlambat,
                    # Total hari kerja
                    'total_hari_kerja': total_hari_kerja,
                    'total_hadir_kerja': total_hadir_kerja,
                    'total_sakit_kerja': total_sakit_kerja,
                    'total_izin_kerja': total_izin_kerja,
                    'total_tidak_hadir_kerja': total_tidak_hadir_kerja,
                    'total_tepat_waktu_kerja': total_tepat_waktu_kerja,
                    'total_terlambat_kerja': total_terlambat_kerja,
                    'total_menit_terlambat_kerja': total_menit_terlambat_kerja,
                    'tanggal_cetak': timezone.localtime(timezone.now()).strftime('%d-%m-%Y %H:%M:%S'),
                    'API_LINK': reverse('api_guru') + '?jenjang=' + request.GET.get('jenjang', '') + 
                                '&kelas=' + request.GET.get('kelas', '') + 
                                '&mata_pelajaran=' + request.GET.get('mata_pelajaran', ''),
                }
                
                return render(request, 'CustomAdmin/print_absensi_guru.html', context)
                
            except Guru.DoesNotExist:
                messages.error(request, 'Guru tidak ditemukan')
                return redirect('admin_guru')
            except ValueError:
                messages.error(request, 'Format tanggal tidak valid')
                return redirect('admin_guru')
            except Exception as e:
                messages.error(request, f'Gagal mencetak record: {str(e)}')
                return redirect('admin_guru')
        if request.method == 'POST':
            action =  request.POST.get('action')
            if action == 'tambah':
                username = request.POST.get('username')
                email = request.POST.get('email')
                password = request.POST.get('password')
                userid = request.POST.get('userid')
                
                user = CustomUser.objects.create_user(username=username, email=email, password=password, userid=userid, is_staff=True)
                
                nama = request.POST.get('nama')
                nuptk = request.POST.get('nuptk')
                tanggal_lahir = request.POST.get('tanggal_lahir')
                jenjang_selected = request.POST.get('jenjang')
                kelas_selected = request.POST.get('kelas')
                mata_pelajaran_selected = request.POST.get('mata_pelajaran')
                alamat = request.POST.get('alamat')
                telegram_chat_id = request.POST.get('chatid')
                walas = request.POST.get('is_wali_kelas')
                if walas:
                    wali_kelas = True
                else:
                    wali_kelas = False
                    
                kepsek = request.POST.get('is_kepsek')
                if kepsek:
                    kepala_sekolah = True
                else:
                    kepala_sekolah = False
                guru = Guru.objects.create(
                    user=user,
                    nama=nama,
                    nuptk=nuptk,
                    tanggal_lahir=tanggal_lahir,
                    jenjang_id=jenjang_selected,
                    kelas_id=kelas_selected,
                    mata_pelajaran_id=mata_pelajaran_selected,
                    alamat=alamat,
                    telegram_chat_id=telegram_chat_id,
                    wali_kelas=wali_kelas,
                    kepala_sekolah=kepala_sekolah
                )
                messages.success(request, f'Data guru {nama} berhasil ditambahkan.')
                
            if action == 'edit':
                id_guru = request.POST.get('id')
                id_user = request.POST.get('iduser')
                userid = request.POST.get('userid')
                username = request.POST.get('username')
                nama = request.POST.get('nama')
                email = request.POST.get('email')
                nuptk = request.POST.get('nuptk')
                tanggal_lahir = request.POST.get('tanggal_lahir')
                jenjang_selected = request.POST.get('jenjang')
                kelas_selected = request.POST.get('kelas')
                mata_pelajaran_selected = request.POST.get('mapel')
                alamat = request.POST.get('alamat')
                password = request.POST.get('new_password')
                telegram_chat_id = request.POST.get('chatid')
                walas = request.POST.get('is_wali_kelas')
                if walas:
                    wali_kelas = True
                else:
                    wali_kelas = False
                kepsek = request.POST.get('is_kepsek')
                if kepsek:
                    kepala_sekolah = True
                else:
                    kepala_sekolah = False                
                user = CustomUser.objects.get(id=id_user)
                user.username = username
                user.email = email
                user.userid = userid
                if password not in (None, ''):
                    user.set_password(password)
                user.save()
                
                guru = Guru.objects.get(id=id_guru)
                
                
                if mata_pelajaran_selected not in ('None', '', 'Pilih Mata Pelajaran', None, 0, '0'):
                    guru.mata_pelajaran = mata_pelajaran.objects.get(nama=mata_pelajaran_selected)
                else:
                    pass
                if kelas_selected not in ('None', '', 'Pilih Kelas', None, 0, '0'):
                    guru.kelas = kelas.objects.get(nama=kelas_selected)
                else:
                    pass
                if jenjang_selected not in ('None', '', 'Pilih Jenjang', None, 0, '0'):
                    guru.jenjang = jenjang.objects.get(nama=jenjang_selected)
                else:
                    pass
                
                guru.nama = nama
                guru.nuptk = nuptk
                guru.tanggal_lahir = tanggal_lahir
                
                guru.alamat = alamat
                guru.telegram_chat_id = telegram_chat_id
                guru.wali_kelas = wali_kelas
                guru.kepala_sekolah = kepala_sekolah
                guru.save()
                
                messages.success(request, f'Data guru {nama} berhasil diperbarui.')
                return redirect('admin_guru')
            
            if action == 'hapus':
                selected_ids = request.POST.getlist('selectedIds')
                # Menangani kasus di mana selectedIds berisi string dengan beberapa ID
                all_ids = []
                for id_string in selected_ids:
                    all_ids.extend(id_string.split(','))
                
                guru_list = Guru.objects.filter(id__in=all_ids)
                deleted_count = 0
                for guru in guru_list:
                    user = guru.user
                    # Menghapus semua record_absensi terkait
                    record_absensi.objects.filter(user=user).delete()
                    # menghapus semua izin terkait
                    izin.objects.filter(user=user).delete()
                    # menghapus semua sakit terkait
                    sakit.objects.filter(user=user).delete()
                    # menghapus guru
                    guru.delete()
                    # menghapus user
                    user.delete()
                    deleted_count += 1
                    
                messages.success(request, f'{deleted_count} data guru berhasil dihapus.')
                return redirect('admin_guru')
            
            if action == 'import':
                try:
                    file_type = request.POST.get('file_type')
                    file = request.FILES.get('file_input')
                    
                    if file_type == 'csv':
                        df = pd.read_csv(file)
                    elif file_type == 'excel':
                        df = pd.read_excel(file)
                    else:
                        messages.error(request, 'Tipe file tidak didukung.')
                        return redirect('admin_guru')
                    
                    # Periksa kolom yang diperlukan
                    required_columns = ['username', 'email', 'password', 'userid', 'nuptk', 'nama', 
                                      'tanggal_lahir', 'jenjang', 'kelas', 'mata_pelajaran', 'alamat', 'telegram_chat_id',
                                      'wali_kelas', 'kepala_sekolah']
                    
                    missing_columns = [col for col in required_columns if col not in df.columns]
                    if missing_columns:
                        messages.error(request, f'Kolom yang diperlukan tidak ditemukan: {", ".join(missing_columns)}')
                        return redirect('admin_guru')
                    
                    success_count = 0
                    error_count = 0
                    error_details = []
                    
                    # Daftar format tanggal yang umum digunakan
                    date_formats = [
                        '%Y-%m-%d %H:%M:%S',    # Format datetime dari Excel: 2024-12-16 00:00:00
                        '%Y-%m-%d',             # 2024-03-21
                        '%d-%m-%Y',             # 21-03-2024
                        '%d/%m/%Y',             # 21/03/2024
                        '%Y/%m/%d',             # 2024/03/21
                        '%d-%B-%Y',             # 21-March-2024
                        '%d %B %Y',             # 21 March 2024
                        '%d.%m.%Y',             # 21.03.2024
                        '%m/%d/%Y',             # 03/21/2024
                        '%B %d, %Y',            # March 21, 2024
                        '%d-%b-%Y',             # 21-Mar-2024
                        '%Y%m%d',               # 20240321
                    ]
                    
                    for index, row in df.iterrows():
                        try:
                            # Konversi tanggal lahir
                            tanggal_str = str(row['tanggal_lahir']).strip()
                            tanggal_lahir = None
                            
                            if pd.isna(tanggal_str) or tanggal_str == '' or tanggal_str.lower() == 'nan':
                                raise ValueError("Tanggal lahir tidak boleh kosong")
                            
                            # Jika input adalah timestamp/datetime dari pandas
                            if isinstance(row['tanggal_lahir'], (pd.Timestamp, datetime)):
                                tanggal_lahir = row['tanggal_lahir'].date()
                            else:
                                # Coba setiap format tanggal
                                for date_format in date_formats:
                                    try:
                                        parsed_date = datetime.strptime(tanggal_str, date_format)
                                        tanggal_lahir = parsed_date.date()  # Ambil hanya tanggalnya
                                        break
                                    except ValueError:
                                        continue
                            
                            if tanggal_lahir is None:
                                raise ValueError(f"Format tanggal '{tanggal_str}' tidak valid")
                            
                            # Validasi data lainnya
                            if not row['username'] or pd.isna(row['username']):
                                raise ValueError("Username tidak boleh kosong")
                            if not row['email'] or pd.isna(row['email']):
                                raise ValueError("Email tidak boleh kosong")
                            if not row['password'] or pd.isna(row['password']):
                                raise ValueError("Password tidak boleh kosong")
                            
                            # Proses data seperti biasa
                            username = str(row['username']).strip()
                            counter = 1
                            original_username = username
                            while CustomUser.objects.filter(username=username).exists():
                                username = f"{original_username}_{counter}"
                                counter += 1
                            
                            user = CustomUser.objects.create_user(
                                username=username,
                                email=str(row['email']).strip(),
                                password=str(row['password']).strip(),
                                userid=str(row['userid']).strip(),
                                is_staff=True
                            )
                            
                            jenjang_obj, _ = jenjang.objects.get_or_create(nama=str(row['jenjang']).strip())
                            kelas_obj, _ = kelas.objects.get_or_create(nama=str(row['kelas']).strip())
                            mata_pelajaran_obj, _ = mata_pelajaran.objects.get_or_create(nama=str(row['mata_pelajaran']).strip())
                            
                            # Konversi nilai wali_kelas dan kepala_sekolah ke boolean
                            wali_kelas = str(row['wali_kelas']).strip().lower() in ['true', '1', 'yes', 'ya']
                            kepala_sekolah = str(row['kepala_sekolah']).strip().lower() in ['true', '1', 'yes', 'ya']
                            
                            Guru.objects.create(
                                user=user,
                                nuptk=str(row['nuptk']).strip(),
                                nama=str(row['nama']).strip(),
                                tanggal_lahir=tanggal_lahir,
                                jenjang=jenjang_obj,
                                kelas=kelas_obj,
                                mata_pelajaran=mata_pelajaran_obj,
                                alamat=str(row['alamat']).strip(),
                                telegram_chat_id=str(row['telegram_chat_id']).strip(),
                                wali_kelas=wali_kelas,
                                kepala_sekolah=kepala_sekolah
                            )
                            success_count += 1
                        except Exception as e:
                            error_count += 1
                            error_message = f'Baris {index + 2}: {str(e)}'
                            error_details.append(error_message)
                            print(error_message)
                            
                            # Jika user sudah terlanjur dibuat tapi ada error, hapus user tersebut
                            if 'user' in locals():
                                user.delete()
                    
                    if success_count > 0:
                        messages.success(request, f'{success_count} data guru berhasil diimpor.')
                    if error_count > 0:
                        messages.warning(request, f'{error_count} data guru gagal diimpor.')
                        messages.warning(request, 'Detail error:')
                        for error in error_details[:5]:  # Tampilkan 5 error pertama
                            messages.warning(request, error)
                        if len(error_details) > 5:
                            messages.warning(request, f'...dan {len(error_details) - 5} error lainnya')
                    
                    return redirect('admin_guru')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                    return redirect('admin_guru')
            
        # Subquery untuk mendapatkan status record_absensi terbaru untuk setiap guru hari ini
        latest_absensi = record_absensi.objects.filter(
            user__guru=OuterRef('pk'),
            checktime__date=today
        ).order_by('-checktime').values('status', 'status_verifikasi')[:1]

        # Query utama
        guru = guru_filter.select_related('user', 'jenjang', 'kelas', 'mata_pelajaran').annotate(
            today_status=Subquery(latest_absensi.values('status')),
            today_status_verifikasi=Subquery(latest_absensi.values('status_verifikasi')),
            today_checktime=Subquery(latest_absensi.values('checktime')),
            today_tipe_absensi=Subquery(latest_absensi.values('tipe_absensi'))
        ).values_list(
            'id',
            'user__userid',
            'nama',
            'jenjang__nama',
            'kelas__nama',
            'mata_pelajaran__nama',
            'alamat',
            'user__username',
            'today_status',
            'today_status_verifikasi',
            'today_checktime',
            'today_tipe_absensi',
            'wali_kelas'
        )

        # Memproses queryset untuk menampilkan status yang lebih detail
        table_data = []
        for guru_data in guru:
            status = guru_data[-4]  # today_status
            status_verifikasi = guru_data[-3]  # today_status_verifikasi
            checktime = timezone.localtime(guru_data[-2]) if guru_data[-2] else None  # today_checktime
            tipe_absensi = guru_data[-1]  # today_tipe_absensi
            
            
            if status_verifikasi == 'menunggu':
                display_status = "Belum Diverifikasi"
            elif status_verifikasi == 'ditolak':
                display_status = "Ditolak"
            elif tipe_absensi == 'pulang':
                display_status = "Sudah Pulang"
            elif status == 'hadir' and tipe_absensi == 'masuk':
                latest_record = record_absensi.objects.filter(
                    user__guru=guru_data[0],  # ID guru
                    checktime__date=today,
                    tipe_absensi='masuk',
                    status_verifikasi='diterima'
                ).first()
                
                if latest_record and latest_record.terlambat > 0:
                    menit_terlambat = latest_record.terlambat
                    if menit_terlambat < 60:
                        display_status = f"Hadir, terlambat {menit_terlambat} menit"
                    else:
                        jam_terlambat = menit_terlambat // 60
                        sisa_menit = menit_terlambat % 60
                        display_status = f"Hadir, terlambat {jam_terlambat} jam {sisa_menit} menit"
                else:
                    display_status = "Hadir"
            else:
                display_status = status if status else "Belum Hadir"
            
            
            
            table_data.append(list(guru_data[:-4]) + [display_status])
            
        context = get_context()
        context.update({
            'table_columns': ['ID', 'UserID', 'Nama', 'Jenjang', 'Kelas', 'Mata Pelajaran', 'Alamat', 'Username', 'Status', 'Wali Kelas'],
            'table_data': table_data,
            
            'jenjang_list': jenjang.objects.all(),
            'kelas_list': kelas.objects.all(),
            'mata_pelajaran_list': mata_pelajaran.objects.all(),
            
            'edit_data_guru': edit_data_guru,
            
            'guru': True,
            
            'total_data_table': guru_filter.count(),
            'API_LINK': reverse('api_guru') + '?jenjang=' + request.GET.get('jenjang', '') + 
                        '&kelas=' + request.GET.get('kelas', '') + 
                        '&mata_pelajaran=' + request.GET.get('mata_pelajaran', ''),
            'print': True,
        })
        return render(request, 'CustomAdmin/admin_guru.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_guru')


@cek_instalasi
@superuser_required
@require_http_methods(['GET'])
def api_guru(request):
    try:
        today = timezone.localtime(timezone.now()).date()
        
        # Subquery untuk status absensi
        latest_absensi = record_absensi.objects.filter(
            user__guru=OuterRef('pk'),
            checktime__date=today
        ).order_by('-checktime').values('status', 'status_verifikasi', 'tipe_absensi', 'checktime')[:1]
        
        # Base queryset
        guru_list = Guru.objects.select_related('user', 'jenjang', 'kelas', 'mata_pelajaran').annotate(
            today_status=Subquery(latest_absensi.values('status')),
            today_status_verifikasi=Subquery(latest_absensi.values('status_verifikasi')),
            today_tipe_absensi=Subquery(latest_absensi.values('tipe_absensi')),
            today_checktime=Subquery(latest_absensi.values('checktime'))
        )
        
        # Terapkan filter berdasarkan parameter URL
        jenjang_filter = request.GET.get('jenjang')
        kelas_filter = request.GET.get('amp;kelas')
        mata_pelajaran_filter = request.GET.get('amp;mata_pelajaran')
        
        if jenjang_filter:
            guru_list = guru_list.filter(jenjang__nama=jenjang_filter)
        if kelas_filter:
            guru_list = guru_list.filter(kelas__nama=kelas_filter)
        if mata_pelajaran_filter:
            guru_list = guru_list.filter(mata_pelajaran__nama=mata_pelajaran_filter)
        
        data = []
        for guru in guru_list:
            status = guru.today_status
            status_verifikasi = guru.today_status_verifikasi
            tipe_absensi = guru.today_tipe_absensi
            
            # Logic untuk display status
            if status_verifikasi == 'menunggu':
                display_status = "Belum Diverifikasi"
            elif status_verifikasi == 'ditolak':
                display_status = "Ditolak"
            elif tipe_absensi == 'pulang':
                display_status = "Sudah Pulang"
            elif status == 'hadir' and tipe_absensi == 'masuk':
                absensi = record_absensi.objects.filter(
                    user__guru__id=guru.id,
                    checktime__date=today,
                    tipe_absensi='masuk'
                ).first()
                
                if absensi and absensi.terlambat > 0:
                    if absensi.terlambat < 60:
                        display_status = f"Hadir, terlambat {absensi.terlambat} menit"
                    else:
                        jam_terlambat = int(absensi.terlambat // 60)
                        sisa_menit = int(absensi.terlambat % 60)
                        display_status = f"Hadir, terlambat {jam_terlambat} jam {sisa_menit} menit"
                else:
                    display_status = "Hadir"
            else:
                display_status = status if status else "Belum Hadir"
            
            data.append({
                'id': guru.id,
                'userid': guru.user.userid,
                'nama': guru.nama,
                'jenjang': guru.jenjang.nama if guru.jenjang else '-',
                'kelas': guru.kelas.nama if guru.kelas else '-',
                'mata_pelajaran': guru.mata_pelajaran.nama if guru.mata_pelajaran else '-',
                'alamat': guru.alamat or '-',
                'username': guru.user.username,
                'status': display_status,
                'wali_kelas': 'Ya' if guru.wali_kelas else 'Tidak'
            })
        
        return JsonResponse({'guru': data}, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


