from django.core.management.base import BaseCommand
from django.apps import apps

class Command(BaseCommand):
    help = 'Generate serializers, views, and URLs for all models'

    def handle(self, *args, **kwargs):
        app_name = 'core'
        models = apps.get_app_config(app_name).get_models()

        for model in models:
            model_name = model.__name__
            print(f"Generating API for: {model_name}")

            # Create serializer
            serializer_code = f"""
from rest_framework import serializers
from ..models import {model_name}

class {model_name}Serializer(serializers.ModelSerializer):
    class Meta:
        model = {model_name}
        fields = '__all__'
"""
            # Write to serializers.py
            with open('core/serializers.py', 'a') as f:
                f.write(serializer_code)

            # Create views
            view_code = f"""
from rest_framework import viewsets
from ..models import {model_name}
from ..serializers import {model_name}Serializer

class {model_name}ViewSet(viewsets.ModelViewSet):
    queryset = {model_name}.objects.all()
    serializer_class = {model_name}Serializer
"""
            # Write to views.py
            with open('core/views.py', 'a') as f:
                f.write(view_code)

            # Create URLs
            url_code = f"path('{model_name.lower()}/', {model_name}ViewSet.as_view({{'get': 'list', 'post': 'create'}})),\n"
            with open('core/urls.py', 'a') as f:
                f.write(url_code)

        self.stdout.write(self.style.SUCCESS("API generation complete!"))
