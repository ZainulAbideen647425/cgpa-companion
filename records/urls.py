from django.urls import path

from . import views

urlpatterns = [
    path('semesters/', views.semester_list, name='semester_list'),
    path('semesters/<int:pk>/', views.semester_detail, name='semester_detail'),
    path('semesters/<int:pk>/delete/', views.semester_delete, name='semester_delete'),
    path('courses/<int:pk>/edit/', views.course_edit, name='course_edit'),
    path('courses/<int:pk>/delete/', views.course_delete, name='course_delete'),
    path('planner/', views.planner, name='planner'),
]
