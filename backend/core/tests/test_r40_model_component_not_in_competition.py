"""R40 (2026-09-21): a model-scored grading component is an instructor option
for ordinary classes and may not reach a competition heat's grade.

R31 severed the model from the coherence score. `communication_quality` is the
second route: it averages the model's `overall_score` straight into a rubric
category. The owner kept it, outside the competition.
"""
from decimal import Decimal

from django.utils import timezone

from core.models.course import SimulationInstance
from core.models.grading import (
    GradingRubric, GradingRubricCategory, GradingComponentMapping, TeamGrade,
)
from core.services import grading
from core.tests.test_cohort_caps import CohortCapTestBase


class ModelComponentCompetitionGuardTests(CohortCapTestBase):

    def _heat(self, *, competition, component):
        instructor = self._instructor('r40')
        course, section = self._make_section(
            instructor_id=instructor.pk, tag='R40')
        instance = SimulationInstance.objects.create(
            section_id=section.section_id, current_round=1, total_rounds=5,
            status='active',
            settings={'is_competition': True} if competition else {})
        rubric = GradingRubric.objects.create(
            course_id=course.course_id, rubric_name='R40', is_active=True,
            created_at=timezone.now(), updated_at=timezone.now())
        category = GradingRubricCategory.objects.create(
            rubric_id=rubric.rubric_id, category_name='Writing',
            weight=Decimal('100.00'), sort_order=1)
        GradingComponentMapping.objects.create(
            category_id=category.category_id, component_key=component,
            component_weight=Decimal('100.00'), score_transform='linear')
        return instructor, course, instance

    def test_a_competition_heat_refuses_a_model_scored_component(self):
        _, course, instance = self._heat(
            competition=True, component='communication_quality')
        with self.assertRaises(grading.ModelDerivedComponentInCompetition):
            grading.calculate_team_grades(instance.instance_id, course.course_id)
        # Refused before anything was written.
        self.assertFalse(
            TeamGrade.objects.filter(instance_id=instance.instance_id).exists())

    def test_an_ordinary_class_keeps_the_instructor_option(self):
        _, course, instance = self._heat(
            competition=False, component='communication_quality')
        grading.calculate_team_grades(instance.instance_id, course.course_id)

    def test_a_competition_heat_still_grades_deterministic_components(self):
        _, course, instance = self._heat(
            competition=True, component='performance_index')
        grading.calculate_team_grades(instance.instance_id, course.course_id)

    def test_the_instructor_is_told_why_in_the_response(self):
        instructor, course, instance = self._heat(
            competition=True, component='communication_quality')
        response = self._client(instructor).post(
            '/api/grades/calculate/',
            {'instance_id': instance.instance_id,
             'course_id': course.course_id}, format='json')
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['code'],
                         'model_derived_component_in_competition')
        self.assertIn('Communication Quality', response.json()['error'])

    def test_every_model_scored_extractor_is_listed(self):
        """A new extractor that reads a model evaluation must join the set."""
        import inspect
        for key, extractor in grading.COMPONENT_EXTRACTORS.items():
            reads_model = 'evaluation' in inspect.getsource(extractor)
            self.assertEqual(
                reads_model, key in grading.MODEL_DERIVED_COMPONENTS, key)
