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
        bulan = request.GET.get('bulan')
        if print_id and bulan:
            try:
                guru = Guru.objects.get(id=print_id)
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
                    
                    # Cek status ketidakhadiran
                    ketidakhadiran = record_absensi.objects.filter(
                        user=guru.user,
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
                    'guru': guru,
                    'bulan': tanggal_awal.strftime('%B %Y'),
                    'hari_records': semua_hari,
                    'total_hadir': total_hadir,
                    'total_sakit': total_sakit,
                    'total_izin': total_izin,
                    'total_tidak_hadir': total_tidak_hadir,
                    'tanggal_cetak': timezone.now().strftime('%d-%m-%Y %H:%M:%S')
                }
                
                return render(request, 'CustomAdmin/print_absensi_guru.html', context)
                
            except Guru.DoesNotExist:
                messages.error(request, 'Guru tidak ditemukan')
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
                
                guru = Guru.objects.create(
                    user=user,
                    nama=nama,
                    nuptk=nuptk,
                    tanggal_lahir=tanggal_lahir,
                    jenjang_id=jenjang_selected,
                    kelas_id=kelas_selected,
                    mata_pelajaran_id=mata_pelajaran_selected,
                    alamat=alamat,
                    telegram_chat_id=telegram_chat_id
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
                file_type = request.POST.get('file_type')
                file = request.FILES.get('file_input')
                
                if file_type == 'csv':
                    df = pd.read_csv(file)
                elif file_type == 'excel':
                    df = pd.read_excel(file)
                else:
                    messages.error(request, 'Tipe file tidak didukung.')
                    return redirect('admin_guru')
                
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
                        
                        jenjang_obj, _ = jenjang.objects.get_or_create(nama=row['jenjang'])
                        kelas_obj, _ = kelas.objects.get_or_create(nama=row['kelas'])
                        mata_pelajaran_obj, _ = mata_pelajaran.objects.get_or_create(nama=row['mata_pelajaran'])
                        
                        Guru.objects.create(
                            user=user,
                            nuptk=row['nuptk'],
                            nama=row['nama'],
                            tanggal_lahir=row['tanggal_lahir'],
                            jenjang=jenjang_obj,
                            kelas=kelas_obj,
                            mata_pelajaran=mata_pelajaran_obj,
                            alamat=row['alamat'],
                            telegram_chat_id=row['telegram_chat_id']
                        )
                        success_count += 1
                    except Exception as e:
                        error_count += 1
                        print(f'Gagal mengimpor data: {str(e)}')
                
                if success_count > 0:
                    messages.success(request, f'{success_count} data guru berhasil diimpor.')
                if error_count > 0:
                    messages.warning(request, f'{error_count} data guru gagal diimpor. Silakan periksa log untuk detailnya.')
                
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
            'today_tipe_absensi'
        )

        # Memproses queryset untuk menampilkan status yang lebih detail
        table_data = []
        for guru_data in guru:
            status = guru_data[-4]  # today_status
            status_verifikasi = guru_data[-3]  # today_status_verifikasi
            checktime = timezone.localtime(guru_data[-2])  # today_checktime
            tipe_absensi = guru_data[-1]  # today_tipe_absensi
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
            
            table_data.append(list(guru_data[:-4]) + [display_status])
            
        context = get_context()
        context.update({
            'table_columns': ['ID Guru', 'UserID', 'Nama', 'Jenjang', 'Kelas', 'Mata Pelajaran', 'Alamat', 'Username', 'Status'],
            'table_data': table_data,
            
            'jenjang_list': jenjang.objects.all(),
            'kelas_list': kelas.objects.all(),
            'mata_pelajaran_list': mata_pelajaran.objects.all(),
            
            'edit_data_guru': edit_data_guru,
            
            'guru': True,
            
            'total_data_table': guru_filter.count(),
            'print': True,
        })
        return render(request, 'CustomAdmin/admin_guru.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_guru')


