import hashlib

from rest_framework import serializers
from core.models import (
    Team, User, Round, SimulationState,
    SimulationSettings, SimulationParameters, )


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = '__all__'


class RoundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Round
        fields = '__all__'


class SimulationStateSerializer(serializers.ModelSerializer):
    current_round_number = serializers.SerializerMethodField()

    class Meta:
        model = SimulationState
        fields = '__all__'

    def get_current_round_number(self, obj):
        if obj.current_round_id is None:
            return None
        r = Round.objects.filter(round_id=obj.current_round_id).first()
        return r.round_number if r else obj.current_round_id


class SimulationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SimulationSettings
        fields = '__all__'


class SimulationParametersSerializer(serializers.ModelSerializer):
    class Meta:
        model = SimulationParameters
        fields = '__all__'


def _team_name_for(user):
    """The team's name, looked up by id.

    `User.team_id` is a plain IntegerField, not a ForeignKey -- the table is
    unmanaged and the column was never declared as a relation -- so there is no
    `user.team` to traverse and no join to follow.
    """
    from core.models import Team
    if not getattr(user, 'team_id', None):
        return None
    team = Team.objects.filter(pk=user.team_id).first()
    return team.name if team else None


class UserSerializer(serializers.ModelSerializer):
    # `team` was declared here and on the write serializer, and `team_name`
    # sourced from `team.team_name`. Neither exists: DRF raised
    # ImproperlyConfigured on instantiation, so every read through
    # /api/users/ failed. Both now use the integer column the model declares.
    team_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['user_id', 'username', 'role', 'team_id', 'team_name']
        read_only_fields = ['user_id']

    def get_team_name(self, obj):
        return _team_name_for(obj)


class UserWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False,
                                     allow_blank=True)
    team_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['user_id', 'username', 'password', 'role', 'team_id',
                  'team_name']
        read_only_fields = ['user_id']

    def get_team_name(self, obj):
        return _team_name_for(obj)

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        if password:
            validated_data['password_hash'] = hashlib.sha256(
                password.encode()).hexdigest()
        else:
            # Default to empty string for students with no password
            validated_data.setdefault('password_hash', '')
        return super().create(validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        if password is not None and password != '':
            validated_data['password_hash'] = hashlib.sha256(
                password.encode()).hexdigest()
        return super().update(instance, validated_data)


class DashboardSerializer(serializers.Serializer):
    team_id = serializers.IntegerField()
    team_name = serializers.CharField()
    current_round = serializers.IntegerField()
    esg_scores = serializers.DictField(child=serializers.IntegerField())
    financial_summary = serializers.DictField()
    stakeholder_scores = serializers.ListField(child=serializers.DictField())
    leaderboard_rank = serializers.IntegerField(allow_null=True)
    total_programs = serializers.IntegerField()
    sdg_count = serializers.IntegerField(default=0)
    scope_scores = serializers.DictField(child=serializers.FloatField(), required=False, default=dict)
    compliance_status = serializers.CharField(default='no_framework')
    intl_framework_status = serializers.ListField(
        child=serializers.DictField(), required=False, default=list,
    )
    deadline = serializers.DateTimeField(allow_null=True, required=False)
    decisions_locked = serializers.BooleanField(required=False, default=False)
    lock_reason = serializers.CharField(allow_null=True, required=False)
