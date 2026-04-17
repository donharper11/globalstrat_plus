"""
Management command to check Qdrant connection and collection status.

Usage:
    python manage.py check_qdrant
"""
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Check Qdrant connection status and collection info.'

    def handle(self, *args, **options):
        self.stdout.write('=== Qdrant Health Check ===\n')
        self.stdout.write(f'Host: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}')
        self.stdout.write(f'Collection: {settings.QDRANT_COLLECTION}')
        self.stdout.write(f'Embedding model: {settings.EMBEDDING_MODEL}')
        self.stdout.write(f'Embedding dimension: {settings.EMBEDDING_DIMENSION}')
        self.stdout.write('')

        # Test connection
        try:
            from core.rag.client import get_qdrant_client
            client = get_qdrant_client()
            collections = [c.name for c in client.get_collections().collections]
            self.stdout.write(self.style.SUCCESS('Connection: OK'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Connection: FAILED — {e}'))
            return

        # Check collection
        if settings.QDRANT_COLLECTION in collections:
            self.stdout.write(self.style.SUCCESS(
                f'Collection "{settings.QDRANT_COLLECTION}": EXISTS'
            ))
            try:
                info = client.get_collection(settings.QDRANT_COLLECTION)
                self.stdout.write(f'  Points count: {info.points_count}')
                if hasattr(info, 'vectors_count'):
                    self.stdout.write(f'  Vectors count: {info.vectors_count}')
            except Exception as e:
                self.stdout.write(f'  Could not fetch details: {e}')
        else:
            self.stdout.write(self.style.WARNING(
                f'Collection "{settings.QDRANT_COLLECTION}": NOT FOUND'
            ))
            self.stdout.write('  Run "python manage.py setup_qdrant" to create it.')

        # Check embedding model availability
        self.stdout.write('')
        if settings.EMBEDDING_MODEL.startswith('BAAI/'):
            try:
                from sentence_transformers import SentenceTransformer
                self.stdout.write(self.style.SUCCESS(
                    'Embedding library (sentence-transformers): AVAILABLE'
                ))
            except ImportError:
                self.stdout.write(self.style.WARNING(
                    'Embedding library (sentence-transformers): NOT INSTALLED'
                ))
                self.stdout.write(
                    '  pip install sentence-transformers --break-system-packages'
                )
        else:
            if settings.DASHSCOPE_API_KEY:
                self.stdout.write(self.style.SUCCESS('DashScope API key: CONFIGURED'))
            else:
                self.stdout.write(self.style.WARNING('DashScope API key: NOT SET'))
