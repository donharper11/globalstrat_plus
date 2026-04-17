from django.db import models


class GradingRubric(models.Model):
    rubric_id = models.AutoField(primary_key=True)
    course_id = models.IntegerField()
    rubric_name = models.CharField(max_length=200, default='Default Rubric')
    is_active = models.BooleanField(default=True)
    created_by = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'grading_rubric'

    def __str__(self):
        return f"{self.rubric_name} (Course {self.course_id})"


class GradingRubricCategory(models.Model):
    category_id = models.AutoField(primary_key=True)
    rubric = models.ForeignKey(
        GradingRubric, on_delete=models.CASCADE,
        db_column='rubric_id', related_name='categories',
    )
    category_name = models.CharField(max_length=200)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sort_order = models.IntegerField(default=0)
    description = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'grading_rubric_category'
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.category_name} ({self.weight}%)"


class GradingComponentMapping(models.Model):
    mapping_id = models.AutoField(primary_key=True)
    category = models.ForeignKey(
        GradingRubricCategory, on_delete=models.CASCADE,
        db_column='category_id', related_name='components',
    )
    component_key = models.CharField(max_length=100)
    component_weight = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    score_transform = models.CharField(max_length=50, default='linear')
    threshold_value = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
    )
    description = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'grading_component_mapping'

    def __str__(self):
        return f"{self.component_key} ({self.component_weight}%)"


class TeamGrade(models.Model):
    grade_id = models.AutoField(primary_key=True)
    instance_id = models.IntegerField()
    team_id = models.IntegerField()
    category_id = models.IntegerField(blank=True, null=True)
    computed_score = models.DecimalField(
        max_digits=6, decimal_places=2, blank=True, null=True,
    )
    override_score = models.DecimalField(
        max_digits=6, decimal_places=2, blank=True, null=True,
    )
    final_score = models.DecimalField(
        max_digits=6, decimal_places=2, blank=True, null=True,
    )
    instructor_comments = models.TextField(blank=True, null=True)
    graded_by = models.IntegerField(blank=True, null=True)
    graded_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'team_grade'
        unique_together = (('instance_id', 'team_id', 'category_id'),)

    def __str__(self):
        return f"Grade: Team {self.team_id}, Final {self.final_score}"


class StudentGradeAdjustment(models.Model):
    adjustment_id = models.AutoField(primary_key=True)
    instance_id = models.IntegerField()
    user_id = models.IntegerField()
    team_id = models.IntegerField()
    adjustment_type = models.CharField(max_length=100, default='participation')
    adjustment_value = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
    )
    reason = models.TextField(blank=True, null=True)
    adjusted_by = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'student_grade_adjustment'
        unique_together = (('instance_id', 'user_id', 'adjustment_type'),)

    def __str__(self):
        return f"Adj: User {self.user_id} ({self.adjustment_value:+})"
