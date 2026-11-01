from django.contrib import admin

from .models import CourseEntry, Semester

admin.site.register(Semester)
admin.site.register(CourseEntry)
