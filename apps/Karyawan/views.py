import json
from datetime import datetime, timedelta
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.utils import timezone
from django.contrib import messages

from apps.Karyawan.models import Karyawan
from apps.main.instalasi import get_context
from apps.main.models import CustomUser, Instalasi, izin, record_absensi, sakit


def get_karyawan_absensi_hari_ini(karyawan):
    hari_ini = timezone.localtime(timezone.now()).date()
    try:
        absensi_hari_ini = record_absensi.objects.filter(
            user=karyawan.user,
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

def karyawan_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Anda harus login terlebih dahulu.')
            return redirect('login_view')
        try:
            karyawan = Karyawan.objects.get(user=request.user)
        except Karyawan.DoesNotExist:
            messages.error(request, 'Anda tidak memiliki akses sebagai karyawan.')
            return redirect('login_view')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@login_required
@karyawan_required
def karyawan_dashboard(request):
    karyawan = Karyawan.objects.get(user=request.user)
    if request.method == 'POST':
        status_absensi = request.POST.get('status_absensi')
        keterangan = request.POST.get('keterangan')
        
        if status_absensi in ['sakit', 'izin']:
            if status_absensi == 'sakit':
                surat_sakit = request.FILES.get('surat_sakit')
                sakit_obj = sakit.objects.create(user=request.user, keterangan=keterangan, surat_sakit=surat_sakit)
                record_absensi.objects.create(user=request.user, status='sakit', id_sakit=sakit_obj, checktime=timezone.now(), status_verifikasi='menunggu')
                messages.success(request, 'Absensi sakit berhasil disubmit.')
            else:  # izin
                izin_obj = izin.objects.create(user=request.user, keterangan=keterangan)
                record_absensi.objects.create(user=request.user, status='izin', id_izin=izin_obj, checktime=timezone.now(), status_verifikasi='menunggu')
                messages.success(request, 'Absensi izin berhasil disubmit.')
            
            return redirect('karyawan_dashboard')
        else:
            messages.error(request, 'Status absensi tidak valid.')

    status_absensi = get_karyawan_absensi_hari_ini(karyawan)
    context = get_context()
    context.update({
        'status_absensi': status_absensi['status'],
        'status_verifikasi': status_absensi['status_verifikasi'],
        'user_is_karyawan': True,
    })
    
    return render(request, 'Karyawan/karyawan_dashboard.html', context)

@login_required
@karyawan_required
def karyawan_statistik(request):
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
    
    hadir_percentage = round((total_hadir / total_all) * 100, 2) if total_all > 0 else 0
    sakit_percentage = round((total_sakit / total_all) * 100, 2) if total_all > 0 else 0
    izin_percentage = round((total_izin / total_all) * 100, 2) if total_all > 0 else 0
    tanpa_keterangan_percentage = round((total_tanpa_keterangan / total_all) * 100, 2) if total_all > 0 else 0
    
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
        'user_is_karyawan': True,
    })
    
    messages.info(request, f'Menampilkan statistik absensi dari {start_date.strftime("%d %B %Y")} sampai {end_date.strftime("%d %B %Y")}.')
    return render(request, 'Karyawan/karyawan_statistik.html', context)
