from django.db import models


class Message(models.Model):
    message_id = models.AutoField(primary_key=True)
    sender_name = models.CharField(max_length=255, blank=True, null=True)
    sender_title = models.CharField(max_length=255, blank=True, null=True)
    sender_type = models.CharField(max_length=50, default='system', blank=True, null=True)
    persona_key = models.CharField(max_length=50, blank=True, null=True)
    recipient_type = models.CharField(max_length=50, default='Team', blank=True, null=True)
    recipient_id = models.IntegerField(blank=True, null=True)
    subject = models.CharField(max_length=255, blank=True, null=True)
    message_body = models.TextField(blank=True, null=True)
    round_number = models.IntegerField(blank=True, null=True)
    severity = models.CharField(max_length=20, blank=True, null=True)
    source = models.CharField(max_length=50, blank=True, null=True)
    avatar_image = models.CharField(max_length=255, blank=True, null=True)
    parent_message_id = models.IntegerField(blank=True, null=True)
    thread_root_id = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    due_date = models.DateTimeField(blank=True, null=True)
    escalation_triggered = models.BooleanField(default=False, blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'messages'

    def __str__(self):
        return self.subject or f"Message {self.message_id}"


class MessageResponse(models.Model):
    response_id = models.AutoField(primary_key=True)
    message_id = models.IntegerField(blank=True, null=True)
    team_id = models.IntegerField(blank=True, null=True)
    response_text = models.TextField(blank=True, null=True)
    impact_on_scores = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    feedback = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'message_responses'

    def __str__(self):
        return f"Response {self.response_id}: Message {self.message_id}, Team {self.team_id}"


class MessageThread(models.Model):
    thread_id = models.AutoField(primary_key=True)
    root_message_id = models.IntegerField(blank=True, null=True)
    follow_up_message_id = models.IntegerField(blank=True, null=True)
    thread_status = models.CharField(max_length=50, default='Open', blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    team_id = models.IntegerField(blank=True, null=True)
    round_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'message_threads'

    def __str__(self):
        return f"Thread {self.thread_id}: Root {self.root_message_id}, Status {self.thread_status}"


class TeamNotification(models.Model):
    notification_id = models.AutoField(primary_key=True)
    team_id = models.IntegerField(blank=True, null=True)
    round_id = models.IntegerField(blank=True, null=True)
    notification_text = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'team_notifications'

    def __str__(self):
        return f"TeamNotification {self.notification_id}: Team {self.team_id}"


class NotificationLog(models.Model):
    notification_id = models.AutoField(primary_key=True)
    recipient_type = models.CharField(max_length=50, blank=True, null=True)
    recipient_id = models.IntegerField(blank=True, null=True)
    notification_text = models.TextField()
    round_id = models.IntegerField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'notification_logs'

    def __str__(self):
        return f"NotificationLog {self.notification_id}: {self.recipient_type} {self.recipient_id}"
