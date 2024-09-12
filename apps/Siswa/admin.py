from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import *


# Register your models here.
@admin.register(Siswa)
class SiswaAdmin(ModelAdmin):
    pass

