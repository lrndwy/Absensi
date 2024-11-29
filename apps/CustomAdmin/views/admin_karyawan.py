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
def admin_karyawan(request):
    try:
        today = timezone.localtime(timezone.now()).date()
        jabatan_filter = request.GET.get('jabatan')
        instalasi = Instalasi.objects.first()
        
        edit_data_karyawan = []
        edit_id = request.GET.get('id')
        if edit_id:
            for data_karyawan in Karyawan.objects.filter(id=edit_id):
                data_edit = {
                    'id': data_karyawan.id,
                    'iduser': data_karyawan.user.id if data_karyawan.user else None,
                    'username': data_karyawan.user.username if data_karyawan.user else None,
                    'email': data_karyawan.user.email if data_karyawan.user else None,
                    'nama': data_karyawan.nama,
                    'nip': data_karyawan.nip,
                    'tanggal_lahir': data_karyawan.tanggal_lahir.strftime('%Y-%m-%d'),
                    'jabatan': data_karyawan.jabatan.nama if data_karyawan.jabatan else None,
                    'alamat': data_karyawan.alamat if data_karyawan else None,
                    'userid': data_karyawan.user.userid if data_karyawan.user else None,
                    'telegram_chat_id': data_karyawan.telegram_chat_id if data_karyawan else None,
                }
                edit_data_karyawan.append(data_edit)
                
                
        karyawan_filter = Karyawan.objects.all()
        if jabatan_filter:
            karyawan_filter = karyawan_filter.filter(jabatan__nama=jabatan_filter)
            
            
        # IF PRINT
        print_id = request.GET.get('print')
        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        
        if print_id and start_date and end_date:
            try:
                karyawan = Karyawan.objects.get(id=print_id)
                
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
                        kategori__in=['karyawan', 'semua']
                    ).first()
                    
                    if tanggal_merah_obj:
                        # Jika tanggal merah, set status dan keterangan sesuai tanggal merah
                        hari_data = {
                            'tanggal': f"{tanggal.strftime('%A')}, {tanggal.strftime('%d %B %Y')}",
                            'jam_masuk': '-',
                            'jam_pulang': '-',
                            'status': f"Tanggal Merah: {tanggal_merah_obj.nama_acara}",
                            'keterangan': tanggal_merah_obj.keterangan,
                            'keterlambatan': None
                        }
                    else:
                        # Jika bukan tanggal merah, proses seperti biasa
                        absensi_masuk = record_absensi.objects.filter(
                            user=karyawan.user,
                            checktime__date=tanggal.date(),
                            tipe_absensi='masuk',
                            status_verifikasi='diterima'
                        ).first()
                        
                        absensi_pulang = record_absensi.objects.filter(
                            user=karyawan.user,
                            checktime__date=tanggal.date(),
                            tipe_absensi='pulang',
                            status_verifikasi='diterima'
                        ).first()
                        
                        # Cek ketidakhadiran (sakit/izin)
                        ketidakhadiran = record_absensi.objects.filter(
                            user=karyawan.user,
                            checktime__date=tanggal.date(),
                            status__in=['sakit', 'izin'],
                            status_verifikasi='diterima'
                        ).first()

                        # Hitung keterlambatan berdasarkan jam masuk karyawan dari instalasi
                        keterlambatan = None
                        if absensi_masuk:
                            keterlambatan = absensi_masuk.terlambat  # Langsung mengambil nilai terlambat dari record

                        # Hitung durasi kerja jika ada absensi masuk dan pulang
                        durasi_kerja = None
                        if absensi_masuk and absensi_pulang:
                            durasi = absensi_pulang.checktime - absensi_masuk.checktime
                            durasi_kerja = durasi.total_seconds() / 3600  # Konversi ke jam

                        hari_data = {
                            'tanggal': f"{tanggal.strftime('%A')}, {tanggal.strftime('%d %B %Y')}",
                            'jam_masuk': timezone.localtime(absensi_masuk.checktime).strftime('%H:%M') if absensi_masuk else '-',
                            'jam_pulang': timezone.localtime(absensi_pulang.checktime).strftime('%H:%M') if absensi_pulang else '-',
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
                    'karyawan': karyawan,
                    'periode': f"{tanggal_awal.strftime('%d %B %Y')} - {tanggal_akhir.strftime('%d %B %Y')}",
                    'hari_records': semua_hari,
                    'jam_masuk_karyawan': instalasi.jam_masuk_karyawan.strftime('%H:%M') if instalasi.jam_masuk_karyawan else '-',
                    'jam_pulang_karyawan': instalasi.jam_pulang_karyawan.strftime('%H:%M') if instalasi.jam_pulang_karyawan else '-',
                    'jam_kerja_karyawan': f"{instalasi.jam_kerja_karyawan.total_seconds()/3600:.2f} jam" if instalasi.jam_kerja_karyawan else '-',
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
                
                return render(request, 'CustomAdmin/print_absensi_karyawan.html', context)
                
            except Karyawan.DoesNotExist:
                messages.error(request, 'Karyawan tidak ditemukan')
                return redirect('admin_karyawan')
            except ValueError:
                messages.error(request, 'Format tanggal tidak valid')
                return redirect('admin_karyawan')
            except Exception as e:
                messages.error(request, f'Gagal mencetak record: {str(e)}')
                return redirect('admin_karyawan')
        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'tambah':
                username = request.POST.get('username')
                email = request.POST.get('email')
                password = request.POST.get('password')
                userid = request.POST.get('userid')
                
                user = CustomUser.objects.create_user(username=username, email=email, password=password, userid=userid, is_staff=True)
                
                nama = request.POST.get('nama')
                nip = request.POST.get('nip')
                tanggal_lahir = request.POST.get('tanggal_lahir')
                jabatan_karyawan = request.POST.get('jabatan')
                alamat = request.POST.get('alamat')
                telegram_chat_id = request.POST.get('chatid')
                karyawan = Karyawan.objects.create(
                    user=user,
                    nama=nama,
                    nip=nip,
                    tanggal_lahir=tanggal_lahir,
                    jabatan_id=jabatan_karyawan,
                    alamat=alamat,
                    telegram_chat_id=telegram_chat_id,
                )
                messages.success(request, 'Data karyawan berhasil ditambahkan.')
                
            if action == 'edit':
                id_karyawan = request.POST.get('id')
                id_user = request.POST.get('iduser')
                userid = request.POST.get('userid')
                username = request.POST.get('username')
                nama = request.POST.get('nama')
                email = request.POST.get('email')
                nip = request.POST.get('nip')
                tanggal_lahir = request.POST.get('tanggal_lahir')
                jabatan_selected = request.POST.get('jabatan')
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
                
                karyawan = Karyawan.objects.get(id=id_karyawan)
                karyawan.nama = nama
                karyawan.nip = nip
                karyawan.tanggal_lahir = tanggal_lahir
                if jabatan_selected not in ('None', '', 'Pilih Jabatan', None, 0, '0'):
                    jabatan_karyawan = jabatan.objects.get(nama=jabatan_selected)
                    karyawan.jabatan = jabatan_karyawan
                else:
                    pass
                karyawan.alamat = alamat
                karyawan.telegram_chat_id = telegram_chat_id
                karyawan.save()
                
                messages.success(request, 'Data karyawan berhasil diperbarui.')
                return redirect('admin_karyawan')
            
            if action == 'hapus':
                selected_ids = request.POST.getlist('selectedIds')
                # Menangani kasus di mana selectedIds berisi string dengan beberapa ID
                all_ids = []
                for id_string in selected_ids:
                    all_ids.extend(id_string.split(','))
                
                karyawan_list = Karyawan.objects.filter(id__in=all_ids)
                deleted_count = 0
                for karyawan in karyawan_list:
                    user = karyawan.user
                    # menghapus semua record_absensi terkait
                    record_absensi.objects.filter(user=user).delete()
                    # menghapus semua izin terkait
                    izin.objects.filter(user=user).delete()
                    # menghapus semua sakit terkait
                    sakit.objects.filter(user=user).delete()
                    # menghapus karyawan
                    karyawan.delete()
                    # menghapus user
                    user.delete()
                    deleted_count += 1
                
                messages.success(request, f'{deleted_count} data karyawan berhasil dihapus.')
                return redirect('admin_karyawan')
            
            if action == 'import':
                file_type = request.POST.get('file_type')
                file = request.FILES.get('file_input')
                
                if file_type == 'csv':
                    df = pd.read_csv(file)
                elif file_type == 'excel':
                    df = pd.read_excel(file)
                else:
                    messages.error(request, 'Tipe file tidak didukung.')
                    return redirect('admin_karyawan')
                
                success_count = 0
                error_count = 0
                
                def parse_tanggal(tanggal_str):
                    format_tanggal = [
                        '%Y-%m-%d',           # 2024-03-21
                        '%d-%m-%Y',           # 21-03-2024
                        '%d/%m/%Y',           # 21/03/2024
                        '%Y/%m/%d',           # 2024/03/21
                        '%d-%B-%Y',           # 21-March-2024
                        '%d %B %Y',           # 21 March 2024
                        '%B %d, %Y',          # March 21, 2024
                        '%d.%m.%Y',           # 21.03.2024
                        '%Y.%m.%d',           # 2024.03.21
                    ]
                    
                    for fmt in format_tanggal:
                        try:
                            return datetime.strptime(str(tanggal_str), fmt).date()
                        except ValueError:
                            continue
                    
                    raise ValueError(f'Format tanggal tidak valid: {tanggal_str}')

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
                        
                        jabatan_obj, created = jabatan.objects.get_or_create(nama=row['jabatan'])
                        
                        # Parse tanggal lahir dengan format yang fleksibel
                        tanggal_lahir = parse_tanggal(row['tanggal_lahir'])
                        
                        Karyawan.objects.create(
                            user=user,
                            nip=row['nip'],
                            nama=row['nama'],
                            tanggal_lahir=tanggal_lahir,  # Gunakan hasil parsing
                            jabatan=jabatan_obj,
                            alamat=row['alamat'],
                            telegram_chat_id=row['telegram_chat_id']
                        )
                        success_count += 1
                    except ValueError as e:
                        error_count += 1
                        print(f'Gagal mengimpor data - Error format tanggal: {str(e)}')
                    except Exception as e:
                        error_count += 1
                        print(f'Gagal mengimpor data: {str(e)}')
                
                if success_count > 0:
                    messages.success(request, f'{success_count} data karyawan berhasil diimpor.')
                if error_count > 0:
                    messages.warning(request, f'{error_count} data karyawan gagal diimpor. Silakan periksa log untuk detailnya.')
                
                return redirect('admin_karyawan')
            
        
        # Subquery untuk mendapatkan status record_absensi terbaru untuk setiap karyawan hari ini
        latest_absensi = record_absensi.objects.filter(
            user__karyawan=OuterRef('pk'),
            checktime__date=today
        ).order_by('-checktime').values('status', 'status_verifikasi')[:1]

        # Query utama
        karyawan = karyawan_filter.select_related('user', 'jabatan').annotate(
            today_status=Subquery(latest_absensi.values('status')),
            today_status_verifikasi=Subquery(latest_absensi.values('status_verifikasi')),
            today_checktime=Subquery(latest_absensi.values('checktime')),
            today_tipe_absensi=Subquery(latest_absensi.values('tipe_absensi'))
        ).values_list(
            'id',
            'user__userid',
            'nama',
            'jabatan__nama',
            'alamat',
            'user__username',
            'today_status',
            'today_status_verifikasi',
            'today_checktime',
            'today_tipe_absensi'
        )

        # Memproses queryset untuk menampilkan status yang lebih detail
        table_data = []
        for karyawan_data in karyawan:
            status = karyawan_data[-4]  # today_status
            status_verifikasi = karyawan_data[-3]  # today_status_verifikasi
            checktime = timezone.localtime(karyawan_data[-2])  # today_checktime
            tipe_absensi = karyawan_data[-1]  # today_tipe_absensi
            print(status, status_verifikasi, checktime, tipe_absensi)
            
            if status_verifikasi == 'menunggu':
                display_status = "Belum Diverifikasi"
            elif status_verifikasi == 'ditolak':
                display_status = "Ditolak"
            elif tipe_absensi == 'pulang':
                display_status = "Sudah Pulang"
            elif status == 'hadir' and tipe_absensi == 'masuk':
                absensi = record_absensi.objects.filter(
                    user__karyawan__id=karyawan_data[0],
                    checktime__date=today,
                    tipe_absensi='masuk',
                    status_verifikasi='diterima'
                ).first()
                
                if absensi and absensi.terlambat > 0:
                    menit_terlambat = absensi.terlambat
                    if menit_terlambat < 60:
                        display_status = f"Hadir, terlambat {int(menit_terlambat)} menit"
                    else:
                        jam_terlambat = int(menit_terlambat // 60)
                        sisa_menit = int(menit_terlambat % 60)
                        display_status = f"Hadir, terlambat {jam_terlambat} jam {sisa_menit} menit"
                else:
                    display_status = "Hadir"
            else:
                display_status = status if status else "Belum Hadir"
            
            table_data.append(list(karyawan_data[:-4]) + [display_status])
        context = get_context()
        context.update({
            'table_columns': ['ID Karyawan', 'UserID', 'Nama', 'Jabatan', 'Alamat', 'Username', 'Status'],
            'table_data': table_data,
            
            'jabatan_list': jabatan.objects.all(),
            
            'edit_data_karyawan': edit_data_karyawan,
            
            'karyawan': True,
            
            'total_data_table': karyawan_filter.count(),
            'print': True,
        })
        return render(request, 'CustomAdmin/admin_karyawan.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_karyawan')
