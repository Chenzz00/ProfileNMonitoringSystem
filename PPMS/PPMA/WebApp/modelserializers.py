from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import transaction
from WebApp.models import Account, Barangay, BHW
import re
from datetime import date


# ============================
# Account Fetch Serializer
# ============================
class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = '__all__'


# ============================
# Register Serializer
# ============================
class RegisterSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True)

    # Phone number validation
    phone_regex = RegexValidator(
        regex=r'^\+?63\d{10}$|^09\d{9}$',
        message="Phone number must be in format: 09XXXXXXXXX or +63XXXXXXXXXX"
    )

    contact_number = serializers.CharField(
        validators=[phone_regex],
        max_length=15,
        required=True,
        help_text="Contact number in format: 09XXXXXXXXX or +63XXXXXXXXXX"
    )

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'}
    )

    barangay_name = serializers.CharField(
        write_only=True,
        required=True,
        help_text="Name of the barangay"
    )

    class Meta:
        model = Account
        fields = [
            'full_name',
            'email',
            'contact_number',
            'address',
            'birthdate',
            'password',
            'confirm_password',
            'user_role',
            'barangay_name'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'full_name': {'required': True},
            'user_role': {'required': True},
            'address': {'required': True},
            'birthdate': {'required': True},
        }

    # ============================
    # Field Validators
    # ============================
    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError("Email is required.")

        value = value.lower().strip()

        if Account.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")

        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")

        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value):
            raise serializers.ValidationError("Please enter a valid email address.")

        return value

    def validate_full_name(self, value):
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError("Full name must be at least 2 characters long.")

        if not re.match(r'^[a-zA-Z\s\.\-\']+$', value):
            raise serializers.ValidationError(
                "Full name should only contain letters, spaces, periods, hyphens, and apostrophes."
            )

        return value.strip().title()

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")

        if not re.search(r'[A-Za-z]', value):
            raise serializers.ValidationError("Password must contain at least one letter.")

        if not re.search(r'\d', value):
            raise serializers.ValidationError("Password must contain at least one number.")

        return value

    def validate_user_role(self, value):
        allowed_roles = ['BHW', 'Parent', 'Admin', 'healthworker']
        if value not in allowed_roles:
            raise serializers.ValidationError(f"User role must be one of: {', '.join(allowed_roles)}")

        if value == 'BHW':
            return 'healthworker'

        return value.lower()

    def validate_birthdate(self, value):
        if not value:
            raise serializers.ValidationError("Birthdate is required.")

        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))

        if age < 0:
            raise serializers.ValidationError("Birthdate cannot be in the future.")

        if age > 120:
            raise serializers.ValidationError("Please enter a valid birthdate.")

        if age < 18:
            raise serializers.ValidationError("You must be at least 18 years old to register.")

        return value

    def validate_address(self, value):
        if not value or len(value.strip()) < 5:
            raise serializers.ValidationError("Address must be at least 5 characters long.")

        return value.strip()

    def validate_barangay_name(self, value):
        if not value:
            raise serializers.ValidationError("Barangay name is required.")

        if not Barangay.objects.filter(name__iexact=value.strip()).exists():
            raise serializers.ValidationError(f"Barangay '{value}' does not exist.")

        return value.strip()

    def validate(self, data):
        if data.get('password') != data.get('confirm_password'):
            raise serializers.ValidationError({'confirm_password': "Passwords do not match."})
        return data

    # ============================
    # Create Account
    # ============================
    def create(self, validated_data):
        confirm_password = validated_data.pop('confirm_password', None)
        barangay_name = validated_data.pop('barangay_name', None)
        password = validated_data.pop('password')
        email = validated_data['email']
        full_name = validated_data['full_name']
        user_role = validated_data['user_role']
        contact_number = validated_data.get('contact_number', '')

        barangay = Barangay.objects.get(name__iexact=barangay_name)

        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        with transaction.atomic():
            try:
                # Create Django User
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )

                # Create Account
                validated_data['password'] = make_password(password)
                validated_data['barangay'] = barangay
                validated_data['is_validated'] = True if user_role == 'parent' else False
                validated_data['is_rejected'] = False

                account = Account.objects.create(**validated_data)
                account.user = user
                account.save()

                # Role-specific records
                if user_role == 'healthworker':
                    BHW.objects.create(
                        full_name=full_name,
                        email=email,
                        contact_number=contact_number,
                        password=make_password(password),
                        barangay=barangay
                    )
                    barangay.assigned_bhw = full_name
                    barangay.save()

                elif user_role == 'parent':
                    from WebApp.models import Parent
                    Parent.objects.create(
                        full_name=full_name,
                        email=email,
                        contact_number=contact_number,
                        birthdate=validated_data.get('birthdate'),
                        password=make_password(password),
                        address=validated_data.get('address', ''),
                        barangay=barangay,
                        must_change_password=False
                    )

                return account

            except Exception as e:
                raise serializers.ValidationError(f"Failed to create account: {str(e)}")

    # ============================
    # Custom Response
    # ============================
    def to_representation(self, instance):
        return {
            'message': 'Account created successfully',
            'account': {
                'account_id': instance.account_id,
                'full_name': instance.full_name,
                'email': instance.email,
                'user_role': instance.user_role,
                'barangay': instance.barangay.name if instance.barangay else None,
                'is_validated': instance.is_validated,
                'created_at': instance.created_at.isoformat() if instance.created_at else None,
            }
        }


# ============================
# Profile Serializer
# ============================
class ProfileSerializer(serializers.ModelSerializer):
    barangay_name = serializers.CharField(source='barangay.name', read_only=True)
    barangay_id = serializers.IntegerField(source='barangay.id', read_only=True)
    barangay_location = serializers.CharField(source='barangay.location', read_only=True)
    profile_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            'account_id', 'full_name', 'email', 'contact_number',
            'address', 'birthdate', 'user_role', 'barangay_name',
            'barangay_id', 'barangay_location', 'profile_photo_url',
            'is_validated', 'created_at'
        ]

    def get_profile_photo_url(self, obj):
        if hasattr(obj, 'profile_photo') and obj.profile_photo.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_photo.image.url)
        return None


# ============================
# Barangay Serializer
# ============================
class BarangaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Barangay
        fields = ['id', 'name', 'location']


from rest_framework import serializers
from WebApp.models import Preschooler, BMI

class BMIResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = BMI
        fields = ["height", "weight", "bmi_value"]

class PreschoolerResponseSerializer(serializers.ModelSerializer):
    latest_bmi = serializers.SerializerMethodField()
    barangay = serializers.CharField(source="barangay.name", read_only=True)
    parent_name = serializers.CharField(source="parent_id.full_name", read_only=True)
    nutritional_status = serializers.SerializerMethodField()
    weight_for_age = serializers.SerializerMethodField()
    height_for_age = serializers.SerializerMethodField()
    weight_height_for_age = serializers.SerializerMethodField()

    class Meta:
        model = Preschooler
        fields = [
            "preschooler_id",
            "first_name",
            "last_name",
            "age",
            "barangay",
            "birth_date",
            "sex",
            "address",
            "nutritional_status",
            "latest_bmi",
            "parent_name",
            "weight_for_age",
            "height_for_age",
            "weight_height_for_age",
        ]

    # ------------------ HELPERS ------------------

    def _calculate_age_months(self, obj):
        today = date.today()
        birth_date = obj.birth_date
        age_years = today.year - birth_date.year
        age_months = today.month - birth_date.month
        age_days = today.day - birth_date.day

        if age_days < 0:
            age_months -= 1
        if age_months < 0:
            age_years -= 1
            age_months += 12
        return age_years * 12 + age_months

    # WHO reference tables (mean values, 0–60 months)
    WHO_WEIGHT_FOR_AGE = {
        "male": {
            0: 3.3, 1: 4.5, 2: 5.6, 3: 6.4, 6: 7.9, 12: 9.6, 24: 12.2, 36: 14.3, 48: 16.3, 60: 18.3
        },
        "female": {
            0: 3.2, 1: 4.2, 2: 5.1, 3: 5.8, 6: 7.3, 12: 8.9, 24: 11.5, 36: 13.9, 48: 15.9, 60: 17.9
        },
    }

    WHO_HEIGHT_FOR_AGE = {
        "male": {
            0: 49.9, 1: 54.7, 2: 58.4, 3: 61.4, 6: 67.6, 12: 76.1, 24: 87.8, 36: 96.1, 48: 103.3, 60: 110.0
        },
        "female": {
            0: 49.1, 1: 53.7, 2: 57.1, 3: 59.8, 6: 65.7, 12: 74.0, 24: 86.4, 36: 95.1, 48: 102.7, 60: 109.4
        },
    }

    def _lookup_standard(self, table, age_months, sex):
        """Simple linear interpolation between WHO reference points"""
        sex = sex.lower()
        if sex not in table:
            return None
        refs = table[sex]

        # Exact month
        if age_months in refs:
            return refs[age_months]

        # Find nearest reference points
        lower = max([m for m in refs if m <= age_months], default=None)
        upper = min([m for m in refs if m >= age_months], default=None)

        if lower is None or upper is None:
            return None

        if lower == upper:
            return refs[lower]

        # Linear interpolate
        low_val, high_val = refs[lower], refs[upper]
        return low_val + (high_val - low_val) * (age_months - lower) / (upper - lower)

    # ------------------ SERIALIZER FIELDS ------------------

    def get_latest_bmi(self, obj):
        latest_bmi = BMI.objects.filter(preschooler_id=obj).order_by("-date_recorded").first()
        if latest_bmi:
            return {
                "height": latest_bmi.height,
                "weight": latest_bmi.weight,
                "bmi_value": latest_bmi.bmi_value,
                "date_recorded": latest_bmi.date_recorded,
            }
        return None

    def get_nutritional_status(self, obj):
        latest_bmi = BMI.objects.filter(preschooler_id=obj).order_by("-date_recorded").first()
        if not latest_bmi or not latest_bmi.bmi_value:
            return obj.nutritional_status or "N/A"

        bmi = latest_bmi.bmi_value
        if bmi < 13:
            return "Severely Underweight"
        elif 13 <= bmi < 14.9:
            return "Underweight"
        elif 14.9 <= bmi <= 17.5:
            return "Normal"
        elif 17.6 <= bmi <= 18.9:
            return "Overweight"
        elif bmi >= 19:
            return "Obese"
        return "N/A"

    def get_weight_for_age(self, obj):
        latest_bmi = BMI.objects.filter(preschooler_id=obj).order_by("-date_recorded").first()
        if not latest_bmi:
            return "N/A"

        total_age_months = self._calculate_age_months(obj)
        standard_weight = self._lookup_standard(self.WHO_WEIGHT_FOR_AGE, total_age_months, obj.sex)
        if not standard_weight:
            return "N/A"

        ratio = latest_bmi.weight / standard_weight
        if ratio < 0.8:
            return "Underweight"
        elif 0.8 <= ratio <= 1.2:
            return "Normal"
        else:
            return "Overweight"

    def get_height_for_age(self, obj):
        latest_bmi = BMI.objects.filter(preschooler_id=obj).order_by("-date_recorded").first()
        if not latest_bmi:
            return "N/A"

        total_age_months = self._calculate_age_months(obj)
        standard_height = self._lookup_standard(self.WHO_HEIGHT_FOR_AGE, total_age_months, obj.sex)
        if not standard_height:
            return "N/A"

        ratio = latest_bmi.height / standard_height
        if ratio < 0.95:
            return "Stunted"
        return "Normal"

    def get_weight_height_for_age(self, obj):
        weight_status = self.get_weight_for_age(obj)
        height_status = self.get_height_for_age(obj)
        if weight_status == "N/A" or height_status == "N/A":
            return "N/A"

        if weight_status == "Normal" and height_status == "Normal":
            return "Normal"
        elif weight_status == "Underweight" or height_status == "Stunted":
            return "At Risk"
        else:
            return "Review Needed"