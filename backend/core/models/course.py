from django.db import models


class Course(models.Model):
    course_id = models.AutoField(primary_key=True)
    course_code = models.CharField(unique=True, max_length=20)
    course_name = models.CharField(max_length=200)
    instructor_id = models.IntegerField(blank=True, null=True)
    academic_year = models.CharField(max_length=20, blank=True, null=True)
    semester = models.CharField(max_length=20, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'course'

    def __str__(self):
        return f"{self.course_code} — {self.course_name}"


class Section(models.Model):
    section_id = models.AutoField(primary_key=True)
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE,
        db_column='course_id', related_name='sections',
    )
    section_code = models.CharField(max_length=20)
    section_name = models.CharField(max_length=200, blank=True, null=True)
    max_teams = models.IntegerField(default=8)
    team_size_min = models.IntegerField(default=3)
    team_size_max = models.IntegerField(default=5)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'section'
        unique_together = (('course', 'section_code'),)

    def __str__(self):
        return f"{self.section_code} — {self.section_name or ''}"


class SimulationInstance(models.Model):
    instance_id = models.AutoField(primary_key=True)
    section = models.OneToOneField(
        Section, on_delete=models.CASCADE,
        db_column='section_id', related_name='simulation',
    )
    game_id = models.IntegerField(blank=True, null=True)
    current_round = models.IntegerField(default=0)
    total_rounds = models.IntegerField(default=10)
    status = models.CharField(max_length=20, default='setup')
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    settings = models.JSONField(default=dict, blank=True)
    auto_advance = models.BooleanField(default=False)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'simulation_instance'

    def __str__(self):
        return f"Instance {self.instance_id} — Section {self.section_id} ({self.status})"


class Enrollment(models.Model):
    enrollment_id = models.AutoField(primary_key=True)
    user_id = models.IntegerField()
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE,
        db_column='section_id', related_name='enrollments',
    )
    team_id = models.IntegerField(blank=True, null=True)
    enrolled_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    onboarding_completed = models.BooleanField(default=False)
    language = models.CharField(max_length=10, default='en', blank=True)

    class Meta:
        managed = False
        db_table = 'enrollment'
        unique_together = (('user_id', 'section'),)

    def __str__(self):
        return f"Enrollment {self.enrollment_id}: User {self.user_id} → Section {self.section_id}"
