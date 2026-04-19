from django.db import models


class InstructorAction(models.Model):
    action_id = models.AutoField(primary_key=True)
    user_id = models.IntegerField(blank=True, null=True)
    action_type = models.CharField(max_length=255, blank=True, null=True)
    action_details = models.TextField(blank=True, null=True)
    team_id = models.IntegerField(blank=True, null=True)
    round_id = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'instructor_actions'

    def __str__(self):
        return f"InstructorAction {self.action_id}: {self.action_type}"


class InstructorEvaluation(models.Model):
    evaluation_id = models.AutoField(primary_key=True)
    instructor_id = models.IntegerField(blank=True, null=True)
    team_id = models.IntegerField(blank=True, null=True)
    round_id = models.IntegerField(blank=True, null=True)
    evaluation_score = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )
    comments = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'instructor_evaluations'

    def __str__(self):
        return f"Evaluation {self.evaluation_id}: Team {self.team_id}, Score {self.evaluation_score}"


class InstructorNote(models.Model):
    note_id = models.AutoField(primary_key=True)
    user_id = models.IntegerField(blank=True, null=True)
    team_id = models.IntegerField(blank=True, null=True)
    round_id = models.IntegerField(blank=True, null=True)
    note_text = models.TextField()
    created_at = models.DateTimeField(blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'instructor_notes'

    def __str__(self):
        return f"Note {self.note_id}: Team {self.team_id}"


class InstructorFeedbackTemplate(models.Model):
    template_id = models.AutoField(primary_key=True)
    template_name = models.CharField(max_length=255)
    feedback_text = models.TextField()
    created_by = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'instructor_feedback_templates'

    def __str__(self):
        return self.template_name


class InstructorScenarioCustomization(models.Model):
    customization_id = models.AutoField(primary_key=True)
    instructor_id = models.IntegerField(blank=True, null=True)
    config_id = models.IntegerField(blank=True, null=True)
    modified_event = models.TextField(blank=True, null=True)
    modified_challenge = models.TextField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'instructor_scenario_customization'

    def __str__(self):
        return f"Customization {self.customization_id}: Instructor {self.instructor_id}"
