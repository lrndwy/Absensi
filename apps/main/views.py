import json
import time
from datetime import date, datetime
from threading import Thread

import requests
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.Guru.models import Guru
from apps.Karyawan.models import Karyawan
from apps.Siswa.models import Siswa

from .instalasi import cek_instalasi, get_context
from .models import *


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


@cek_instalasi
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Login berhasil.')
            if user.is_superuser:
                return redirect('admin_dashboard')
            elif Siswa.objects.filter(user=user).exists():
                return redirect('siswa_dashboard')
            elif Guru.objects.filter(user=user).exists():
                return redirect('guru_dashboard')
            elif Karyawan.objects.filter(user=user).exists():
                return redirect('karyawan_dashboard')
        else:
            messages.error(request, 'Username atau password salah.')
    context = get_context()
    return render(request, 'main/auth/login.html', context)

def logout_view(request):
    logout(request)
    messages.info(request, 'Anda telah berhasil logout.')
    return redirect('login_view')

def instalasi(request):
    try:
        instalasi = Instalasi.objects.first()
    except Instalasi.DoesNotExist:
        instalasi = None
    
    if request.method == 'POST':
        form = request.POST.get('form')
        
        if form == 'instalasi':
            # Ambil data dasar
            nama_sekolah = request.POST.get('nama_sekolah')
            deskripsi = request.POST.get('deskripsi')
            alamat = request.POST.get('alamat')
            logo = request.FILES.get('logo')
            telegram_token = request.POST.get('telegram_token')
            
            # Ambil status fitur
            fitur_siswa = 'fitur_siswa' in request.POST
            fitur_guru = 'fitur_guru' in request.POST
            fitur_karyawan = 'fitur_karyawan' in request.POST
            
            # Proses jam masuk dan pulang untuk setiap fitur
            jam_masuk_siswa = jam_pulang_siswa = None
            jam_masuk_guru = jam_pulang_guru = None
            jam_masuk_karyawan = jam_pulang_karyawan = None
            
            if fitur_siswa:
                jam_masuk_siswa = datetime.strptime(request.POST.get('jam_masuk_siswa'), '%H:%M').time()
                jam_pulang_siswa = datetime.strptime(request.POST.get('jam_pulang_siswa'), '%H:%M').time()
                
            if fitur_guru:
                jam_masuk_guru = datetime.strptime(request.POST.get('jam_masuk_guru'), '%H:%M').time()
                jam_pulang_guru = datetime.strptime(request.POST.get('jam_pulang_guru'), '%H:%M').time()
                
            if fitur_karyawan:
                jam_masuk_karyawan = datetime.strptime(request.POST.get('jam_masuk_karyawan'), '%H:%M').time()
                jam_pulang_karyawan = datetime.strptime(request.POST.get('jam_pulang_karyawan'), '%H:%M').time()
            
            instalasi = Instalasi.objects.create(
                nama_sekolah=nama_sekolah,
                deskripsi=deskripsi,
                alamat=alamat,
                logo=logo,
                fitur_siswa=fitur_siswa,
                fitur_guru=fitur_guru,
                fitur_karyawan=fitur_karyawan,
                telegram_token=telegram_token,
                jam_masuk_siswa=jam_masuk_siswa,
                jam_pulang_siswa=jam_pulang_siswa,
                jam_masuk_guru=jam_masuk_guru,
                jam_pulang_guru=jam_pulang_guru,
                jam_masuk_karyawan=jam_masuk_karyawan,
                jam_pulang_karyawan=jam_pulang_karyawan
            )
            
            messages.success(request, 'Instalasi berhasil dilakukan.')
            context = get_context()
            context.update({
                'logoimage': instalasi.logo.url if instalasi.logo else static('images/example_logo.png'),
                'nama_sekolah': instalasi.nama_sekolah,
                'alamat': instalasi.alamat,
                'deskripsi': instalasi.deskripsi,
                'fitur_siswa': instalasi.fitur_siswa,
                'fitur_guru': instalasi.fitur_guru,
                'fitur_karyawan': instalasi.fitur_karyawan,
                'create_super_user': True
            })
            return render(request, 'main/instalasi.html', context)
        
        elif form == 'create_super_user':
            username = request.POST.get('username')
            password = request.POST.get('password')
            CustomUser.objects.create_superuser(username=username, password=password)
            messages.success(request, 'Superuser berhasil dibuat.')
            return redirect('admin_dashboard')
        
    if instalasi is not None:
        context = get_context()
        
        # Periksa apakah ada superuser
        if CustomUser.objects.filter(is_superuser=True).exists():
            return redirect('login_view')
        else:
            context.update({
                'create_super_user': True
            })
            return render(request, 'main/instalasi.html', context)
    
    context = get_context()
    context.update({
        'create_super_user': False
    })
    return render(request, 'main/instalasi.html', context)

@csrf_exempt
@require_POST
def webhook_kehadiran(request):
    try:
        data = json.loads(request.body)
        if not isinstance(data, list):
            data = [data]
        
        instalasi = Instalasi.objects.first()
        new_records = []
        messages_to_send = []
        
        for item in data:
            pin = item['pin']
            tanggal = timezone.make_aware(timezone.datetime.fromisoformat(item['date']))
            today = tanggal.date()
            waktu = tanggal.time()
            
            user = CustomUser.objects.filter(userid=pin).first()
            if not user:
                continue
            
            # Tentukan tipe user dan ambil data yang sesuai
            if Siswa.objects.filter(user=user).exists():
                person = Siswa.objects.get(user=user)
                jam_masuk = instalasi.jam_masuk_siswa
                jam_pulang = instalasi.jam_pulang_siswa
                tipe_user = "siswa"
            elif Guru.objects.filter(user=user).exists():
                person = Guru.objects.get(user=user)
                jam_masuk = instalasi.jam_masuk_guru
                jam_pulang = instalasi.jam_pulang_guru
                tipe_user = "guru"
            elif Karyawan.objects.filter(user=user).exists():
                person = Karyawan.objects.get(user=user)
                jam_masuk = instalasi.jam_masuk_karyawan
                jam_pulang = instalasi.jam_pulang_karyawan
                tipe_user = "karyawan"
            else:
                continue

            chat_id = person.telegram_chat_id
            nama = person.nama
            
            # Cek absensi yang sudah ada
            absensi_tanggal_ini = record_absensi.objects.filter(
                user=user,
                checktime__date=today
            )
            absen_masuk = absensi_tanggal_ini.filter(tipe_absensi='masuk').first()
            absen_pulang = absensi_tanggal_ini.filter(tipe_absensi='pulang').first()
            
            # Modifikasi logika penentuan tipe absensi
            if waktu < jam_pulang:
                # Izinkan absen masuk sebelum jam masuk
                tipe_absensi = 'masuk'
                jam_absen = waktu.hour
                menit_absen = waktu.minute
                jam_seharusnya = jam_masuk.hour
                menit_seharusnya = jam_masuk.minute
                
                total_menit_absen = (jam_absen * 60) + menit_absen
                total_menit_seharusnya = (jam_seharusnya * 60) + menit_seharusnya
                
                # Jika absen lebih awal, terlambat = 0
                if total_menit_absen <= total_menit_seharusnya:
                    terlambat = 0
                else:
                    terlambat = total_menit_absen - total_menit_seharusnya
            else:
                tipe_absensi = 'pulang'
                terlambat = 0
            
            # Proses absensi masuk
            if tipe_absensi == 'masuk' and not absen_masuk:
                new_record = record_absensi(
                    user=user,
                    checktime=tanggal,
                    status='hadir',
                    status_verifikasi='diterima',
                    tipe_absensi=tipe_absensi,
                    terlambat=terlambat
                )
                new_records.append(new_record)
                
                if chat_id:
                    keterlambatan_text = f" (terlambat {terlambat} menit)" if terlambat > 0 else ""
                    if tipe_user == "siswa":
                        message = f"Selamat {cek_waktu()} Bapak/Ibu Orang Tua/Wali Murid. Informasi bahwa {nama} {tipe_absensi} pada {today} jam {tanggal.time().strftime('%H.%M.%S')}{keterlambatan_text}"
                    else:
                        message = f"Selamat {cek_waktu()}. Informasi bahwa {nama} telah {tipe_absensi} pada {today} jam {tanggal.time().strftime('%H.%M.%S')}{keterlambatan_text}"
                    messages_to_send.append((chat_id, message))
            
            # Proses absensi pulang
            elif tipe_absensi == 'pulang' and absen_masuk and not absen_pulang:
                new_record = record_absensi(
                    user=user,
                    checktime=tanggal,
                    status='hadir',
                    status_verifikasi='diterima',
                    tipe_absensi=tipe_absensi,
                    terlambat=0
                )
                new_records.append(new_record)
                
                if chat_id:
                    if tipe_user == "siswa":
                        message = f"Selamat {cek_waktu()} Bapak/Ibu Orang Tua/Wali Murid. Informasi bahwa {nama} {tipe_absensi} pada {today} jam {tanggal.time().strftime('%H.%M.%S')}"
                    else:
                        message = f"Selamat {cek_waktu()}. Informasi bahwa {nama} telah {tipe_absensi} pada {today} jam {tanggal.time().strftime('%H.%M.%S')}"
                    messages_to_send.append((chat_id, message))
        
        # Simpan records dan kirim notifikasi
        record_absensi.objects.bulk_create(new_records)
        
        telegram_token = instalasi.telegram_token
        for chat_id, message in messages_to_send:
            try:
                telegram_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage?chat_id={chat_id}&text={message}"
                Thread(target=lambda: requests.get(telegram_url)).start()
                print('Berhasil Mengirim Chat Telegram')
            except Exception as e:
                print(f"Gagal mengirim pesan Telegram ke {chat_id}: {str(e)}")
                continue
        
        return HttpResponse(f"Berhasil mencatat {len(new_records)} kehadiran", status=200)
    except Exception as e:
        return HttpResponse(f"Error dalam memproses webhook: {str(e)}", status=500)

import csv
import json

from django.http import HttpResponse
from openpyxl import Workbook


def export_data(request):
    if request.method == 'POST':
        file_type = request.POST.get('file_type')
        table_data = json.loads(request.POST.get('table_data'))

        if file_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="exported_data.csv"'
            writer = csv.writer(response)
            for row in table_data:
                writer.writerow(row)
            messages.success(request, 'Data berhasil diekspor ke CSV.')
            return response
        elif file_type == 'excel':
            wb = Workbook()
            ws = wb.active
            for row in table_data:
                ws.append(row)
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename="exported_data.xlsx"'
            wb.save(response)
            messages.success(request, 'Data berhasil diekspor ke Excel.')
            return response

    messages.error(request, 'Permintaan tidak valid.')
    return HttpResponse('Invalid request')

