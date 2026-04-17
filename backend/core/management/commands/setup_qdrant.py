"""
Management command to set up Qdrant collection for RAG.

Usage:
    python manage.py setup_qdrant
    python manage.py setup_qdrant --reset
"""
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create or reset the Qdrant collection for article storage.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete and recreate the collection if it exists.',
        )

    def handle(self, *args, **options):
        reset = options['reset']

        self.stdout.write(f'Qdrant: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}')
        self.stdout.write(f'Collection: {settings.QDRANT_COLLECTION}')
        self.stdout.write(f'Vector dimension: {settings.EMBEDDING_DIMENSION}')
        self.stdout.write('')

        try:
            from core.rag.client import get_qdrant_client
            from qdrant_client.models import Distance, VectorParams

            client = get_qdrant_client()
            collections = [c.name for c in client.get_collections().collections]

            if settings.QDRANT_COLLECTION in collections:
                if reset:
                    self.stdout.write(self.style.WARNING(
                        f'Deleting existing collection "{settings.QDRANT_COLLECTION}"...'
                    ))
                    client.delete_collection(settings.QDRANT_COLLECTION)
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f'Collection "{settings.QDRANT_COLLECTION}" already exists. '
                        f'Use --reset to recreate.'
                    ))
                    return

            self.stdout.write(f'Creating collection "{settings.QDRANT_COLLECTION}"...')
            client.create_collection(
                collection_name=settings.QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIMENSION,
                    distance=Distance.COSINE,
                ),
            )
            self.stdout.write(self.style.SUCCESS(
                f'Collection "{settings.QDRANT_COLLECTION}" created successfully.'
            ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed: {e}'))
