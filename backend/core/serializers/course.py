from rest_framework import serializers
from core.models import Course, Section, SimulationInstance, Enrollment, Team, User


# ---------------------------------------------------------------------------
# Course
# ---------------------------------------------------------------------------

class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = '__all__'


class CourseListSerializer(serializers.ModelSerializer):
    section_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Course
        fields = [
            'course_id', 'course_code', 'course_name',
            'instructor_id', 'academic_year', 'semester',
            'is_active', 'created_at', 'section_count',
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Section
# ---------------------------------------------------------------------------

class SectionSerializer(serializers.ModelSerializer):
    # Accept course_id from frontend (maps to the 'course' FK)
    course = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.all(),
        source=None,  # keep default
    )

    class Meta:
        model = Section
        fields = '__all__'

    def to_internal_value(self, data):
        # Map course_id -> course so frontend can send either name
        if 'course_id' in data and 'course' not in data:
            data = {**data, 'course': data.pop('course_id')}
        return super().to_internal_value(data)


class SectionDetailSerializer(serializers.ModelSerializer):
    simulation_status = serializers.SerializerMethodField()
    student_count = serializers.IntegerField(read_only=True)
    team_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Section
        fields = [
            'section_id', 'course', 'section_code', 'section_name',
            'max_teams', 'team_size_min', 'team_size_max',
            'is_active', 'created_at',
            'simulation_status', 'student_count', 'team_count',
        ]
        read_only_fields = fields

    def get_simulation_status(self, obj):
        """Return the simulation instance status, or None if no instance exists."""
        sim = getattr(obj, 'simulation', None)
        if sim is None:
            # Attempt a query only when the reverse relation was not prefetched
            try:
                sim = SimulationInstance.objects.get(section_id=obj.section_id)
            except SimulationInstance.DoesNotExist:
                return None
        return {
            'instance_id': sim.instance_id,
            'current_round': sim.current_round,
            'total_rounds': sim.total_rounds,
            'status': sim.status,
            'started_at': sim.started_at,
            'completed_at': sim.completed_at,
            'auto_advance': sim.auto_advance,
        }


# ---------------------------------------------------------------------------
# SimulationInstance
# ---------------------------------------------------------------------------

class SimulationInstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SimulationInstance
        fields = '__all__'


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------

class EnrollmentSerializer(serializers.ModelSerializer):
    # Read-only nested fields for convenience on GET responses
    display_name = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    team_name = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = [
            'enrollment_id', 'user_id', 'section', 'team_id',
            'enrolled_at', 'is_active',
            'display_name', 'username', 'student_id', 'email', 'team_name',
        ]

    def _get_user(self, obj):
        # Cache user lookups on the instance to avoid repeated queries
        if not hasattr(obj, '_cached_user'):
            obj._cached_user = User.objects.filter(user_id=obj.user_id).first()
        return obj._cached_user

    def get_display_name(self, obj):
        user = self._get_user(obj)
        return user.display_name if user else None

    def get_username(self, obj):
        user = self._get_user(obj)
        return user.username if user else None

    def get_student_id(self, obj):
        user = self._get_user(obj)
        return user.student_id if user else None

    def get_email(self, obj):
        user = self._get_user(obj)
        return user.email if user else None

    def get_team_name(self, obj):
        if obj.team_id is None:
            return None
        try:
            team = Team.objects.get(id=obj.team_id)
            return team.name
        except Team.DoesNotExist:
            return None


# ---------------------------------------------------------------------------
# Roster & Team generation helpers
# ---------------------------------------------------------------------------

class RosterUploadSerializer(serializers.Serializer):
    csv = serializers.CharField(
        help_text='CSV content with student roster data.',
    )


class TeamGenerateSerializer(serializers.Serializer):
    METHOD_CHOICES = [
        ('random', 'Random'),
        ('alphabetical', 'Alphabetical'),
    ]

    method = serializers.ChoiceField(choices=METHOD_CHOICES)
    team_name_prefix = serializers.CharField(
        default='Team',
        required=False,
        help_text='Prefix used when generating team names (e.g. "Team" → Team 1, Team 2, …).',
    )
