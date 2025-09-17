from rest_framework import serializers
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import datetime

# ===============================
# Simple serializers for sensors
# ===============================

class TemperatureSerializer(serializers.Serializer):
    temperature = serializers.FloatField(min_value=-50, max_value=150)
    timestamp = serializers.DateTimeField(default=datetime.now, read_only=True)

class DistanceSerializer(serializers.Serializer):
    distance = serializers.FloatField(min_value=0, max_value=8000)  # TF Luna max range ~8m
    timestamp = serializers.DateTimeField(default=datetime.now, read_only=True)

class WeightSerializer(serializers.Serializer):
    weight = serializers.FloatField(min_value=0, max_value=10000)  # Adjust max based on your loadcell
    timestamp = serializers.DateTimeField(default=datetime.now, read_only=True)

# Combined sensor data serializer
class SensorDataSerializer(serializers.Serializer):
    temperature = serializers.FloatField(required=False, allow_null=True)
    distance = serializers.IntegerField(required=False, allow_null=True)
    weight = serializers.FloatField(required=False, allow_null=True)
    timestamp = serializers.DateTimeField(default=datetime.now, read_only=True)

# Response serializers for GET endpoints
class TemperatureResponseSerializer(serializers.Serializer):
    temperature = serializers.FloatField()

class DistanceResponseSerializer(serializers.Serializer):
    distance = serializers.IntegerField()

class WeightResponseSerializer(serializers.Serializer):
    weight = serializers.FloatField()

# Status response serializer
class StatusResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField(required=False)


# ===============================
# ESP32 serializers with BMI logic
# ===============================

class ESP32DataSerializer(serializers.Serializer):
    """
    Serializer for ESP32 measurement data
    """
    weight = serializers.FloatField(
        validators=[
            MinValueValidator(0.1, message="Weight must be greater than 0.1 kg"),
            MaxValueValidator(50000.0, message="Weight cannot exceed 50000 kg")
        ],
        help_text="Weight in kilograms"
    )

    height = serializers.FloatField(
        validators=[
            MinValueValidator(30.0, message="Height must be at least 30 cm"),
            MaxValueValidator(300.0, message="Height cannot exceed 300 cm")
        ],
        help_text="Height in centimeters"
    )

    temperature = serializers.FloatField(
        validators=[
            MinValueValidator(25.0, message="Temperature must be at least 25°C"),
            MaxValueValidator(45.0, message="Temperature cannot exceed 45°C")
        ],
        help_text="Body temperature in Celsius"
    )

    device_id = serializers.CharField(
        max_length=50,
        default="ESP32_BMI_Station",
        help_text="Unique identifier for the ESP32 device"
    )

    timestamp = serializers.IntegerField(
        required=False,
        help_text="ESP32 millis() timestamp"
    )

    bmi = serializers.FloatField(
        required=False,
        validators=[
            MinValueValidator(10.0),
            MaxValueValidator(10000.0)
        ],
        help_text="Calculated BMI value"
    )

    bmi_category = serializers.CharField(
        max_length=20,
        required=False,
        help_text="BMI category (Underweight, Normal, Overweight, Obese)"
    )

    temperature_status = serializers.CharField(
        max_length=20,
        required=False,
        help_text="Temperature status (Normal, Fever, etc.)"
    )

    def validate(self, data):
        """
        Custom validation for the entire data set
        """
        weight = data.get('weight')
        height = data.get('height')
        temperature = data.get('temperature')

        # Validate BMI
        if 'bmi' in data and weight and height:
            height_m = height / 100.0
            calculated_bmi = weight / (height_m * height_m)
            provided_bmi = data['bmi']

            if abs(calculated_bmi - provided_bmi) > 0.1:
                raise serializers.ValidationError(
                    f"BMI mismatch. Expected: {calculated_bmi:.2f}, Got: {provided_bmi:.2f}"
                )

        # Validate temperature status
        temp_status = data.get('temperature_status', '').lower()
        if temp_status:
            if temp_status == 'normal' and not (36.1 <= temperature <= 37.2):
                raise serializers.ValidationError(
                    "Temperature marked as 'normal' but value is outside normal range (36.1–37.2°C)"
                )
            elif temp_status in ['fever', 'high fever'] and temperature < 37.3:
                raise serializers.ValidationError(
                    "Temperature marked as fever but below fever threshold (37.3°C)"
                )

        return data

    def to_representation(self, instance):
        """
        Customize output
        """
        data = super().to_representation(instance)

        if 'weight' in data and 'height' in data:
            weight = data['weight']
            height_m = data['height'] / 100.0
            data['calculated_bmi'] = round(weight / (height_m * height_m), 2)

        if 'timestamp' in data and data['timestamp']:
            data['readable_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return data


class ESP32ResponseSerializer(serializers.Serializer):
    """
    Serializer for responses back to ESP32
    """
    status = serializers.ChoiceField(
        choices=['success', 'error', 'warning'],
        help_text="Response status"
    )

    message = serializers.CharField(
        max_length=200,
        help_text="Human-readable response message"
    )

    data = ESP32DataSerializer(
        required=False,
        help_text="Echo of the received data"
    )

    errors = serializers.DictField(
        required=False,
        help_text="Validation errors if any"
    )

    server_timestamp = serializers.DateTimeField(
        required=False,
        help_text="Server timestamp when data was received"
    )
