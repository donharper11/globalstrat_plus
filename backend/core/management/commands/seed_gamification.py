"""
Management command: seed_gamification

Seeds the achievements and gamification_badges tables with reference data.
Uses SELECT-then-INSERT pattern (no unique constraint on name columns).

Usage:  python manage.py seed_gamification
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone


ACHIEVEMENTS = [
    {
        'name': 'First Revenue',
        'description': 'Generate your first revenue from stakeholder adoption.',
        'criteria': 'revenue > 0 any round',
    },
    {
        'name': 'Revenue Milestone: $100K',
        'description': 'Reach $100,000 in cumulative revenue.',
        'criteria': 'cumulative revenue >= 100000',
    },
    {
        'name': 'Revenue Milestone: $500K',
        'description': 'Reach $500,000 in cumulative revenue.',
        'criteria': 'cumulative revenue >= 500000',
    },
    {
        'name': 'Triple Crown',
        'description': 'Score above zero in all three ESG pillars in a single round.',
        'criteria': 'E > 0 AND S > 0 AND G > 0 same round',
    },
    {
        'name': 'ESG Leader',
        'description': 'Achieve a combined ESG score of 150 or higher.',
        'criteria': 'E + S + G >= 150',
    },
    {
        'name': 'Segment Champion',
        'description': 'Reach an average stakeholder satisfaction of 60% or higher.',
        'criteria': 'avg satisfaction >= 0.60',
    },
    {
        'name': 'Ethical Compass',
        'description': 'Achieve an ethical alignment score of 70 or higher.',
        'criteria': 'ethical_alignment >= 70',
    },
    {
        'name': 'Ethics Architect',
        'description': 'Activate all six components of your Code of Ethics.',
        'criteria': 'team_code_of_ethics count >= 6',
    },
    {
        'name': 'B-Corp Certified',
        'description': 'Earn official B-Corp Certification by meeting all milestones.',
        'criteria': 'bcorp certified == True',
    },
    {
        'name': 'Market Mover',
        'description': 'Capture 500 or more adoption units in a single round.',
        'criteria': 'total_units >= 500 in one round',
    },
    {
        'name': 'Program Diversifier',
        'description': 'Have 3 or more distinct program types active simultaneously.',
        'criteria': '3+ distinct program types active',
    },
]

BADGES = [
    {
        'name': 'ESG Champion',
        'description': 'Awarded each round to the team with the highest combined ESG score.',
        'criteria': 'highest ESG total among all teams this round',
    },
    {
        'name': 'Revenue Growth',
        'description': 'Awarded when your revenue exceeds the previous round.',
        'criteria': 'revenue > previous round revenue',
    },
    {
        'name': 'Environmental Excellence',
        'description': 'Awarded when your Environmental score reaches 80 or higher.',
        'criteria': 'E >= 80',
    },
    {
        'name': 'Social Excellence',
        'description': 'Awarded when your Social score reaches 80 or higher.',
        'criteria': 'S >= 80',
    },
    {
        'name': 'Governance Excellence',
        'description': 'Awarded when your Governance score reaches 80 or higher.',
        'criteria': 'G >= 80',
    },
]


class Command(BaseCommand):
    help = 'Seed achievements and gamification_badges tables with reference data.'

    def handle(self, *args, **options):
        now = timezone.now()
        inserted_ach = 0
        skipped_ach = 0
        inserted_badge = 0
        skipped_badge = 0

        with connection.cursor() as cursor:
            # Seed achievements
            for ach in ACHIEVEMENTS:
                cursor.execute(
                    "SELECT achievement_id FROM achievements "
                    "WHERE achievement_name = %s LIMIT 1",
                    [ach['name']],
                )
                if cursor.fetchone():
                    skipped_ach += 1
                    continue

                cursor.execute(
                    "INSERT INTO achievements "
                    "(achievement_name, description, criteria, created_at) "
                    "VALUES (%s, %s, %s, %s)",
                    [ach['name'], ach['description'], ach['criteria'], now],
                )
                inserted_ach += 1

            # Seed badges
            for badge in BADGES:
                cursor.execute(
                    "SELECT badge_id FROM gamification_badges "
                    "WHERE badge_name = %s LIMIT 1",
                    [badge['name']],
                )
                if cursor.fetchone():
                    skipped_badge += 1
                    continue

                cursor.execute(
                    "INSERT INTO gamification_badges "
                    "(badge_name, description, criteria, created_at) "
                    "VALUES (%s, %s, %s, %s)",
                    [badge['name'], badge['description'], badge['criteria'], now],
                )
                inserted_badge += 1

        self.stdout.write(self.style.SUCCESS(
            f'Achievements: {inserted_ach} inserted, {skipped_ach} skipped (already exist)'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'Badges: {inserted_badge} inserted, {skipped_badge} skipped (already exist)'
        ))
        self.stdout.write(self.style.SUCCESS('Gamification seed complete.'))
