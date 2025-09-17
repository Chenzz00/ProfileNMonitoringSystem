# Add this to your models.py or create a separate vaccine_schedules.py file

# WHO-recommended vaccine schedule by age in months
VACCINE_SCHEDULE = {
    'BCG Vaccine': [
        {'dose': 1, 'age_months': 0, 'description': 'At birth'},
    ],
    'Hepatitis B Vaccine': [
        {'dose': 1, 'age_months': 0, 'description': 'At birth'},
        {'dose': 2, 'age_months': 1.5, 'description': '1½ months'},
        {'dose': 3, 'age_months': 6, 'description': '6 months'},
    ],
    'Pentavalent Vaccine': [
        {'dose': 1, 'age_months': 1.5, 'description': '1½ months'},
        {'dose': 2, 'age_months': 2.5, 'description': '2½ months'},
        {'dose': 3, 'age_months': 3.5, 'description': '3½ months'},
    ],
    'Oral Polio Vaccine': [
        {'dose': 1, 'age_months': 1.5, 'description': '1½ months'},
        {'dose': 2, 'age_months': 2.5, 'description': '2½ months'},
        {'dose': 3, 'age_months': 3.5, 'description': '3½ months'},
        {'dose': 4, 'age_months': 9, 'description': '9 months'},
    ],
    'Inactivated Polio Vaccine': [
        {'dose': 1, 'age_months': 3.5, 'description': '3½ months'},
        {'dose': 2, 'age_months': 9, 'description': '9 months'},
        {'dose': 3, 'age_months': 12, 'description': '12 months (1 year)'},
    ],
    'Pneumococcal Conjugate Vaccine': [
        {'dose': 1, 'age_months': 1.5, 'description': '1½ months'},
        {'dose': 2, 'age_months': 2.5, 'description': '2½ months'},
        {'dose': 3, 'age_months': 3.5, 'description': '3½ months'},
        {'dose': 4, 'age_months': 12, 'description': '12 months (1 year)'},
    ],
    'Measles, Mumps, and Rubella': [
        {'dose': 1, 'age_months': 9, 'description': '9 months'},
        {'dose': 2, 'age_months': 12, 'description': '12 months (1 year)'},
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