from rest_framework import serializers
from .models import LeituraPalmilha

class LeituraPalmilhaSerializer(serializers.ModelSerializer) :
    class Meta :
        model = LeituraPalmilha
        fields = '__all__'