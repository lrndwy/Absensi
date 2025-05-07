import json
import time
from datetime import date, datetime
from threading import Thread
import os

import requests
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, FileResponse, Http404
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

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
            
    cek_user = request.user
    if cek_user.is_authenticated:
        if cek_user.is_superuser:
            return redirect('admin_dashboard')
        elif Siswa.objects.filter(user=cek_user).exists():
            return redirect('siswa_dashboard')
        elif Guru.objects.filter(user=cek_user).exists():
            return redirect('guru_dashboard')
        elif Karyawan.objects.filter(user=cek_user).exists():
            return redirect('karyawan_dashboard')
          
    context = get_context()
    return render(request, 'main/auth/login.html', context)

@cek_instalasi
def login_ortu_view(request):
    try:
        # Cek jika sudah login sebagai ortu
        if request.user.is_authenticated and request.session.get('is_parent'):
            return redirect('ortu_dashboard')
            
        if request.method == 'POST':
            username = request.POST.get('username')
            password = request.POST.get('password')
            pinortu = request.POST.get('pinortu')
            
            user = authenticate(username=username, password=password)
            if user:
                siswa = Siswa.objects.get(user=user)
                if siswa.pin_ortu == pinortu:
                    # Set session untuk menandai bahwa ini adalah akses orang tua
                    request.session['is_parent'] = True
                    login(request, user)
                    return redirect('ortu_dashboard')
                else:
                    messages.error(request, 'PIN Orang Tua salah.')
            else:
                messages.error(request, 'Username atau password salah.')
                
        context = get_context()
        return render(request, 'main/auth/login_ortu.html', context)
    except Exception as e:
        messages.error(request, str(e))
        return redirect('login_ortu_view')


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
            fitur_ortu = 'fitur_ortu' in request.POST
            
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
                akun_ortu=fitur_ortu,
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
                'fitur_ortu': instalasi.akun_ortu,
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
            
            # Ambil data mesin dari item
            mesin = item.get('mesin', '')  # Default ke string kosong jika tidak ada
            
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
            
            # Tambahkan pengecekan status sakit atau izin
            if absensi_tanggal_ini.filter(status__in=['sakit', 'izin']).exists():
                continue
                
            absen_masuk = absensi_tanggal_ini.filter(tipe_absensi='masuk').first()
            absen_pulang = absensi_tanggal_ini.filter(tipe_absensi='pulang').first()
            
            # Modifikasi logika penentuan tipe absensi
            if waktu < jam_pulang:
                tipe_absensi = 'masuk'
                try:
                    # Konversi waktu absen ke waktu lokal
                    local_checktime = timezone.localtime(tanggal)
                    
                    # Tentukan jam masuk berdasarkan tipe user
                    if hasattr(user, 'siswa'):
                        jam_masuk = instalasi.jam_masuk_siswa
                    elif hasattr(user, 'guru'):
                        jam_masuk = instalasi.jam_masuk_guru
                    elif hasattr(user, 'karyawan'):
                        jam_masuk = instalasi.jam_masuk_karyawan
                    else:
                        print("Debug - Tipe user tidak dikenali")
                        terlambat = 0
                        
                    if not jam_masuk:
                        print(f"Debug - Jam masuk tidak ditemukan untuk user type: {user}")
                        terlambat = 0
                    else:
                        # Ambil jam dan menit dari waktu absen
                        waktu_absen = local_checktime.time()
                        
                        # Hitung selisih dalam menit
                        selisih_menit = (
                            waktu_absen.hour * 60 + waktu_absen.minute
                        ) - (
                            jam_masuk.hour * 60 + jam_masuk.minute
                        )
                        
                        # Set keterlambatan (minimal 0 menit)
                        terlambat = max(0, selisih_menit)
                        
                        print(f"Debug - Jam Masuk: {jam_masuk}")
                        print(f"Debug - Waktu Absen: {waktu_absen}")
                        print(f"Debug - Terlambat: {terlambat} menit")

                except Exception as e:
                    print(f"Error dalam perhitungan keterlambatan: {str(e)}")
                    terlambat = 0
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
                    terlambat=terlambat,
                    mesin=mesin  # Simpan data mesin
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
                    terlambat=0,
                    mesin=mesin  # Simpan data mesin
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



def download_format(request):
    file_type = request.GET.get('file_type')
    import_title = request.GET.get('import_title').lower().replace(' ', '_')
    
    # Base directory untuk file format (gunakan staticfiles)
    base_dir = os.path.join(settings.BASE_DIR, 'static')
    
    if file_type == 'csv':
        file_path = os.path.join(base_dir, 'import_format', 'csv', f'{import_title}.csv')
        content_type = 'text/csv'
        extension = 'csv'
    else:
        file_path = os.path.join(base_dir, 'import_format', 'excel', f'{import_title}.xlsx')
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        extension = 'xlsx'
    
    print(f"Mencoba membuka file: {file_path}") # untuk debugging
    
    if os.path.exists(file_path):
        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="format_{import_title}.{extension}"'
        return response
    else:
        # Tampilkan pesan error yang lebih detail
        raise Http404(f"File tidak ditemukan di lokasi: {file_path}")