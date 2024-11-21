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

from apps.main.instalasi import get_context
from apps.main.models import *

from .models import Guru

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
                'keterlambatan': None
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
    })
    
    return render(request, 'Guru/guru_dashboard.html', context)

@login_required
@guru_required
def guru_statistik(request):
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
        'statistik_user': True
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
    })
    
    return render(request, 'Guru/guru_pengaturan.html', context)
