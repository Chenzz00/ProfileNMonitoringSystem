from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import random
import string
from datetime import date
from django.contrib.auth.models import User
from .who_lms import WHO_BMI_LMS
import os

# Create your models here.
class Admin(models.Model):
    admin_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=100)
    
    
    email = models.EmailField(max_length=254, unique=True, blank=True, null=True)
    
    def __str__(self):
        return self.username
      

class Account(models.Model):
    account_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="account", null=True)

    # Names
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    full_name = models.CharField(max_length=200, editable=False, blank=True)  # auto-generated

    # Contact
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(max_length=254, unique=True, null=True)
    password = models.CharField(max_length=100, null=True)  # store hashed password

    # ✅ Address fields
    house_number = models.CharField(max_length=50, blank=True, null=True)
    block = models.CharField(max_length=50, blank=True, null=True)
    lot = models.CharField(max_length=50, blank=True, null=True)
    phase = models.CharField(max_length=50, blank=True, null=True)
    street = models.CharField(max_length=100, blank=True, null=True)
    subdivision = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    province = models.CharField(max_length=100, blank=True, null=True)
    editable_address = models.CharField(max_length=255, blank=True, null=True)

    # Other details
    birthdate = models.DateField(blank=True, null=True)
    user_role = models.CharField(max_length=100)
    is_validated = models.BooleanField(default=False)
    is_rejected = models.BooleanField(default=False)

    validated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validated_accounts'
    )
    barangay = models.ForeignKey('Barangay', on_delete=models.SET_NULL, null=True, blank=True)

    last_activity = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    is_notif_read = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)
    fcm_token = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        # build full_name before saving
        parts = [self.first_name or "", self.last_name or ""]
        self.full_name = " ".join(p for p in parts if p).strip()
        super().save(*args, **kwargs)


    def __str__(self):
        return self.user.email
    
    @property
    def computed_age(self):
        if self.birthdate:
            today = date.today()
            return today.year - self.birthdate.year - (
                (today.month, today.day) < (self.birthdate.month, self.birthdate.day)
            )
        return None

def announcement_image_upload_path(instance, filename):
    """Generate upload path for announcement images"""
    return f'announcements/{filename}'

class Announcement(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    image = models.ImageField(upload_to=announcement_image_upload_path, blank=True, null=True, help_text="Upload an image for this announcement")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    
    class Meta:
        ordering = ['-created_at']
        db_table = 'webapp_announcement'
    
    def __str__(self):
        return self.title
    
    def delete(self, *args, **kwargs):
        """Delete associated image file when announcement is deleted"""
        if self.image:
            try:
                if os.path.isfile(self.image.path):
                    os.remove(self.image.path)
            except:
                pass
        super().delete(*args, **kwargs)

class BNS(models.Model):
    bns_id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=254, unique=True, blank=True, null=True)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    password = models.CharField(max_length=100)
    barangay = models.ForeignKey('Barangay', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
class BHW(models.Model):
    bhw_id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=254, unique=True, blank=True, null=True)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    password = models.CharField(max_length=100)
    barangay = models.ForeignKey('Barangay', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.email

class Midwife(models.Model):
    midwife_id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=254, unique=True, blank=True, null=True)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    password = models.CharField(max_length=100)
    barangay = models.ForeignKey('Barangay', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.email
    
class Nurse(models.Model):
    nurse_id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=254, unique=True, blank=True, null=True)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    password = models.CharField(max_length=100)
    barangay = models.ForeignKey('Barangay', on_delete=models.CASCADE, null=True, blank=True)
    def __str__(self):
        return self.email    

class Barangay(models.Model):
    name=models.CharField(max_length=100,null=True)
    hall_address=models.CharField(max_length=100,null=True)
    phone_number=models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return self.name
    

    @property
    def computed_age(self):
        if self.birthdate:
            today = date.today()
            return today.year - self.birthdate.year - (
                (today.month, today.day) < (self.birthdate.month, self.birthdate.day)
            )
        return None
    
class Parent(models.Model):
    parent_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    full_name = models.CharField(max_length=200, editable=False, blank=True)  # auto-generated
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    age = models.IntegerField(blank=True, null=True)  # Optional: can be kept for historical record
    birthdate = models.DateField(blank=True, null=True)
    registered_preschoolers = models.ManyToManyField('Preschooler', blank=True, related_name='parents')
    mother_name = models.CharField(max_length=100, blank=True, null=True)
    father_name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(max_length=254, unique=True, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    password = models.CharField(max_length=100)
    barangay = models.ForeignKey('Barangay', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    must_change_password = models.BooleanField(default=True)
    
    def save(self, *args, **kwargs):
        # ✅ AUTO-GENERATE FULL_NAME
        if self.first_name and self.last_name:
            self.full_name = f"{self.first_name} {self.last_name}".strip()
        elif self.first_name:
            self.full_name = self.first_name.strip()
        elif self.last_name:
            self.full_name = self.last_name.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name or self.email or f"Parent {self.parent_id}"

    @property
    def computed_age(self):
        if self.birthdate:
            today = date.today()
            return today.year - self.birthdate.year - (
                (today.month, today.day) < (self.birthdate.month, self.birthdate.day)
            )
        return None
    
class Preschooler(models.Model):
    preschooler_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    
    # Modified to use WHO standard M/F format
    SEX_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]
    sex = models.CharField(max_length=1, choices=SEX_CHOICES)
    
    birth_date = models.DateField()
    age = models.IntegerField()
    address = models.CharField(max_length=255, blank=True, null=True)
    parent_id = models.ForeignKey('Parent', on_delete=models.CASCADE, blank=True, null=True)
    bhw_id = models.ForeignKey('BHW', on_delete=models.CASCADE, blank=True, null=True)
    barangay = models.ForeignKey('Barangay', on_delete=models.CASCADE, blank=True, null=True)
    nutritional_status = models.CharField(max_length=50, blank=True, null=True)
    profile_photo = models.ImageField(upload_to='preschoolers/', null=True, blank=True)
    
    # Existing birth fields
    birth_weight = models.FloatField(blank=True, null=True, help_text="Birth weight in kilograms")
    birth_height = models.FloatField(blank=True, null=True, help_text="Birth length/height in centimeters")
    place_of_birth = models.CharField(max_length=255, blank=True, null=True, help_text="Place where the child was born")
    time_of_birth = models.TimeField(blank=True, null=True, help_text="Time when the child was born (HH:MM)")
    
    # New birth fields
    TYPE_OF_BIRTH_CHOICES = [
        ('Normal', 'Normal'),
        ('CS', 'Cesarean Section (CS)'),
    ]
    type_of_birth = models.CharField(
        max_length=20, 
        choices=TYPE_OF_BIRTH_CHOICES, 
        blank=True, 
        null=True,
        help_text="Type of delivery"
    )
    
    PLACE_OF_DELIVERY_CHOICES = [
        ('Home', 'Home'),
        ('Lying-in', 'Lying-in'),
        ('Hospital', 'Hospital'),
        ('Others', 'Others'),
    ]
    place_of_delivery = models.CharField(
        max_length=20, 
        choices=PLACE_OF_DELIVERY_CHOICES, 
        blank=True, 
        null=True,
        help_text="Place where delivery occurred"
    )

    @property
    def age_in_months(self):
        if not self.birth_date:
            return None
        
        today = date.today()
        birth_date = self.birth_date
        
        months = (today.year - birth_date.year) * 12 + (today.month - birth_date.month)
        
        if today.day < birth_date.day:
            months -= 1
        
        # Key fix: ensure newborns show 0 instead of negative
        return max(0, months)
    
    # Existing fields
    is_archived = models.BooleanField(default=False)
    date_registered = models.DateTimeField(default=timezone.now)
    is_notif_read = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.preschooler_id})"
    
    class Meta:
        verbose_name = "Preschooler"
        verbose_name_plural = "Preschoolers"
        ordering = ['-date_registered']


class BMI(models.Model):
    bmi_id = models.AutoField(primary_key=True)
    preschooler_id = models.ForeignKey(Preschooler, on_delete=models.CASCADE)
    weight = models.FloatField()    
    height = models.FloatField()
    bmi_value = models.FloatField()
    bmi_zscore = models.FloatField(blank=True, null=True, help_text="WHO BMI-for-age Z-score")
    nutritional_status = models.CharField(max_length=50, blank=True, null=True, help_text="WHO BMI classification")
    date_recorded = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"BMI Record for {self.preschooler_id} on {self.date_recorded}"


class Temperature(models.Model):
    temperature_id = models.AutoField(primary_key=True)
    preschooler_id = models.ForeignKey(Preschooler, on_delete=models.CASCADE)
    temperature_value = models.FloatField()
    date_recorded = models.DateField(auto_now_add=True)
    recorded_by = models.ForeignKey('BHW', on_delete=models.CASCADE, blank=True, null=True)

    def __str__(self):
        return f"Temperature Record for {self.preschooler_id} on {self.date_recorded}"


# Utility functions
def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    """Calculate BMI = weight (kg) / height (m)^2"""
    height_m = height_cm / 100
    return weight_kg / (height_m ** 2)


def bmi_zscore(sex: str, age_months: int, bmi: float) -> float:
    """
    Calculate BMI-for-age Z-score for children 0–59 months.
    """
    if sex not in WHO_BMI_LMS:
        raise ValueError("Invalid sex, must be 'M' or 'F'")
    if age_months not in WHO_BMI_LMS[sex]:
        raise ValueError("Age must be between 0 and 59 months")

    params = WHO_BMI_LMS[sex][age_months]
    L, M, S = params["L"], params["M"], params["S"]

    if L == 0:
        z = (bmi / M - 1) / S
    else:
        z = ((bmi / M) ** L - 1) / (L * S)

    return z


def classify_bmi_for_age(z: float) -> str:
    """
    Classify nutritional status based on WHO BMI-for-age Z-scores.
    """
    if z < -3:
        return "Severely Wasted"
    elif -3 <= z < -2:
        return "Wasted"
    elif -2 <= z <= 1:
        return "Normal"
    elif 1 < z <= 2:
        return "Risk of overweight"
    elif 2 < z <= 3:
        return "Overweight"
    else:
        return "Obese"
    
class Immunization(models.Model):
    immunization_id = models.AutoField(primary_key=True)
    preschooler_id = models.ForeignKey(Preschooler, on_delete=models.CASCADE)
    vaccine_name = models.CharField(max_length=100)
    date_administered = models.DateField()
    administered_by = models.ForeignKey(BHW, on_delete=models.CASCADE, blank=True, null=True)

    def __str__(self):
        return f"{self.vaccine_name} for {self.preschooler_id} on {self.date_administered}"

class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    
    def save(self, *args, **kwargs):
        if not self.otp_code:
            self.otp_code = ''.join(random.choices(string.digits, k=6))
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=10)
        super().save(*args, **kwargs)
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    class Meta:
        ordering = ['-created_at']

class ProfilePhoto(models.Model):
    account = models.OneToOneField('Account', on_delete=models.CASCADE, related_name='profile_photo')
    image = models.ImageField(upload_to='profile_photos/', default='default-profile.png')

    def __str__(self):
        return f"{self.account.full_name}'s Photo"

class VaccinationSchedule(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('rescheduled', 'Rescheduled'),
        ('missed', 'Missed'),
    ]
    
    preschooler = models.ForeignKey(
        Preschooler, on_delete=models.CASCADE, related_name='vaccination_schedules'
    )
    vaccine_name = models.CharField(max_length=100)
    doses = models.IntegerField(blank=True, null=True)
    required_doses = models.IntegerField(blank=True, null=True)
    scheduled_date = models.DateField()
    next_vaccine_schedule = models.DateField(blank=True, null=True)
    current_dose = models.IntegerField(default=1)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    
    scheduled_by = models.ForeignKey(BHW, on_delete=models.SET_NULL, null=True, blank=True)
    confirmed_by_parent = models.BooleanField(default=False)
    administered_date = models.DateField(blank=True, null=True)
    administered_by = models.ForeignKey(
        BHW, on_delete=models.SET_NULL, blank=True, null=True, related_name='administered_schedules'
    )
    
    # Additional fields for tracking
    completion_date = models.DateTimeField(blank=True, null=True)
    reschedule_reason = models.TextField(blank=True, null=True)
    
    notified = models.BooleanField(default=False)
    lapsed = models.BooleanField(default=False)
    
    def save(self, *args, **kwargs):
        # Auto-set completion and administered dates when marked as completed
        if self.status == 'completed' and not self.completion_date:
            self.completion_date = timezone.now()
            self.administered_date = timezone.now().date()
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.vaccine_name} for {self.preschooler.first_name} {self.preschooler.last_name} - {self.get_status_display()}"


# WHO-recommended vaccine schedule by age in months (based on your reference image)
VACCINE_SCHEDULE = {
    'BCG Vaccine': [
        {'dose': 1, 'age_months': 0, 'description': 'At birth'},
    ],
    'Hepatitis B Vaccine': [
        {'dose': 1, 'age_months': 0, 'description': 'At birth'},
        # Only one dose shown in your reference image
    ],
    'Pentavalent Vaccine': [
        {'dose': 1, 'age_months': 1.5, 'description': '1½, 2½, 3½ months'},
        {'dose': 2, 'age_months': 2.5, 'description': '1½, 2½, 3½ months'},
        {'dose': 3, 'age_months': 3.5, 'description': '1½, 2½, 3½ months'},
    ],
    'Oral Polio Vaccine': [
        {'dose': 1, 'age_months': 1.5, 'description': '1½, 2½, 3½ months'},
        {'dose': 2, 'age_months': 2.5, 'description': '1½, 2½, 3½ months'},
        {'dose': 3, 'age_months': 3.5, 'description': '1½, 2½, 3½ months'},
    ],
    'Inactivated Polio Vaccine': [
        {'dose': 1, 'age_months': 3.5, 'description': '3½ months'},
        {'dose': 2, 'age_months': 9, 'description': '& 9 months'},
    ],
    'Pneumococcal Conjugate Vaccine': [
        {'dose': 1, 'age_months': 1.5, 'description': '1½, 2½, 3½ months'},
        {'dose': 2, 'age_months': 2.5, 'description': '1½, 2½, 3½ months'},
        {'dose': 3, 'age_months': 3.5, 'description': '1½, 2½, 3½ months'},
    ],
    'Measles, Mumps, and Rubella': [
        {'dose': 1, 'age_months': 9, 'description': '9 months'},
        {'dose': 2, 'age_months': 12, 'description': '& 1 year'},
    ],
}

def get_vaccine_eligibility(preschooler, vaccine_name):
    """
    Determine which doses of a vaccine the preschooler is eligible for based on age.
    Returns a list of eligible doses with their scheduling information.
    """
    current_age_months = preschooler.age_in_months
    if current_age_months is None:
        return []
    
    vaccine_schedule = VACCINE_SCHEDULE.get(vaccine_name, [])
    if not vaccine_schedule:
        return []
    
    # Get completed doses for this vaccine
    completed_schedules = preschooler.vaccination_schedules.filter(
        vaccine_name=vaccine_name,
        status='completed'
    ).count()
    
    # Get pending/scheduled doses
    pending_schedules = preschooler.vaccination_schedules.filter(
        vaccine_name=vaccine_name,
        status__in=['scheduled', 'rescheduled']
    ).count()
    
    total_existing = completed_schedules + pending_schedules
    
    eligible_doses = []
    for dose_info in vaccine_schedule:
        dose_number = dose_info['dose']
        required_age_months = dose_info['age_months']
        
        # Skip if this dose is already completed or scheduled
        if dose_number <= total_existing:
            continue
            
        # Check if child is old enough for this dose
        if current_age_months >= required_age_months:
            eligible_doses.append({
                'dose': dose_number,
                'age_months': required_age_months,
                'description': dose_info['description'],
                'can_schedule': True,
                'reason': f'Child is {current_age_months} months old'
            })
        else:
            # Child is not old enough yet
            months_to_wait = required_age_months - current_age_months
            eligible_doses.append({
                'dose': dose_number,
                'age_months': required_age_months,
                'description': dose_info['description'],
                'can_schedule': False,
                'reason': f'Available in {months_to_wait:.1f} months (at {required_age_months} months old)'
            })
    
    return eligible_doses

def get_enhanced_vaccine_status(preschooler, vaccine_name, total_doses):
    """
    Enhanced vaccine status that includes age-based eligibility
    """
    current_age_months = preschooler.age_in_months or 0
    
    # Get completed doses
    completed_schedules = preschooler.vaccination_schedules.filter(
        vaccine_name=vaccine_name,
        status='completed'
    ).order_by('completion_date')
    
    completed_doses = completed_schedules.count()
    
    # Get next scheduled dose
    next_schedule = preschooler.vaccination_schedules.filter(
        vaccine_name=vaccine_name,
        status__in=['scheduled', 'rescheduled']
    ).order_by('scheduled_date').first()
    
    # Get eligibility for next dose
    eligible_doses = get_vaccine_eligibility(preschooler, vaccine_name)
    next_eligible = next(
        (dose for dose in eligible_doses if dose['can_schedule']), 
        None
    )
    
    # For Hepatitis B, only allow 1 dose (as per your reference image)
    if vaccine_name == 'Hepatitis B Vaccine':
        total_doses = 1
    
    # Determine status and available actions
    if completed_doses >= total_doses:
        return {
            'completed_doses': completed_doses,
            'status': 'completed',
            'immunization_date': completed_schedules.last().completion_date.strftime('%m/%d/%Y') if completed_schedules.last() else 'N/A',
            'can_schedule': False,
            'next_dose_info': None,
            'schedule_id': None,
        }
    
    if next_schedule:
        return {
            'completed_doses': completed_doses,
            'status': next_schedule.status,
            'immunization_date': next_schedule.scheduled_date.strftime('%m/%d/%Y'),
            'scheduled_date': next_schedule.scheduled_date.strftime('%Y-%m-%d'),
            'can_schedule': False,
            'can_complete': True,
            'can_reschedule': True,
            'next_dose_info': f"Dose {completed_doses + 1} scheduled",
            'schedule_id': next_schedule.id,
        }
    
    if next_eligible:
        return {
            'completed_doses': completed_doses,
            'status': 'pending',
            'immunization_date': 'N/A',
            'can_schedule': True,
            'next_dose_info': f"Ready for dose {next_eligible['dose']} ({next_eligible['description']})",
            'schedule_id': None,
            'eligible_dose': next_eligible,
        }
    
    # Check if there are future doses the child will be eligible for
    future_doses = [dose for dose in eligible_doses if not dose['can_schedule']]
    if future_doses:
        next_future = future_doses[0]
        return {
            'completed_doses': completed_doses,
            'status': 'pending',
            'immunization_date': 'N/A',
            'can_schedule': False,
            'next_dose_info': f"Dose {next_future['dose']} {next_future['reason']}",
            'schedule_id': None,
            'future_dose': next_future,
        }
    
    return {
        'completed_doses': completed_doses,
        'status': 'completed',
        'immunization_date': 'N/A',
        'can_schedule': False,
        'next_dose_info': 'All doses complete or not applicable for age',
        'schedule_id': None,
    }
    
class ParentActivityLog(models.Model):
    parent = models.ForeignKey(Parent, on_delete=models.CASCADE)
    barangay = models.ForeignKey(Barangay, on_delete=models.CASCADE)
    activity = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.full_name} - {self.activity}"

class PreschoolerActivityLog(models.Model):
    preschooler_name = models.CharField(max_length=255)
    activity = models.TextField()
    performed_by = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    barangay = models.ForeignKey(Barangay, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.preschooler_name} - {self.activity}"
    



    def create_account(email, raw_password, full_name, role):
    # Create Django User (hashed password stored here)
        user = User.objects.create_user(
            username=email,
            email=email,
            password=raw_password
        )

        # Create Account model (optional: store hashed pw too)
        account = Account.objects.create(
            full_name=full_name,
            email=email,
            password=user.password,   # hashed password
            user_role=role,
            validated_by=None
        )

        return account
    
class NutritionService(models.Model):
    preschooler = models.ForeignKey(Preschooler, on_delete=models.CASCADE, related_name='nutrition_services')
    service_type = models.CharField(max_length=100)
    doses = models.IntegerField(default=1)
    required_doses = models.IntegerField(default=10)
    scheduled_date = models.DateField(null=True, blank=True)
    completion_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default='scheduled', choices=[
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('rescheduled', 'Rescheduled'),
        ('missed', 'Missed'),
    ])
    reschedule_reason = models.TextField(blank=True, null=True)
    confirmed_by_parent = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.preschooler.first_name} - {self.service_type} - {self.scheduled_date or self.completion_date}"
    
class FCMToken(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    token = models.TextField(unique=True)
    device_type = models.CharField(max_length=20, default="android")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account.email} - {self.token}"