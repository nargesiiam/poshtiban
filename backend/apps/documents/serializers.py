from rest_framework import serializers

from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "title", "file", "ingestion_status", "created_at"]
        read_only_fields = ["id", "ingestion_status", "created_at"]
