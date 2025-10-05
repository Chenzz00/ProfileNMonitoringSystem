from rest_framework import serializers
from django.core.validators import MinValueValidator, MaxValueValidator

class ESP32DataSerializer(serializers.Serializer):
    """
    Serializer for ESP32 measurement data - Updated for multiple devices with unique IDs
    """
    weight = serializers.FloatField(
        required=False,  # Made optional for temperature-only requests
        validators=[
            MinValueValidator(0, message="Weight must be greater than 0.1 kg"),
            MaxValueValidator(300.0, message="Weight cannot exceed 300 kg")
        ],
        help_text="Weight in kilograms"
    )
    
    height = serializers.FloatField(
        required=False,  # Made optional for temperature-only requests
        validators=[
            MinValueValidator(30.0, message="Height must be at least 30 cm"),
            MaxValueValidator(300.0, message="Height cannot exceed 300 cm")
        ],
        help_text="Height in centimeters"
    )
    
    temperature = serializers.FloatField(
        required=False,  # Made optional for BMI-only requests
        validators=[
            MinValueValidator(25.0, message="Temperature must be at least 25°C"),
            MaxValueValidator(45.0, message="Temperature cannot exceed 45°C")
        ],
        help_text="Body temperature in Celsius"
    )
    
    device_id = serializers.CharField(
        max_length=50,
        required=True,  # NOW REQUIRED for multi-device support
        help_text="Unique identifier for the ESP32 device (e.g., BMI_STATION_A, BMI_STATION_B)"
    )
    
    timestamp = serializers.IntegerField(
        required=False,
        help_text="ESP32 millis() timestamp"
    )
    
    bmi = serializers.FloatField(
        required=False,
        validators=[
            MinValueValidator(0.0),
            MaxValueValidator(100.0)
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
    
    measurement_type = serializers.CharField(
        max_length=20,
        required=False,
        help_text="Type of measurement: BMI or TEMPERATURE"
    )
    
    subject_type = serializers.CharField(
        max_length=20,
        required=False,
        help_text="Subject type: CHILD_STANDING or INFANT_LYING"
    )
    
    sensor_height = serializers.FloatField(
        required=False,
        validators=[
            MinValueValidator(50.0),
            MaxValueValidator(500.0)
        ],
        help_text="Height of the distance sensor from floor in cm"
    )
    
    def validate_device_id(self, value):
        """
        Validate device ID format and allowed values
        """
        allowed_devices = [
            'BMI_STATION_A',
            'BMI_STATION_B',
            'ESP32_BMI_Station_001',  # Legacy support
            'ESP32_BMI_Station_002'   # Legacy support
        ]
        
        if value not in allowed_devices:
            raise serializers.ValidationError(
                f"Invalid device_id '{value}'. Allowed devices: {', '.join(allowed_devices)}"
            )
        
        return value
    
    def validate(self, data):
        """
        Custom validation based on measurement type and device
        """
        measurement_type = data.get('measurement_type', '').upper()
        device_id = data.get('device_id')
        
        # Log device information for debugging
        if device_id:
            print(f"VALIDATION: Processing data from device {device_id}")
        
        if measurement_type == 'BMI':
            # For BMI measurements, require weight and height
            weight = data.get('weight')
            height = data.get('height')
            
            if not weight:
                raise serializers.ValidationError(
                    f"Weight is required for BMI measurements from device {device_id}"
                )
            if not height:
                raise serializers.ValidationError(
                    f"Height is required for BMI measurements from device {device_id}"
                )
                
            # Validate BMI calculation if BMI is provided
            if 'bmi' in data and weight and height:
                height_m = height / 100.0
                calculated_bmi = weight / (height_m * height_m)
                provided_bmi = data['bmi']
                
                # Allow small difference due to floating point precision
                if abs(calculated_bmi - provided_bmi) > 0.1:
                    raise serializers.ValidationError(
                        f"BMI calculation mismatch from device {device_id}. Expected: {calculated_bmi:.2f}, Got: {provided_bmi:.2f}"
                    )
                    
        elif measurement_type == 'TEMPERATURE':
            # For temperature measurements, require temperature
            temperature = data.get('temperature')
            
            if not temperature:
                raise serializers.ValidationError(
                    f"Temperature is required for temperature measurements from device {device_id}"
                )
                
            # Validate temperature status consistency
            temp_status = data.get('temperature_status', '').lower()
            if temp_status:
                if temp_status == 'normal' and not (36.1 <= temperature <= 37.2):
                    raise serializers.ValidationError(
                        f"Temperature marked as 'normal' but value is outside normal range from device {device_id}"
                    )
                elif 'fever' in temp_status and temperature < 37.3:
                    raise serializers.ValidationError(
                        f"Temperature marked as fever but value is below fever threshold from device {device_id}"
                    )
        else:
            # If no measurement type specified, require at least one measurement
            if not any([data.get('weight'), data.get('height'), data.get('temperature')]):
                raise serializers.ValidationError(
                    f"At least one measurement (weight, height, or temperature) is required from device {device_id}"
                )
        
        return data
    
    def to_representation(self, instance):
        """
        Customize the output representation with device information
        """
        data = super().to_representation(instance)
        
        # Add calculated BMI if weight and height are present
        if data.get('weight') and data.get('height'):
            weight = data['weight']
            height_m = data['height'] / 100.0
            data['calculated_bmi'] = round(weight / (height_m * height_m), 2)
        
        # Add timestamp in readable format
        if data.get('timestamp'):
            from datetime import datetime
            data['readable_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Add measurement completeness info with device context
        has_bmi_data = bool(data.get('weight') and data.get('height'))
        has_temp_data = bool(data.get('temperature'))
        
        data['measurement_completeness'] = {
            'device_id': data.get('device_id'),
            'has_bmi_data': has_bmi_data,
            'has_temperature_data': has_temp_data,
            'is_complete_health_check': has_bmi_data and has_temp_data
        }
        
        # Add device-specific metadata
        device_id = data.get('device_id')
        if device_id:
            if 'STATION_A' in device_id:
                data['device_location'] = 'Station A'
                data['device_number'] = 1
            elif 'STATION_B' in device_id:
                data['device_location'] = 'Station B' 
                data['device_number'] = 2
            else:
                data['device_location'] = 'Unknown'
                data['device_number'] = 0
        
        return data


class ESP32ResponseSerializer(serializers.Serializer):
    """
    Serializer for responses back to ESP32 - Updated for multi-device support
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
    
    measurement_type = serializers.CharField(
        max_length=20,
        required=False,
        help_text="Type of measurement received"
    )
    
    device_id = serializers.CharField(
        max_length=50,
        required=False,
        help_text="Device ID that sent the data"
    )
    
    device_status = serializers.CharField(
        max_length=20,
        required=False,
        help_text="Status of the device (online, offline, etc.)"
    )


class DeviceStatusSerializer(serializers.Serializer):
    """
    New serializer for tracking device status and availability
    """
    device_id = serializers.CharField(max_length=50)
    device_name = serializers.CharField(max_length=100, required=False)
    last_seen = serializers.DateTimeField(required=False)
    is_online = serializers.BooleanField(default=False)
    last_measurement_type = serializers.CharField(max_length=20, required=False)
    measurements_today = serializers.IntegerField(default=0)
    wifi_signal_strength = serializers.IntegerField(required=False)
    hardware_status = serializers.DictField(required=False)


class BMIMeasurementSerializer(serializers.Serializer):
    """
    Specialized serializer for BMI-only measurements with device ID
    """
    weight = serializers.FloatField(
        validators=[
            MinValueValidator(0.1),
            MaxValueValidator(300.0)
        ]
    )
    height = serializers.FloatField(
        validators=[
            MinValueValidator(30.0),
            MaxValueValidator(300.0)
        ]
    )
    bmi = serializers.FloatField(required=False)
    bmi_category = serializers.CharField(max_length=20, required=False)
    device_id = serializers.CharField(max_length=50, required=True)
    timestamp = serializers.IntegerField(required=False)
    subject_type = serializers.CharField(max_length=20, required=False)
    sensor_height = serializers.FloatField(required=False)


class TemperatureMeasurementSerializer(serializers.Serializer):
    """
    Specialized serializer for temperature-only measurements with device ID
    """
    temperature = serializers.FloatField(
        validators=[
            MinValueValidator(25.0),
            MaxValueValidator(45.0)
        ]
    )
    temperature_status = serializers.CharField(max_length=20, required=False)
    device_id = serializers.CharField(max_length=50, required=True)
    timestamp = serializers.IntegerField(required=False)
