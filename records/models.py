from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Semester(models.Model):
    """A student's semester/term. Always owned by exactly one user."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='semesters')
    name = models.CharField(max_length=80)
    position = models.PositiveIntegerField(default=0)   # chronological order, 1 = first
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'id']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='uniq_semester_name_per_user'),
        ]

    def __str__(self):
        return self.name


class CourseEntry(models.Model):
    """A course taken in a semester. A blank grade means "not graded yet"."""
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='courses')
    code = models.CharField(max_length=20, blank=True)      # same code in two semesters = a retake
    name = models.CharField(max_length=120)
    credit_hours = models.DecimalField(
        max_digits=4, decimal_places=1,
        validators=[MinValueValidator(0), MaxValueValidator(30)])
    grade = models.CharField(max_length=4, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.name} ({self.grade or "ungraded"})'
