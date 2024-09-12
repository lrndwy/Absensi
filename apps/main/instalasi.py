from django.shortcuts import redirect
from django.templatetags.static import static
from django.utils.safestring import mark_safe

from .models import Instalasi


def get_context():
    context = {}
    data_instalasi = Instalasi.objects.first()
    if data_instalasi and data_instalasi.nama_sekolah:
        context.update({
            'logoimage': data_instalasi.logo.url if data_instalasi.logo else static('images/example_logo.png'),
            'nama_sekolah': data_instalasi.nama_sekolah,
            'alamat': data_instalasi.alamat,
            'deskripsi': data_instalasi.deskripsi,
            'fitur_siswa': data_instalasi.fitur_siswa,
            'fitur_guru': data_instalasi.fitur_guru,
            'fitur_karyawan': data_instalasi.fitur_karyawan,
        })
    return context

def cek_instalasi(view_func):
    def wrapper(request, *args, **kwargs):
        try:
            data_instalasi = Instalasi.objects.first()
            if data_instalasi and data_instalasi.nama_sekolah:
                context = get_context()
                context.update({
                    'logoimage': data_instalasi.logo.url if data_instalasi.logo else static('images/example_logo.png'),
                    'nama_sekolah': data_instalasi.nama_sekolah,
                    'alamat': data_instalasi.alamat,
                    'deskripsi': data_instalasi.deskripsi,
                    'fitur_siswa': data_instalasi.fitur_siswa,
                    'fitur_guru': data_instalasi.fitur_guru,
                    'fitur_karyawan': data_instalasi.fitur_karyawan,
                })
                return view_func(request, *args, **kwargs)
            else:
                return redirect('instalasi')
        except Instalasi.DoesNotExist:
            return redirect('instalasi')
    return wrapper

