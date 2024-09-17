import json
import time
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
            # Proses instalasi awal
            nama_sekolah = request.POST.get('nama_sekolah')
            deskripsi = request.POST.get('deskripsi')
            alamat = request.POST.get('alamat')
            logo = request.FILES.get('logo')
            fitur_siswa = request.POST.get('fitur_siswa')
            fitur_guru = request.POST.get('fitur_guru')
            fitur_karyawan = request.POST.get('fitur_karyawan')
            
            telegram_token = request.POST.get('telegram_token')
            siswa_fitur = True if fitur_siswa else False
            guru_fitur = True if fitur_guru else False
            karyawan_fitur = True if fitur_karyawan else False

            instalasi = Instalasi.objects.create(
                nama_sekolah=nama_sekolah,
                deskripsi=deskripsi,
                alamat=alamat,
                logo=logo,
                fitur_siswa=siswa_fitur,
                fitur_guru=guru_fitur,
                fitur_karyawan=karyawan_fitur,
                telegram_token=telegram_token
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
        
        # Menggunakan bulk_create untuk efisiensi
        new_records = []
        messages_to_send = []
        
        for item in data:
            pin = item['pin']
            tanggal = timezone.make_aware(timezone.datetime.fromisoformat(item['date']))
            today = tanggal.date()
            
            user = CustomUser.objects.filter(userid=pin).first()
            if not user:
                continue
            
            siswa = Siswa.objects.filter(user=user).first()
            chat_id = siswa.telegram_chat_id if siswa else None
            
            existing_record = record_absensi.objects.filter(
                user=user,
                checktime__date=today
            ).order_by('-checktime').first()
            
            if not existing_record or (tanggal - existing_record.checktime).total_seconds() > 900:  # 15 menit
                new_records.append(record_absensi(
                    user=user,
                    checktime=tanggal,
                    status='hadir',
                    status_verifikasi='diterima'
                ))
                
                if chat_id:
                    status = "masuk" if not existing_record else "pulang"
                    message = f"Selamat {cek_waktu()} Bapak/Ibu Orang Tua/Wali Murid. Informasi bahwa {siswa.nama} {status} pada {today} jam {tanggal.time().strftime('%H.%M.%S')}"
                    messages_to_send.append((chat_id, message))
        
        # Bulk create untuk record absensi
        record_absensi.objects.bulk_create(new_records)
        
        # Kirim pesan Telegram secara asinkron
        telegram_token = Instalasi.objects.first().telegram_token
        for chat_id, message in messages_to_send:
            telegram_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage?chat_id={chat_id}&text={message}"
            Thread(target=lambda: requests.get(telegram_url)).start()
        
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

