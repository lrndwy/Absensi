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
        bulan = request.GET.get('bulan')
        if print_id and bulan:
            try:
                siswa = Siswa.objects.get(id=print_id)
                tahun = timezone.now().year
                bulan_int = int(bulan)
                
                # Dapatkan tanggal awal dan akhir bulan
                tanggal_awal = timezone.datetime(tahun, bulan_int, 1)
                if bulan_int == 12:
                    tanggal_akhir = timezone.datetime(tahun + 1, 1, 1) - timezone.timedelta(days=1)
                else:
                    tanggal_akhir = timezone.datetime(tahun, bulan_int + 1, 1) - timezone.timedelta(days=1)

                # Buat list semua hari dalam bulan tersebut
                jumlah_hari = (tanggal_akhir - tanggal_awal).days + 1
                semua_hari = []
                
                for i in range(jumlah_hari):
                    tanggal = tanggal_awal + timezone.timedelta(days=i)
                    
                    # Ambil record absensi untuk tanggal tersebut
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
                    
                    # Cek status ketidakhadiran
                    ketidakhadiran = record_absensi.objects.filter(
                        user=siswa.user,
                        checktime__date=tanggal.date(),
                        status__in=['sakit', 'izin'],
                        status_verifikasi='diterima'
                    ).first()
                    
                    hari_data = {
                        'tanggal': tanggal,
                        'hari': tanggal.strftime('%A'),
                        'jam_masuk': timezone.localtime(absensi_masuk.checktime).strftime('%H:%M') if absensi_masuk else '-',
                        'jam_pulang': timezone.localtime(absensi_pulang.checktime).strftime('%H:%M') if absensi_pulang else '-',
                        'status': ketidakhadiran.status if ketidakhadiran else ('Hadir' if absensi_masuk else 'Tidak Hadir'),
                        'keterangan': ketidakhadiran.id_sakit.keterangan if ketidakhadiran and ketidakhadiran.status == 'sakit' and ketidakhadiran.id_sakit
                                    else ketidakhadiran.id_izin.keterangan if ketidakhadiran and ketidakhadiran.status == 'izin' and ketidakhadiran.id_izin
                                    else '-'
                    }
                    semua_hari.append(hari_data)
                
                # Hitung total
                total_hadir = sum(1 for hari in semua_hari if hari['status'] == 'Hadir')
                total_sakit = sum(1 for hari in semua_hari if hari['status'] == 'sakit')
                total_izin = sum(1 for hari in semua_hari if hari['status'] == 'izin')
                total_tidak_hadir = sum(1 for hari in semua_hari if hari['status'] == 'Tidak Hadir')
                
                context = {
                    'siswa': siswa,
                    'bulan': tanggal_awal.strftime('%B %Y'),
                    'hari_records': semua_hari,
                    'total_hadir': total_hadir,
                    'total_sakit': total_sakit,
                    'total_izin': total_izin,
                    'total_tidak_hadir': total_tidak_hadir,
                    'tanggal_cetak': timezone.now().strftime('%d-%m-%Y %H:%M:%S')
                }
                
                return render(request, 'CustomAdmin/print_absensi_siswa.html', context)
                
            except Siswa.DoesNotExist:
                messages.error(request, 'Siswa tidak ditemukan')
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
                    
                    success_count = 0
                    error_count = 0
                    
                    for _, row in df.iterrows():
                        try:
                            # Cek apakah username sudah ada
                            username = row['username']
                            counter = 1
                            while CustomUser.objects.filter(username=username).exists():
                                username = f"{row['username']}_{counter}"
                                counter += 1
                            
                            user = CustomUser.objects.create_user(
                                username=username,
                                email=row['email'],
                                password=row['password'],
                                userid=row['userid'],
                                is_staff=True
                            )
                            
                            # Cek dan buat jenjang jika belum ada
                            jenjang_obj, _ = jenjang.objects.get_or_create(nama=row['jenjang'])
                            
                            # Cek dan buat kelas jika belum ada
                            kelas_obj, _ = kelas.objects.get_or_create(nama=row['kelas'])
                            
                            Siswa.objects.create(
                                user=user,
                                nisn=row['nisn'],
                                nama=row['nama'],
                                tanggal_lahir=row['tanggal_lahir'],
                                jenjang=jenjang_obj,
                                kelas=kelas_obj,
                                alamat=row['alamat'],
                                telegram_chat_id=row['telegram_chat_id']
                            )
                            success_count += 1
                        except Exception as e:
                            error_count += 1
                            print(f'Gagal mengimpor data: {str(e)}')
                    
                    if success_count > 0:
                        messages.success(request, f'{success_count} data siswa berhasil diimpor.')
                    if error_count > 0:
                        messages.warning(request, f'{error_count} data siswa gagal diimpor. Silakan periksa log untuk detailnya.')
                    
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
            checktime = timezone.localtime(student[-2])  # today_checktime
            tipe_absensi = student[-1]  # today_tipe_absensi
            print(status, status_verifikasi, checktime, tipe_absensi)
            
            if status_verifikasi == 'menunggu':
                display_status = "Belum Diverifikasi"
            elif status_verifikasi == 'ditolak':
                display_status = "Ditolak"
            elif tipe_absensi == 'pulang':
                display_status = "Sudah Pulang"
            elif status == 'hadir' and tipe_absensi == 'masuk':
                instalasi = Instalasi.objects.first()
                jam_masuk = instalasi.jam_masuk if instalasi.jam_masuk else None
                jam_pulang = instalasi.jam_pulang if instalasi.jam_pulang else None
                if checktime and jam_masuk:
                    selisih = datetime.combine(date.min, datetime.strptime(checktime.strftime('%I:%M %p'), '%I:%M %p').time()) - datetime.combine(date.min, jam_masuk)
                    if selisih.total_seconds() > 0:
                        menit_terlambat = selisih.total_seconds() // 60
                        if menit_terlambat < 60:
                            display_status = f"Hadir, terlambat {int(menit_terlambat)} menit"
                        else:
                            jam_terlambat = int(menit_terlambat // 60)
                            sisa_menit = int(menit_terlambat % 60)
                            display_status = f"Hadir, terlambat {jam_terlambat} jam {sisa_menit} menit"
                    else:
                        display_status = "Hadir"
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
