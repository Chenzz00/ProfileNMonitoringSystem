from django.urls import path
from . import views
from .views import *
from django.conf import settings
from django.conf.urls.static import static

from WebApp.views import generate_nutrition_excel

urlpatterns = [
   #hardware - start

    path('api/esp32/announce/', views.announce_device, name='esp32_announce'),

    # ESP32 Data Reception (existing endpoints - updated for multi-device)
    path('api/esp32/data/', views.receive_esp32_data_simple, name='esp32_data_receive'),
    path('api/esp32/get-data/', views.get_esp32_data_simple, name='esp32_data_get'),
    
    # Device Management (new endpoints for multi-device support)
    path('api/esp32/device-status/', views.get_device_status, name='esp32_device_status'),
    path('api/esp32/list-devices/', views.list_esp32_devices, name='esp32_list_devices'),
    
    # Data Management (existing endpoint - now device-aware)
    path('api/esp32/clear-data/', views.clear_esp32_data, name='esp32_clear_data'),
    path('api/esp32/clear-all/', views.clear_all_esp32_data, name='esp32_clear_all'),
    
    # Debug and Monitoring (existing endpoint - enhanced for multi-device)
    path('api/esp32/debug/', views.debug_esp32_cache, name='esp32_debug'),
    
    # DRF Endpoints (optional - for REST framework users)
    path('api/esp32/data-drf/', views.receive_esp32_data, name='esp32_data_receive_drf'),
    path('api/esp32/get-data-drf/', views.get_esp32_data, name='esp32_data_get_drf'),

    #hardware - end
    path('', views.login, name='login'), 
    path('logout/', views.logout_view, name='logout'), 
    path('add-barangay/', views.addbarangay, name='addbarangay'),
    path('admin-dashboard/',views.Admin, name='Admindashboard'),
    path('archived-details/', views.archived_details, name='archived_details'),
    path('archived/', views.archived, name='archived'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('parent-dashboard/', views.parent_dashboard, name='parent_dashboard'),
    path('parents-mypreschooler/<int:preschooler_id>/', views.parents_mypreschooler, name='parents_mypreschooler'),
    path('preschooler/<int:preschooler_id>/upload-photo/', 
         views.upload_preschooler_photo, 
         name='upload_preschooler_photo'),
   
    path('preschoolers/', views.preschoolers, name='preschoolers'),
    path('profile/', views.profile, name='profile'),
    path('register-preschooler/', views.register_preschooler, name='register_preschooler'),
    path('register/', views.register, name='register'),
    path('registered_bhw/', views.registered_bhw, name='registered_bhw'),
    path('registered-preschoolers/', views.registered_preschoolers, name='registered_preschoolers'),
    path('report-template/', views.reportTemplate, name='reportTemplate'),
    path('validate/', views.validate, name='validate'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-otp/<int:user_id>/', views.verify_otp, name='verify_otp'),
    path('reset-password/<int:user_id>/', views.reset_password, name='reset_password'),
    path('upload-cropped-photo/', views.upload_cropped_photo, name='upload_cropped_photo'),
    
    path('validate_account/<int:account_id>/', views.validate_account, name='validate_account'),
    path('reject_account/<int:account_id>/', views.reject_account, name='reject_account'),
    path('remove_bhw/<int:account_id>/', views.remove_bhw, name='remove_bhw'),
   
    path('register-preschooler-entry/', views.register_preschooler_entry, name='register_preschooler_entry'),
    path('manage-announcements/', views.manage_announcements, name='manage_announcements'),
    path('add-announcement/', views.add_announcement, name='add_announcement'),
    path('edit-announcement/<int:announcement_id>/', views.edit_announcement, name='edit_announcement'),
    path('delete-announcement/<int:announcement_id>/', views.delete_announcement, name='delete_announcement'),
    path('get-announcement/<int:announcement_id>/', views.get_announcement_data, name='get_announcement_data'),
    path('registered_midwife/', views.registered_midwife, name='registered_midwife'),
    path('remove_midwife/<int:account_id>/', views.remove_midwife, name='remove_midwife'),
    path('update_schedule_status/<int:schedule_id>/', views.update_schedule_status, name='update_schedule_status'),
    path('reschedule_vaccination/', views.reschedule_vaccination, name='reschedule_vaccination'),
    path('add_schedule/<int:preschooler_id>/', views.add_schedule, name='add_schedule'),
    path('update_child_info/<int:preschooler_id>/', views.update_child_info, name='update_child_info'),
    path('input-bmi/<int:preschooler_id>/', views.bmi_form, name='bmi_form'),
    path('generate-immunization-report/', views.generate_immunization_report, name='generate_immunization_report'),
    path('add_vaccine/<int:preschooler_id>/', views.add_vaccine, name='add_vaccine'),
    path('add_nutrition_service/<int:preschooler_id>/', views.add_nutrition_service, name='add_nutrition_service'),
    path(
        'add_completed_nutrition_service/<int:preschooler_id>/',
        views.add_nutrition_service,
        name='add_completed_nutrition_service'
    ),
    
    path('schedule_nutrition_service/<int:preschooler_id>/', views.schedule_nutrition_service, name='schedule_nutrition_service'),
    path('update_nutrition_status/<int:schedule_id>/', views.update_nutrition_status, name='update_nutrition_status'),
    path('reschedule_nutrition_service/<int:schedule_id>/', views.reschedule_nutrition_service, name='reschedule_nutrition_service'),
    path('healthcare-workers/', views.healthcare_workers, name='healthcare_workers'),
    
    
    # dinagdag
    path('preschooler/<int:preschooler_id>/', views.preschooler_detail, name='preschooler_data'),
    path('add-schedule/<int:preschooler_id>/', views.add_schedule, name='add_schedule'),
    path('confirm-schedule/<int:schedule_id>/', views.confirm_schedule, name='confirm_schedule'),
    path('input-bmi/<int:preschooler_id>/', views.bmi_form, name='input_bmi'),
    path('submit-bmi/', views.submit_bmi, name='submit_bmi'),
    path('bmi-form/<int:preschooler_id>/', views.bmi_form, name='bmi_form'),
    path('remove-preschooler/', views.remove_preschooler, name='remove_preschooler'),
    path('archived-preschoolers/', views.archived_preschoolers, name='archived_preschoolers'),
    path('email-endorsement/', views.email_endorsement, name='email_endorsement'),
    path('preschooler/<int:preschooler_id>/', views.preschooler_detail, name='preschooler_detail'),
    path('preschooler/<int:preschooler_id>/upload-photo/', views.update_preschooler_photo, name='update_preschooler_photo'),
    path('update-child-info/<int:preschooler_id>/', views.update_child_info, name='update_child_info'),
    path('register-parent/', views.register_parent, name='register_parent'),
    path('change-password/', views.change_password_first, name='change_password_first'),
    
    path('history/', views.history, name='history'),
    path('admin-logs/', views.admin_logs, name='admin_logs'),
    path('registered-parents/', views.registered_parents, name='registered_parents'),
    path('admin-registered-parents/', views.admin_registered_parents, name='admin_registered_parents'),


    path("registered_bns/", views.registered_bns, name="registered_bns"),
    path("remove_bns/<int:account_id>/", views.remove_bns, name="remove_bns"),

    
    path("registered-barangays/", views.registered_barangays, name="registered_barangays"),
    path('registered_nurse/', views.registered_nurse, name='registered_midwife'),
    path('remove_nurse/<int:account_id>/', views.remove_nurse, name='remove_nurse'),

    
   
    # Parent API Endpoints
    
    path('api/latest-weight/', views.get_latest_weight, name='get_latest_weight'),
    path('api/latest-temp/', views.get_latest_temp, name='get_latest_temp'),
    path('api/latest-distance/', views.get_latest_distance, name='get_latest_distance'),
    

    #Excel
     # Nutrition Report URLs
    path('generate-report/', views.generate_report, name='generate_report'),
    path('generate-nutrition-excel/', views.generate_nutrition_excel, name='generate_nutrition_excel'),

    #Notification
    path("api/save-fcm-token/", views.save_fcm_token, name="save_fcm_token"),
    path('api/register-fcm-token/', views.register_fcm_token, name='register_fcm_token'),
    path('check_notification_status/', views.check_notification_status, name='check_notification_status'),
    path('test_push_notification/', views.test_push_notification, name='test_push_notification'),
    path('api/pending-validation-count/', get_pending_validation_count, name='pending-validation-count'),

    #Temperature
    path('save-temperature/', views.save_temperature, name='save_temperature'),
    path('generate-admin-report/', views.generate_admin_report, name='generate_admin_report'),
    path('create-admin/', views.create_admin_view, name='create_admin'),
    
      
    
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)







