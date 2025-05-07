import json
from datetime import datetime, timedelta
from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.utils import timezone
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models import Subquery, OuterRef
from django.db.models.functions import Coalesce, TruncDate

from apps.main.instalasi import get_context
from apps.main.models import *


from .models import Guru
from apps.Siswa.models import *
from apps.Karyawan.models import *

import requests


def get_guru_absensi_hari_ini(guru):
    hari_ini = timezone.localtime(timezone.now()).date()
    
    try:
        absensi_hari_ini = record_absensi.objects.filter(
            user=guru.user,
            checktime__date=hari_ini
        ).latest('checktime')
        return {
            'status': absensi_hari_ini.status,
            'status_verifikasi': absensi_hari_ini.status_verifikasi
        }
    except record_absensi.DoesNotExist:
        return {
            'status': 'belum_absen',
            'status_verifikasi': None
        }



def guru_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Anda harus login terlebih dahulu.')
            return redirect('login_view')
        try:
            guru = Guru.objects.get(user=request.user)
        except Guru.DoesNotExist:
            messages.error(request, 'Anda tidak memiliki akses sebagai guru.')
            return redirect('login_view')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@login_required
@guru_required
def guru_dashboard(request):
    guru = Guru.objects.get(user=request.user)
    walas = guru.wali_kelas
    kepsek = guru.kepala_sekolah
    if request.method == 'POST':
        status_absensi = request.POST.get('status_absensi')
        keterangan = request.POST.get('keterangan')
        waktu_absen = timezone.localtime(timezone.now()).strftime('%H.%M.%S')
        tanggal_absen = timezone.localtime(timezone.now()).date()
        
        if status_absensi in ['sakit', 'izin']:
            if status_absensi == 'sakit':
                surat_sakit = request.FILES.get('surat_sakit')
                sakit_obj = sakit.objects.create(user=request.user, keterangan=keterangan, surat_sakit=surat_sakit)
                record = record_absensi.objects.create(user=request.user, status='sakit', id_sakit=sakit_obj, checktime=timezone.now(), status_verifikasi='menunggu')
                messages.success(request, 'Absensi sakit berhasil dicatat.')
                send_telegram_message(guru.telegram_chat_id, f"Selamat {cek_waktu()} Bapak/Ibu. Informasi bahwa {guru.nama} sakit pada {tanggal_absen} jam {waktu_absen}")
            elif status_absensi == 'izin':
                izin_obj = izin.objects.create(user=request.user, keterangan=keterangan)
                record = record_absensi.objects.create(user=request.user, status='izin', id_izin=izin_obj, checktime=timezone.now(), status_verifikasi='menunggu')
                messages.success(request, 'Absensi izin berhasil dicatat.')
                send_telegram_message(guru.telegram_chat_id, f"Selamat {cek_waktu()} Bapak/Ibu. Informasi bahwa {guru.nama} izin pada {tanggal_absen} jam {waktu_absen}")
            
            return redirect('guru_dashboard')
        else:
            messages.error(request, 'Status absensi tidak valid.')
            
    status_absensi = get_guru_absensi_hari_ini(guru)
    
    today = timezone.localtime(timezone.now()).date()
    
    # Get start and end dates from request
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')

    # If no dates provided, default to today and last 7 days
    if not end_date:
        end_date = today
    else:
        try:
            end_date = datetime.strptime(end_date, '%m/%d/%Y').date()
        except ValueError:
            messages.error(request, 'Format tanggal akhir tidak valid')
            end_date = today

    if not start_date:
        start_date = end_date - timedelta(days=6)
    else:
        try:
            start_date = datetime.strptime(start_date, '%m/%d/%Y').date()
        except ValueError:
            messages.error(request, 'Format tanggal mulai tidak valid')
            start_date = end_date - timedelta(days=6)

    # Ensure start_date is not after end_date
    if start_date > end_date:
        start_date, end_date = end_date, start_date
        messages.warning(request, 'Tanggal mulai setelah tanggal akhir, urutan dibalik otomatis')

    # Limit date range to 31 days
    max_range = 31
    if (end_date - start_date).days > max_range:
        messages.warning(request, f'Rentang waktu dibatasi maksimal {max_range} hari.')
        start_date = end_date - timedelta(days=max_range)
    
    days_difference = (end_date - start_date).days + 1
    
    history_records = []
    
    instalasi = Instalasi.objects.first()
    jam_masuk = instalasi.jam_masuk_guru if instalasi else None
    
    for i in range(days_difference):
        tanggal = start_date + timedelta(days=i)
        
        tanggal_merah_obj = tanggal_merah.objects.filter(
            tanggal=tanggal,
            kategori__in=['guru', 'semua']
        ).first()
        
        if tanggal_merah_obj:
            hari_data = {
                'tanggal': tanggal,
                'hari': tanggal.strftime('%A'),
                'jam_masuk': '-',
                'jam_pulang': '-',
                'status': f"Tanggal Merah: {tanggal_merah_obj.nama_acara}",
                'keterangan': tanggal_merah_obj.keterangan,
                'keterlambatan': None,
                'username': request.user.username
            }
        else:
            absensi_masuk = record_absensi.objects.filter(
                user=request.user,
                checktime__date=tanggal,
                tipe_absensi='masuk',
                status_verifikasi='diterima'
            ).first()
            
            absensi_pulang = record_absensi.objects.filter(
                user=request.user,
                checktime__date=tanggal,
                tipe_absensi='pulang',
                status_verifikasi='diterima'
            ).first()
            
            ketidakhadiran = record_absensi.objects.filter(
                user=request.user,
                checktime__date=tanggal,
                status__in=['sakit', 'izin'],
                status_verifikasi='diterima'
            ).first()

            keterlambatan = absensi_masuk.terlambat if absensi_masuk else None

            hari_data = {
                'tanggal': tanggal,
                'hari': tanggal.strftime('%A'),
                'jam_masuk': timezone.localtime(absensi_masuk.checktime).strftime('%H:%M') if absensi_masuk else '-',
                'jam_pulang': timezone.localtime(absensi_pulang.checktime).strftime('%H:%M') if absensi_pulang else '-',
                'status': ketidakhadiran.status if ketidakhadiran else ('Hadir' if absensi_masuk else 'Tidak Hadir'),
                'keterlambatan': keterlambatan,
                'is_terlambat': keterlambatan > 0 if keterlambatan is not None else False,
                'username': request.user.username,
                'keterangan': ketidakhadiran.id_sakit.keterangan if ketidakhadiran and ketidakhadiran.status == 'sakit' and ketidakhadiran.id_sakit
                            else ketidakhadiran.id_izin.keterangan if ketidakhadiran and ketidakhadiran.status == 'izin' and ketidakhadiran.id_izin
                            else f"Terlambat {keterlambatan} menit" if keterlambatan and keterlambatan > 0
                            else '-' if not absensi_masuk
                            else 'Tepat Waktu'
            }
        
        history_records.append(hari_data)

    context = get_context()
    context.update({
        'status_absensi': status_absensi['status'],
        'status_verifikasi': status_absensi['status_verifikasi'],
        'user_is_guru': True,
        'history_records': history_records,
        'start_date': start_date.strftime('%m/%d/%Y'),
        'end_date': end_date.strftime('%m/%d/%Y'),
        'walas': walas,
        'kepsek': kepsek
    })
    
    return render(request, 'Guru/guru_dashboard.html', context)

@login_required
@guru_required
def guru_statistik(request):
    guru = Guru.objects.get(user=request.user)
    walas = guru.wali_kelas
    kepsek = guru.kepala_sekolah
    end_date = request.GET.get('end', timezone.localtime(timezone.now()).date())
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%m/%d/%Y').date()
    start_date = request.GET.get('start', (end_date - timedelta(days=30)).strftime('%m/%d/%Y'))
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%m/%d/%Y').date()
    
    absensi_records = record_absensi.objects.filter(
        user=request.user,
        checktime__date__gte=start_date,
        checktime__date__lte=end_date
    )
    
    total_hadir = absensi_records.filter(status='hadir').count()
    total_sakit = absensi_records.filter(status='sakit').count()
    total_izin = absensi_records.filter(status='izin').count()
    
    total_hari = (end_date - start_date).days + 1
    total_tanpa_keterangan = total_hari - (total_hadir + total_sakit + total_izin)
    
    total_all = total_hari
    
    hadir_percentage = total_hadir if total_all > 0 else 0
    sakit_percentage = total_sakit if total_all > 0 else 0
    izin_percentage = total_izin if total_all > 0 else 0
    tanpa_keterangan_percentage = total_tanpa_keterangan if total_all > 0 else 0
    
    context = get_context()
    context.update({
        'pc_title': 'Statistik Absensi',
        'pc_month': f"{start_date.strftime('%d %B')} - {end_date.strftime('%d %B %Y')}",
        'pc_data': json.dumps([hadir_percentage, sakit_percentage, izin_percentage, tanpa_keterangan_percentage]),
        'pc_labels': json.dumps(['Hadir', 'Sakit', 'Izin', 'Tanpa Keterangan']),
        
        'day_ago': total_hari,
        
        'total_hadir': total_hadir,
        'total_sakit': total_sakit,
        'total_izin': total_izin,
        'total_tanpa_keterangan': total_tanpa_keterangan,
        'hadir_percentage': hadir_percentage,
        'sakit_percentage': sakit_percentage,
        'izin_percentage': izin_percentage,
        'tanpa_keterangan_percentage': tanpa_keterangan_percentage,
        
        'start_date': start_date,
        'end_date': end_date,
        'user_is_guru': True,
        'statistik_user': True,
        'walas': walas,
        'kepsek': kepsek
    })
    
    messages.info(request, f'Menampilkan statistik absensi dari {start_date.strftime("%d %B %Y")} hingga {end_date.strftime("%d %B %Y")}.')
    return render(request, 'Guru/guru_statistik.html', context)

def send_telegram_message(chat_id, message):
    telegram_token = Instalasi.objects.first().telegram_token
    telegram_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage?chat_id={chat_id}&text={message}"
    requests.get(telegram_url)
    
def cek_waktu():
    sekarang = timezone.localtime(timezone.now())
    jam = sekarang.hour
    
    if 5 <= jam < 12:
        return "pagi"
    elif 12 <= jam < 15:
        return "siang"
    elif 15 <= jam < 18:
        return "sore"
    else:
        return "malam"

@login_required
@guru_required
def guru_pengaturan(request):
    guru = Guru.objects.get(user=request.user)
    
    walas = guru.wali_kelas
    kepsek = guru.kepala_sekolah
    
    if request.method == 'POST':
        telegram_chat_id = request.POST.get('telegram_chat_id')
        notifikasi_telegram = request.POST.get('notifikasi_telegram') == 'on'
        
        # Update pengaturan
        guru.telegram_chat_id = telegram_chat_id
        guru.notifikasi_telegram = notifikasi_telegram
        guru.save()
        
        # Kirim pesan test jika notifikasi diaktifkan
        if notifikasi_telegram and telegram_chat_id:
            try:
                send_telegram_message(telegram_chat_id, f"Selamat {cek_waktu()} {guru.nama}, ini adalah pesan test notifikasi Telegram.")
                messages.success(request, 'Pengaturan berhasil disimpan dan pesan test telah dikirim.')
            except:
                messages.warning(request, 'Pengaturan berhasil disimpan tetapi gagal mengirim pesan test. Pastikan Chat ID valid.')
        else:
            messages.success(request, 'Pengaturan berhasil disimpan.')
        
        return redirect('guru_pengaturan')
    
    context = get_context()
    context.update({
        'guru': guru,
        'user_is_guru': True,
        'walas': walas,
        'kepsek': kepsek
    })
    
    return render(request, 'Guru/guru_pengaturan.html', context)


@login_required
@guru_required
def guru_verifikasi(request):
    try:
        guru = Guru.objects.get(user=request.user)
        walas = guru.wali_kelas
        kepsek = guru.kepala_sekolah
        
        # Filter record absensi untuk siswa dengan jenjang dan kelas yang sama dengan guru
        record_absensi_list = record_absensi.objects.filter(
            status_verifikasi='menunggu',
            user__siswa__jenjang=guru.jenjang,
            user__siswa__kelas=guru.kelas,
            user__siswa__isnull=False  # Memastikan hanya data siswa
        )
        
        edit_data_verifikasi = None
        edit_id = request.GET.get('id')
        if edit_id:
            data_record = record_absensi.objects.filter(id=edit_id).first()
            if data_record:
                siswa = Siswa.objects.get(user=data_record.user)
                edit_data_verifikasi = {
                    'id': data_record.id,
                    'username': data_record.user.username,
                    'entitas': 'Siswa',
                    'nama': siswa.nama,
                    'status': data_record.status,
                    'checktime': timezone.localtime(data_record.checktime).strftime('%Y-%m-%d %H:%M:%S'),
                }
                if data_record.status == 'sakit':
                    edit_data_verifikasi['id_sakit'] = data_record.id_sakit.id if data_record.id_sakit else None
                    edit_data_verifikasi['surat_sakit'] = data_record.id_sakit.surat_sakit.url if data_record.id_sakit and data_record.id_sakit.surat_sakit else None  
                    edit_data_verifikasi['keterangan'] = data_record.id_sakit.keterangan if data_record.id_sakit else None
                elif data_record.status == 'izin':
                    edit_data_verifikasi['id_izin'] = data_record.id_izin.id if data_record.id_izin else None
                    edit_data_verifikasi['keterangan'] = data_record.id_izin.keterangan if data_record.id_izin else None
                
                messages.info(request, 'Data absensi berhasil dimuat untuk diverifikasi.')
            else:
                messages.error(request, 'Data absensi tidak ditemukan.')
        
        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'verifikasi':
                id_record = request.POST.get('id')
                record = record_absensi.objects.get(id=id_record)
                record.status_verifikasi = 'diterima'
                checktime = request.POST.get('checktime')
                if checktime:
                    record.checktime = datetime.strptime(checktime, '%Y-%m-%d %H:%M:%S')
                record.save()
                messages.success(request, 'Data berhasil diverifikasi.')
                return redirect('guru_verifikasi')
        
        table_data = []
        for record in record_absensi_list:
            siswa = Siswa.objects.get(user=record.user)
            table_data.append([
                record.id,
                record.user.username,
                'Siswa',
                siswa.nama,
                record.status,
                timezone.localtime(record.checktime).strftime('%Y-%m-%d %H:%M:%S'),
                record.status_verifikasi,
            ])

        if not table_data:
            messages.info(request, 'Tidak ada data absensi yang perlu diverifikasi.')
        else:
            messages.info(request, f'Terdapat {len(table_data)} data absensi yang perlu diverifikasi.')

        context = get_context()
        context.update({
            'table_columns': ['ID', 'Username', 'Entitas', 'Nama', 'Status', 'Waktu', 'Status Verifikasi'],
            'table_data': table_data,
            'total_data_table': len(table_data),
            'verifikasi': True,
            'edit_data_verifikasi': edit_data_verifikasi,
            'status_verifikasi_list': ['menunggu', 'diterima', 'ditolak'],
            'API_LINK': reverse('api_verifikasi_guru'),
            'walas': walas,
            'user_is_guru': True,
            'verifikasi': True,
            'kepsek': kepsek,
        })
        return render(request, 'guru/guru_verifikasi.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('guru_verifikasi')

@login_required
@guru_required
@require_http_methods(['GET'])
def api_verifikasi_guru(request):
    try:
        guru = Guru.objects.get(user=request.user)
        
        # Filter record absensi untuk siswa dengan jenjang dan kelas yang sama
        record_absensi_list = record_absensi.objects.filter(
            status_verifikasi='menunggu',
            user__siswa__jenjang=guru.jenjang,
            user__siswa__kelas=guru.kelas,
            user__siswa__isnull=False  # Memastikan hanya data siswa
        )
        
        data = []
        for record in record_absensi_list:
            siswa = Siswa.objects.get(user=record.user)
            
            data.append({
                'id': record.id,
                'username': record.user.username,
                'entitas': 'Siswa',
                'nama': siswa.nama,
                'status': record.status,
                'waktu': timezone.localtime(record.checktime).strftime('%Y-%m-%d %H:%M:%S'),
                'status_verifikasi': record.status_verifikasi,
                'jenjang': siswa.jenjang.nama if siswa.jenjang else '-',
                'kelas': siswa.kelas.nama if siswa.kelas else '-'
            })

        return JsonResponse({'data': data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    


@login_required
@guru_required
def guru_siswa(request):
    try:
        guru = Guru.objects.get(user=request.user)
        walas = guru.wali_kelas
        kepsek = guru.kepala_sekolah
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
                    'tanggal_cetak': timezone.localtime(timezone.now()).strftime('%d-%m-%Y %H:%M:%S'),
                    'table_columns': ['ID Siswa', 'UserID', 'Nama', 'Jenjang', 'Kelas', 'Alamat', 'Username'],
                    'API_LINK': reverse('api_siswa_guru'),
                    'edit_url': reverse('guru_siswa'),
                    'siswa': True,
                }
                
                return render(request, 'guru/print_absensi_siswa.html', context)
                
            except Siswa.DoesNotExist:
                messages.error(request, 'Siswa tidak ditemukan')
                return redirect('guru_siswa')
            except ValueError:
                messages.error(request, 'Format tanggal tidak valid')
                return redirect('guru_siswa')
            except Exception as e:
                messages.error(request, f'Gagal mencetak record: {str(e)}')
                return redirect('guru_siswa')
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
                    return redirect('guru_siswa')
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
                    return redirect('guru_siswa')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                    return redirect('guru_siswa')
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
                    return redirect('guru_siswa')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                    return redirect('guru_siswa')

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
                        return redirect('guru_siswa')
                    
                    # Periksa kolom yang diperlukan
                    required_columns = ['username', 'email', 'password', 'userid', 'nisn', 'nama', 
                                      'tanggal_lahir', 'jenjang', 'kelas', 'alamat', 'telegram_chat_id']
                    
                    missing_columns = [col for col in required_columns if col not in df.columns]
                    if missing_columns:
                        messages.error(request, f'Kolom yang diperlukan tidak ditemukan: {", ".join(missing_columns)}')
                        return redirect('guru_siswa')
                    
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
                    
                    return redirect('guru_siswa')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                    return redirect('guru_siswa')

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
            
            'table_columns': ['ID', 'UserID', 'Nama', 'Jenjang', 'Kelas', 'Alamat', 'Username', 'Status'],
            'table_data': table_data,
            
            'jenjang_list': jenjang.objects.all(),
            'kelas_list': kelas.objects.all(),
            
            'edit_data_siswa': edit_data_siswa,
            
            'total_data_table': siswa_filter.count(),
            'API_LINK': reverse('api_siswa_guru') + '?jenjang=' + request.GET.get('jenjang', '') + '&kelas=' + request.GET.get('kelas', ''),
            'print': True,
            'user_is_guru': True,
            'walas': walas,
            'kepsek': kepsek
        })
        return render(request, 'guru/guru_siswa.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('guru_siswa')

@login_required
@guru_required
@require_http_methods(['GET'])
def api_siswa_guru(request):
    try:
        today = timezone.localtime(timezone.now()).date()
        guru = Guru.objects.get(user=request.user)
        
        # Subquery untuk status absensi
        latest_absensi = record_absensi.objects.filter(
            user__siswa=OuterRef('pk'),
            checktime__date=today
        ).order_by('-checktime').values('status', 'status_verifikasi', 'tipe_absensi', 'checktime')[:1]
        
        # Base queryset dengan filter berdasarkan jenjang dan kelas guru
        siswa_list = Siswa.objects.select_related('user', 'jenjang', 'kelas').filter(
            jenjang=guru.jenjang,
            kelas=guru.kelas
        ).annotate(
            today_status=Subquery(latest_absensi.values('status')),
            today_status_verifikasi=Subquery(latest_absensi.values('status_verifikasi')),
            today_tipe_absensi=Subquery(latest_absensi.values('tipe_absensi')),
            today_checktime=Subquery(latest_absensi.values('checktime'))
        )
        
        data = []
        for siswa in siswa_list:
            status = siswa.today_status
            status_verifikasi = siswa.today_status_verifikasi
            tipe_absensi = siswa.today_tipe_absensi
            
            # Logic untuk display status
            if status_verifikasi == 'menunggu':
                display_status = "Belum Diverifikasi"
            elif status_verifikasi == 'ditolak':
                display_status = "Ditolak"
            elif tipe_absensi == 'pulang':
                display_status = "Sudah Pulang"
            elif status == 'hadir' and tipe_absensi == 'masuk':
                absensi = record_absensi.objects.filter(
                    user__siswa__id=siswa.id,
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
                'id': siswa.id,
                'userid': siswa.user.userid,
                'nama': siswa.nama,
                'jenjang': siswa.jenjang.nama if siswa.jenjang else '-',
                'kelas': siswa.kelas.nama if siswa.kelas else '-',
                'alamat': siswa.alamat or '-',
                'username': siswa.user.username,
                'status': display_status
            })
        
        return JsonResponse({'siswa': data}, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)





# Dashboard Kepala Sekolah
@login_required
@guru_required
def admin_dashboard_absensi_siswa_kepsek(request):
    try:
        guru = Guru.objects.get(user=request.user)
    
        walas = guru.wali_kelas
        kepsek = guru.kepala_sekolah
        absensi_records = record_absensi.objects.filter(
            user__siswa__isnull=False, 
            status_verifikasi='diterima'
        ).order_by('-checktime')
        
        absensi_records_charts = record_absensi.objects.filter(
            user__siswa__isnull=False, 
            status_verifikasi='diterima'
        ).order_by('-checktime')

        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        jenjang_selected = request.GET.get('jenjang')
        kelas_selected = request.GET.get('kelas')
        
        if not start_date or not end_date:
            end_date = timezone.localtime(timezone.now()).date()
            start_date = end_date - timezone.timedelta(days=6)
        else:
            try:
                start_date = datetime.strptime(start_date, '%m/%d/%Y').date()
                end_date = datetime.strptime(end_date, '%m/%d/%Y').date()
                messages.info(request, f'Data difilter berdasarkan tanggal: {start_date} - {end_date}')
            except ValueError:
                end_date = timezone.now().date()
                start_date = end_date - timezone.timedelta(days=6)
                messages.error(request, 'Format tanggal tidak valid. Menggunakan rentang tanggal default.')

        absensi_records = absensi_records.filter(
            checktime__date__gte=start_date,
            checktime__date__lte=end_date
        )
        
        absensi_records_charts = absensi_records_charts.filter(
            checktime__date__gte=start_date,
            checktime__date__lte=end_date
        )

        # Filter berdasarkan jenjang
        if jenjang_selected:
            absensi_records = absensi_records.filter(user__siswa__jenjang__nama=jenjang_selected)
            absensi_records_charts = absensi_records_charts.filter(user__siswa__jenjang__nama=jenjang_selected)
            messages.info(request, f'Data difilter berdasarkan jenjang: {jenjang_selected}')

        # Filter berdasarkan kelas
        if kelas_selected:
            absensi_records = absensi_records.filter(user__siswa__kelas__nama=kelas_selected)
            absensi_records_charts = absensi_records_charts.filter(user__siswa__kelas__nama=kelas_selected)
            messages.info(request, f'Data difilter berdasarkan kelas: {kelas_selected}')

        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'tambah':
                try:
                    user_id = request.POST.get('siswa')
                    status = request.POST.get('status')
                    checktime = request.POST.get('checktime')
                    tipe_absensi = request.POST.get('tipe_absensi')
                    
                    user = CustomUser.objects.get(id=user_id)
                    
                    siswa = Siswa.objects.get(user=user)
                    instalasi = Instalasi.objects.first()
                    
                    if status == 'hadir':
                        print(f"user: {user}")
                        # Cek existing record
                        existing_record = record_absensi.objects.filter(
                            user=user,
                            status='hadir',
                            tipe_absensi=tipe_absensi,
                            checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                        ).exists()
                        
                        if existing_record:
                            messages.error(request, f'Sudah ada data absensi {tipe_absensi} untuk hari ini.')
                            return redirect('admin_dashboard_absensi_siswa_kepsek')
                        
                        if tipe_absensi == 'masuk':
                            try:
                                instalasi = Instalasi.objects.first()
                                if not instalasi:
                                    terlambat = 0
                                else:
                                    # Tentukan jam masuk berdasarkan tipe user
                                    jam_masuk = instalasi.jam_masuk_siswa
                                    
                                    if jam_masuk:
                                        # Ambil jam dan menit dari waktu absen
                                        waktu_absen = timezone.make_aware(datetime.strptime(checktime, '%Y-%m-%dT%H:%M')).time()
                                        
                                        # Hitung selisih dalam menit
                                        selisih_menit = (
                                            waktu_absen.hour * 60 + waktu_absen.minute
                                        ) - (
                                            jam_masuk.hour * 60 + jam_masuk.minute
                                        )
                                        
                                        # Set keterlambatan (minimal 0 menit)
                                        terlambat = max(0, selisih_menit)
                                    else:
                                        terlambat = 0
                            except Exception as e:
                                messages.error(request, f'Error menghitung keterlambatan: {str(e)}')
                                terlambat = 0
                                
                        elif tipe_absensi == 'pulang':
                            try:
                                # Ambil jam masuk terakhir siswa
                                jam_masuk = record_absensi.objects.filter(
                                    user=user,
                                    status='hadir',
                                    tipe_absensi='masuk',
                                    checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                                ).latest('checktime')
                                
                                # # Ambil jam kerja dari Instalasi
                                # instalasi = Instalasi.objects.first()
                                # jam_kerja = instalasi.jam_sekolah_siswa
                                
                                # if jam_kerja:
                                #     # Hitung selisih waktu
                                #     waktu_pulang = checktime_aware
                                #     selisih_waktu = waktu_pulang - jam_masuk.checktime
                                    
                                #     if selisih_waktu < jam_kerja:
                                #         messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {jam_kerja} dari jam masuk.')
                                #         return redirect('admin_dashboard_absensi_siswa')
                                terlambat = 0
                            except record_absensi.DoesNotExist:
                                messages.error(request, 'Tidak ada data absensi masuk untuk hari ini. Siswa harus absen masuk terlebih dahulu.')
                                return redirect('admin_dashboard_absensi_siswa_kepsek')

                        # Buat record baru
                        record = record_absensi.objects.create(
                            user=user,
                            status=status,
                            checktime=checktime,
                            status_verifikasi='diterima',
                            tipe_absensi=tipe_absensi,
                            terlambat=terlambat
                        )
                        
                    elif status == 'izin':
                        id_izin = request.POST.get('id_izin')
                        izin_obj = izin.objects.get(id=id_izin)
                        if izin_obj.user != user:
                            messages.error(request, f'Data izin user {user.username} dengan id {id_izin} tidak ditemukan.')
                            return redirect('admin_dashboard_absensi_siswa_kepsek')
                        record = record_absensi.objects.create(
                            user=user,
                            status=status,
                            id_izin=izin_obj,
                            checktime=checktime,
                            status_verifikasi='diterima',
                            tipe_absensi='izin',
                            terlambat=0
                        )
                        
                    elif status == 'sakit':
                        id_sakit = request.POST.get('id_sakit')
                        sakit_obj = sakit.objects.get(id=id_sakit)
                        if sakit_obj.user != user:
                            messages.error(request, f'Data sakit user {user.username} dengan id {id_sakit} tidak ditemukan.')
                            return redirect('admin_dashboard_absensi_siswa_kepsek')
                        record = record_absensi.objects.create(
                            user=user,
                            status=status,
                            id_sakit=sakit_obj,
                            checktime=checktime,
                            status_verifikasi='diterima',
                            tipe_absensi='sakit',
                            terlambat=0
                        )
                        
                    messages.success(request, 'Data absensi berhasil ditambahkan.')
                    
                except CustomUser.DoesNotExist:
                    messages.error(request, f'Pengguna {user_id} tidak ditemukan.')
                except Siswa.DoesNotExist:
                    messages.error(request, 'Data siswa tidak ditemukan.')
                except izin.DoesNotExist:
                    messages.error(request, 'Data izin tidak ditemukan.')
                except sakit.DoesNotExist:
                    messages.error(request, 'Data sakit tidak ditemukan.')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                
                return redirect('admin_dashboard_absensi_siswa_kepsek')
              
            elif action == 'edit':
                absensi_id = request.POST.get('id')
                checktime = request.POST.get('tanggal_waktu')
                status = request.POST.get('status')
                status_verifikasi = request.POST.get('status_verifikasi')
                tipe_absensi = request.POST.get('tipe_absensi')
                
                try:
                    absensi = record_absensi.objects.get(id=absensi_id)
                    user = absensi.user
                    terlambat = 0
                    
                    # Ubah format waktu dengan benar
                    try:
                        checktime_datetime = datetime.strptime(checktime, '%Y-%m-%dT%H:%M')
                        checktime_aware = timezone.make_aware(checktime_datetime)
                        absensi.checktime = checktime_aware
                    except ValueError:
                        messages.error(request, 'Format tanggal dan waktu tidak valid')
                        return redirect('admin_dashboard_absensi_siswa_kepsek')
                        
                    
                    if status == 'izin':
                        id_izin = request.POST.get('id_izin')
                        absensi.id_izin = izin.objects.get(id=id_izin) if id_izin else None
                        absensi.id_sakit = None
                        terlambat = 0
                    elif status == 'sakit':
                        id_sakit = request.POST.get('id_sakit')
                        absensi.id_sakit = sakit.objects.get(id=id_sakit) if id_sakit else None
                        absensi.id_izin = None
                        terlambat = 0
                    else:
                        absensi.id_izin = None
                        absensi.id_sakit = None
                        
                        # Cek apakah sudah ada absensi dengan tipe yang sama untuk hari ini
                        existing_record = record_absensi.objects.filter(
                            user=user,
                            status='hadir',
                            tipe_absensi=tipe_absensi,
                            checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                        ).exclude(id=absensi_id).exists()  # Tambahkan .exclude(id=absensi_id)
                        
                        if existing_record:
                            messages.error(request, f'Sudah ada data absensi {tipe_absensi} untuk hari ini.')
                            return redirect('admin_dashboard_absensi_siswa_kepsek')
                        
                        if tipe_absensi == 'masuk':
                            try:
                                instalasi = Instalasi.objects.first()
                                if not instalasi:
                                    absensi.terlambat = 0
                                else:
                                    # Tentukan jam masuk berdasarkan tipe user
                                    jam_masuk = instalasi.jam_masuk_siswa
                                    
                                    if jam_masuk:
                                        # Ambil jam dan menit dari waktu absen
                                        waktu_absen = checktime_aware.time()
                                        
                                        # Hitung selisih dalam menit
                                        selisih_menit = (
                                            waktu_absen.hour * 60 + waktu_absen.minute
                                        ) - (
                                            jam_masuk.hour * 60 + jam_masuk.minute
                                        )
                                        
                                        # Set keterlambatan (minimal 0 menit)
                                        terlambat = max(0, selisih_menit)
                                        
                                    else:
                                        absensi.terlambat = 0
                            except Exception as e:
                                messages.error(request, f'Error menghitung keterlambatan: {str(e)}')
                                absensi.terlambat = 0
                                
                        elif tipe_absensi == 'pulang':
                            try: 
                                # Ambil jam masuk terakhir siswa
                                jam_masuk = record_absensi.objects.filter(
                                    user=user,
                                    status='hadir',
                                    tipe_absensi='masuk',
                                    checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                                ).latest('checktime')
                                
                                # # Ambil jam kerja dari Instalasi
                                # instalasi = Instalasi.objects.first()
                                # jam_kerja = instalasi.jam_sekolah_siswa
                                
                                # if jam_kerja:
                                #     # Hitung selisih waktu
                                #     waktu_pulang = checktime_aware
                                #     selisih_waktu = waktu_pulang - jam_masuk.checktime
                                    
                                #     if selisih_waktu < jam_kerja:
                                #         messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {jam_kerja} dari jam masuk.')
                                #         return redirect('admin_dashboard_absensi_siswa')
                                terlambat = 0
                            except record_absensi.DoesNotExist:
                                messages.error(request, 'Tidak ada data absensi masuk untuk hari ini. Siswa harus absen masuk terlebih dahulu.')
                                return redirect('admin_dashboard_absensi_siswa_kepsek')
                    absensi.status = status
                    absensi.status_verifikasi = status_verifikasi
                    absensi.tipe_absensi = tipe_absensi
                    absensi.terlambat = terlambat
                    print(f'absensi: {absensi.status}, {absensi.status_verifikasi}, {absensi.tipe_absensi}, {absensi.terlambat}')
                    absensi.save()
                    messages.success(request, 'Data absensi berhasil diperbarui.')
                except record_absensi.DoesNotExist:
                    messages.error(request, 'Data absensi tidak ditemukan.')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                
                return redirect('admin_dashboard_absensi_siswa_kepsek')
              
            elif action == 'hapus':
                selected_ids = request.POST.get('selectedIds')
                if selected_ids:
                    valid_ids = [int(id.strip()) for id in selected_ids.split(',') if id.strip().isdigit()]
                    if valid_ids:
                        deleted_count = record_absensi.objects.filter(id__in=valid_ids).delete()[0]
                        messages.success(request, f'{deleted_count} data absensi berhasil dihapus.')
                    else:
                        messages.error(request, 'Tidak ada ID valid yang dipilih untuk dihapus.')
                else:
                    messages.error(request, 'Tidak ada data yang dipilih untuk dihapus.')
                return redirect('admin_dashboard_absensi_siswa_kepsek')

        daily_counts = absensi_records_charts.annotate(date=TruncDate('checktime')).values('date').annotate(
            hadir=Count('id', filter=Q(status='hadir')),
            sakit=Count('id', filter=Q(status='sakit')),
            izin=Count('id', filter=Q(status='izin'))
        ).order_by('date')
        
        dates = [(start_date + timezone.timedelta(days=x)).strftime('%d') for x in range((end_date - start_date).days + 1)]
        hadir_data = [0] * len(dates)
        sakit_data = [0] * len(dates)
        izin_data = [0] * len(dates)

        for count in daily_counts:
            if count['date'] is not None:
                index = (count['date'] - start_date).days
                if 0 <= index < len(dates):
                    hadir_data[index] = count['hadir']
                    sakit_data[index] = count['sakit']
                    izin_data[index] = count['izin']

        total_hadir = sum(hadir_data)
        total_sakit = sum(sakit_data)
        total_izin = sum(izin_data)
        total_all = total_hadir + total_sakit + total_izin

        hadir_percentage = round((total_hadir / total_all) * 100) if total_all > 0 else 0
        sakit_percentage = round((total_sakit / total_all) * 100) if total_all > 0 else 0
        izin_percentage = round((total_izin / total_all) * 100) if total_all > 0 else 0

        # untuk edit data
        edit_data_absensi_siswa = []
        edit_id = request.GET.get('id')
        if edit_id:
            for record in record_absensi.objects.filter(id=edit_id).select_related('user'):
                siswa = record.user.siswa_set.first()
                record_data = {
                    'id': record.id,
                    'siswa': siswa.nama if siswa else None,
                    'checktime': timezone.localtime(record.checktime).strftime('%Y-%m-%d %H:%M'),
                    'status': record.status,
                    'id_izin': record.id_izin.id if record.id_izin else None,
                    'id_sakit': record.id_sakit.id if record.id_sakit else None,
                    'status_verifikasi': record.status_verifikasi,
                    'tipe_absensi': record.tipe_absensi,
                }
                edit_data_absensi_siswa.append(record_data)

        context = get_context()
        context.update({
            'siswa': True,
            
            # Tambahkan API_LINK ke context
            'API_LINK': reverse('api_dashboard_siswa_kepsek') + f'?start={start_date.strftime("%m/%d/%Y")}&end={end_date.strftime("%m/%d/%Y")}&jenjang={jenjang_selected or ""}&kelas={kelas_selected or ""}',
            
            # Data Series
            'ds_title': 'Statistik Absensi Siswa',
            'ds_percentage': f'{hadir_percentage}%',
            'ds_name_1': 'Hadir',
            'ds_data_1': hadir_data,
            'ds_name_2': 'Sakit',
            'ds_data_2': sakit_data,
            'ds_name_3': 'Izin',
            'ds_data_3': izin_data,
            'ds_categories_json': json.dumps(dates),
            'ds_month': f"{start_date.strftime('%d %B')} - {end_date.strftime('%d %B %Y')}",
            
            # Pie Charts
            'pc_title': 'Statistik Absensi Siswa',
            'pc_month': f"{start_date.strftime('%d %B')} - {end_date.strftime('%d %B %Y')}",
            'pc_data': json.dumps([total_izin, total_sakit, total_hadir]),
            'pc_labels': json.dumps(['Izin', 'Sakit', 'Hadir']),
            
            # Radial Charts
            'rc_title': 'Statistik Absensi Siswa',
            'rc_month': f"{start_date.strftime('%d %B')} - {end_date.strftime('%d %B %Y')}",
            'rc_data_percentage_1': str(hadir_percentage),
            'rc_data_total_1': str(total_hadir),
            'rc_name_1': 'Hadir',
            'rc_data_percentage_2': str(sakit_percentage),
            'rc_data_total_2': str(total_sakit),
            'rc_name_2': 'Sakit',
            'rc_data_percentage_3': str(izin_percentage),
            'rc_data_total_3': str(total_izin),
            'rc_name_3': 'Izin',
            
            'day_ago': (end_date - start_date).days + 1,
            
            # Table data
            'table_columns': ['ID', 'NISN', 'Nama', 'Jenjang', 'Kelas', 'Checktime', 'Status', 'Tipe Absensi', 'Terlambat', 'Mesin'],
            'table_data': absensi_records.values_list(
                'id',
                'user__siswa__nisn',
                'user__siswa__nama',
                'user__siswa__jenjang__nama',
                'user__siswa__kelas__nama',
                'checktime',
                'status',
                'tipe_absensi',
                'terlambat',
                'mesin'
            ),
            
            'start_date': start_date.strftime('%m/%d/%Y'),
            'end_date': end_date.strftime('%m/%d/%Y'),
            'selected_jenjang': jenjang,
            'selected_kelas': kelas,
            
            'total_data_table': absensi_records.count(),
            
            # form tambah record
            'siswa_list': Siswa.objects.all(),
            'id_izin': izin.objects.exclude(record_absensi__id_izin__isnull=False),
            'id_sakit': sakit.objects.exclude(record_absensi__id_sakit__isnull=False),
            
            # form edit record
            'edit_data_absensi_siswa': edit_data_absensi_siswa,
            
            'status_list': ['hadir', 'izin', 'sakit'],
            
            # Kelas dan Jenjang
            'kelas_list': kelas.objects.all(),
            'jenjang_list': jenjang.objects.all(),
            'status_verifikasi_list': ['menunggu', 'diterima', 'ditolak'],
            'tipe_absensi_list': ['masuk', 'pulang'],
            'walas': walas,
            'kepsek': kepsek,
            'user_is_guru': True,
        })
        return render(request, 'Guru/kepsek_dashboard_absensi_siswa.html', context)
        
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_dashboard_absensi_siswa_kepsek')

@login_required
@guru_required
@require_http_methods(['GET'])
def api_dashboard_siswa_kepsek(request):
    try:
        start_date = request.GET.get('start')
        end_date = request.GET.get('amp;end')
        jenjang_selected = request.GET.get('amp;jenjang')
        kelas_selected = request.GET.get('amp;kelas')
        
        if not start_date or not end_date:
            end_date = timezone.localtime(timezone.now()).date()
            start_date = end_date - timezone.timedelta(days=6)
        else:
            try:
                start_date = datetime.strptime(start_date, '%m/%d/%Y').date()
                end_date = datetime.strptime(end_date, '%m/%d/%Y').date()
            except ValueError:
                end_date = timezone.now().date()
                start_date = end_date - timezone.timedelta(days=6)

        absensi_records = record_absensi.objects.filter(
            user__siswa__isnull=False,
            status_verifikasi='diterima',
            checktime__date__gte=start_date,
            checktime__date__lte=end_date
        ).order_by('-checktime')

        # Filter berdasarkan jenjang
        if jenjang_selected:
            absensi_records = absensi_records.filter(user__siswa__jenjang__nama=jenjang_selected)

        # Filter berdasarkan kelas
        if kelas_selected:
            absensi_records = absensi_records.filter(user__siswa__kelas__nama=kelas_selected)

        data = []
        for record in absensi_records:
            # Format keterlambatan
            terlambat_display = '-'
            if record.terlambat and record.terlambat > 0:
                if record.terlambat < 60:
                    terlambat_display = f"{record.terlambat} menit"
                else:
                    jam = record.terlambat // 60
                    menit = record.terlambat % 60
                    if menit > 0:
                        terlambat_display = f"{jam} jam {menit} menit"
                    else:
                        terlambat_display = f"{jam} jam"

            data.append({
                'id': record.id,
                'nisn': record.user.siswa_set.first().nisn,
                'nama': record.user.siswa_set.first().nama,
                'jenjang': record.user.siswa_set.first().jenjang.nama,
                'kelas': record.user.siswa_set.first().kelas.nama,
                'checktime': timezone.localtime(record.checktime).strftime('%Y-%m-%d %H:%M'),
                'status': record.status,
                'tipe_absensi': record.tipe_absensi,
                'terlambat': terlambat_display,
                'mesin': record.mesin or '-'
            })

        return JsonResponse({'absensi': data}, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



@login_required
@guru_required
def admin_dashboard_absensi_guru_kepsek(request):
    try:
        guru = Guru.objects.get(user=request.user)
    
        walas = guru.wali_kelas
        kepsek = guru.kepala_sekolah
        absensi_records = record_absensi.objects.filter(user__guru__isnull=False, status_verifikasi='diterima').order_by('-checktime')
        absensi_records_charts = record_absensi.objects.filter(
            user__guru__isnull=False,
            status_verifikasi='diterima'
        ).order_by('-checktime')

        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        jenjang_selected = request.GET.get('jenjang')
        mata_pelajaran_selected = request.GET.get('mata_pelajaran')
        kelas_selected = request.GET.get('kelas')
        
        # Pastikan start_date dan end_date memiliki nilai default
        if not start_date or not end_date:
            end_date = timezone.localtime(timezone.now()).date()
            start_date = end_date - timezone.timedelta(days=6)
        else:
            try:
                start_date = datetime.strptime(start_date, '%m/%d/%Y').date()
                end_date = datetime.strptime(end_date, '%m/%d/%Y').date()
                messages.info(request, f'Data difilter berdasarkan tanggal: {start_date} - {end_date}')
            except ValueError:
                end_date = timezone.now().date()
                start_date = end_date - timezone.timedelta(days=6)
                messages.error(request, 'Format tanggal tidak valid. Menggunakan rentang tanggal default.')

        # Filter berdasarkan tanggal
        absensi_records = absensi_records.filter(
            checktime__date__gte=start_date,
            checktime__date__lte=end_date
        )
        
        absensi_records_charts = absensi_records_charts.filter(
            checktime__date__gte=start_date,
            checktime__date__lte=end_date
        )

        # Filter tambahan
        filters = {
            'jenjang': ('user__guru__jenjang__nama', jenjang_selected),
            'mata_pelajaran': ('user__guru__mata_pelajaran__nama', mata_pelajaran_selected),
            'kelas': ('user__guru__kelas__nama', kelas_selected)
        }

        for filter_name, (filter_field, filter_value) in filters.items():
            if filter_value:
                absensi_records = absensi_records.filter(**{filter_field: filter_value})
                absensi_records_charts = absensi_records_charts.filter(**{filter_field: filter_value})
                messages.info(request, f'Data difilter berdasarkan {filter_name}: {filter_value}')

        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'tambah':
                try:
                    user_id = request.POST.get('guru')
                    status = request.POST.get('status')
                    checktime = request.POST.get('checktime')
                    tipe_absensi = request.POST.get('tipe_absensi')
                    
                    user = CustomUser.objects.get(id=user_id)
                    guru = Guru.objects.get(user=user)
                    instalasi = Instalasi.objects.first()
                    
                    if status == 'hadir':
                        # Cek existing record
                        existing_record = record_absensi.objects.filter(
                            user=user,
                            status='hadir',
                            tipe_absensi=tipe_absensi,
                            checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                        ).exists()
                        
                        if existing_record:
                            messages.error(request, f'Sudah ada data absensi {tipe_absensi} untuk hari ini.')
                            return redirect('admin_dashboard_absensi_guru_kepsek')
                        
                        if tipe_absensi == 'masuk':
                            try:
                                instalasi = Instalasi.objects.first()
                                if not instalasi:
                                    terlambat = 0
                                else:
                                    # Tentukan jam masuk berdasarkan tipe user
                                    jam_masuk = instalasi.jam_masuk_guru
                                    
                                    if jam_masuk:
                                        # Ambil jam dan menit dari waktu absen
                                        waktu_absen = timezone.make_aware(datetime.strptime(checktime, '%Y-%m-%dT%H:%M')).time()
                                        
                                        # Hitung selisih dalam menit
                                        selisih_menit = (
                                            waktu_absen.hour * 60 + waktu_absen.minute
                                        ) - (
                                            jam_masuk.hour * 60 + jam_masuk.minute
                                        )
                                        
                                        # Set keterlambatan (minimal 0 menit)
                                        terlambat = max(0, selisih_menit)
                                        
                                    else:
                                        terlambat = 0
                            except Exception as e:
                                messages.error(request, f'Error menghitung keterlambatan: {str(e)}')
                                terlambat = 0

                        elif tipe_absensi == 'pulang':
                            try:
                                # Ambil jam masuk terakhir
                                jam_masuk_record = record_absensi.objects.filter(
                                    user=user,
                                    status='hadir',
                                    tipe_absensi='masuk',
                                    checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                                ).latest('checktime')
                                
                                # waktu_pulang = timezone.make_aware(datetime.strptime(checktime, '%Y-%m-%dT%H:%M'))
                                # selisih_waktu = waktu_pulang - jam_masuk_record.checktime
                                
                                # Gunakan jam_kerja_guru dari instalasi
                                # if selisih_waktu < instalasi.jam_kerja_guru:
                                #     messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {instalasi.jam_kerja_guru} dari jam masuk.')
                                #     return redirect('admin_dashboard_absensi_guru')
                                terlambat = 0
                            except record_absensi.DoesNotExist:
                                messages.error(request, 'Tidak ada data absensi masuk untuk hari ini.')
                                return redirect('admin_dashboard_absensi_guru_kepsek')
                        # Buat record baru
                        record = record_absensi.objects.create(
                            user=user,
                            status=status,
                            checktime=checktime,
                            status_verifikasi='diterima',
                            tipe_absensi=tipe_absensi,
                            terlambat=terlambat
                        )
                        
                    elif status == 'izin':
                        id_izin = request.POST.get('id_izin')
                        izin_obj = izin.objects.get(id=id_izin)
                        if izin_obj.user != user:
                            messages.error(request, f'Data izin user {user.username} dengan id {id_izin} tidak ditemukan.')
                            return redirect('admin_dashboard_absensi_guru_kepsek')
                        record = record_absensi.objects.create(
                            user=user,
                            status=status,
                            id_izin=izin_obj,
                            checktime=checktime,
                            status_verifikasi='diterima',
                            tipe_absensi='izin',
                            terlambat=0
                        )
                        
                    elif status == 'sakit':
                        id_sakit = request.POST.get('id_sakit')
                        sakit_obj = sakit.objects.get(id=id_sakit)
                        if sakit_obj.user != user:
                            messages.error(request, f'Data sakit user {user.username} dengan id {id_sakit} tidak ditemukan.')
                            return redirect('admin_dashboard_absensi_guru_kepsek')
                        record = record_absensi.objects.create(
                            user=user,
                            status=status,
                            id_sakit=sakit_obj,
                            checktime=checktime,
                            status_verifikasi='diterima',
                            tipe_absensi='sakit',
                            terlambat=0
                        )
                        
                    messages.success(request, 'Data absensi berhasil ditambahkan.')
                    
                except CustomUser.DoesNotExist:
                    messages.error(request, 'Pengguna tidak ditemukan.')
                except Guru.DoesNotExist:
                    messages.error(request, 'Data guru tidak ditemukan.')
                except izin.DoesNotExist:
                    messages.error(request, 'Data izin tidak ditemukan.')
                except sakit.DoesNotExist:
                    messages.error(request, 'Data sakit tidak ditemukan.')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                
                return redirect('admin_dashboard_absensi_guru_kepsek')
              
            elif action == 'edit':
                absensi_id = request.POST.get('id')
                checktime = request.POST.get('tanggal_waktu')
                status = request.POST.get('status')
                status_verifikasi = request.POST.get('status_verifikasi')
                tipe_absensi = request.POST.get('tipe_absensi')
                
                try:
                    absensi = record_absensi.objects.get(id=absensi_id)
                    user = absensi.user
                    terlambat = 0
                    # Ubah format waktu dengan benar
                    try:
                        checktime_datetime = datetime.strptime(checktime, '%Y-%m-%dT%H:%M')
                        checktime_aware = timezone.make_aware(checktime_datetime)
                        absensi.checktime = checktime_aware
                    except ValueError:
                        messages.error(request, 'Format tanggal dan waktu tidak valid')
                        return redirect('admin_dashboard_absensi_guru_kepsek')
                        
                    if status == 'izin':
                        id_izin = request.POST.get('id_izin')
                        absensi.id_izin = izin.objects.get(id=id_izin) if id_izin else None
                        absensi.id_sakit = None
                        terlambat = 0
                    elif status == 'sakit':
                        id_sakit = request.POST.get('id_sakit')
                        absensi.id_sakit = sakit.objects.get(id=id_sakit) if id_sakit else None
                        absensi.id_izin = None
                        terlambat = 0
                    else:
                        absensi.id_izin = None
                        absensi.id_sakit = None
                        
                        # Cek apakah sudah ada absensi dengan tipe yang sama untuk hari ini
                        existing_record = record_absensi.objects.filter(
                            user=user,
                            status='hadir',
                            tipe_absensi=tipe_absensi,
                            checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                        ).exclude(id=absensi_id).exists()  # Tambahkan .exclude(id=absensi_id)
                        
                        if existing_record:
                            messages.error(request, f'Sudah ada data absensi {tipe_absensi} untuk hari ini.')
                            return redirect('admin_dashboard_absensi_guru_kepsek')
                        
                        if tipe_absensi == 'masuk':
                            try:
                                instalasi = Instalasi.objects.first()
                                if not instalasi:
                                    absensi.terlambat = 0
                                else:
                                    # Tentukan jam masuk berdasarkan tipe user
                                    jam_masuk = instalasi.jam_masuk_guru
                                    
                                    if jam_masuk:
                                        # Ambil jam dan menit dari waktu absen
                                        waktu_absen = checktime_aware.time()
                                        
                                        # Hitung selisih dalam menit
                                        selisih_menit = (
                                            waktu_absen.hour * 60 + waktu_absen.minute
                                        ) - (
                                            jam_masuk.hour * 60 + jam_masuk.minute
                                        )
                                        
                                        # Set keterlambatan (minimal 0 menit)
                                        terlambat = max(0, selisih_menit)
                                        
                                    else:
                                        absensi.terlambat = 0
                            except Exception as e:
                                messages.error(request, f'Error menghitung keterlambatan: {str(e)}')
                                absensi.terlambat = 0
                                
                        elif tipe_absensi == 'pulang':
                            try: 
                                # Ambil jam masuk terakhir guru
                                jam_masuk = record_absensi.objects.filter(
                                    user=user,
                                    status='hadir',
                                    tipe_absensi='masuk',
                                    checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                                ).latest('checktime')
                                
                                # Ambil jam kerja dari Instalasi
                                # instalasi = Instalasi.objects.first()
                                # jam_kerja = instalasi.jam_kerja_guru
                                
                                # if jam_kerja:
                                #     # Hitung selisih waktu
                                #     waktu_pulang = checktime_aware
                                #     selisih_waktu = waktu_pulang - jam_masuk.checktime
                                
                                #     if selisih_waktu < jam_kerja:
                                #         messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {jam_kerja} dari jam masuk.')
                                #         return redirect('admin_dashboard_absensi_guru')
                                terlambat = 0
                            except record_absensi.DoesNotExist:
                                messages.error(request, 'Tidak ada data absensi masuk untuk hari ini. Guru harus absen masuk terlebih dahulu.')
                                return redirect('admin_dashboard_absensi_guru_kepsek')
                    absensi.status = status
                    absensi.status_verifikasi = status_verifikasi
                    absensi.tipe_absensi = tipe_absensi
                    absensi.terlambat = terlambat
                    print(f'absensi: {absensi.status}, {absensi.status_verifikasi}, {absensi.tipe_absensi}, {absensi.terlambat}')
                    absensi.save()
                    messages.success(request, 'Data absensi berhasil diperbarui.')
                except record_absensi.DoesNotExist:
                    messages.error(request, 'Data absensi tidak ditemukan.')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                
                return redirect('admin_dashboard_absensi_guru_kepsek')
              
            elif action == 'hapus':
                selected_ids = request.POST.get('selectedIds')
                if selected_ids:
                    valid_ids = [int(id.strip()) for id in selected_ids.split(',') if id.strip().isdigit()]
                    if valid_ids:
                        deleted_count = record_absensi.objects.filter(id__in=valid_ids).delete()[0]
                        messages.success(request, f'{deleted_count} data absensi berhasil dihapus.')
                    else:
                        messages.error(request, 'Tidak ada ID valid yang dipilih untuk dihapus.')
                else:
                    messages.error(request, 'Tidak ada data yang dipilih untuk dihapus.')
                return redirect('admin_dashboard_absensi_guru_kepsek')

        daily_counts = absensi_records_charts.annotate(date=TruncDate('checktime')).values('date').annotate(
            hadir=Count('id', filter=Q(status='hadir')),
            sakit=Count('id', filter=Q(status='sakit')),
            izin=Count('id', filter=Q(status='izin'))
        ).order_by('date')
        
        dates = [(start_date + timezone.timedelta(days=x)).strftime('%d') for x in range((end_date - start_date).days + 1)]
        hadir_data = [0] * len(dates)
        sakit_data = [0] * len(dates)
        izin_data = [0] * len(dates)

        for count in daily_counts:
            if count['date'] is not None:
                index = (count['date'] - start_date).days
                if 0 <= index < len(dates):
                    hadir_data[index] = count['hadir']
                    sakit_data[index] = count['sakit']
                    izin_data[index] = count['izin']

        total_hadir = sum(hadir_data)
        total_sakit = sum(sakit_data)
        total_izin = sum(izin_data)
        total_all = total_hadir + total_sakit + total_izin

        hadir_percentage = round((total_hadir / total_all) * 100) if total_all > 0 else 0
        sakit_percentage = round((total_sakit / total_all) * 100) if total_all > 0 else 0
        izin_percentage = round((total_izin / total_all) * 100) if total_all > 0 else 0

        # untuk edit data
        edit_data_absensi_guru = []
        edit_id = request.GET.get('id')
        if edit_id:
            for record in record_absensi.objects.filter(id=edit_id).select_related('user'):
                guru = record.user.guru_set.first()
                record_data = {
                    'id': record.id,
                    'guru': guru.nama if guru else None,
                    'checktime': timezone.localtime(record.checktime).strftime('%Y-%m-%d %H:%M'),
                    'status': record.status,
                    'id_izin': record.id_izin.id if record.id_izin else None,
                    'id_sakit': record.id_sakit.id if record.id_sakit else None,
                    'status_verifikasi': record.status_verifikasi,
                    'tipe_absensi': record.tipe_absensi,
                }
                edit_data_absensi_guru.append(record_data)

        context = get_context()
        context.update({
            'guru': True,
            
            # Tambahkan API_LINK ke context
            'API_LINK': reverse('api_dashboard_guru_kepsek') + f'?start={start_date.strftime("%m/%d/%Y")}&end={end_date.strftime("%m/%d/%Y")}',
            
            # Data Series
            'ds_title': 'Statistik Absensi Guru',
            'ds_percentage': f'{hadir_percentage}%',
            'ds_name_1': 'Hadir',
            'ds_data_1': hadir_data,
            'ds_name_2': 'Sakit',
            'ds_data_2': sakit_data,
            'ds_name_3': 'Izin',
            'ds_data_3': izin_data,
            'ds_categories_json': json.dumps(dates),
            'ds_month': f"{start_date.strftime('%d %B')} - {end_date.strftime('%d %B %Y')}",
            
            # Pie Charts
            'pc_title': 'Statistik Absensi Guru',
            'pc_month': f"{start_date.strftime('%d %B')} - {end_date.strftime('%d %B %Y')}",
            'pc_data': json.dumps([total_izin, total_sakit, total_hadir]),
            'pc_labels': json.dumps(['Izin', 'Sakit', 'Hadir']),
            
            # Radial Charts
            'rc_title': 'Statistik Absensi Guru',
            'rc_month': f"{start_date.strftime('%d %B')} - {end_date.strftime('%d %B %Y')}",
            'rc_data_percentage_1': str(hadir_percentage),
            'rc_data_total_1': str(total_hadir),
            'rc_name_1': 'Hadir',
            'rc_data_percentage_2': str(sakit_percentage),
            'rc_data_total_2': str(total_sakit),
            'rc_name_2': 'Sakit',
            'rc_data_percentage_3': str(izin_percentage),
            'rc_data_total_3': str(total_izin),
            'rc_name_3': 'Izin',
            
            'day_ago': (end_date - start_date).days + 1,
            
            # Table data
            'table_columns': ['ID', 'NUPTK', 'Nama Guru', 'Jenjang', 'Kelas', 'Mata Pelajaran', 'Checktime', 'Status', 'Tipe Absensi', 'Terlambat', 'Mesin'],
            'table_data': absensi_records.values_list(
                'id',
                'user__guru__nuptk', 
                'user__guru__nama',
                'user__guru__jenjang__nama',
                'user__guru__kelas__nama',
                'user__guru__mata_pelajaran__nama',
                'checktime',
                'status',
                'tipe_absensi',
                'terlambat',
                'mesin'
            ),
            
            'start_date': start_date.strftime('%m/%d/%Y'),
            'end_date': end_date.strftime('%m/%d/%Y'),
            'selected_jenjang': jenjang_selected,
            'selected_mata_pelajaran': mata_pelajaran_selected,
            'selected_kelas': kelas_selected,
            
            'total_data_table': absensi_records.count(),
            
            # form tambah record
            'guru_list': Guru.objects.all(),
            'id_izin': izin.objects.exclude(record_absensi__id_izin__isnull=False),
            'id_sakit': sakit.objects.exclude(record_absensi__id_sakit__isnull=False),
            
            # form edit record
            'edit_data_absensi_guru': edit_data_absensi_guru,
            
            'status_list': ['hadir', 'izin', 'sakit'],
            
            # Jenjang, Mata Pelajaran, dan Kelas
            'jenjang_list': jenjang.objects.all(),
            'mata_pelajaran_list': mata_pelajaran.objects.all(),
            'kelas_list': kelas.objects.all(),
            'status_verifikasi_list': ['menunggu', 'diterima', 'ditolak'],
            'tipe_absensi_list': ['masuk', 'pulang'],
            'walas': walas,
            'kepsek': kepsek,
            'user_is_guru': True,
        })
        return render(request, 'Guru/kepsek_dashboard_absensi_guru.html', context)
        
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_dashboard_absensi_guru_kepsek')

@login_required
@guru_required
@require_http_methods(['GET'])
def api_dashboard_guru_kepsek(request):
    try:
        start_date = request.GET.get('start')
        end_date = request.GET.get('amp;end')
        jenjang_selected = request.GET.get('jenjang')
        mata_pelajaran_selected = request.GET.get('mata_pelajaran')
        kelas_selected = request.GET.get('kelas')
        
        if not start_date or not end_date:
            end_date = timezone.localtime(timezone.now()).date()
            start_date = end_date - timezone.timedelta(days=6)
        else:
            try:
                start_date = datetime.strptime(start_date, '%m/%d/%Y').date()
                end_date = datetime.strptime(end_date, '%m/%d/%Y').date()
            except ValueError:
                end_date = timezone.now().date()
                start_date = end_date - timezone.timedelta(days=6)

        # Query dasar dengan prefetch_related untuk guru
        absensi_records = record_absensi.objects.filter(
            user__guru__isnull=False,
            status_verifikasi='diterima',
            checktime__date__gte=start_date,
            checktime__date__lte=end_date
        ).select_related('user').prefetch_related('user__guru_set').order_by('-checktime')

        # Filter tambahan
        filters = {
            'jenjang': ('user__guru__jenjang__nama', jenjang_selected),
            'mata_pelajaran': ('user__guru__mata_pelajaran__nama', mata_pelajaran_selected),
            'kelas': ('user__guru__kelas__nama', kelas_selected)
        }

        for filter_name, (filter_field, filter_value) in filters.items():
            if filter_value:
                absensi_records = absensi_records.filter(**{filter_field: filter_value})

        data = []
        for record in absensi_records:
            guru = record.user.guru_set.first()
            
            # Format keterlambatan
            terlambat_display = '-'
            if record.terlambat is not None and record.terlambat > 0:
                if record.terlambat < 60:
                    terlambat_display = f"{record.terlambat} menit"
                else:
                    jam = record.terlambat // 60
                    menit = record.terlambat % 60
                    if menit > 0:
                        terlambat_display = f"{jam} jam {menit} menit"
                    else:
                        terlambat_display = f"{jam} jam"

            data.append({
                'id': record.id,
                'nuptk': guru.nuptk if guru else '-',
                'nama_guru': guru.nama if guru else '-',
                'jenjang': guru.jenjang.nama if guru and guru.jenjang else '-',
                'kelas': guru.kelas.nama if guru and guru.kelas else '-',
                'mata_pelajaran': guru.mata_pelajaran.nama if guru and guru.mata_pelajaran else '-',
                'checktime': timezone.localtime(record.checktime).strftime('%Y-%m-%d %H:%M'),
                'status': record.status,
                'tipe_absensi': record.tipe_absensi,
                'terlambat': terlambat_display,
                'mesin': record.mesin or '-'
            })

        return JsonResponse({'absensi': data}, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
