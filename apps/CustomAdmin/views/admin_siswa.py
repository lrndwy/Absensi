from datetime import date, datetime
import pandas as pd

from django.contrib import messages
from django.db.models import OuterRef, Subquery
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.CustomAdmin.functions import *

from apps.Guru.models import *
from apps.Karyawan.models import *
from apps.main.instalasi import cek_instalasi, get_context
from apps.main.models import *
from apps.main.models import CustomUser, izin, jenjang, kelas
from apps.Siswa.models import *


@cek_instalasi
@superuser_required
def admin_siswa(request):
    try:
        today = timezone.localtime(timezone.now()).date()
        jenjang_filter = request.GET.get('jenjang')
        kelas_filter = request.GET.get('kelas')
        instalasi = Instalasi.objects.first()

        edit_data_siswa = []
        edit_id = request.GET.get('id')
        if edit_id:
            for data_siswa in Siswa.objects.filter(id=edit_id):
                data_edit = {
                    'id': data_siswa.id,
                    'iduser': data_siswa.user.id if data_siswa.user else None,
                    'username': data_siswa.user.username if data_siswa.user else None,
                    'email': data_siswa.user.email if data_siswa.user else None,
                    'nama': data_siswa.nama,
                    'nisn': data_siswa.nisn,
                    'tanggal_lahir': data_siswa.tanggal_lahir.strftime('%Y-%m-%d'),
                    'jenjang': data_siswa.jenjang.nama if data_siswa.jenjang else None,
                    'kelas': data_siswa.kelas.nama if data_siswa.kelas else None,
                    'alamat': data_siswa.alamat if data_siswa else None,
                    'chatid': data_siswa.telegram_chat_id if data_siswa else None,
                    'userid': data_siswa.user.userid if data_siswa.user else None
                }
                edit_data_siswa.append(data_edit)
                
        # Filter siswa berdasarkan jenjang dan kelas
        siswa_filter = Siswa.objects.all()
        if jenjang_filter:
            siswa_filter = siswa_filter.filter(jenjang__nama=jenjang_filter)
        if kelas_filter:
            siswa_filter = siswa_filter.filter(kelas__nama=kelas_filter)
            
        # IF PRINT
        print_id = request.GET.get('print')
        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        
        if print_id and start_date and end_date:
            try:
                siswa = Siswa.objects.get(id=print_id)
                
                # Konversi string tanggal ke datetime
                tanggal_awal = timezone.datetime.strptime(start_date, '%Y-%m-%d')
                tanggal_akhir = timezone.datetime.strptime(end_date, '%Y-%m-%d')
                
                # Buat list semua hari dalam rentang tanggal
                jumlah_hari = (tanggal_akhir - tanggal_awal).days + 1
                semua_hari = []
                
                for i in range(jumlah_hari):
                    tanggal = tanggal_awal + timezone.timedelta(days=i)
                    
                    # Cek apakah tanggal tersebut adalah tanggal merah
                    tanggal_merah_obj = tanggal_merah.objects.filter(
                        tanggal=tanggal.date(),
                        kategori__in=['siswa', 'semua']
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
                            user=siswa.user,
                            checktime__date=tanggal.date(),
                            tipe_absensi='masuk',
                            status_verifikasi='diterima'
                        ).first()
                        
                        absensi_pulang = record_absensi.objects.filter(
                            user=siswa.user,
                            checktime__date=tanggal.date(),
                            tipe_absensi='pulang',
                            status_verifikasi='diterima'
                        ).first()
                        
                        # Cek ketidakhadiran (sakit/izin)
                        ketidakhadiran = record_absensi.objects.filter(
                            user=siswa.user,
                            checktime__date=tanggal.date(),
                            status__in=['sakit', 'izin'],
                            status_verifikasi='diterima'
                        ).first()

                        # Hitung keterlambatan berdasarkan jam masuk siswa dari instalasi
                        keterlambatan = None
                        if absensi_masuk:
                            keterlambatan = absensi_masuk.terlambat  # Menggunakan field terlambat langsung dari model

                        hari_data = {
                            'tanggal': f"{tanggal.strftime('%A')}, {tanggal.strftime('%d %B %Y')}",
                            'jam_masuk': timezone.localtime(absensi_masuk.checktime).strftime('%H:%M') if absensi_masuk else '-',
                            'mesin_masuk': absensi_masuk.mesin if absensi_masuk else '-',
                            'jam_pulang': timezone.localtime(absensi_pulang.checktime).strftime('%H:%M') if absensi_pulang else '-',
                            'mesin_pulang': absensi_pulang.mesin if absensi_pulang else '-',
                            'status': ketidakhadiran.status if ketidakhadiran else ('Hadir' if absensi_masuk else 'Tidak Hadir'),
                            'keterlambatan': keterlambatan,
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
                    'siswa': siswa,
                    'periode': f"{tanggal_awal.strftime('%d %B %Y')} - {tanggal_akhir.strftime('%d %B %Y')}",
                    'hari_records': semua_hari,
                    'jam_masuk_siswa': instalasi.jam_masuk_siswa.strftime('%H:%M') if instalasi.jam_masuk_siswa else '-',
                    'jam_pulang_siswa': instalasi.jam_pulang_siswa.strftime('%H:%M') if instalasi.jam_pulang_siswa else '-',
                    
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
                    'tanggal_cetak': timezone.localtime(timezone.now()).strftime('%d-%m-%Y %H:%M:%S')
                }
                
                return render(request, 'CustomAdmin/print_absensi_siswa.html', context)
                
            except Siswa.DoesNotExist:
                messages.error(request, 'Siswa tidak ditemukan')
                return redirect('admin_siswa')
            except ValueError:
                messages.error(request, 'Format tanggal tidak valid')
                return redirect('admin_siswa')
            except Exception as e:
                messages.error(request, f'Gagal mencetak record: {str(e)}')
                return redirect('admin_siswa')
        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'tambah':
                try:
                    username = request.POST.get('username')
                    email = request.POST.get('email')
                    password = request.POST.get('password')
                    userid = request.POST.get('userid')
                    
                    # Buat user baru
                    user = CustomUser.objects.create_user(username=username, email=email, password=password, userid=userid, is_staff=True)
                    
                    # Ambil data siswa
                    nama = request.POST.get('nama')
                    nisn = request.POST.get('nisn')
                    tgl_lahir = request.POST.get('tanggal_lahir')
                    jenjang_siswa = request.POST.get('jenjang')
                    kelas_siswa = request.POST.get('kelas')
                    alamat = request.POST.get('alamat')
                    telegram_chat_id = request.POST.get('chatid')
                    
                    
                    # Buat siswa baru dengan user yang telah dibuat
                    siswa = Siswa.objects.create(
                        user=user,
                        nisn=nisn,
                        nama=nama,
                        tanggal_lahir=tgl_lahir,
                        jenjang_id=jenjang_siswa,
                        kelas_id=kelas_siswa,
                        alamat=alamat,
                        telegram_chat_id=telegram_chat_id,
                    )
                    messages.success(request, 'Data siswa berhasil ditambahkan.')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                    return redirect('admin_siswa')
            elif action == 'edit':
                try:
                    id_siswa = request.POST.get('id')
                    id_user = request.POST.get('iduser')
                    userid = request.POST.get('userid')
                    username = request.POST.get('username')
                    nama = request.POST.get('nama')
                    email = request.POST.get('email')
                    nisn = request.POST.get('nisn')
                    tanggal_lahir = request.POST.get('tanggal_lahir')
                    jenjang_selected = request.POST.get('jenjang')
                    kelas_selected = request.POST.get('kelas')
                    alamat = request.POST.get('alamat')
                    chatid = request.POST.get('chatid')
                    password = request.POST.get('new_password')

                    # Update user details
                    user = CustomUser.objects.get(id=id_user)
                    user.username = username
                    user.email = email
                    user.userid = userid
                    if password not in (None, ''):
                        user.set_password(password)
                    user.save()
                    
                    siswa = Siswa.objects.get(id=id_siswa)
                    
                    if jenjang_selected not in ('None', '', 'Pilih Jenjang', None, 0, '0'):
                        siswa.jenjang = jenjang.objects.get(nama=jenjang_selected)
                    else:
                        pass
                    
                    if kelas_selected not in ('None', '', 'Pilih Kelas', None, 0, '0'):
                        siswa.kelas = kelas.objects.get(nama=kelas_selected)
                    else:
                        pass
                    
                    # Update siswa details
                    siswa.nisn = nisn
                    siswa.nama = nama
                    siswa.tanggal_lahir = tanggal_lahir
                    siswa.alamat = alamat
                    siswa.telegram_chat_id = chatid
                    siswa.save()
                    
                    messages.success(request, 'Data siswa berhasil diperbarui.')
                    return redirect('admin_siswa')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                    return redirect('admin_siswa')
            elif action == 'hapus':
                try:
                    selected_ids = request.POST.getlist('selectedIds')
                    # Menangani kasus di mana selectedIds berisi string dengan beberapa ID
                    all_ids = []
                    for id_string in selected_ids:
                        all_ids.extend(id_string.split(','))
                    
                    siswa_list = Siswa.objects.filter(id__in=all_ids)
                    for siswa in siswa_list:
                        user = siswa.user
                        # Menghapus semua record_absensi terkait
                        record_absensi.objects.filter(user=user).delete()
                        # Menghapus semua izin terkait
                        izin.objects.filter(user=user).delete()
                        # Menghapus semua sakit terkait
                        sakit.objects.filter(user=user).delete()
                        # Menghapus Siswa
                        siswa.delete()
                        # Menghapus user
                        user.delete()

                    messages.success(request, f'{len(all_ids)} data siswa berhasil dihapus.')
                    return redirect('admin_siswa')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                    return redirect('admin_siswa')

            elif action == 'import':
                try:
                    file_type = request.POST.get('file_type')
                    file = request.FILES.get('file_input')
                    
                    if file_type == 'csv':
                        df = pd.read_csv(file)
                    elif file_type == 'excel':
                        df = pd.read_excel(file)
                    else:
                        messages.error(request, 'Tipe file tidak didukung.')
                        return redirect('admin_siswa')
                    
                    # Periksa kolom yang diperlukan
                    required_columns = ['username', 'email', 'password', 'userid', 'nisn', 'nama', 
                                      'tanggal_lahir', 'jenjang', 'kelas', 'alamat', 'telegram_chat_id']
                    
                    missing_columns = [col for col in required_columns if col not in df.columns]
                    if missing_columns:
                        messages.error(request, f'Kolom yang diperlukan tidak ditemukan: {", ".join(missing_columns)}')
                        return redirect('admin_siswa')
                    
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
                            
                            Siswa.objects.create(
                                user=user,
                                nisn=str(row['nisn']).strip(),
                                nama=str(row['nama']).strip(),
                                tanggal_lahir=tanggal_lahir,
                                jenjang=jenjang_obj,
                                kelas=kelas_obj,
                                alamat=str(row['alamat']).strip(),
                                telegram_chat_id=str(row['telegram_chat_id']).strip()
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
                        messages.success(request, f'{success_count} data siswa berhasil diimpor.')
                    if error_count > 0:
                        messages.warning(request, f'{error_count} data siswa gagal diimpor.')
                        messages.warning(request, 'Detail error:')
                        for error in error_details[:5]:  # Tampilkan 5 error pertama
                            messages.warning(request, error)
                        if len(error_details) > 5:
                            messages.warning(request, f'...dan {len(error_details) - 5} error lainnya')
                    
                    return redirect('admin_siswa')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                    return redirect('admin_siswa')

        # Subquery untuk mendapatkan status record_absensi terbaru untuk setiap siswa hari ini
        latest_absensi = record_absensi.objects.filter(
            user__siswa=OuterRef('pk'),
            checktime__date=today
        ).order_by('-checktime').values('status', 'status_verifikasi')[:1]

        # Query utama
        students = siswa_filter.select_related('user', 'jenjang', 'kelas').annotate(
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
            'alamat',
            'user__username',
            'today_status',
            'today_status_verifikasi',
            'today_checktime',
            'today_tipe_absensi'
        )

        # Memproses queryset untuk menampilkan status yang lebih detail
        table_data = []
        for student in students:
            status = student[-4]  # today_status
            status_verifikasi = student[-3]  # today_status_verifikasi
            checktime = student[-2]  # today_checktime
            tipe_absensi = student[-1]  # today_tipe_absensi
            
            if status_verifikasi == 'menunggu':
                display_status = "Belum Diverifikasi"
            elif status_verifikasi == 'ditolak':
                display_status = "Ditolak"
            elif tipe_absensi == 'pulang':
                display_status = "Sudah Pulang"
            elif status == 'hadir' and tipe_absensi == 'masuk':
                # Ambil record absensi untuk mendapatkan keterlambatan
                absensi = record_absensi.objects.filter(
                    user__siswa__id=student[0],
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
            
            table_data.append(list(student[:-4]) + [display_status])
        
        context = get_context()
        context.update({
            'siswa': True,
            
            'table_columns': ['ID Siswa', 'UserID', 'Nama', 'Jenjang', 'Kelas', 'Alamat', 'Username', 'Status'],
            'table_data': table_data,
            
            'jenjang_list': jenjang.objects.all(),
            'kelas_list': kelas.objects.all(),
            
            'edit_data_siswa': edit_data_siswa,
            
            'total_data_table': siswa_filter.count(),
            'print': True,
        })
        return render(request, 'CustomAdmin/admin_siswa.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_siswa')
