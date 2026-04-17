"""
Management command to ingest articles into Qdrant for RAG.

Usage:
    python manage.py ingest_articles --source /home/ubuntu/projects/articles/ --catalog /home/ubuntu/projects/articles/catalog.json
    python manage.py ingest_articles --source /path/ --catalog /path/catalog.json --reset
    python manage.py ingest_articles --source /path/ --catalog /path/catalog.json --limit 10
"""
import json
import os
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Ingest articles into Qdrant for RAG knowledge base.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source', type=str, required=True,
            help='Root directory containing article folders.',
        )
        parser.add_argument(
            '--catalog', type=str, required=True,
            help='Path to catalog.json.',
        )
        parser.add_argument(
            '--reset', action='store_true',
            help='Delete and recreate the Qdrant collection before ingesting.',
        )
        parser.add_argument(
            '--limit', type=int, default=0,
            help='Process only first N articles (for testing).',
        )

    def handle(self, *args, **options):
        source_dir = options['source']
        catalog_path = options['catalog']
        reset = options['reset']
        limit = options['limit']

        # Load catalog
        if not os.path.exists(catalog_path):
            raise CommandError(f'Catalog not found: {catalog_path}')

        with open(catalog_path) as f:
            catalog = json.load(f)

        if limit > 0:
            catalog = catalog[:limit]

        total = len(catalog)
        self.stdout.write(f'Ingesting articles into Qdrant ({settings.QDRANT_COLLECTION})')
        self.stdout.write('─' * 50)

        # Connect to Qdrant
        try:
            from core.rag.client import get_qdrant_client
            client = get_qdrant_client()

            if reset:
                from qdrant_client.models import Distance, VectorParams
                try:
                    client.delete_collection(settings.QDRANT_COLLECTION)
                    self.stdout.write(self.style.WARNING('Collection deleted.'))
                except Exception:
                    pass
                client.create_collection(
                    collection_name=settings.QDRANT_COLLECTION,
                    vectors_config=VectorParams(
                        size=settings.EMBEDDING_DIMENSION,
                        distance=Distance.COSINE,
                    ),
                )
                self.stdout.write(self.style.SUCCESS('Collection recreated.'))
            else:
                # Ensure collection exists
                from core.rag.client import ensure_collection
                ensure_collection()

        except Exception as e:
            raise CommandError(f'Qdrant connection failed: {e}')

        self.stdout.write('')

        # Process articles
        from core.rag.ingest import ingest_article

        processed = 0
        skipped = 0
        total_chunks = 0
        tag_counter = Counter()
        errors = []

        for i, entry in enumerate(catalog):
            filepath = os.path.join(source_dir, entry.get('relative_path', entry.get('filename', '')))
            display_name = entry.get('filename', 'unknown')[:60]

            if not os.path.exists(filepath):
                self.stdout.write(
                    f'[{i+1:3d}/{total}] {display_name} — '
                    f'{self.style.WARNING("SKIPPED (file not found)")}'
                )
                skipped += 1
                errors.append((display_name, 'File not found'))
                continue

            try:
                chunks_uploaded, tags, error_msg = ingest_article(
                    filepath, entry, client, settings.QDRANT_COLLECTION,
                )
            except Exception as e:
                self.stdout.write(
                    f'[{i+1:3d}/{total}] {display_name} — '
                    f'{self.style.ERROR(f"ERROR: {e}")}'
                )
                skipped += 1
                errors.append((display_name, str(e)))
                continue

            if chunks_uploaded == 0:
                self.stdout.write(
                    f'[{i+1:3d}/{total}] {display_name} — '
                    f'{self.style.WARNING(f"SKIPPED ({error_msg})")}'
                )
                skipped += 1
                if error_msg:
                    errors.append((display_name, error_msg))
            else:
                self.stdout.write(
                    f'[{i+1:3d}/{total}] {display_name} — '
                    f'{chunks_uploaded} chunks, {len(tags)} tags'
                    f'{f" ({error_msg})" if error_msg else ""}'
                )
                processed += 1
                total_chunks += chunks_uploaded
                for tag in tags:
                    tag_counter[tag] += chunks_uploaded

        # Summary
        self.stdout.write('')
        self.stdout.write('Summary')
        self.stdout.write('─' * 30)
        self.stdout.write(f'Articles processed: {processed}')
        self.stdout.write(f'Articles skipped: {skipped}')
        self.stdout.write(f'Total chunks uploaded: {total_chunks:,}')

        if tag_counter:
            self.stdout.write('\nTags distribution:')
            for tag, count in tag_counter.most_common():
                self.stdout.write(f'  {tag}: {count} chunks')

        # Check collection count
        try:
            info = client.get_collection(settings.QDRANT_COLLECTION)
            self.stdout.write(f'\nCollection document count: {info.points_count}')
        except Exception:
            pass

        if errors:
            self.stdout.write(f'\nErrors ({len(errors)}):')
            for name, err in errors[:20]:
                self.stdout.write(f'  {name}: {err}')

        # Enable RAG for active scenarios
        self._enable_rag_for_scenarios()

        self.stdout.write(self.style.SUCCESS('\nIngestion complete.'))

    def _enable_rag_for_scenarios(self):
        """Enable RAG config for all active scenarios."""
        from core.models.scenario import ScenarioConfig, Scenario

        for scenario in Scenario.objects.filter(is_active=True):
            ScenarioConfig.objects.update_or_create(
                scenario=scenario,
                config_key='rag_enabled',
                defaults={
                    'config_value': 'true',
                    'description': 'RAG knowledge base is active',
                },
            )
            ScenarioConfig.objects.update_or_create(
                scenario=scenario,
                config_key='max_research_queries_per_round',
                defaults={
                    'config_value': '5',
                    'description': 'Max RAG queries per team per round',
                },
            )
            self.stdout.write(f'Enabled RAG for scenario: {scenario.name}')
