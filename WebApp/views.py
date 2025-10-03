from datetime import datetime, date
from venv import logger
import logging
from django.shortcuts import render, redirect
from django.db.models import Count, Q, Sum, Case, When, IntegerField
from django.core.mail import EmailMultiAlternatives
from django.http import HttpResponse
from .models import BMI, Account, Barangay, Parent, Temperature, VaccinationSchedule, BHW, BNS, Announcement, Midwife, Nurse
from .models import get_enhanced_vaccine_status, get_vaccine_eligibility
from .services import PushNotificationService  # Single clean import
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticated
from django.utils.crypto import get_random_string
from django.contrib.auth.hashers import make_password
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required #abang lang
from django.shortcuts import render, redirect, get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import now
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from .models import PasswordResetOTP
from django.core.serializers.json import DjangoJSONEncoder
from .models import Account, ProfilePhoto
from django.views.decorators.csrf import csrf_exempt,csrf_protect
from django.http import JsonResponse
from django.urls import reverse
from django.template.loader import render_to_string
from weasyprint import HTML
from .models import Preschooler, Account, Barangay, BHW, BMI, Parent, PasswordResetOTP, NutritionService
from .models import ParentActivityLog, PreschoolerActivityLog
from django.db.models import Prefetch
from django.db.models import Q, F
import json
from calendar import monthrange
from django.http import HttpResponseForbidden
from django.contrib.auth.hashers import check_password
from django.views.decorators.http import require_POST
from .models import Preschooler, BMI, Temperature, Barangay, BHW, BNS
from django.utils import timezone
from django.utils.timesince import timesince
from datetime import timedelta
from django.db import IntegrityError
from django.core.paginator import Paginator
import calendar
import random
import string
from collections import defaultdict
from django.db.models.functions import TruncMonth
from .models import Account, Parent, Barangay, BHW
from django.db.models import Count, Q
from django.views.decorators.http import require_GET
from django.utils.html import strip_tags
from django.utils.dateparse import parse_date
from django.contrib.auth.decorators import login_required
from rest_framework.views import APIView
from WebApp.modelserializers import AccountSerializer
from .modelserializers import *
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from rest_framework.authtoken.models import Token
from django.utils.decorators import method_decorator

#added for hardware - start
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt                                   
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .serializers import ESP32DataSerializer, ESP32ResponseSerializer
import json
from datetime import datetime, timedelta


#REPORT
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

logger = logging.getLogger(__name__)

ESP32_DATA_CACHE = {}

# Device tracking for status monitoring
DEVICE_STATUS = {}

@csrf_exempt
@require_http_methods(["POST"])
def receive_esp32_data_simple(request):
    """
    Multi-device ESP32 data reception with device ID separation
    """
    global ESP32_DATA_CACHE, DEVICE_STATUS
    try:
        # Parse JSON data
        data = json.loads(request.body)
        
        # Use serializer for validation
        serializer = ESP32DataSerializer(data=data)
        
        if serializer.is_valid():
            validated_data = serializer.validated_data
            device_id = validated_data.get('device_id')
            measurement_type = validated_data.get('measurement_type', 'UNKNOWN').upper()
            
            # Validate device_id is provided
            if not device_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'device_id is required for multi-device support'
                }, status=400)
            
            # Update device status
            if device_id in DEVICE_STATUS:
                DEVICE_STATUS[device_id]['last_seen'] = timezone.now()
                DEVICE_STATUS[device_id]['is_online'] = True
                DEVICE_STATUS[device_id]['last_measurement_type'] = measurement_type
                DEVICE_STATUS[device_id]['measurements_today'] += 1
            
            # Initialize device data if not exists
            if device_id not in ESP32_DATA_CACHE:
                ESP32_DATA_CACHE[device_id] = {}
                print("DEBUG: Initialized new cache entry for device {device_id}")
            else:
                print("DEBUG: Existing cache for device {device_id}: {ESP32_DATA_CACHE[device_id]}")
            
            # Store data based on measurement type - MERGE with existing data
            if measurement_type == 'BMI':
                # Add BMI data while preserving any existing temperature data
                print("DEBUG: Adding BMI data to device {device_id}...")
                ESP32_DATA_CACHE[device_id].update({
                    'weight': validated_data['weight'],
                    'height': validated_data['height'],
                    'bmi': validated_data.get('bmi'),
                    'bmi_category': validated_data.get('bmi_category'),
                    'subject_type': validated_data.get('subject_type'),
                    'sensor_height': validated_data.get('sensor_height'),
                    'bmi_timestamp': str(timezone.now()),
                    'has_bmi_data': True
                })
                print("DEBUG: After BMI update for {device_id}: {ESP32_DATA_CACHE[device_id]}")
                
            elif measurement_type == 'TEMPERATURE':
                # Add temperature data while preserving any existing BMI data
                print("DEBUG: Adding temperature data to device {device_id}...")
                ESP32_DATA_CACHE[device_id].update({
                    'temperature': validated_data['temperature'],
                    'temperature_status': validated_data.get('temperature_status'),
                    'temp_timestamp': str(timezone.now()),
                    'has_temperature_data': True
                })
                print("DEBUG: After temperature update for {device_id}: {ESP32_DATA_CACHE[device_id]}")
                
            else:
                # Legacy support - store all available data
                ESP32_DATA_CACHE[device_id].update({
                    'weight': validated_data.get('weight'),
                    'height': validated_data.get('height'),
                    'temperature': validated_data.get('temperature'),
                    'bmi': validated_data.get('bmi'),
                    'bmi_category': validated_data.get('bmi_category'),
                    'temperature_status': validated_data.get('temperature_status'),
                })
            
            # Always update common fields
            ESP32_DATA_CACHE[device_id].update({
                'device_id': device_id,
                'last_update': str(timezone.now()),
                'esp32_timestamp': validated_data.get('timestamp'),
                'measurement_type': measurement_type
            })
            
            return JsonResponse({
                'status': 'success',
                'message': f'{measurement_type} data received successfully from {device_id}',
                'data': ESP32_DATA_CACHE[device_id],
                'measurement_type': measurement_type,
                'device_id': device_id
            })
            
        else:
            print("DEBUG: Validation failed: {serializer.errors}")
            return JsonResponse({
                'status': 'error',
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
        
    except Exception as e:
        print("DEBUG: Exception occurred: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_esp32_data_simple(request):
    """
    Get ESP32 data with device selection support
    """
    global ESP32_DATA_CACHE
    
    # Get device_id from URL parameter (required for multi-device)
    device_id = request.GET.get('device_id')
    force_clear = request.GET.get('clear', 'false').lower() == 'true'
    
    print("DEBUG: get_esp32_data_simple called - device_id: {device_id}, force_clear: {force_clear}")
    
    # If no device_id specified, return available devices
    if not device_id:
        available_devices = []
        for dev_id, data in ESP32_DATA_CACHE.items():
            available_devices.append({
                'device_id': dev_id,
                'device_name': DEVICE_STATUS.get(dev_id, {}).get('device_name', dev_id),
                'last_update': data.get('last_update'),
                'has_data': True,
                'is_online': DEVICE_STATUS.get(dev_id, {}).get('is_online', False)
            })
        
        # Also include devices with no data but known status
        for dev_id, status in DEVICE_STATUS.items():
            if dev_id not in ESP32_DATA_CACHE:
                available_devices.append({
                    'device_id': dev_id,
                    'device_name': status.get('device_name', dev_id),
                    'last_update': None,
                    'has_data': False,
                    'is_online': status.get('is_online', False)
                })
        
        return JsonResponse({
            'status': 'device_list',
            'message': 'Please specify device_id parameter',
            'available_devices': available_devices,
            'example_url': '/api/esp32/get-data/?device_id=BMI_STATION_A'
        })
    
    # If force clear is requested, clear data first and return
    if force_clear:
        if device_id in ESP32_DATA_CACHE:
            cleared_data = ESP32_DATA_CACHE[device_id].copy()
            del ESP32_DATA_CACHE[device_id]
            print("DEBUG: FORCE CLEARED data for device {device_id}: {cleared_data}")
        else:
            print("DEBUG: No data to clear for device {device_id} (already empty)")
        
        return JsonResponse({
            'status': 'no_data',
            'message': f'ESP32 data cleared for device {device_id}',
            'device_id': device_id,
            'data_cleared': True,
            'waiting_for': ['BMI', 'Temperature']
        })
    
    # Normal data retrieval logic for specific device
    esp32_data = ESP32_DATA_CACHE.get(device_id, {})
    print("DEBUG: Retrieved ESP32 data for {device_id}: {esp32_data}")
    
    if esp32_data:
        has_bmi = esp32_data.get('has_bmi_data', False)
        has_temp = esp32_data.get('has_temperature_data', False)
        is_complete = has_bmi and has_temp
        
        response_data = {
            'status': 'success',
            'data': esp32_data.copy(),
            'device_id': device_id,
            'device_name': DEVICE_STATUS.get(device_id, {}).get('device_name', device_id),
            'has_bmi_data': has_bmi,
            'has_temperature_data': has_temp,
            'last_measurement_type': esp32_data.get('measurement_type', 'UNKNOWN'),
            'is_complete': is_complete,
            'waiting_for': []
        }
        
        # Add info about what data we're still waiting for
        if not has_bmi:
            response_data['waiting_for'].append('BMI')
        if not has_temp:
            response_data['waiting_for'].append('Temperature')
        
        # Only clear if we have BOTH BMI and temperature data
        if is_complete:
            del ESP32_DATA_CACHE[device_id]
            print("DEBUG: Auto-cleared COMPLETE data for device {device_id} (BMI + Temperature)")
            response_data['data_cleared'] = True
        else:
            print("DEBUG: Keeping PARTIAL data for device {device_id} (BMI: {has_bmi}, Temp: {has_temp})")
            response_data['data_cleared'] = False
        
        return JsonResponse(response_data)
    else:
        return JsonResponse({
            'status': 'no_data',
            'message': f'No ESP32 data available for device {device_id}',
            'device_id': device_id,
            'device_name': DEVICE_STATUS.get(device_id, {}).get('device_name', device_id),
            'waiting_for': ['BMI', 'Temperature']
        })


@csrf_exempt
@require_http_methods(["POST"])
def clear_esp32_data(request):
    """
    FORCE clear ESP32 data cache for specific device or all devices
    """
    global ESP32_DATA_CACHE
    
    try:
        # Handle different content types
        if hasattr(request, 'content_type') and 'application/json' in request.content_type:
            data = json.loads(request.body)
            device_id = data.get('device_id')
        else:
            # Handle form data or beacon data
            try:
                # Try JSON first
                data = json.loads(request.body)
                device_id = data.get('device_id')
            except:
                # Fallback to POST parameters
                device_id = request.POST.get('device_id')
    except Exception as e:
        print("DEBUG: Error parsing clear request: {e}")
        device_id = None
    
    # If no device_id specified, show available devices
    if not device_id:
        return JsonResponse({
            'status': 'error',
            'message': 'device_id is required for clearing data',
            'available_devices': list(ESP32_DATA_CACHE.keys()),
            'example': {'device_id': 'BMI_STATION_A'}
        }, status=400)
    
    # ALWAYS clear data for specified device
    if device_id in ESP32_DATA_CACHE:
        cleared_data = ESP32_DATA_CACHE[device_id].copy()
        del ESP32_DATA_CACHE[device_id]
        print("DEBUG: POST CLEAR - Forcefully cleared data for device {device_id}: {cleared_data}")
        return JsonResponse({
            'status': 'success',
            'message': f'Data forcefully cleared for device {device_id}',
            'device_id': device_id,
            'cleared_data': cleared_data
        })
    else:
        print("DEBUG: POST CLEAR - No data to clear for device {device_id} (cache was already empty)")
        return JsonResponse({
            'status': 'success',  # Still return success even if no data
            'message': f'No data found for device {device_id} (already clear)',
            'device_id': device_id,
            'cleared_data': None
        })


@csrf_exempt
@require_http_methods(["GET"])
def get_device_status(request):
    """
    Get status of all ESP32 devices
    """
    global ESP32_DATA_CACHE, DEVICE_STATUS
    
    device_statuses = []
    for device_id, status in DEVICE_STATUS.items():
        has_cached_data = device_id in ESP32_DATA_CACHE
        cached_data = ESP32_DATA_CACHE.get(device_id, {})
        
        device_info = {
            'device_id': device_id,
            'device_name': status['device_name'],
            'is_online': status['is_online'],
            'last_seen': str(status['last_seen']) if status['last_seen'] else None,
            'last_measurement_type': status['last_measurement_type'],
            'measurements_today': status['measurements_today'],
            'has_cached_data': has_cached_data,
            'cached_data_preview': {
                'has_bmi': cached_data.get('has_bmi_data', False),
                'has_temperature': cached_data.get('has_temperature_data', False),
                'last_update': cached_data.get('last_update')
            } if has_cached_data else None
        }
        device_statuses.append(device_info)
    
    return JsonResponse({
        'status': 'success',
        'devices': device_statuses,
        'total_devices': len(device_statuses),
        'online_devices': len([d for d in device_statuses if d['is_online']]),
        'devices_with_data': len([d for d in device_statuses if d['has_cached_data']])
    })


@csrf_exempt
@require_http_methods(["GET"])
def debug_esp32_cache(request):
    """
    Debug view to see current ESP32 cache contents with device separation
    """
    global ESP32_DATA_CACHE, DEVICE_STATUS
    
    return JsonResponse({
        'status': 'debug',
        'cache_contents': ESP32_DATA_CACHE,
        'device_status': DEVICE_STATUS,
        'device_count': len(ESP32_DATA_CACHE),
        'known_devices': list(DEVICE_STATUS.keys()),
        'timestamp': str(timezone.now())
    })


@csrf_exempt
@require_http_methods(["POST"])
def clear_all_esp32_data(request):
    """
    Clear all ESP32 data for all devices (useful for testing)
    """
    global ESP32_DATA_CACHE
    
    device_count = len(ESP32_DATA_CACHE)
    cleared_data = ESP32_DATA_CACHE.copy()
    ESP32_DATA_CACHE.clear()
    
    print("DEBUG: Cleared all ESP32 data ({device_count} devices): {cleared_data}")
    
    return JsonResponse({
        'status': 'success',
        'message': f'Cleared data for all {device_count} devices',
        'devices_cleared': device_count,
        'cleared_devices': list(cleared_data.keys()),
        'cleared_data': cleared_data
    })


@csrf_exempt
@require_http_methods(["GET"])
def list_esp32_devices(request):
    """
    List all ESP32 devices that have sent data or are known
    """
    global ESP32_DATA_CACHE, DEVICE_STATUS
    
    devices = []
    all_device_ids = set(list(ESP32_DATA_CACHE.keys()) + list(DEVICE_STATUS.keys()))
    
    for device_id in all_device_ids:
        data = ESP32_DATA_CACHE.get(device_id, {})
        status = DEVICE_STATUS.get(device_id, {})
        
        devices.append({
            'device_id': device_id,
            'device_name': status.get('device_name', device_id),
            'last_update': data.get('last_update'),
            'has_bmi_data': data.get('has_bmi_data', False),
            'has_temperature_data': data.get('has_temperature_data', False),
            'last_measurement_type': data.get('measurement_type', status.get('last_measurement_type')),
            'is_online': status.get('is_online', False),
            'last_seen': str(status.get('last_seen')) if status.get('last_seen') else None,
            'data_preview': {
                'weight': data.get('weight'),
                'height': data.get('height'),
                'temperature': data.get('temperature')
            } if data else None
        })
    
    return JsonResponse({
        'status': 'success',
        'devices': devices,
        'device_count': len(devices),
        'cache_device_count': len(ESP32_DATA_CACHE),
        'known_device_count': len(DEVICE_STATUS)
    })


# DRF versions (if you prefer using Django REST Framework)
@api_view(['POST'])
@permission_classes([AllowAny])
def receive_esp32_data(request):
    """
    API endpoint to receive data from ESP32 using proper serializers (DRF version with multi-device)
    """
    try:
        # Use serializer to validate incoming data
        serializer = ESP32DataSerializer(data=request.data)
        
        if serializer.is_valid():
            validated_data = serializer.validated_data
            device_id = validated_data.get('device_id')
            measurement_type = validated_data.get('measurement_type', 'UNKNOWN').upper()
            
            # Update device tracking
            if device_id in DEVICE_STATUS:
                DEVICE_STATUS[device_id]['last_seen'] = timezone.now()
                DEVICE_STATUS[device_id]['is_online'] = True
                DEVICE_STATUS[device_id]['last_measurement_type'] = measurement_type
                DEVICE_STATUS[device_id]['measurements_today'] += 1
            
            # Initialize device data if not exists
            if device_id not in ESP32_DATA_CACHE:
                ESP32_DATA_CACHE[device_id] = {}
            
            # Store data based on measurement type - MERGE with existing data
            if measurement_type == 'BMI':
                ESP32_DATA_CACHE[device_id].update({
                    'weight': validated_data['weight'],
                    'height': validated_data['height'],
                    'bmi': validated_data.get('bmi'),
                    'bmi_category': validated_data.get('bmi_category'),
                    'subject_type': validated_data.get('subject_type'),
                    'sensor_height': validated_data.get('sensor_height'),
                    'bmi_timestamp': str(timezone.now()),
                    'has_bmi_data': True
                })
            elif measurement_type == 'TEMPERATURE':
                ESP32_DATA_CACHE[device_id].update({
                    'temperature': validated_data['temperature'],
                    'temperature_status': validated_data.get('temperature_status'),
                    'temp_timestamp': str(timezone.now()),
                    'has_temperature_data': True
                })
            
            # Always update common fields
            ESP32_DATA_CACHE[device_id].update({
                'device_id': device_id,
                'last_update': str(timezone.now()),
                'esp32_timestamp': validated_data.get('timestamp'),
                'measurement_type': measurement_type
            })
            
            # Create response using response serializer
            response_data = {
                'status': 'success',
                'message': f'{measurement_type} data received and validated successfully from {device_id}',
                'data': validated_data,
                'server_timestamp': timezone.now(),
                'measurement_type': measurement_type,
                'device_id': device_id
            }
            
            response_serializer = ESP32ResponseSerializer(response_data)
            
            # Debug logging
            print("=== ESP32 DATA RECEIVED ({measurement_type}) ===")
            print("Device: {device_id}")
            print("Data: {validated_data}")
            print("Cache: {ESP32_DATA_CACHE[device_id]}")
            print("=" * 50)
            
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        else:
            # Validation failed
            response_data = {
                'status': 'error',
                'message': 'Data validation failed',
                'errors': serializer.errors,
                'server_timestamp': timezone.now()
            }
            
            response_serializer = ESP32ResponseSerializer(response_data)
            
            print("=== VALIDATION FAILED ===")
            print("Errors: {serializer.errors}")
            print("Raw data: {request.data}")
            print("=" * 30)
            
            return Response(response_serializer.data, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        # Unexpected error
        response_data = {
            'status': 'error',
            'message': f'Server error: {str(e)}',
            'server_timestamp': timezone.now()
        }
        
        response_serializer = ESP32ResponseSerializer(response_data)
        
        print("=== SERVER ERROR ===")
        print("Error: {str(e)}")
        print("Raw data: {request.data}")
        print("=" * 20)
        
        return Response(response_serializer.data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_esp32_data(request):
    """
    API endpoint for the webpage to get the latest ESP32 data (DRF version with device selection)
    """
    device_id = request.GET.get('device_id')
    
    if not device_id:
        # Return list of available devices
        return Response({
            'status': 'device_selection_required',
            'message': 'Please specify device_id parameter',
            'available_devices': list(DEVICE_STATUS.keys()),
            'example_url': '/api/esp32/data/?device_id=BMI_STATION_A'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    esp32_data = ESP32_DATA_CACHE.get(device_id, None)
    
    if esp32_data:
        response_data = {
            'status': 'success',
            'message': f'ESP32 data found for device {device_id}',
            'data': esp32_data,
            'device_id': device_id,
            'server_timestamp': timezone.now()
        }
        
        response_serializer = ESP32ResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    else:
        response_data = {
            'status': 'no_data',
            'message': f'No ESP32 data available for device {device_id}',
            'device_id': device_id,
            'server_timestamp': timezone.now()
        }
        
        response_serializer = ESP32ResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_404_NOT_FOUND)

#added for hardware - end



#def view_vaccine_stocks(request):
    """Updated medicine/vaccine stocks view with better filtering"""
    
    # Get user's barangay if applicable
    user_barangay = None
    debug_info = []
    
    debug_info.append("Current user: {request.user}")
    debug_info.append("User email: {request.user.email}")
    debug_info.append("User is authenticated: {request.user.is_authenticated}")
    
    if request.user.is_authenticated:
        # Check each model type
        debug_info.append("Checking Account model...")
        try:
            account = Account.objects.get(email=request.user.email)
            user_barangay = account.barangay
            debug_info.append("✓ Found in Account: {account.email}, Barangay: {user_barangay}")
        except Account.DoesNotExist:
            debug_info.append("✗ Not found in Account model")
            
        if not user_barangay:
            debug_info.append("Checking BHW model...")
            try:
                bhw = BHW.objects.get(email=request.user.email)
                user_barangay = bhw.barangay
                debug_info.append("✓ Found in BHW: {bhw.email}, Barangay: {user_barangay}")
            except BHW.DoesNotExist:
                debug_info.append("✗ Not found in BHW model")
                
        if not user_barangay:
            debug_info.append("Checking BNS model...")
            try:
                bns = BNS.objects.get(email=request.user.email)
                user_barangay = bns.barangay
                debug_info.append("✓ Found in BNS: {bns.email}, Barangay: {user_barangay}")
            except BNS.DoesNotExist:
                debug_info.append("✗ Not found in BNS model")
                
        if not user_barangay:
            debug_info.append("Checking Midwife model...")
            try:
                midwife = Midwife.objects.get(email=request.user.email)
                user_barangay = midwife.barangay
                debug_info.append("✓ Found in Midwife: {midwife.email}, Barangay: {user_barangay}")
            except Midwife.DoesNotExist:
                debug_info.append("✗ Not found in Midwife model")
                
        if not user_barangay:
            debug_info.append("Checking Nurse model...")
            try:
                nurse = Nurse.objects.get(email=request.user.email)
                user_barangay = nurse.barangay
                debug_info.append("✓ Found in Nurse: {nurse.email}, Barangay: {user_barangay}")
            except Nurse.DoesNotExist:
                debug_info.append("✗ Not found in Nurse model")
                
        if not user_barangay:
            debug_info.append("Checking Parent model...")
            try:
                parent = Parent.objects.get(email=request.user.email)
                user_barangay = parent.barangay
                debug_info.append("✓ Found in Parent: {parent.email}, Barangay: {user_barangay}")
            except Parent.DoesNotExist:
                debug_info.append("✗ Not found in Parent model")

    debug_info.append("Final user_barangay: {user_barangay}")

    # Check all vaccine stocks in database first
    all_stocks = VaccineStock.objects.all()
    debug_info.append("Total vaccine stocks in database: {all_stocks.count()}")
    
    for stock in all_stocks:
        if stock.barangay:
            debug_info.append("Stock: {stock.vaccine_name} - Barangay: {stock.barangay.name}")
        else:
            debug_info.append("Stock: {stock.vaccine_name} - No barangay assigned")

    # Filter stocks by barangay if user has one
    if user_barangay:
        stocks = VaccineStock.objects.filter(barangay=user_barangay)
        debug_info.append("Filtering by barangay: {user_barangay}")
        debug_info.append("Found {stocks.count()} stocks for this barangay")
    else:
        stocks = VaccineStock.objects.all()
        debug_info.append("No barangay filter applied. Showing all {stocks.count()} stocks")

    # Print all debug info
    for info in debug_info:
        print(info)

    # Statistics
    total_vaccines = stocks.count()
    total_stock = sum(stock.total_stock for stock in stocks)
    available_stock = sum(stock.available_stock for stock in stocks)
    low_stock_count = sum(1 for stock in stocks if stock.available_stock < 10)

    context = {
        'vaccine_stocks': stocks,
        'total_vaccines': total_vaccines,
        'total_stock': total_stock,
        'available_stock': available_stock,
        'low_stock_count': low_stock_count,
        'user_barangay': user_barangay,
        'debug_info': debug_info,  # Pass debug info to template
    }
    
    return render(request, 'HTML/vaccine_stocks.html', context)


#@login_required
#def add_stock(request):
    """Add medicine/vaccine stock - updated to include deworming and vitamin A"""
    if request.method == 'POST':
        name = request.POST.get('vaccine_name')
        
        try:
            quantity = int(request.POST.get('quantity'))
        except (ValueError, TypeError):
            messages.error(request, "Invalid quantity. Please enter a valid number.")
            return redirect('view_vaccine_stocks')

        # Define valid medicine/vaccine options
        valid_options = [
            'BCG',
            'Hepatitis B',
            'Pentavalent (DPT-Hep B HiB)',
            'Oral Polio Vaccine',
            'Inactivated Polio Vaccine',
            'Pneumococcal Conjugate Vaccine',
            'Measles Mumps and Rubella',
            'Deworming Tablets',
            'Vitamin A Capsules'
        ]

        if name not in valid_options:
            messages.error(request, "Invalid medicine/vaccine name: {name}")
            return redirect('view_vaccine_stocks')

        try:
            # Get user's barangay using the same logic as view_vaccine_stocks
            user_barangay = None
            
            if request.user.is_authenticated:
                try:
                    account = Account.objects.get(email=request.user.email)
                    user_barangay = account.barangay
                except Account.DoesNotExist:
                    try:
                        bhw = BHW.objects.get(email=request.user.email)
                        user_barangay = bhw.barangay
                    except BHW.DoesNotExist:
                        try:
                            bns = BNS.objects.get(email=request.user.email)
                            user_barangay = bns.barangay
                        except BNS.DoesNotExist:
                            try:
                                midwife = Midwife.objects.get(email=request.user.email)
                                user_barangay = midwife.barangay
                            except Midwife.DoesNotExist:
                                try:
                                    nurse = Nurse.objects.get(email=request.user.email)
                                    user_barangay = nurse.barangay
                                except Nurse.DoesNotExist:
                                    try:
                                        parent = Parent.objects.get(email=request.user.email)
                                        user_barangay = parent.barangay
                                    except Parent.DoesNotExist:
                                        pass

            print("Adding stock - User barangay: {user_barangay}")

            # Build query filters
            stock_filter = {'vaccine_name': name}
            if user_barangay:
                stock_filter['barangay'] = user_barangay

            print("Stock filter: {stock_filter}")

            # Try to find existing stock
            try:
                stock = VaccineStock.objects.get(**stock_filter)
                stock.total_stock += quantity
                stock.available_stock += quantity
                stock.save()
                
                messages.success(request, "Stock updated for {name}. Added {quantity} units.")
                print("Updated existing stock for {name} in barangay {user_barangay}")
                
            except VaccineStock.DoesNotExist:
                # Create new stock entry
                stock_data = {
                    'vaccine_name': name,
                    'total_stock': quantity,
                    'available_stock': quantity,
                    'barangay': user_barangay  # This will be None if no barangay
                }
                
                new_stock = VaccineStock.objects.create(**stock_data)
                messages.success(request, "New medicine/vaccine '{name}' added with {quantity} units.")
                print("Created new stock for {name} in barangay {user_barangay}")

        except Exception as e:
            messages.error(request, "An error occurred: {str(e)}")
            print("Error adding stock: {str(e)}")

    return redirect('view_vaccine_stocks')

# Helper function to get medicine categories for reporting
#def get_medicine_categories():
    """Returns categorized list of medicines/vaccines"""
    return {
        'vaccines': [
            'BCG',
            'Hepatitis B', 
            'Pentavalent (DPT-Hep B HiB)',
            'Oral Polio Vaccine',
            'Inactivated Polio Vaccine',
            'Pneumococcal Conjugate Vaccine',
            'Measles Mumps and Rubella'
        ],
        'medicines_supplements': [
            'Deworming Tablets',
            'Vitamin A Capsules'
        ]
    }

@login_required
def email_endorsement(request):
    """Email endorsement view with proper barangay filtering"""
    
    # Get user's barangay using the same logic as vaccine stocks
    user_barangay = None
    account = None
    
    debug_info = []
    debug_info.append("Current user: {request.user}")
    debug_info.append("User email: {request.user.email}")
    
    if request.user.is_authenticated:
        # Check each model type to find the user and their barangay
        try:
            account = Account.objects.select_related('barangay').get(email=request.user.email)
            user_barangay = account.barangay
            debug_info.append("✓ Found in Account: {account.email}, Barangay: {user_barangay}")
        except Account.DoesNotExist:
            debug_info.append("✗ Not found in Account model")
            
            # Try other user models if not found in Account
            try:
                bhw = BHW.objects.select_related('barangay').get(email=request.user.email)
                user_barangay = bhw.barangay
                # Create a mock account object for consistency
                account = type('MockAccount', (), {
                    'email': bhw.email,
                    'barangay': bhw.barangay,
                    'full_name': bhw.full_name
                })()
                debug_info.append("✓ Found in BHW: {bhw.email}, Barangay: {user_barangay}")
            except BHW.DoesNotExist:
                try:
                    bns = BNS.objects.select_related('barangay').get(email=request.user.email)
                    user_barangay = bns.barangay
                    account = type('MockAccount', (), {
                        'email': bns.email,
                        'barangay': bns.barangay,
                        'full_name': bns.full_name
                    })()
                    debug_info.append("✓ Found in BNS: {bns.email}, Barangay: {user_barangay}")
                except BNS.DoesNotExist:
                    try:
                        midwife = Midwife.objects.select_related('barangay').get(email=request.user.email)
                        user_barangay = midwife.barangay
                        account = type('MockAccount', (), {
                            'email': midwife.email,
                            'barangay': midwife.barangay,
                            'full_name': midwife.full_name
                        })()
                        debug_info.append("✓ Found in Midwife: {midwife.email}, Barangay: {user_barangay}")
                    except Midwife.DoesNotExist:
                        try:
                            nurse = Nurse.objects.select_related('barangay').get(email=request.user.email)
                            user_barangay = nurse.barangay
                            account = type('MockAccount', (), {
                                'email': nurse.email,
                                'barangay': nurse.barangay,
                                'full_name': nurse.full_name
                            })()
                            debug_info.append("✓ Found in Nurse: {nurse.email}, Barangay: {user_barangay}")
                        except Nurse.DoesNotExist:
                            try:
                                parent = Parent.objects.select_related('barangay').get(email=request.user.email)
                                user_barangay = parent.barangay
                                account = type('MockAccount', (), {
                                    'email': parent.email,
                                    'barangay': parent.barangay,
                                    'full_name': parent.full_name
                                })()
                                debug_info.append("✓ Found in Parent: {parent.email}, Barangay: {user_barangay}")
                            except Parent.DoesNotExist:
                                debug_info.append("✗ User not found in any model")

    debug_info.append("Final user_barangay: {user_barangay}")

    # If no account found or no barangay assigned, handle appropriately
    if not account:
        messages.error(request, "User account not found. Please contact administrator.")
        return redirect('dashboard')
    
    if not user_barangay:
        messages.error(request, "No barangay assigned to your account. Please contact administrator.")
        return redirect('dashboard')

    # Filter only parents from the same barangay
    parents = Parent.objects.filter(barangay=user_barangay).exclude(email__isnull=True)
    debug_info.append("Found {parents.count()} parents in barangay {user_barangay}")
    
    # Debug: Show which parents were found
    for parent in parents:
        debug_info.append("Parent: {parent.full_name} ({parent.email}) - Barangay: {parent.barangay}")

    # Print debug info
    for info in debug_info:
        print(info)

    if request.method == 'POST':
        from_email = request.POST.get('from_email')
        to_email = request.POST.get('to_email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')

        # Validate that the recipient is from the same barangay
        try:
            recipient_parent = Parent.objects.get(email=to_email, barangay=user_barangay)
            debug_info.append("Recipient validation passed: {recipient_parent.email} is in {user_barangay}")
        except Parent.DoesNotExist:
            messages.error(request, "Invalid recipient. You can only send emails to parents in your barangay.")
            return redirect('email_endorsement')

        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=[to_email],
                fail_silently=False
            )
            messages.success(request, "Endorsement email sent successfully to {to_email}.")
            return redirect('dashboard')
        except Exception as e:
            messages.error(request, "Error sending email: {e}")
            print("Email sending error: {e}")
            return redirect('email_endorsement')

    return render(request, 'HTML/email_endorsement.html', {
        'from_email': account.email,
        'account': account,
        'parents': parents,
        'user_barangay': user_barangay,
        'debug_info': debug_info  # For debugging
    })




def generate_immunization_report(request):
    """Generate PDF report for immunization schedules and vaccination records without vaccine stock tracking"""
    user = request.user
    try:
        account = Account.objects.select_related('barangay').get(email=user.email)
    except Account.DoesNotExist:
        return HttpResponse("Account not found.", status=404)

    user_role_lower = account.user_role.lower() if account.user_role else ''
    is_authorized = any(role in user_role_lower for role in [
        'bhw', 'health worker', 'bns', 'nutrition', 'nutritional', 'scholar', 'midwife', 'admin'
    ])
    if not is_authorized:
        messages.error(request, "Your role ({account.user_role}) is not authorized to generate immunization reports.")
        return redirect('dashboard')

    barangay = account.barangay
    if not barangay:
        return HttpResponse("No barangay assigned to this account.", status=404)

    # Month filter
    month_str = request.GET.get("month")  # expected format: YYYY-MM
    month_filter = None
    month_display = "All Records"
    if month_str:
        try:
            month_filter = datetime.strptime(month_str, "%Y-%m")
            month_display = month_filter.strftime("%B %Y")
        except ValueError:
            month_filter = None
            month_display = "All Records"

    preschoolers = Preschooler.objects.filter(
        is_archived=False
    ).select_related('parent_id').prefetch_related('vaccination_schedules')

    today = date.today()

    vaccination_summary = {
        'Fully Vaccinated': 0,
        'Partially Vaccinated': 0,
        'Not Vaccinated': 0,
        'Overdue': 0,
    }

    preschoolers_data = []

    # Unique vaccines
    scheduled_vaccines = VaccinationSchedule.objects.all().values_list(
        'vaccine_name', flat=True
    ).distinct().order_by('vaccine_name')
    required_vaccines = list(scheduled_vaccines) if scheduled_vaccines else [
        'BCG', 'Hepatitis B', 'DPT', 'OPV', 'MMR', 'Pneumococcal', 'Rotavirus'
    ]

    for p in preschoolers:
        schedules = [s for s in p.vaccination_schedules.all() if s.status == 'completed']
        if month_filter:
            schedules = [s for s in schedules if s.scheduled_date and
                         s.scheduled_date.year == month_filter.year and
                         s.scheduled_date.month == month_filter.month]

        if not schedules:
            continue

        age_years = today.year - p.birth_date.year - ((today.month, today.day) < (p.birth_date.month, p.birth_date.day))
        age_months = (today.year - p.birth_date.year) * 12 + today.month - p.birth_date.month

        total_scheduled = len(schedules)
        total_completed = total_scheduled  # all are completed

        vaccination_status = "Fully Vaccinated" if total_completed == total_scheduled else "Partially Vaccinated"
        vaccination_summary[vaccination_status] += 1

        parent_name = p.parent_id.full_name if p.parent_id else "N/A"
        address = getattr(p.parent_id, 'address', 'N/A') if p.parent_id else getattr(p, 'address', 'N/A') or "N/A"

        last_completed = max([s.completion_date or s.administered_date for s in schedules if s.completion_date or s.administered_date], default=None)
        last_vaccination_date = last_completed.strftime('%m/%d/%Y') if last_completed else "N/A"

        completed_text = "; ".join(["{s.vaccine_name} ({(s.completion_date or s.administered_date or s.scheduled_date).strftime('%m/%d/%Y')})" for s in schedules])

        preschoolers_data.append({
            'name': "{p.first_name} {p.last_name}",
            'age': "{age_years} years, {age_months % 12} months",
            'sex': p.sex,
            'vaccination_status': vaccination_status,
            'vaccines_received': "{total_completed}/{total_scheduled}",
            'last_vaccination': last_vaccination_date,
            'vaccination_schedule': completed_text,
            'parent_name': parent_name,
            'address': address,
            'overdue_count': 0,  # no overdue tracking
        })

    context = {
        'account': account,
        'barangay': barangay,
        'preschoolers': preschoolers_data,
        'summary': vaccination_summary,
        'required_vaccines': required_vaccines,
        'month_filter': month_str or "All",
    }

    html_string = render_to_string('HTML/immunization_report.html', context)
    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    pdf = html.write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="Immunization-Report.pd"'
    return response


def index(request):
    
    return HttpResponse('Welcome to the PPMA Web Application!')

def addbarangay(request):
    if request.method == 'POST':
        name = request.POST.get('barangay-name', '').strip()
        phone_number = request.POST.get('phone-number', '').strip()
        hall_address = request.POST.get('hall-address', '').strip()

        print("[DEBUG] Received: {name=}, {phone_number=}, {hall_address=}")

        # ✅ Check for empty barangay name
        if not name:
            messages.error(request, "Barangay name is required.")
            return render(request, 'HTML/addbarangay.html')

        # ✅ Check if barangay name already exists
        if Barangay.objects.filter(name__iexact=name).exists():
            messages.error(request, "A barangay named '{name}' already exists.")
            return render(request, 'HTML/addbarangay.html')

        # ✅ Try saving the barangay
        try:
            Barangay.objects.create(
                name=name,
                phone_number=phone_number,
                hall_address=hall_address,
            )
            messages.success(request, "Barangay {name} was added successfully!")
            return redirect('addbarangay')
        except Exception as e:
            print("[ERROR] Failed to add barangay: {e}")
            messages.error(request, "Something went wrong while saving. Please try again.")
    
    return render(request, 'HTML/addbarangay.html')

def Admin(request):
    # Count health workers - include all health worker roles
    health_worker_roles = ['BHW', 'Barangay Nutritional Scholar', 'Midwife', 'Nurse']
    health_worker_count = Account.objects.filter(
        user_role__in=health_worker_roles,
        is_validated=True  # Only count validated health workers
    ).count() or 0

    # Get preschoolers and unvalidated accounts
    preschoolers = Preschooler.objects.all()
    accounts = Account.objects.filter(is_validated=False)

    # Total Vaccinated
    total_vaccinated = VaccinationSchedule.objects.filter(status='completed').count()

    # Build notifications
    notifications = []

    for acc in accounts:
        notifications.append({
            'type': 'account',
            'full_name': acc.full_name,
            'created_at': acc.created_at,
            'user_role': acc.user_role,
        })

    for child in preschoolers:
        notifications.append({
            'type': 'preschooler',
            'full_name': "{child.first_name} {child.last_name}",
            'date_registered': child.date_registered,
            'bhw_image': getattr(child.bhw_id.account.profile_photo.image, 'url', None)
                          if child.bhw_id and child.bhw_id.account and hasattr(child.bhw_id.account, 'profile_photo') else None,
        })

    # Process timestamps
    for notif in notifications:
        timestamp = notif.get('created_at') or notif.get('date_registered')
        if timestamp:
            if isinstance(timestamp, date) and not isinstance(timestamp, datetime):
                timestamp = timezone.make_aware(datetime.combine(timestamp, timezone.now().time()))
            elif isinstance(timestamp, datetime) and timezone.is_naive(timestamp):
                timestamp = timezone.make_aware(timestamp)
        else:
            timestamp = timezone.now()
        notif['timestamp'] = timestamp

    notifications.sort(key=lambda x: x['timestamp'], reverse=True)
    latest_notifications = notifications[:15]
    latest_timestamp = latest_notifications[0]['timestamp'] if latest_notifications else None

    # Total preschoolers - Fixed query
    total_preschoolers = Preschooler.objects.filter(is_archived=False).count() or 0

    barangays = Barangay.objects.all()

    # Pie chart: nutritional status
    status_totals = {
        'Severely Wasted': 0,
        'Wasted': 0,
        'Normal': 0,
        'Risk of overweight': 0,
        'Overweight': 0,
        'Obese': 0,
    }

    # Table summary by barangay - Fixed to ensure all barangays appear
    summary = []
    today = date.today()
    
    for brgy in barangays:
        preschoolers_in_barangay = Preschooler.objects.filter(
            barangay=brgy,
            is_archived=False
        ).prefetch_related('bmi_set')

        nutritional_summary = {
            'severely_wasted': 0,
            'wasted': 0,
            'normal': 0,
            'risk_overweight': 0,
            'overweight': 0,
            'obese': 0,
        }

        preschooler_count = preschoolers_in_barangay.count()

        for p in preschoolers_in_barangay:
            latest_bmi = p.bmi_set.order_by('-date_recorded').first()
            if latest_bmi:
                try:
                    # --- Compute age in months ---
                    birth_date = p.birth_date
                    age_years = today.year - birth_date.year
                    age_months = today.month - birth_date.month
                    if today.day < birth_date.day:
                        age_months -= 1
                    if age_months < 0:
                        age_years -= 1
                        age_months += 12
                    total_age_months = age_years * 12 + age_months

                    # --- Compute BMI and classify ---
                    bmi_value = calculate_bmi(latest_bmi.weight, latest_bmi.height)
                    z = bmi_zscore(p.sex, total_age_months, bmi_value)
                    category = classify_bmi_for_age(z)

                    if category == "Severely Wasted":
                        nutritional_summary['severely_wasted'] += 1
                        status_totals['Severely Wasted'] += 1
                    elif category == "Wasted":
                        nutritional_summary['wasted'] += 1
                        status_totals['Wasted'] += 1
                    elif category == "Normal":
                        nutritional_summary['normal'] += 1
                        status_totals['Normal'] += 1
                    elif category == "Risk of overweight":
                        nutritional_summary['risk_overweight'] += 1
                        status_totals['Risk of overweight'] += 1
                    elif category == "Overweight":
                        nutritional_summary['overweight'] += 1
                        status_totals['Overweight'] += 1
                    elif category == "Obese":
                        nutritional_summary['obese'] += 1
                        status_totals['Obese'] += 1

                except Exception as e:
                    print("⚠️ BMI classification error for preschooler {p.id}: {e}")

        # Add barangay data even if it has 0 preschoolers
        summary.append({
            'barangay': brgy.name,
            'preschooler_count': preschooler_count,
            **nutritional_summary
        })

    # NEW: Enhanced Vaccination Trend Data with Dynamic Date Filtering
    from django.db.models import Count, Q
    from datetime import timedelta
    from dateutil.relativedelta import relativedelta
    
    # Get filter parameters from request
    filter_month = request.GET.get('filter_month')
    
    # Determine center month
    if filter_month:
        try:
            center_date = datetime.strptime(filter_month, '%Y-%m').date()
        except ValueError:
            center_date = timezone.now().date().replace(day=1)  # Current month as fallback
    else:
        center_date = timezone.now().date().replace(day=1)  # Current month by default
    
    # Generate 11 months: center month ±5 months
    trend_labels = []
    monthly_registered_trend = []
    vaccinated_preschoolers_trend = []
    all_months_data = []  # For JavaScript filtering
    
    # Generate data for the 11-month window (5 before + current + 5 after)
    for i in range(-5, 6):  # -5 to +5 inclusive
        target_month = center_date + relativedelta(months=i)
        
        # Calculate next month for range queries
        next_month = target_month + relativedelta(months=1)
        
        # Month label
        month_label = target_month.strftime('%b %Y')
        trend_labels.append(month_label)
        
        # Monthly registrations for this specific month
        monthly_registered = Preschooler.objects.filter(
            date_registered__gte=target_month,
            date_registered__lt=next_month,
            is_archived=False
        ).count()
        monthly_registered_trend.append(monthly_registered)
        
        # Vaccinated preschoolers in this specific month
        vaccinated_in_month = VaccinationSchedule.objects.filter(
            administered_date__gte=target_month,
            administered_date__lt=next_month,
            status='completed'
        ).values('preschooler').distinct().count()
        
        vaccinated_preschoolers_trend.append(vaccinated_in_month)
        
        # Store month data for JavaScript
        all_months_data.append({
            'month': target_month.strftime('%Y-%m'),
            'label': month_label,
            'registered': monthly_registered,
            'vaccinated': vaccinated_in_month
        })

    # Generate extended data for JavaScript (±12 months for smooth transitions)
    extended_months_data = []
    for i in range(-12, 13):  # -12 to +12 months
        target_month = timezone.now().date().replace(day=1) + relativedelta(months=i)
        next_month = target_month + relativedelta(months=1)
        
        monthly_registered = Preschooler.objects.filter(
            date_registered__gte=target_month,
            date_registered__lt=next_month,
            is_archived=False
        ).count()
        
        vaccinated_in_month = VaccinationSchedule.objects.filter(
            administered_date__gte=target_month,
            administered_date__lt=next_month,
            status='completed'
        ).values('preschooler').distinct().count()
        
        extended_months_data.append({
            'month': target_month.strftime('%Y-%m'),
            'label': target_month.strftime('%b %Y'),
            'registered': monthly_registered,
            'vaccinated': vaccinated_in_month
        })

    vaccination_trend_data = {
        'labels': trend_labels,
        'registered': monthly_registered_trend,
        'vaccinated': vaccinated_preschoolers_trend,
        'center_month': center_date.strftime('%Y-%m'),
        'all_months': extended_months_data  # For JavaScript filtering
    }

    # Prepare data for Barangay Bar Chart
    barangay_chart_data = {
        'barangays': [row['barangay'] for row in summary],
        'severely_wasted': [row['severely_wasted'] for row in summary],
        'wasted': [row['wasted'] for row in summary],
        'normal': [row['normal'] for row in summary],
        'risk_overweight': [row['risk_overweight'] for row in summary],
        'overweight': [row['overweight'] for row in summary],
        'obese': [row['obese'] for row in summary]
    }

    return render(request, 'HTML/Admindashboard.html', {
        'health_worker_count': health_worker_count,
        'notifications': latest_notifications,
        'latest_notif_timestamp': latest_timestamp.isoformat() if latest_timestamp else '',
        'total_preschoolers': total_preschoolers,
        'total_vaccinated': total_vaccinated,
        'barangay_summary': summary,
        'nutritional_data': {
            'labels': list(status_totals.keys()),
            'values': list(status_totals.values())
        },
        'vaccination_trend_data': vaccination_trend_data,
        'barangay_chart_data': barangay_chart_data,
        'current_filter_month': center_date.strftime('%Y-%m')  # For the date picker
    })

    

def archived(request):
    """Updated archived view with auto-archive check"""
    
    # Run auto-archive check here too
    auto_archived_count = auto_archive_aged_preschoolers()
    if auto_archived_count > 0:
        print("AUTO-ARCHIVED: {auto_archived_count} preschoolers in archived view")
    
    # Get user info for barangay filtering (if not admin)
    user_email = request.session.get('email')
    raw_role = (request.session.get('user_role') or '').strip().lower()
    
    if raw_role == 'admin':
        archived_preschoolers_qs = Preschooler.objects.filter(is_archived=True).select_related('barangay', 'parent_id')
    else:
        # Filter by user's barangay
        account = get_object_or_404(Account, email=user_email)
        archived_preschoolers_qs = Preschooler.objects.filter(
            is_archived=True, 
            barangay=account.barangay
        ).select_related('barangay', 'parent_id')

    # Order by most recently archived
    archived_preschoolers_qs = archived_preschoolers_qs.order_by('-date_registered')

    # Paginate archived preschoolers
    paginator = Paginator(archived_preschoolers_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Convert to JSON with current age data
    archived_json = json.dumps([
        {
            "id": p.preschooler_id,
            "first_name": p.first_name,
            "last_name": p.last_name,
            "name": "{p.first_name} {p.last_name}",
            "age": p.age_in_months if p.age_in_months else p.age,
            "age_display": "{p.age_in_months} months" if p.age_in_months else "{p.age} years",
            "barangay": p.barangay.name if p.barangay else "N/A",
            "gender": p.sex,
            "birthdate": str(p.birth_date),
            "parent_name": "{p.parent_id.first_name} {p.parent_id.last_name}" if p.parent_id else "N/A",
            "archived_date": p.date_registered.strftime("%Y-%m-%d") if p.date_registered else "N/A",
            "weight": "",
            "height": "",
            "bmi": "",
            "immunization_status": "",
            "nutrition_history": [],
            "notes": ""
        } for p in page_obj
    ])

    return render(request, 'HTML/archived.html', {
        'archived_preschoolers_json': archived_json,
        'archived_page': page_obj,
    })

def auto_archive_aged_preschoolers():
    """
    Simple auto-archive function - just sets is_archived=True for 60+ month olds
    """
    # Get all active preschoolers
    active_preschoolers = Preschooler.objects.filter(is_archived=False)
    archived_count = 0
    today = date.today()
    
    for preschooler in active_preschoolers:
        # Use the model's age_in_months property
        age_in_months = preschooler.age_in_months
        
        # Archive if 60+ months old
        if age_in_months and age_in_months >= 60:
            preschooler.is_archived = True
            preschooler.save()
            
            print("AUTO-ARCHIVED: {preschooler.first_name} {preschooler.last_name} - Age: {age_in_months} months")
            archived_count += 1
    
    return archived_count

def archived_details(request):
    return render(request, 'HTML/archived_details.html')

def dashboard(request):
    # ✅ Redirect to login if not authenticated
    if not request.user.is_authenticated:
        return redirect('login')

    # ✅ Get the current user's account (with profile photo)
    account = get_object_or_404(
        Account.objects.select_related('profile_photo'),
        email=request.user.email
    )

    # ✅ Active preschoolers (barangay-specific)
    preschoolers = Preschooler.objects.filter(
        is_archived=False,
        barangay=account.barangay
    ).prefetch_related('bmi_set')

    preschooler_count = preschoolers.count()

    # ✅ Archived preschoolers (barangay-specific)
    archived_preschooler_count = Preschooler.objects.filter(
        is_archived=True,
        barangay=account.barangay
    ).count()

    # ✅ Parents (barangay-specific)
    parent_accounts = Parent.objects.filter(
        barangay=account.barangay
    ).distinct().order_by('-created_at')

    parent_count = parent_accounts.count()
    print("DEBUG Dashboard ({account.barangay}): Parent count = {parent_count}")

    # ✅ Nutritional Summary via WHO BMI-for-age Z-scores
    nutritional_summary = {
        'severely_wasted': 0,
        'wasted': 0,
        'normal': 0,
        'risk_of_overweight': 0,
        'overweight': 0,
        'obese': 0,
    }

    preschoolers_with_bmi = 0
    today = date.today()

    for p in preschoolers:
        latest_bmi = p.bmi_set.order_by('-date_recorded').first()
        if latest_bmi:
            try:
                # --- Compute age in months ---
                birth_date = p.birth_date
                age_years = today.year - birth_date.year
                age_months = today.month - birth_date.month
                if today.day < birth_date.day:
                    age_months -= 1
                if age_months < 0:
                    age_years -= 1
                    age_months += 12
                total_age_months = age_years * 12 + age_months

                # --- Compute BMI and classify ---
                bmi_value = calculate_bmi(latest_bmi.weight, latest_bmi.height)
                z = bmi_zscore(p.sex, total_age_months, bmi_value)
                category = classify_bmi_for_age(z)

                preschoolers_with_bmi += 1
                if category == "Severely Wasted":
                    nutritional_summary['severely_wasted'] += 1
                elif category == "Wasted":
                    nutritional_summary['wasted'] += 1
                elif category == "Normal":
                    nutritional_summary['normal'] += 1
                elif category == "Risk of overweight":
                    nutritional_summary['risk_of_overweight'] += 1
                elif category == "Overweight":
                    nutritional_summary['overweight'] += 1
                elif category == "Obese":
                    nutritional_summary['obese'] += 1

            except Exception as e:
                print("⚠️ BMI classification error for preschooler {p.id}: {e}")

    # ✅ Calculate percentages
    nutritional_percentages = {}
    if preschoolers_with_bmi > 0:
        for key, value in nutritional_summary.items():
            percentage = round((value / preschoolers_with_bmi) * 100, 1)
            nutritional_percentages[key] = percentage
    else:
        nutritional_percentages = {key: 0 for key in nutritional_summary.keys()}

    # ✅ Prepare pie chart data (matching WHO categories)
    pie_chart_data = {
        'labels': [
            'Severely Wasted',
            'Wasted',
            'Normal',
            'Risk of Overweight',
            'Overweight',
            'Obese'
        ],
        'values': [
            nutritional_summary['severely_wasted'],
            nutritional_summary['wasted'],
            nutritional_summary['normal'],
            nutritional_summary['risk_of_overweight'],
            nutritional_summary['overweight'],
            nutritional_summary['obese']
        ],
        'percentages': [
            nutritional_percentages['severely_wasted'],
            nutritional_percentages['wasted'],
            nutritional_percentages['normal'],
            nutritional_percentages['risk_of_overweight'],
            nutritional_percentages['overweight'],
            nutritional_percentages['obese']
        ],
        'colors': ['#e74c3c', '#f39c12', '#27ae60', '#f1c40f', '#e67e22', '#c0392b']
    }

    # ✅ Recent parent account notifications (barangay-specific)
    notifications = []
    seen_ids = set()

    for parent in parent_accounts:
        if parent.parent_id not in seen_ids:
            notifications.append({
                'type': 'account',
                'id': parent.parent_id,
                'full_name': parent.full_name,
                'user_role': 'Parent',
                'timestamp': parent.created_at,
            })
            seen_ids.add(parent.parent_id)

    notifications.sort(key=lambda x: x['timestamp'], reverse=True)
    latest_notif_timestamp = notifications[0]['timestamp'] if notifications else None

    # ✅ Fetch active announcements (global)
    try:
        announcements = Announcement.objects.filter(
            is_active=True
        ).order_by('-created_at')[:10]
    except Exception:
        announcements = []

    return render(request, 'HTML/dashboard.html', {
        'account': account,
        'full_name': account.full_name,
        'preschooler_count': preschooler_count,
        'archived_preschooler_count': archived_preschooler_count,
        'parent_count': parent_count,
        'nutritional_summary': nutritional_summary,
        'nutritional_percentages': nutritional_percentages,
        'preschoolers_with_bmi': preschoolers_with_bmi,
        'pie_chart_data': pie_chart_data,
        'notifications': notifications[:15],
        'latest_notif_timestamp': latest_notif_timestamp.isoformat() if latest_notif_timestamp else '',
        'announcements': announcements,
    })


@csrf_exempt
def upload_cropped_photo(request):
    if request.method == 'POST' and request.user.is_authenticated:
        image = request.FILES.get('cropped_image')
        account = Account.objects.get(email=request.user.email)

        if hasattr(account, 'profile_photo'):
            account.profile_photo.image = image
            account.profile_photo.save()
        else:
            ProfilePhoto.objects.create(account=account, image=image)

        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'unauthorized'}, status=403)

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def login(request):
    # 👇 If already logged in, redirect based on role (persistent login)
    if request.user.is_authenticated:
        role = request.session.get('user_role', '').lower()
        if role == 'parent':
            return redirect('parent_dashboard')
        elif role == 'admin':
            return redirect('Admindashboard')
        else:  # midwife, nurse, bhw, etc.
            return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        fcm_token = request.POST.get('fcm_token', None)  # ✅ Capture FCM token

        # 🔐 Admin hardcoded login
        if email.lower() == 'admin@gmail.com' and password == 'admin123':
            request.session['user_role'] = 'admin'
            request.session['full_name'] = 'Admin'
            return redirect('Admindashboard')

        # ✅ Authenticate using email as username
        user = authenticate(request, username=email, password=password)

        if user is not None:
            try:
                account = Account.objects.get(email=email)

                if account.is_rejected:
                    messages.error(request, "Your account has been rejected by the admin.")
                    return render(request, 'HTML/login.html')

                # ✅ BHW, BNS, MIDWIFE, and NURSE login (requires validation)
                if (account.user_role.lower() == 'healthworker' or 
                    account.user_role.lower() == 'bhw' or
                    account.user_role.lower() in ['bns', 'barangay nutritional scholar'] or
                    account.user_role.lower() == 'midwife' or
                    account.user_role.lower() == 'nurse'):

                    if not account.is_validated:
                        messages.error(request, "Your account is still pending admin validation.")
                        return render(request, 'HTML/login.html')

                    auth_login(request, user)
                    account.last_activity = timezone.now()
                    account.save(update_fields=['last_activity'])

                    request.session['email'] = account.email
                    request.session['user_role'] = account.user_role.lower()
                    request.session['full_name'] = account.full_name
                    request.session['contact_number'] = account.contact_number

                    # 🔥 Save FCM token
                    if fcm_token:
                        account.fcm_token = fcm_token
                        account.save(update_fields=["fcm_token"])

                        FCMToken.objects.update_or_create(
                            token=fcm_token,
                            defaults={
                                'account': account,
                                'device_type': 'android',
                                'is_active': True,
                            }
                        )
                        print("✅ FCM token saved for {account.email}")

                    return redirect('dashboard')

                # ✅ Parent login (NO validation required)
                elif account.user_role.lower() == 'parent':
                    try:
                        parent = Parent.objects.get(email=email)
                    except Parent.DoesNotExist:
                        messages.error(request, "Parent account not found.")
                        return render(request, 'HTML/login.html')

                    if parent.must_change_password:
                        request.session['email'] = email
                        return redirect('change_password_first')

                    auth_login(request, user)
                    account.last_activity = timezone.now()
                    account.save(update_fields=['last_activity'])

                    request.session['email'] = account.email
                    request.session['user_role'] = 'parent'
                    request.session['full_name'] = account.full_name
                    request.session['contact_number'] = account.contact_number

                    # 🔥 Save FCM token
                    if fcm_token:
                        account.fcm_token = fcm_token
                        account.save(update_fields=["fcm_token"])

                        FCMToken.objects.update_or_create(
                            token=fcm_token,
                            defaults={
                                'account': account,
                                'device_type': 'android',
                                'is_active': True,
                            }
                        )
                        print("✅ FCM token saved for {account.email}")

                    return redirect('parent_dashboard')

                # ❌ Unknown role
                else:
                    messages.warning(request, "Unknown user role: {account.user_role}. Please contact support.")
                    return redirect('login')

            except Account.DoesNotExist:
                messages.error(request, "Account record not found. Please contact support.")
                return render(request, 'HTML/login.html')

        else:
            messages.error(request, "Invalid email or password.")

    # ✅ Fetch active announcements for the login page
    try:
        announcements = Announcement.objects.filter(
            is_active=True
        ).order_by('-created_at')[:5]
    except Exception as e:
        announcements = []

    return render(request, 'HTML/login.html', {
        'announcements': announcements,
    })





def logout_view(request):
    if request.user.is_authenticated:
        try:
            account = Account.objects.get(email=request.user.email)
            account.last_activity = timezone.now()
            account.save(update_fields=['last_activity'])
        except Account.DoesNotExist:
            pass

    logout(request)
    return redirect('login')


from .models import BMI  # siguraduhin na naka-import

def parent_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')

    account = get_object_or_404(Account.objects.select_related('profile_photo'), email=request.user.email)
    try:
        parent = Parent.objects.get(email=account.email)
        full_name = parent.full_name
    except Parent.DoesNotExist:
        full_name = account.full_name or "Unknown User"
    preschoolers_raw = Preschooler.objects.filter(parent_id__email=account.email)

    # Compute age per preschooler
    preschoolers = []
    today = date.today()

    for p in preschoolers_raw:
        birth_date = p.birth_date

        # Calculate years
        age_years = today.year - birth_date.year
        # Calculate months
        age_months = today.month - birth_date.month
        # Calculate days
        age_days = today.day - birth_date.day

        # Adjust if days are negative
        if age_days < 0:
            age_months -= 1
            if today.month == 1:
                last_month = 12
                last_year = today.year - 1
            else:
                last_month = today.month - 1
                last_year = today.year

            from calendar import monthrange
            days_in_last_month = monthrange(last_year, last_month)[1]
            age_days += days_in_last_month

        # Adjust if months are negative
        if age_months < 0:
            age_years -= 1
            age_months += 12

        # ✅ Convert total age in months (needed for WHO classification)
        total_age_months = age_years * 12 + age_months

        # ✅ Get latest BMI status using WHO BMI-for-age Z-scores
        latest_bmi = BMI.objects.filter(preschooler_id=p).order_by('-date_recorded').first()
        bmi_status = None
        if latest_bmi:
            try:
                bmi_value = calculate_bmi(latest_bmi.weight, latest_bmi.height)
                z = bmi_zscore(p.sex, total_age_months, bmi_value)
                bmi_status = classify_bmi_for_age(z)
            except Exception as e:
                print("Error calculating BMI/Z-score for preschooler {p.id}: {e}")
                bmi_status = p.nutritional_status  # fallback

        preschoolers.append({
            'data': p,
            'age_years': age_years,
            'age_months': age_months,
            'age_days': age_days,
            'bmi_status': bmi_status or p.nutritional_status  # fallback if no BMI record
        })

    # Show welcome message only once per session
    if not request.session.get('first_login_shown', False):
        messages.success(request, " Welcome, {account.full_name}!")    
        request.session['first_login_shown'] = True

    # ✅ FIXED: Filter upcoming schedules - only show 'scheduled' status
    upcoming_schedules = VaccinationSchedule.objects.filter(
        preschooler__in=preschoolers_raw,
        status='scheduled'
    ).order_by('scheduled_date')

    # ✅ Fetch active announcements for parents
    try:
        announcements = Announcement.objects.filter(
            is_active=True
        ).order_by('-created_at')[:10]
    except Exception as e:
        announcements = []

    return render(request, 'HTML/parent_dashboard.html', {
        'account': account,
        'full_name': "{account.first_name} {account.last_name}".strip(),
        'preschoolers': preschoolers,
        'upcoming_schedules': upcoming_schedules,
        'announcements': announcements,
        'today': today,
    })




import threading

def send_notifications_async(parent, account, preschooler, vaccine_name, dose_number, required_doses, immunization_date, next_schedule, schedule):
    """Background thread to handle both email + push notifications"""
    try:
        # === Email notification ===
        if parent.email:
            try:
                subject = "[PPMS] Vaccination Scheduled for {preschooler.first_name}"
                message = (
                    "Dear {parent.full_name},\n\n"
                    "A vaccination appointment has been scheduled for your child, "
                    "{preschooler.first_name} {preschooler.last_name}.\n\n"
                    "Vaccine: {vaccine_name}\n"
                    "Dose: {dose_number} of {required_doses}\n"
                    "Scheduled Date: {immunization_date}\n"
                    "{f'Next Dose: {next_schedule}\n' if next_schedule else ''}"
                    "\nPlease bring your child on the scheduled date.\n"
                    "You can confirm completion on your dashboard.\n\n"
                    "Thank you,\nPPMS System"
                )

                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [parent.email],
                    fail_silently=False
                )
                logger.info("[ASYNC] Email sent to {parent.email}")
            except Exception as email_error:
                logger.error("[ASYNC] Email failed for {parent.email}: {email_error}")

        # === Push notification ===
        if account and account.fcm_token:
            try:
                notification_title = "Vaccination Scheduled for {preschooler.first_name}"
                notification_body = (
                    "{vaccine_name} (Dose {dose_number}/{required_doses}) "
                    "scheduled for {immunization_date}"
                )

                notification_data = {
                    "type": "vaccination_schedule",
                    "preschooler_id": str(preschooler.preschooler_id),
                    "preschooler_name": "{preschooler.first_name} {preschooler.last_name}",
                    "vaccine_name": vaccine_name,
                    "dose_number": str(dose_number),
                    "total_doses": str(required_doses),
                    "scheduled_date": str(immunization_date),
                    "schedule_id": str(schedule.id)
                }

                logger.info("[ASYNC] Sending push to {parent.email}")
                PushNotificationService.send_push_notification(
                    token=account.fcm_token,
                    title=notification_title,
                    body=notification_body,
                    data=notification_data
                )
            except Exception as push_error:
                logger.error("[ASYNC] Push failed for {parent.email}: {push_error}")
        else:
            logger.warning("[ASYNC] No FCM token found for {parent.email}")

    except Exception as e:
        logger.error("[ASYNC] Notification error for {parent.email}: {e}")


@login_required
def add_schedule(request, preschooler_id):
    """Add vaccination schedule with improved async notification handling"""
    logger.info("[DEBUG] Entered add_schedule view for preschooler {preschooler_id}")

    try:
        from .models import Preschooler, VaccinationSchedule, Account
        preschooler = get_object_or_404(Preschooler, pk=preschooler_id)
        logger.info("[DEBUG] Found preschooler: {preschooler.first_name} {preschooler.last_name}")
    except Exception as e:
        logger.error("[DEBUG] Error getting preschooler: {e}")
        messages.error(request, "Preschooler not found")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    if request.method != "POST":
        logger.warning("[DEBUG] Request method is not POST")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    # Extract POST values
    vaccine_name = request.POST.get("vaccine_name")
    required_doses = request.POST.get("required_doses", "1")
    vaccine_doses = request.POST.get("vaccine_doses", "1")
    immunization_date = request.POST.get("immunization_date")
    next_schedule = request.POST.get("next_vaccine_schedule")
    current_dose = request.POST.get("current_dose")

    if not vaccine_name or not immunization_date:
        logger.warning("[DEBUG] Missing required fields")
        messages.error(request, "Please fill in all required fields.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    try:
        existing_completed = VaccinationSchedule.objects.filter(
            preschooler=preschooler,
            vaccine_name=vaccine_name,
            status='completed'
        ).count()

        existing_pending = VaccinationSchedule.objects.filter(
            preschooler=preschooler,
            vaccine_name=vaccine_name,
            status__in=['scheduled', 'rescheduled']
        ).count()

        dose_number = int(current_dose) if current_dose else existing_completed + existing_pending + 1

        schedule = VaccinationSchedule.objects.create(
            preschooler=preschooler,
            vaccine_name=vaccine_name,
            doses=dose_number,
            required_doses=int(required_doses) if required_doses else 1,
            scheduled_date=immunization_date,
            next_vaccine_schedule=next_schedule or None,
            status='scheduled',
            confirmed_by_parent=False
        )
        logger.info("[DEBUG] VaccinationSchedule saved: {schedule.id}")

        messages.success(
            request,
            "Vaccination schedule for {vaccine_name} (Dose {dose_number}) added successfully!"
        )

        # === Fire off async notifications ===
        parents = preschooler.parents.all()
        for parent in parents:
            account = Account.objects.filter(email=parent.email).first()
            threading.Thread(
                target=send_notifications_async,
                args=(parent, account, preschooler, vaccine_name, dose_number, required_doses, immunization_date, next_schedule, schedule)
            ).start()

    except Exception as e:
        logger.error("[ERROR] Failed to save schedule or notify: {e}")
        messages.error(request, "Error: {str(e)}")

    return redirect(request.META.get("HTTP_REFERER", "/"))


def send_nutrition_notifications_async(parents, preschooler, service_type, dose_number, total_doses, service_date, notes, schedule):
    """Background task: send email + push notifications for nutrition services"""
    from .models import Account
    from .services import PushNotificationService

    for parent in parents:
        try:
            # === Email Notification ===
            if parent.email:
                try:
                    subject = "[PPMS] Nutrition Service Scheduled for {preschooler.first_name}"
                    message = (
                        "Dear {parent.full_name},\n\n"
                        "A nutrition service appointment has been scheduled for your child, "
                        "{preschooler.first_name} {preschooler.last_name}.\n\n"
                        "Service Type: {service_type}\n"
                        "Dose: {dose_number} of {total_doses}\n"
                        "Scheduled Date: {service_date}\n"
                        "{f'Notes: {notes}\n' if notes else ''}"
                        "\nPlease bring your child on the scheduled date.\n"
                        "You can confirm completion on your dashboard.\n\n"
                        "Thank you,\nPPMS System"
                    )
                    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [parent.email], fail_silently=False)
                    logger.info("[ASYNC] Nutrition email sent to {parent.email}")
                except Exception as e:
                    logger.error("[ASYNC] Failed to send nutrition email to {parent.email}: {e}")

            # === Push Notification ===
            try:
                account = Account.objects.filter(email=parent.email).first()
                if account and account.fcm_token:
                    service_emoji = "🍎" if service_type == "Vitamin A" else "💊"
                    title = "{service_emoji} Nutrition Service Scheduled for {preschooler.first_name}"
                    body = "{service_type} (Dose {dose_number}/{total_doses}) scheduled for {service_date}"
                    data = {
                        "type": "nutrition_service_schedule",
                        "preschooler_id": str(preschooler.preschooler_id),
                        "preschooler_name": "{preschooler.first_name} {preschooler.last_name}",
                        "service_type": service_type,
                        "dose_number": str(dose_number),
                        "total_doses": str(total_doses),
                        "scheduled_date": str(service_date),
                        "schedule_id": str(schedule.id),
                        "notes": notes
                    }
                    PushNotificationService.send_push_notification(
                        token=account.fcm_token,
                        title=title,
                        body=body,
                        data=data
                    )
                    logger.info("[ASYNC] Nutrition push sent to {parent.email}")
                else:
                    logger.warning("[ASYNC] No FCM token for {parent.email}")
            except Exception as e:
                logger.error("[ASYNC] Failed to send nutrition push to {parent.email}: {e}")

        except Exception as e:
            logger.error("[ASYNC] Error handling parent {parent.email}: {e}")


@login_required
def schedule_nutrition_service(request, preschooler_id):
    """Schedule nutrition service with async push/email notifications"""
    from .models import Preschooler, NutritionService

    logger.info("[DEBUG] Entered schedule_nutrition_service view for preschooler {preschooler_id}")
    try:
        preschooler = get_object_or_404(Preschooler, pk=preschooler_id)
        logger.info("[DEBUG] Found preschooler: {preschooler.first_name} {preschooler.last_name}")
    except Exception as e:
        logger.error("[DEBUG] Error getting preschooler: {e}")
        messages.error(request, "Preschooler not found")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    if request.method != "POST":
        logger.warning("[DEBUG] Request method is not POST")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    # Extract POST values
    service_type = request.POST.get("service_type")
    service_date = request.POST.get("service_date")
    notes = request.POST.get("notes", "")

    if not service_type or not service_date:
        messages.error(request, "Please fill in all required fields.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    try:
        # Calculate dose
        existing_completed = NutritionService.objects.filter(
            preschooler=preschooler,
            service_type=service_type,
            status='completed'
        ).count()
        existing_pending = NutritionService.objects.filter(
            preschooler=preschooler,
            service_type=service_type,
            status__in=['scheduled', 'rescheduled']
        ).count()
        dose_number = existing_completed + existing_pending + 1
        total_doses = 10

        # Save nutrition service schedule
        schedule = NutritionService.objects.create(
            preschooler=preschooler,
            service_type=service_type,
            scheduled_date=service_date,
            status='scheduled',
            notes=notes,
            confirmed_by_parent=False
        )
        logger.info("[DEBUG] NutritionService saved: {schedule.id}")

        messages.success(
            request,
            "Nutrition service schedule for {service_type} (Dose {dose_number}) added successfully!"
        )

        # === Async notifications ===
        parents = preschooler.parents.all()
        if parents:
            threading.Thread(
                target=send_nutrition_notifications_async,
                args=(parents, preschooler, service_type, dose_number, total_doses, service_date, notes, schedule)
            ).start()
        else:
            logger.warning("No parents found for this preschooler")

    except Exception as e:
        logger.error("[ERROR] Failed to save nutrition schedule or send notifications: {e}")
        messages.error(request, "Error: {str(e)}")

    return redirect(request.META.get("HTTP_REFERER", "/"))

@csrf_exempt
@login_required
def update_nutrition_status(request, schedule_id):
    """Update nutrition service status with enhanced notifications"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    try:
        import json
        from .models import NutritionService, Account

        data = json.loads(request.body)
        status = data.get('status')
        enhanced_notifications = data.get('enhanced_notifications', False)
        
        schedule = get_object_or_404(NutritionService, id=schedule_id)
        preschooler = schedule.preschooler
        
        logger.info("[DEBUG] Updating nutrition status for schedule {schedule_id} to {status}")
        
        if status == 'completed':
            from django.utils import timezone
            schedule.status = 'completed'
            schedule.completion_date = timezone.now()
            schedule.save()
            
            # Check if more doses are needed
            completed_doses = NutritionService.objects.filter(
                preschooler=preschooler,
                service_type=schedule.service_type,
                status='completed'
            ).count()
            
            total_doses = 10  # Standard
            needs_next_dose = completed_doses < total_doses
            fully_completed = completed_doses >= total_doses
            
            logger.info("[DEBUG] Completed doses: {completed_doses}/{total_doses}")
            
            # === Run notifications asynchronously ===
            if enhanced_notifications:
                def send_notifications():
                    parents = preschooler.parents.all()
                    for parent in parents:
                        # --- EMAIL ---
                        if parent.email:
                            try:
                                if fully_completed:
                                    subject = "[PPMS] {schedule.service_type} Treatment Complete for {preschooler.first_name}"
                                    message = (
                                        "Dear {parent.full_name},\n\n"
                                        "Congratulations! Your child {preschooler.first_name} {preschooler.last_name} "
                                        "has completed all {total_doses} doses of {schedule.service_type}.\n\n"
                                        "Treatment completed on: {schedule.completion_date.strftime('%B %d, %Y at %I:%M %p')}\n\n"
                                        "Thank you for ensuring your child received proper nutrition care.\n\n"
                                        "PPMS System"
                                    )
                                else:
                                    subject = "[PPMS] {schedule.service_type} Dose Completed for {preschooler.first_name}"
                                    message = (
                                        "Dear {parent.full_name},\n\n"
                                        "Your child {preschooler.first_name} {preschooler.last_name} "
                                        "has received dose {completed_doses} of {total_doses} "
                                        "for {schedule.service_type}.\n\n"
                                        "Completed on: {schedule.completion_date.strftime('%B %d, %Y at %I:%M %p')}\n\n"
                                        "Remaining doses needed: {total_doses - completed_doses}\n\n"
                                        "Thank you,\nPPMS System"
                                    )

                                send_mail(
                                    subject, 
                                    message, 
                                    settings.DEFAULT_FROM_EMAIL,
                                    [parent.email], 
                                    fail_silently=False
                                )
                                logger.info("[DEBUG] Email sent to {parent.email}")
                            except Exception as email_error:
                                logger.error("[DEBUG] Email sending failed: {email_error}")
                        
                        # --- PUSH ---
                        try:
                            account = Account.objects.filter(email=parent.email).first()
                            if account and account.fcm_token:
                                service_emoji = "🍎" if schedule.service_type == "Vitamin A" else "💊"
                                
                                if fully_completed:
                                    notification_title = "🏆 {schedule.service_type} Treatment Complete!"
                                    notification_body = "{preschooler.first_name} completed all {total_doses} doses"
                                else:
                                    notification_title = "{service_emoji} {schedule.service_type} Dose Complete"
                                    notification_body = "Dose {completed_doses}/{total_doses} completed for {preschooler.first_name}"
                                
                                notification_data = {
                                    "type": "nutrition_service_completed",
                                    "preschooler_id": str(preschooler.preschooler_id),
                                    "preschooler_name": "{preschooler.first_name} {preschooler.last_name}",
                                    "service_type": schedule.service_type,
                                    "completed_doses": str(completed_doses),
                                    "total_doses": str(total_doses),
                                    "fully_completed": str(fully_completed).lower(),
                                    "completion_date": schedule.completion_date.isoformat() if schedule.completion_date else ""
                                }
                                
                                push_result = PushNotificationService.send_push_notification(
                                    token=account.fcm_token,
                                    title=notification_title,
                                    body=notification_body,
                                    data=notification_data
                                )
                                logger.info("[DEBUG] Push result: {push_result}")
                        except Exception as push_error:
                            logger.error("[DEBUG] Push error: {push_error}")

                # 🔹 Run notifications in a background thread
                threading.Thread(target=send_notifications, daemon=True).start()
            
            # Return response immediately
            if fully_completed:
                return JsonResponse({
                    'success': True,
                    'message': f'All {schedule.service_type} doses completed successfully!',
                    'fully_completed': True,
                    'service_type': schedule.service_type,
                    'completed_doses': completed_doses,
                    'total_doses': total_doses
                })
            elif needs_next_dose:
                return JsonResponse({
                    'success': True,
                    'message': f'Dose {completed_doses} completed! {total_doses - completed_doses} doses remaining.',
                    'needs_next_dose': True,
                    'service_type': schedule.service_type,
                    'completed_doses': completed_doses,
                    'total_doses': total_doses
                })
            else:
                return JsonResponse({
                    'success': True,
                    'message': 'Nutrition service status updated successfully!',
                    'completed_doses': completed_doses,
                    'total_doses': total_doses
                })
        
        else:
            # Handle other status updates
            schedule.status = status
            schedule.save()
            return JsonResponse({
                'success': True,
                'message': f'Status updated to {status} successfully!'
            })
            
    except Exception as e:
        logger.error("[ERROR] Failed to update nutrition status: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error updating status: {str(e)}'
        })

@login_required
def reschedule_nutrition_service(request, schedule_id):
    """Reschedule nutrition service with async push/email notification handling"""
    logger.info("[DEBUG] Entered reschedule_nutrition_service view for schedule {schedule_id}")

    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method"})

    try:
        from .models import NutritionService, Account
        import json, threading
        
        # Parse JSON data
        data = json.loads(request.body)
        new_date = data.get('new_date')
        reschedule_reason = data.get('reschedule_reason', '')
        enhanced_notifications = data.get('enhanced_notifications', False)
        
        logger.info("[DEBUG] Reschedule data: new_date={new_date}, reason={reschedule_reason}, enhanced={enhanced_notifications}")

        # Get the nutrition service schedule
        schedule = get_object_or_404(NutritionService, pk=schedule_id)
        preschooler = schedule.preschooler
        old_date = schedule.scheduled_date
        
        # Validate required fields
        if not new_date or not reschedule_reason.strip():
            return JsonResponse({
                "success": False, 
                "message": "Please provide both a new date and reason for rescheduling."
            })

        # Update the schedule
        schedule.scheduled_date = new_date
        schedule.status = 'rescheduled'
        reschedule_info = "Rescheduled from {old_date} to {new_date}. Reason: {reschedule_reason}"
        schedule.notes = "{(schedule.notes + '; ') if schedule.notes else ''}{reschedule_info}"
        schedule.save()
        
        logger.info("[DEBUG] Schedule updated successfully")

        # === Run notifications asynchronously ===
        if enhanced_notifications:
            def send_notifications():
                parents = preschooler.parents.all()
                logger.info("[DEBUG] Found {parents.count()} parent(s) for reschedule notifications")
                
                for parent in parents:
                    logger.info("[DEBUG] Processing notifications for parent: {parent.full_name} ({parent.email})")

                    # --- EMAIL ---
                    if parent.email:
                        try:
                            subject = "[PPMS] Nutrition Service Rescheduled for {preschooler.first_name}"
                            message = (
                                "Dear {parent.full_name},\n\n"
                                "The nutrition service appointment for your child, "
                                "{preschooler.first_name} {preschooler.last_name}, has been rescheduled.\n\n"
                                "Service Type: {schedule.service_type}\n"
                                "Original Date: {old_date}\n"
                                "New Date: {new_date}\n"
                                "Reason: {reschedule_reason}\n"
                                "\nPlease bring your child on the new scheduled date.\n"
                                "You can view the updated schedule on your dashboard.\n\n"
                                "Thank you for your understanding,\nPPMS System"
                            )
                            
                            send_mail(
                                subject, 
                                message, 
                                settings.DEFAULT_FROM_EMAIL,
                                [parent.email], 
                                fail_silently=False
                            )
                            logger.info("[DEBUG] Reschedule email sent to {parent.email}")
                        except Exception as email_error:
                            logger.error("[DEBUG] Reschedule email failed: {email_error}")

                    # --- PUSH ---
                    try:
                        account = Account.objects.filter(email=parent.email).first()
                        if account and account.fcm_token:
                            service_emoji = "🍎" if schedule.service_type == "Vitamin A" else "💊"
                            notification_title = "{service_emoji} Nutrition Service Rescheduled"
                            notification_body = (
                                "{schedule.service_type} for {preschooler.first_name} moved to {new_date}"
                            )
                            
                            notification_data = {
                                "type": "nutrition_service_reschedule",
                                "preschooler_id": str(preschooler.preschooler_id),
                                "preschooler_name": "{preschooler.first_name} {preschooler.last_name}",
                                "service_type": schedule.service_type,
                                "old_date": str(old_date),
                                "new_date": str(new_date),
                                "reschedule_reason": reschedule_reason,
                                "schedule_id": str(schedule.id)
                            }
                            
                            push_result = PushNotificationService.send_push_notification(
                                token=account.fcm_token,
                                title=notification_title,
                                body=notification_body,
                                data=notification_data
                            )
                            logger.info("[DEBUG] Push notification result for {parent.email}: {push_result}")
                        else:
                            logger.warning("[DEBUG] No FCM token found for parent {parent.email}")
                    except Exception as push_error:
                        logger.error("[DEBUG] Push error for {parent.email}: {push_error}")

            # 🔹 Launch async thread for notifications
            threading.Thread(target=send_notifications, daemon=True).start()

        # Return response immediately
        return JsonResponse({
            "success": True,
            "message": "{schedule.service_type} successfully rescheduled to {new_date}",
            "new_date": new_date,
            "reschedule_reason": reschedule_reason
        })

    except Exception as e:
        logger.error("[ERROR] Failed to reschedule nutrition service: {e}")
        return JsonResponse({
            "success": False,
            "message": "Error rescheduling service: {str(e)}"
        })
@login_required
def add_nutrition_service(request, preschooler_id):
    """Add completed nutrition service with notifications"""
    logger.info("[DEBUG] Entered add_nutrition_service view for preschooler {preschooler_id}")

    try:
        from .models import Preschooler, NutritionHistory, Account
        preschooler = get_object_or_404(Preschooler, pk=preschooler_id)
        logger.info("[DEBUG] Found preschooler: {preschooler.first_name} {preschooler.last_name}")
    except Exception as e:
        logger.error("[DEBUG] Error getting preschooler: {e}")
        messages.error(request, "Preschooler not found")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    if request.method != "POST":
        logger.warning("[DEBUG] Request method is not POST")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    # Extract POST values
    service_type = request.POST.get("service_type")
    completion_date = request.POST.get("completion_date")
    notes = request.POST.get("notes", "")

    logger.info("[DEBUG] Form data:")
    logger.info("[DEBUG]   service_type: {service_type}")
    logger.info("[DEBUG]   completion_date: {completion_date}")
    logger.info("[DEBUG]   notes: {notes}")

    # Validate required fields
    if not service_type or not completion_date:
        logger.warning("[DEBUG] Missing required fields")
        messages.error(request, "Please fill in all required fields.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    try:
        # Count existing completed services
        existing_count = NutritionHistory.objects.filter(
            preschooler=preschooler,
            service_type=service_type,
            status='completed'
        ).count()

        dose_number = existing_count + 1

        # Save nutrition history
        nutrition_history = NutritionHistory.objects.create(
            preschooler=preschooler,
            service_type=service_type,
            completion_date=completion_date,
            notes=notes,
            status='completed',
            dose_number=dose_number
        )
        logger.info("[DEBUG] NutritionHistory saved: {nutrition_history.id}")
        
        messages.success(
            request,
            "Nutrition service {service_type} (Dose {dose_number}) added successfully!"
        )

        # === SEND COMPLETION NOTIFICATIONS ===
        parents = preschooler.parents.all()
        logger.info("[DEBUG] Found {parents.count()} parent(s) for completion notification")
        
        for parent in parents:
            # Send email
            if parent.email:
                try:
                    subject = "[PPMS] Nutrition Service Completed for {preschooler.first_name}"
                    message = (
                        "Dear {parent.full_name},\n\n"
                        "A nutrition service has been completed for your child, "
                        "{preschooler.first_name} {preschooler.last_name}.\n\n"
                        "Service: {service_type}\n"
                        "Dose: {dose_number}\n"
                        "Completion Date: {completion_date}\n"
                        "{f'Notes: {notes}\n' if notes else ''}"
                        "\nThank you,\nPPMS System"
                    )
                    
                    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [parent.email], fail_silently=False)
                    logger.info("[DEBUG] Completion email sent to parent {parent.email}")
                except Exception as email_error:
                    logger.error("[DEBUG] Completion email sending failed: {email_error}")

            # Send push notification
            try:
                account = Account.objects.filter(email=parent.email).first()
                if account and account.fcm_token:
                    nutrition_icon = "✅🍎" if service_type == "Vitamin A" else "✅💊"
                    notification_title = "{nutrition_icon} Nutrition Service Completed"
                    notification_body = "{service_type} completed for {preschooler.first_name}"
                    
                    notification_data = {
                        "type": "nutrition_completed",
                        "preschooler_id": str(preschooler.preschooler_id),
                        "preschooler_name": "{preschooler.first_name} {preschooler.last_name}",
                        "service_type": service_type,
                        "dose_number": str(dose_number),
                        "completion_date": str(completion_date)
                    }
                    
                    push_result = PushNotificationService.send_push_notification(
                        token=account.fcm_token,
                        title=notification_title,
                        body=notification_body,
                        data=notification_data
                    )
                    
                    if push_result.get("success"):
                        logger.info("[DEBUG] Completion push notification sent to {parent.email}")
                    else:
                        logger.error("[DEBUG] Completion push notification failed for {parent.email}")
                        
            except Exception as push_error:
                logger.error("[DEBUG] Error sending completion push notification: {push_error}")

    except Exception as e:
        logger.error("[ERROR] Failed to save nutrition history: {e}")
        messages.error(request, "Error: {str(e)}")

    return redirect(request.META.get("HTTP_REFERER", "/"))


@require_POST #may binago ako dito
def confirm_schedule(request, schedule_id):
    if not request.user.is_authenticated:
        return redirect('login')

    schedule = get_object_or_404(VaccinationSchedule, id=schedule_id)

    if schedule.preschooler.parent_id.email != request.user.email:
        messages.error(request, "Unauthorized confirmation attempt.")
        return redirect('parent_dashboard')

    # ✅ Mark current schedule as confirmed
    schedule.confirmed_by_parent = True
    schedule.save()

    # 🚫 Prevent over-scheduling
    if (
        schedule.next_vaccine_schedule and 
        schedule.doses < schedule.required_doses
    ):
        # Double check that no future duplicate already exists
        existing = VaccinationSchedule.objects.filter(
            preschooler=schedule.preschooler,
            vaccine_name=schedule.vaccine_name,
            doses=schedule.doses + 1
        ).exists()

        if not existing:
            next_schedule = VaccinationSchedule.objects.create(
                preschooler=schedule.preschooler,
                vaccine_name=schedule.vaccine_name,
                doses=schedule.doses + 1,
                required_doses=schedule.required_doses,
                scheduled_date=schedule.next_vaccine_schedule,
                scheduled_by=schedule.scheduled_by,
                confirmed_by_parent=False
            )
            print("[DEBUG] ➕ Created next dose schedule:", next_schedule)
            messages.success(request, "Dose {schedule.doses} confirmed. ✅ Next dose scheduled.")
        else:
            print("[DEBUG] ⛔ Skipped creating duplicate schedule")
    else:
        print("[DEBUG] ✅ Final dose confirmed. No more schedules.")
        messages.success(request, "Vaccination confirmed. ✅")

    return redirect('parent_dashboard')

def confirm_vaccine_schedule(request, schedule_id):
    if request.method == 'POST':
        schedule = get_object_or_404(VaccinationSchedule, id=schedule_id)
        schedule.confirmed_by_parent = True
        schedule.save()
        return JsonResponse({'status': 'success', 'message': 'Schedule confirmed!'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

def get_vaccine_status(preschooler, vaccine_name, total_doses):
    """Calculate vaccine status and completed doses"""
    # Count actual completed doses (each completed schedule = 1 dose)
    completed_doses = VaccinationSchedule.objects.filter(
        preschooler=preschooler,
        vaccine_name=vaccine_name,
        status='completed'
    ).count()
    
    # Get any pending schedule
    pending_schedule = VaccinationSchedule.objects.filter(
        preschooler=preschooler,
        vaccine_name=vaccine_name,
        status__in=['scheduled', 'rescheduled']
    ).first()
    
    # Determine status based on completed doses vs total required
    if completed_doses >= total_doses:
        # All doses completed
        return {
            'status': 'completed',
            'completed_doses': completed_doses,
            'total_doses': total_doses,
            'immunization_date': 'Completed',
            'action': 'Fully Vaccinated'
        }
    elif pending_schedule:
        # Has a pending schedule
        return {
            'status': pending_schedule.status,
            'completed_doses': completed_doses,
            'total_doses': total_doses,
            'immunization_date': pending_schedule.scheduled_date.strftime("%m/%d/%Y"),
            'action': 'scheduled',
            'schedule_id': pending_schedule.id
        }
    else:
        # No completed doses and no pending schedule
        return {
            'status': 'not_scheduled',
            'completed_doses': completed_doses,
            'total_doses': total_doses,
            'immunization_date': 'N/A',
            'action': 'needs_schedule'
        }

def get_vaccine_status_with_dose_tracking(preschooler, vaccine_name, total_doses):
    """
    Calculate vaccine status with proper dose tracking
    Assumes you have a 'current_dose' field in VaccinationSchedule model
    """
    # Get all schedules for this vaccine
    schedules = VaccinationSchedule.objects.filter(
        preschooler=preschooler,
        vaccine_name=vaccine_name
    ).order_by('scheduled_date')
    
    completed_doses = 0
    pending_schedule = None
    
    for schedule in schedules:
        if schedule.status == 'completed':
            # If you have a current_dose field, use it; otherwise count as 1 dose
            completed_doses += getattr(schedule, 'current_dose', 1)
        elif schedule.status in ['scheduled', 'rescheduled'] and not pending_schedule:
            pending_schedule = schedule
    
    if completed_doses >= total_doses:
        return {
            'status': 'completed',
            'completed_doses': min(completed_doses, total_doses),  # Cap at total_doses
            'total_doses': total_doses,
            'immunization_date': 'Completed',
            'action': 'Fully Vaccinated'
        }
    elif pending_schedule:
        return {
            'status': pending_schedule.status,
            'completed_doses': completed_doses,
            'total_doses': total_doses,
            'immunization_date': pending_schedule.scheduled_date.strftime("%m/%d/%Y"),
            'action': 'scheduled',
            'schedule_id': pending_schedule.id
        }
    else:
        return {
            'status': 'not_scheduled',
            'completed_doses': completed_doses,
            'total_doses': total_doses,
            'immunization_date': 'N/A',
            'action': 'needs_schedule'
        }

def parents_mypreschooler(request, preschooler_id):
    preschooler = get_object_or_404(
        Preschooler.objects.prefetch_related(
            Prefetch('bmi_set', queryset=BMI.objects.order_by('-date_recorded'), to_attr='bmi_records')
        ),
        pk=preschooler_id
    )

    # --- Calculate age with years, months, and days ---
    today = date.today()
    birth_date = preschooler.birth_date
    
    age_years = today.year - birth_date.year
    age_months = today.month - birth_date.month
    age_days = today.day - birth_date.day
    
    if age_days < 0:
        age_months -= 1
        if today.month == 1:
            last_month = 12
            last_year = today.year - 1
        else:
            last_month = today.month - 1
            last_year = today.year
        days_in_last_month = monthrange(last_year, last_month)[1]
        age_days += days_in_last_month
    
    if age_months < 0:
        age_years -= 1
        age_months += 12

    total_age_months = age_years * 12 + age_months  # ✅ needed for WHO standards

    # --- Get latest BMI ---
    latest_bmi = preschooler.bmi_records[0] if preschooler.bmi_records else None

    # --- Interpret BMI-for-age (WHO Z-scores) ---
    weight_for_age_status = "N/A"
    height_for_age_status = "N/A"
    weight_height_for_age_status = "N/A"
    
    if latest_bmi:
        try:
            bmi_value = calculate_bmi(latest_bmi.weight, latest_bmi.height)
            z = bmi_zscore(preschooler.sex, total_age_months, bmi_value)
            weight_height_for_age_status = classify_bmi_for_age(z)
        except Exception as e:
            print("⚠️ BMI calculation error for preschooler {preschooler.id}: {e}")
            weight_height_for_age_status = preschooler.nutritional_status or "N/A"

    # --- Get immunization history (detailed per dose with numbering) ---
    immunization_records = preschooler.vaccination_schedules.filter(
        confirmed_by_parent=True,
        status='completed'
    ).order_by('vaccine_name', 'scheduled_date')

    immunization_history = []
    vaccine_dose_counter = defaultdict(int)

    for record in immunization_records:
        vaccine_dose_counter[record.vaccine_name] += 1
        
        immunization_history.append({
            'vaccine_name': record.vaccine_name,
            'doses': "{vaccine_dose_counter[record.vaccine_name]}/{record.required_doses}",
            'given_date': record.scheduled_date,  # or record.completion_date
        })

    # --- Get nutrition services ---
    nutrition_services = preschooler.nutrition_services.all().order_by('-completion_date')

    # --- Get parent account (with profile photo) ---
    account = get_object_or_404(Account.objects.select_related('profile_photo'), email=request.user.email)

    return render(request, 'HTML/parents_mypreschooler.html', {
        'preschooler': preschooler,
        'account': account,
        'age_years': age_years,
        'age_months': age_months,
        'age_days': age_days,
        'latest_bmi': latest_bmi,
        'weight_for_age_status': weight_for_age_status,
        'height_for_age_status': height_for_age_status,
        'weight_height_for_age_status': weight_height_for_age_status,
        'immunization_history': immunization_history,
        'nutrition_services': nutrition_services,
    })


@login_required
def add_vaccine(request, preschooler_id):
    if request.method == 'POST':
        preschooler = get_object_or_404(Preschooler, preschooler_id=preschooler_id)

        vaccine_name = request.POST.get('vaccine_name')
        doses = request.POST.get('required_doses')  # This will always be 1
        immunization_date = request.POST.get('immunization_date')

        try:
            # Parse the immunization date
            immunization_date_obj = datetime.strptime(immunization_date, '%Y-%m-%d').date()
            
            # Create completion_date from immunization_date (set time to noon)
            completion_datetime = datetime.combine(immunization_date_obj, datetime.min.time().replace(hour=12))
            completion_date = timezone.make_aware(completion_datetime, timezone.get_current_timezone())

            doses_int = int(doses)  # This will be 1

            # Create the vaccination record for 1 dose
            VaccinationSchedule.objects.create(
                preschooler=preschooler,
                vaccine_name=vaccine_name,
                required_doses=doses_int,  # Always 1
                scheduled_date=immunization_date_obj,
                status='completed',
                completion_date=completion_date,
                reschedule_reason=None
            )

            messages.success(request, f'1 dose of {vaccine_name} added to immunization history successfully!')

        except ValueError:
            messages.error(request, 'Invalid date format provided.')
        except Exception as e:
            messages.error(request, f'Error adding vaccine: {str(e)}')

    return redirect('preschooler_detail', preschooler_id=preschooler_id)


from datetime import date
from calendar import monthrange
from django.shortcuts import render, get_object_or_404
from .models import Preschooler

# -------------------------------
# WHO Growth Standards Reference
# -------------------------------

WEIGHT_REF_GIRLS = {
    0: {"-3SD": 2.0, "-2SD": 2.4, "median": 3.2, "+2SD": 4.2, "+3SD": 4.8},
    6: {"-3SD": 5.1, "-2SD": 5.7, "median": 7.3, "+2SD": 9.0, "+3SD": 9.8},
    12: {"-3SD": 6.0, "-2SD": 7.0, "median": 8.9, "+2SD": 10.8, "+3SD": 12.0},
    24: {"-3SD": 7.5, "-2SD": 8.7, "median": 11.5, "+2SD": 14.2, "+3SD": 15.8},
    36: {"-3SD": 8.8, "-2SD": 10.2, "median": 13.9, "+2SD": 17.0, "+3SD": 19.0},
    48: {"-3SD": 10.2, "-2SD": 11.8, "median": 16.0, "+2SD": 19.8, "+3SD": 22.2},
    60: {"-3SD": 11.5, "-2SD": 13.3, "median": 18.2, "+2SD": 22.7, "+3SD": 25.5},
}

HEIGHT_REF_GIRLS = {
    0: {"-3SD": 43.6, "-2SD": 45.4, "median": 49.1, "+2SD": 52.9, "+3SD": 54.7},
    6: {"-3SD": 58.1, "-2SD": 61.0, "median": 65.7, "+2SD": 70.5, "+3SD": 73.5},
    12: {"-3SD": 65.9, "-2SD": 68.9, "median": 74.0, "+2SD": 79.2, "+3SD": 82.3},
    24: {"-3SD": 76.0, "-2SD": 80.0, "median": 86.4, "+2SD": 92.9, "+3SD": 96.9},
    36: {"-3SD": 83.6, "-2SD": 88.0, "median": 95.1, "+2SD": 102.2, "+3SD": 106.6},
    48: {"-3SD": 90.7, "-2SD": 95.0, "median": 102.7, "+2SD": 110.6, "+3SD": 115.0},
    60: {"-3SD": 96.1, "-2SD": 100.7, "median": 109.4, "+2SD": 118.2, "+3SD": 122.8},
}

WEIGHT_REF_BOYS = {
    0: {"-3SD": 2.1, "-2SD": 2.5, "median": 3.3, "+2SD": 4.4, "+3SD": 5.0},
    6: {"-3SD": 5.4, "-2SD": 6.0, "median": 7.9, "+2SD": 9.7, "+3SD": 10.9},
    12: {"-3SD": 6.4, "-2SD": 7.5, "median": 9.6, "+2SD": 11.8, "+3SD": 13.3},
    24: {"-3SD": 8.6, "-2SD": 9.7, "median": 12.2, "+2SD": 15.3, "+3SD": 17.1},
    36: {"-3SD": 10.0, "-2SD": 11.3, "median": 14.3, "+2SD": 17.9, "+3SD": 20.0},
    48: {"-3SD": 11.5, "-2SD": 12.9, "median": 16.3, "+2SD": 20.6, "+3SD": 23.1},
    60: {"-3SD": 12.9, "-2SD": 14.5, "median": 18.7, "+2SD": 23.9, "+3SD": 26.8},
}

HEIGHT_REF_BOYS = {
    0: {"-3SD": 44.2, "-2SD": 46.1, "median": 49.9, "+2SD": 53.7, "+3SD": 55.6},
    6: {"-3SD": 61.0, "-2SD": 63.0, "median": 67.6, "+2SD": 72.2, "+3SD": 74.2},
    12: {"-3SD": 68.6, "-2SD": 71.0, "median": 75.7, "+2SD": 80.5, "+3SD": 82.9},
    24: {"-3SD": 78.0, "-2SD": 81.0, "median": 87.1, "+2SD": 93.3, "+3SD": 96.3},
    36: {"-3SD": 85.0, "-2SD": 89.0, "median": 96.0, "+2SD": 103.1, "+3SD": 106.9},
    48: {"-3SD": 91.9, "-2SD": 96.0, "median": 103.9, "+2SD": 111.9, "+3SD": 116.1},
    60: {"-3SD": 97.2, "-2SD": 101.2, "median": 111.2, "+2SD": 121.4, "+3SD": 125.9},
}

WFH_GIRLS = {
    65: {"-3SD": 5.0, "-2SD": 5.8, "median": 7.5, "+2SD": 9.5, "+3SD": 10.9},
    70: {"-3SD": 5.7, "-2SD": 6.5, "median": 8.5, "+2SD": 10.8, "+3SD": 12.4},
    75: {"-3SD": 6.3, "-2SD": 7.2, "median": 9.5, "+2SD": 12.1, "+3SD": 13.9},
    80: {"-3SD": 7.0, "-2SD": 8.0, "median": 10.6, "+2SD": 13.5, "+3SD": 15.6},
    90: {"-3SD": 8.8, "-2SD": 10.1, "median": 13.1, "+2SD": 16.7, "+3SD": 19.4},
    100: {"-3SD": 11.2, "-2SD": 12.8, "median": 16.0, "+2SD": 20.6, "+3SD": 23.9},
    110: {"-3SD": 14.3, "-2SD": 16.4, "median": 19.2, "+2SD": 24.5, "+3SD": 28.2},
}

WFH_BOYS = {
    65: {"-3SD": 5.1, "-2SD": 5.9, "median": 7.6, "+2SD": 9.7, "+3SD": 11.1},
    70: {"-3SD": 5.9, "-2SD": 6.7, "median": 8.7, "+2SD": 11.0, "+3SD": 12.6},
    75: {"-3SD": 6.5, "-2SD": 7.5, "median": 9.8, "+2SD": 12.4, "+3SD": 14.2},
    80: {"-3SD": 7.3, "-2SD": 8.3, "median": 11.0, "+2SD": 13.9, "+3SD": 16.0},
    90: {"-3SD": 9.1, "-2SD": 10.5, "median": 13.6, "+2SD": 17.2, "+3SD": 20.0},
    100: {"-3SD": 11.6, "-2SD": 13.2, "median": 16.5, "+2SD": 21.0, "+3SD": 24.4},
    110: {"-3SD": 14.8, "-2SD": 16.8, "median": 20.0, "+2SD": 25.6, "+3SD": 29.5},
}

# -------------------------------
# Helper Functions
# -------------------------------

def interpolate_value(x, ref_table):
    """Interpolate between reference points."""
    pts = sorted(ref_table.keys())
    if x <= pts[0]:
        return ref_table[pts[0]]
    if x >= pts[-1]:
        return ref_table[pts[-1]]
    for i in range(len(pts) - 1):
        p1, p2 = pts[i], pts[i + 1]
        if p1 <= x <= p2:
            r1, r2 = ref_table[p1], ref_table[p2]
            return {k: r1[k] + (r2[k] - r1[k]) * ((x - p1) / (p2 - p1)) for k in r1}

def classify_weight_for_age(age_months, weight, table):
    r = interpolate_value(age_months, table)
    if weight < r["-3SD"]:
        return "Severely Underweight"
    elif weight < r["-2SD"]:
        return "Underweight"
    elif weight > r["+2SD"]:
        return "Overweight"
    else:
        return "Normal"

def classify_height_for_age(age_months, height, table):
    r = interpolate_value(age_months, table)
    if height < r["-3SD"]:
        return "Severely stunted"
    elif height < r["-2SD"]:
        return "Stunted"
    elif height > r["+2SD"]:
        return "Tall"
    else:
        return "Normal"

def classify_weight_for_height(height, weight, table):
    r = interpolate_value(height, table)
    if weight < r["-3SD"]:
        return "Severely Wasted"
    elif weight < r["-2SD"]:
        return "Wasted"
    elif weight > r["+3SD"]:
        return "Obese"
    elif weight > r["+2SD"]:
        return "Overweight"
    else:
        return "Normal"
    
def preschooler_detail(request, preschooler_id):
    """
    Enhanced view function with age-based vaccine scheduling that automatically archives 
    preschoolers who reach 60+ months and provides age-appropriate vaccine scheduling.
    """
    # AUTO-ARCHIVE CHECK - Run before showing preschooler details
    auto_archived_count = auto_archive_aged_preschoolers()
    if auto_archived_count > 0:
        print("AUTO-ARCHIVED: {auto_archived_count} preschoolers during detail view")
    
    # Get preschooler or 404 if not found or archived
    preschooler = get_object_or_404(Preschooler, preschooler_id=preschooler_id, is_archived=False)
    
    # Check if this specific preschooler should be archived (safety check)
    if preschooler.age_in_months and preschooler.age_in_months >= 60:
        preschooler.is_archived = True
        preschooler.save()
        messages.warning(request, "{preschooler.first_name} {preschooler.last_name} has been automatically archived as they have exceeded the preschooler age limit (60 months).")
        return redirect('preschoolers')
    
    bmi = preschooler.bmi_set.order_by('-date_recorded').first()

    # Calculate age in months using timezone.now() for time zone consistency
    today = timezone.now().date()
    birth_date = preschooler.birth_date
    age_years = today.year - birth_date.year
    age_months = today.month - birth_date.month
    age_days = today.day - birth_date.day

    if age_days < 0:
        age_months -= 1
        if today.month == 1:
            last_month, last_year = 12, today.year - 1
        else:
            last_month, last_year = today.month - 1, today.year
        age_days += monthrange(last_year, last_month)[1]

    if age_months < 0:
        age_years -= 1
        age_months += 12

    total_age_months = age_years * 12 + age_months

    # Defaults
    weight_for_age_status = "N/A"
    height_for_age_status = "N/A"
    weight_for_height_status = "N/A"
    nutritional_status = "N/A"

    if bmi:  # we have a BMI record
        sex = preschooler.sex.lower()
        
        try:
            # Choose correct tables based on gender
            if sex in ['female', 'girl', 'f']:
                weight_for_age_status = classify_weight_for_age(total_age_months, bmi.weight, WEIGHT_REF_GIRLS)
                height_for_age_status = classify_height_for_age(total_age_months, bmi.height, HEIGHT_REF_GIRLS)
                weight_for_height_status = classify_weight_for_height(bmi.height, bmi.weight, WFH_GIRLS)
            else:
                weight_for_age_status = classify_weight_for_age(total_age_months, bmi.weight, WEIGHT_REF_BOYS)
                height_for_age_status = classify_height_for_age(total_age_months, bmi.height, HEIGHT_REF_BOYS)
                weight_for_height_status = classify_weight_for_height(bmi.height, bmi.weight, WFH_BOYS)

            z = bmi_zscore(preschooler.sex, total_age_months, bmi.bmi_value)
            nutritional_status = classify_bmi_for_age(z)
        except Exception as e:
            print("Error during BMI classification: {e}")
            nutritional_status = "Error"

    # Define standard vaccines with corrected doses based on your requirements
    standard_vaccines = [
        {'name': 'BCG Vaccine', 'total_doses': 1},
        {'name': 'Hepatitis B Vaccine', 'total_doses': 1},  # Changed to 1 as per your requirement
        {'name': 'Pentavalent Vaccine', 'total_doses': 3},
        {'name': 'Oral Polio Vaccine', 'total_doses': 3},   # Changed from 4 to 3
        {'name': 'Inactivated Polio Vaccine', 'total_doses': 2},  # Changed from 3 to 2
        {'name': 'Pneumococcal Conjugate Vaccine', 'total_doses': 3},  # Changed from 4 to 3
        {'name': 'Measles, Mumps, and Rubella', 'total_doses': 2},
    ]
    
    
    # Calculate enhanced status for each vaccine with age-based scheduling
    vaccine_statuses = []
    for vaccine in standard_vaccines:
        
        status = get_enhanced_vaccine_status(preschooler, vaccine['name'], vaccine['total_doses'])
        
        # Add eligibility information
        eligibility = get_vaccine_eligibility(preschooler, vaccine['name'])

        
        status['eligibility_info'] = eligibility
        
        vaccine_statuses.append({
            'name': vaccine['name'],
            'total_doses': vaccine['total_doses'],
            **status
        })
    

    # Define standard nutrition services (age-independent for now)
    standard_nutrition_services = [
        {'name': 'Vitamin A', 'total_doses': 10},
        {'name': 'Deworming', 'total_doses': 10},
    ]
    
    # Calculate status for each nutrition service
    nutrition_statuses = []
    for service in standard_nutrition_services:
        status = get_enhanced_nutrition_status(preschooler, service['name'], service['total_doses'])
        nutrition_statuses.append({
            'name': service['name'],
            'total_doses': service['total_doses'],
            **status
        })

    # FIXED: Enhanced data retrieval with proper separation of completed vs scheduled
    try:
        # Only COMPLETED vaccinations for vaccine card and PDF
        immunization_history = preschooler.vaccination_schedules.filter(
            status='completed'
        ).order_by('vaccine_name', 'completion_date')
        
        # Only SCHEDULED/PENDING appointments for the schedule table
        pending_schedules = preschooler.vaccination_schedules.filter(
            status__in=['scheduled', 'rescheduled', 'pending']
        ).exclude(status='completed').order_by('scheduled_date')
        
    except AttributeError:
        from .models import VaccinationSchedule
        
        # Only COMPLETED vaccinations for vaccine card and PDF
        immunization_history = VaccinationSchedule.objects.filter(
            preschooler=preschooler,
            status='completed'
        ).order_by('vaccine_name', 'completion_date')
        
        # Only SCHEDULED/PENDING appointments for the schedule table  
        pending_schedules = VaccinationSchedule.objects.filter(
            preschooler=preschooler,
            status__in=['scheduled', 'rescheduled', 'pending']
        ).exclude(status='completed').order_by('scheduled_date')

    # Add dose numbers to completed vaccinations only
    vaccine_dose_counter = defaultdict(int)
    for record in immunization_history:
        vaccine_dose_counter[record.vaccine_name] += 1
        record.dose_number = vaccine_dose_counter[record.vaccine_name]

    # Debug: Print what we're sending to template
    print("DEBUG - Completed vaccinations: {immunization_history.count()}")
    print("DEBUG - Pending schedules: {pending_schedules.count()}")
    for record in immunization_history:
        print("  Completed: {record.vaccine_name} - {record.status} - {record.completion_date}")
    for record in pending_schedules:
        print("  Pending: {record.vaccine_name} - {record.status} - {record.scheduled_date}")

    # Enhanced nutrition services handling
    try:
        nutrition_services = preschooler.nutrition_services.all().order_by('-completion_date')
    except AttributeError:
        try:
            from .models import NutritionSchedule
            nutrition_services = NutritionSchedule.objects.filter(
                preschooler=preschooler
            ).order_by('-service_date')
        except:
            from .models import NutritionHistory
            nutrition_services = NutritionHistory.objects.filter(
                preschooler=preschooler
            ).order_by('-completion_date')

    context = {
        'preschooler': preschooler,
        'bmi': bmi,
        'immunization_history': immunization_history,  # ONLY completed vaccinations
        'pending_schedules': pending_schedules,        # ONLY scheduled/pending appointments
        'nutrition_services': nutrition_services,
        'nutrition_statuses': nutrition_statuses,
        'vaccine_statuses': vaccine_statuses,
        'age_years': age_years,
        'age_months': age_months,
        'age_days': age_days,
        'total_age_months': total_age_months,
        'nutritional_status': nutritional_status,
        'weight_for_age_status': weight_for_age_status,
        'height_for_age_status': height_for_age_status,
        'weight_for_height_status': weight_for_height_status,
    }

    return render(request, 'HTML/preschooler_data.html', context)

def get_nutrition_eligibility(preschooler, service_type):
    """
    Enhanced nutrition eligibility that properly handles completed services
    and calculates next availability based on 6-month intervals
    """
    today = timezone.now().date()
    birth_date = preschooler.birth_date
    
    # Calculate total age in months
    age_years = today.year - birth_date.year
    age_months = today.month - birth_date.month
    age_days = today.day - birth_date.day

    if age_days < 0:
        age_months -= 1
        if today.month == 1:
            last_month, last_year = 12, today.year - 1
        else:
            last_month, last_year = today.month - 1, today.year
        age_days += monthrange(last_year, last_month)[1]

    if age_months < 0:
        age_years -= 1
        age_months += 12

    total_age_months = age_years * 12 + age_months
    
    # Nutrition services eligibility rules - both start at 6 months
    nutrition_schedule = {
        'Vitamin A': {
            'min_age_months': 6,
            'interval_months': 6,
            'max_age_months': 59,
            'eligible_ages': [6, 12, 18, 24, 30, 36, 42, 48, 54]
        },
        'Deworming': {
            'min_age_months': 6,
            'interval_months': 6,
            'max_age_months': 59,
            'eligible_ages': [6, 12, 18, 24, 30, 36, 42, 48, 54]
        }
    }
    
    if service_type not in nutrition_schedule:
        return {
            'can_schedule': False,
            'reason': 'Unknown service type',
            'next_eligible_age': None,
            'description': 'Service not recognized'
        }
    
    service_info = nutrition_schedule[service_type]
    
    # Check if child is too young
    if total_age_months < service_info['min_age_months']:
        return {
            'can_schedule': False,
            'reason': f'Too young. {service_type} starts at {service_info["min_age_months"]} months.',
            'next_eligible_age': service_info['min_age_months'],
            'description': f'Available at {service_info["min_age_months"]} months'
        }
    
    # Check if child is too old
    if total_age_months > service_info['max_age_months']:
        return {
            'can_schedule': False,
            'reason': f'Child has exceeded age limit for {service_type}.',
            'next_eligible_age': None,
            'description': 'No longer age-appropriate'
        }
    
    # Get completed services from database
    try:
        completed_services = preschooler.nutrition_services.filter(
            service_type=service_type,
            status='completed'
        ).order_by('completion_date')
    except AttributeError:
        try:
            from .models import NutritionSchedule
            completed_services = NutritionSchedule.objects.filter(
                preschooler=preschooler,
                service_type=service_type,
                status='completed'
            ).order_by('service_date')
        except:
            completed_services = []
    
    # Check for pending schedules first
    try:
        pending_schedules = preschooler.nutrition_schedules.filter(
            service_type=service_type,
            status__in=['scheduled', 'rescheduled']
        ).exists()
    except AttributeError:
        try:
            from .models import NutritionSchedule
            pending_schedules = NutritionSchedule.objects.filter(
                preschooler=preschooler,
                service_type=service_type,
                status__in=['scheduled', 'rescheduled']
            ).exists()
        except:
            pending_schedules = False
    
    if pending_schedules:
        return {
            'can_schedule': False,
            'reason': f'{service_type} already scheduled.',
            'next_eligible_age': None,
            'description': 'Service already scheduled'
        }
    
    # Enhanced logic for determining eligibility after completed services
    if completed_services.exists():
        last_service = completed_services.last()
        try:
            last_service_date = last_service.completion_date
        except AttributeError:
            last_service_date = last_service.service_date
        
        # Calculate months since last service
        months_since_last = (today - last_service_date).days // 30
        print("DEBUG: {service_type} - Last service: {last_service_date}, Months since: {months_since_last}")
        
        # Must wait at least 6 months
        if months_since_last < 6:
            months_to_wait = 6 - months_since_last
            # Calculate the next eligible date based on last service + 6 months
            next_eligible_date = last_service_date + timedelta(days=180)  # Approximately 6 months
            next_eligible_age_months = ((next_eligible_date.year - birth_date.year) * 12 + 
                                     (next_eligible_date.month - birth_date.month))
            
            return {
                'can_schedule': False,
                'reason': f'Too soon since last {service_type}. Wait {months_to_wait} more months.',
                'next_eligible_age': next_eligible_age_months,
                'description': f'Next dose available in {months_to_wait} months'
            }
        else:
            # It's been 6+ months since last service, can schedule now
            return {
                'can_schedule': True,
                'reason': f'Child is eligible for {service_type} (6+ months since last dose)',
                'next_eligible_age': None,
                'description': f'Ready for next dose (every 6 months)',
                'current_age_months': total_age_months,
                'last_service_months_ago': months_since_last
            }
    else:
        # No completed services yet - check if at eligible age
        eligible_ages = service_info['eligible_ages']
        
        # Find the closest eligible age
        current_eligible = False
        next_eligible_age = None
        
        for age in eligible_ages:
            if total_age_months >= age:
                current_eligible = True
                # Find next eligible age for future reference
                for future_age in eligible_ages:
                    if future_age > total_age_months:
                        next_eligible_age = future_age
                        break
                break
        
        if current_eligible:
            return {
                'can_schedule': True,
                'reason': f'Child is eligible for first {service_type} dose',
                'next_eligible_age': next_eligible_age,
                'description': f'First dose (starts at 6 months)',
                'current_age_months': total_age_months
            }
        else:
            # Not old enough for first dose
            for age in eligible_ages:
                if age > total_age_months:
                    next_eligible_age = age
                    break
            
            return {
                'can_schedule': False,
                'reason': f'Not at eligible age for {service_type}.',
                'next_eligible_age': next_eligible_age,
                'description': f'First dose available at {next_eligible_age} months'
            }

def get_enhanced_nutrition_status(preschooler, service_type, total_doses):
    """
    Enhanced nutrition status that includes age-based eligibility - standalone version
    """
    # Get completed services count
    try:
        completed_services = preschooler.nutrition_services.filter(
            service_type=service_type,
            status='completed'
        )
        completed_count = completed_services.count()
        latest_service = completed_services.order_by('-completion_date').first() if completed_services.exists() else None
    except AttributeError:
        try:
            from .models import NutritionSchedule
            completed_services = NutritionSchedule.objects.filter(
                preschooler=preschooler,
                service_type=service_type,
                status='completed'
            )
            completed_count = completed_services.count()
            latest_service = completed_services.order_by('-service_date').first() if completed_services.exists() else None
        except:
            completed_count = 0
            latest_service = None
    
    # Get pending schedules
    try:
        pending_schedule = preschooler.nutrition_schedules.filter(
            service_type=service_type,
            status__in=['scheduled', 'rescheduled']
        ).first()
    except AttributeError:
        try:
            from .models import NutritionSchedule
            pending_schedule = NutritionSchedule.objects.filter(
                preschooler=preschooler,
                service_type=service_type,
                status__in=['scheduled', 'rescheduled']
            ).first()
        except:
            pending_schedule = None
    
    # Determine current status
    if pending_schedule:
        current_status = pending_schedule.status
        service_date = getattr(pending_schedule, 'service_date', None)
        schedule_id = pending_schedule.id
    elif completed_count > 0:
        current_status = 'completed'
        service_date = getattr(latest_service, 'completion_date', None) or getattr(latest_service, 'service_date', None)
        schedule_id = None
    else:
        current_status = 'pending'
        service_date = None
        schedule_id = None
    
    # Get eligibility information
    eligibility = get_nutrition_eligibility(preschooler, service_type)
    
    # Enhanced status logic
    enhanced_status = {
        'status': current_status,
        'completed_doses': completed_count,
        'total_doses': total_doses,
        'service_date': service_date,
        'schedule_id': schedule_id,
        'eligibility': eligibility,
        'can_schedule': eligibility['can_schedule'],
        'eligibility_reason': eligibility['reason'],
        'next_eligible_age': eligibility.get('next_eligible_age'),
        'age_description': eligibility['description']
    }
    
    # Debug logging
    print("DEBUG: {service_type} Status:")
    print("  - Completed doses: {completed_count}")
    print("  - Current status: {current_status}")
    print("  - Can schedule: {eligibility['can_schedule']}")
    print("  - Eligibility reason: {eligibility['reason']}")
    print("  - Age description: {eligibility['description']}")
    
    return enhanced_status
    

def add_nutrition_service(request, preschooler_id):
    """Add completed nutrition service (Vitamin A or Deworming) for a preschooler"""
    if request.method == 'POST':
        try:
            preschooler = get_object_or_404(Preschooler, preschooler_id=preschooler_id)
            
            service_type = request.POST.get('service_type')
            completion_date = request.POST.get('completion_date')
            notes = request.POST.get('notes', '')
            
            # Create nutrition service record as completed
            nutrition_service = NutritionService.objects.create(
                preschooler=preschooler,
                service_type=service_type,
                completion_date=completion_date,
                status='completed',
                notes=notes
            )
            
            messages.success(request, "{service_type} recorded successfully.")
            return redirect('preschooler_detail', preschooler_id=preschooler_id)
            
        except Exception as e:
            messages.error(request, "Error recording nutrition service: {str(e)}")
            return redirect('preschooler_detail', preschooler_id=preschooler_id)
    
    return redirect('preschooler_detail', preschooler_id=preschooler_id)



def send_completion_notifications_async(parents, preschooler, schedule, completed_count, required_doses):
    """Background task: send email + push notifications for vaccination completion"""
    from .models import Account
    from .services import PushNotificationService

    for parent in parents:
        try:
            # === Email Notification ===
            if parent.email:
                try:
                    if completed_count >= required_doses:
                        subject = "[PPMS] {schedule.vaccine_name} Vaccination Complete for {preschooler.first_name}"
                        message = (
                            "Dear {parent.full_name},\n\n"
                            "Great news! Your child {preschooler.first_name} {preschooler.last_name} "
                            "has completed all {required_doses} doses of {schedule.vaccine_name}.\n\n"
                            "Vaccination completed on: {schedule.completion_date.strftime('%B %d, %Y at %I:%M %p')}\n"
                            "Total doses completed: {completed_count}/{required_doses}\n\n"
                            "Your child is now fully protected against this disease.\n\n"
                            "Thank you for keeping your child's vaccinations up to date!\n\n"
                            "PPMS System"
                        )
                    else:
                        subject = "[PPMS] {schedule.vaccine_name} Dose Completed for {preschooler.first_name}"
                        message = (
                            "Dear {parent.full_name},\n\n"
                            "Your child {preschooler.first_name} {preschooler.last_name} "
                            "has received dose {completed_count} of {required_doses} for {schedule.vaccine_name}.\n\n"
                            "Vaccination completed on: {schedule.completion_date.strftime('%B %d, %Y at %I:%M %p')}\n"
                            "Progress: {completed_count}/{required_doses} doses completed\n"
                            "Remaining doses: {required_doses - completed_count}\n\n"
                            "Please ensure your child receives the remaining doses.\n\n"
                            "Thank you,\nPPMS System"
                        )

                    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [parent.email], fail_silently=False)
                    logger.info("[ASYNC] Vaccination email sent to {parent.email}")
                except Exception as e:
                    logger.error("[ASYNC] Failed to send vaccination email to {parent.email}: {e}")

            # === Push Notification ===
            account = Account.objects.filter(email=parent.email).first()
            if account and account.fcm_token:
                try:
                    if completed_count >= required_doses:
                        title = "🎉 {schedule.vaccine_name} Complete!"
                        body = "{preschooler.first_name} completed all {required_doses} doses"
                    else:
                        title = "💉 {schedule.vaccine_name} Dose Complete"
                        body = "Dose {completed_count}/{required_doses} completed for {preschooler.first_name}"

                    data = {
                        "type": "vaccination_completed",
                        "preschooler_id": str(preschooler.preschooler_id),
                        "preschooler_name": "{preschooler.first_name} {preschooler.last_name}",
                        "vaccine_name": schedule.vaccine_name,
                        "completed_doses": str(completed_count),
                        "total_doses": str(required_doses),
                        "completion_date": schedule.completion_date.isoformat(),
                        "schedule_id": str(schedule.id),
                        "fully_completed": str(completed_count >= required_doses).lower(),
                        "needs_next_dose": str(completed_count < required_doses).lower()
                    }

                    PushNotificationService.send_push_notification(
                        token=account.fcm_token,
                        title=title,
                        body=body,
                        data=data
                    )
                    logger.info("[ASYNC] Vaccination push sent to {parent.email}")
                except Exception as e:
                    logger.error("[ASYNC] Failed to send push to {parent.email}: {e}")
            else:
                logger.warning("[ASYNC] No FCM token for {parent.email}")

        except Exception as e:
            logger.error("[ASYNC] Error handling parent {parent.email}: {e}")


@require_POST
@csrf_exempt
def update_schedule_status(request, schedule_id):
    """Update vaccination schedule status with async notifications"""
    try:
        from .models import VaccinationSchedule, PreschoolerActivityLog

        schedule = get_object_or_404(VaccinationSchedule, id=schedule_id)
        data = json.loads(request.body)
        new_status = data.get('status')

        if new_status not in ['scheduled', 'completed', 'rescheduled', 'missed']:
            return JsonResponse({'success': False, 'message': 'Invalid status'})

        old_status = schedule.status
        preschooler = schedule.preschooler

        # Prevent duplicate completion
        if old_status == 'completed' and new_status == 'completed':
            return JsonResponse({'success': False, 'message': 'Already completed'})

        # ✅ NEW CHECK: Prevent early completion
        if new_status == 'completed':
            immunization_date = schedule.scheduled_date
            if immunization_date and now().date() < immunization_date:
                return JsonResponse({
                    'success': False,
                    'message': f'You can only mark this as completed on or after {immunization_date.strftime("%B %d, %Y")}.'
                })

            schedule.status = new_status
            schedule.completion_date = timezone.now()
            schedule.administered_date = timezone.now().date()
            schedule.confirmed_by_parent = True
            schedule.save()

            current_dose = schedule.doses or 1
            required_doses = schedule.required_doses or 1

            completed_count = VaccinationSchedule.objects.filter(
                preschooler=schedule.preschooler,
                vaccine_name=schedule.vaccine_name,
                status='completed'
            ).count()

            PreschoolerActivityLog.objects.create(
                preschooler_name="{preschooler.first_name} {preschooler.last_name}",
                activity="Vaccination completed: {schedule.vaccine_name} (Dose {current_dose})",
                performed_by=request.user.username if request.user.is_authenticated else 'System',
                barangay=schedule.preschooler.barangay
            )

            # === Async notifications ===
            parents = preschooler.parents.all()
            threading.Thread(
                target=send_completion_notifications_async,
                args=(parents, preschooler, schedule, completed_count, required_doses)
            ).start()

            if completed_count < required_doses:
                return JsonResponse({
                    'success': True,
                    'message': f'Dose {completed_count} completed. {required_doses - completed_count} doses remaining.',
                    'needs_next_dose': True,
                    'completed_doses': completed_count,
                    'total_doses': required_doses,
                    'vaccine_name': schedule.vaccine_name
                })
            else:
                return JsonResponse({
                    'success': True,
                    'message': f'All {required_doses} doses completed for {schedule.vaccine_name}!',
                    'fully_completed': True
                })

        else:
            schedule.status = new_status
            schedule.save()
            status_messages = {
                'scheduled': 'Vaccination rescheduled successfully',
                'rescheduled': 'Vaccination marked as rescheduled',
                'missed': 'Vaccination marked as missed'
            }
            return JsonResponse({'success': True, 'message': status_messages.get(new_status, 'Status updated')})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'})
    except Exception as e:
        logger.error("[ERROR] update_schedule_status: {e}")
        return JsonResponse({'success': False, 'message': f'Error updating status: {str(e)}'})



def send_reschedule_notifications_async(parent, account, preschooler, schedule, old_date, new_date, reschedule_reason):
    """Background thread for reschedule notifications"""
    try:
        # === Email notification ===
        if parent.email:
            try:
                subject = "[PPMS] Vaccination Rescheduled for {preschooler.first_name}"
                message = (
                    "Dear {parent.full_name},\n\n"
                    "The vaccination appointment for your child {preschooler.first_name} {preschooler.last_name} "
                    "has been rescheduled.\n\n"
                    "Vaccine: {schedule.vaccine_name}\n"
                    "Original Date: {old_date.strftime('%B %d, %Y')}\n"
                    "New Date: {new_date.strftime('%B %d, %Y')}\n"
                    "Reason: {reschedule_reason}\n\n"
                    "Please mark your calendar with the new appointment date.\n"
                    "If you have any questions, please contact the health center.\n\n"
                    "Thank you for your understanding,\nPPMS System"
                )

                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [parent.email],
                    fail_silently=False
                )
                logger.info("[ASYNC] Reschedule email sent to {parent.email}")
            except Exception as email_error:
                logger.error("[ASYNC] Reschedule email failed for {parent.email}: {email_error}")

        # === Push notification ===
        if account and account.fcm_token:
            try:
                notification_title = "Vaccination Rescheduled - {preschooler.first_name}"
                notification_body = (
                    "{schedule.vaccine_name} moved from {old_date.strftime('%b %d')} "
                    "to {new_date.strftime('%b %d, %Y')}. "
                    "Reason: {reschedule_reason}"
                )

                notification_data = {
                    "type": "vaccination_reschedule",
                    "preschooler_id": str(preschooler.preschooler_id),
                    "preschooler_name": "{preschooler.first_name} {preschooler.last_name}",
                    "vaccine_name": schedule.vaccine_name,
                    "old_date": str(old_date),
                    "new_date": str(new_date),
                    "reason": reschedule_reason,
                    "schedule_id": str(schedule.id)
                }

                PushNotificationService.send_push_notification(
                    token=account.fcm_token,
                    title=notification_title,
                    body=notification_body,
                    data=notification_data
                )
                logger.info("[ASYNC] Reschedule push sent to {parent.email}")
            except Exception as push_error:
                logger.error("[ASYNC] Reschedule push failed for {parent.email}: {push_error}")
        else:
            logger.warning("[ASYNC] No FCM token for {parent.email}")

    except Exception as e:
        logger.error("[ASYNC] Error in reschedule notification for {parent.email}: {e}")


@require_POST
def reschedule_vaccination(request):
    """Handle vaccination rescheduling with async notifications"""
    schedule_id = request.POST.get('schedule_id')
    new_date = request.POST.get('new_date')
    reschedule_reason = request.POST.get('reschedule_reason', '')

    try:
        from .models import VaccinationSchedule, PreschoolerActivityLog, Account

        schedule = get_object_or_404(VaccinationSchedule, id=schedule_id)
        preschooler = schedule.preschooler

        # Parse and update
        new_schedule_date = datetime.strptime(new_date, '%Y-%m-%d').date()
        old_date = schedule.scheduled_date

        schedule.scheduled_date = new_schedule_date
        schedule.status = 'rescheduled'
        schedule.reschedule_reason = reschedule_reason
        schedule.save()

        logger.info("[DEBUG] Vaccination rescheduled: {schedule.vaccine_name} from {old_date} to {new_schedule_date}")

        PreschoolerActivityLog.objects.create(
            preschooler_name="{preschooler.first_name} {preschooler.last_name}",
            activity="Vaccination rescheduled: {schedule.vaccine_name} from {old_date} to {new_schedule_date}",
            performed_by=request.user.email if hasattr(request.user, 'email') else 'System',
            barangay=preschooler.barangay
        )

        # === Async notifications per parent ===
        parents = preschooler.parents.all()
        for parent in parents:
            account = Account.objects.filter(email=parent.email).first()
            threading.Thread(
                target=send_reschedule_notifications_async,
                args=(parent, account, preschooler, schedule, old_date, new_schedule_date, reschedule_reason)
            ).start()

        messages.success(
            request,
            f'Vaccination successfully rescheduled to {new_schedule_date.strftime("%B %d, %Y")}. Notifications are being sent.'
        )

    except Exception as e:
        logger.error("[ERROR] Failed to reschedule vaccination: {e}")
        messages.error(request, f'Error rescheduling vaccination: {str(e)}')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    return redirect('preschooler_detail', preschooler_id=schedule.preschooler.preschooler_id)
    
def update_preschooler_photo(request, preschooler_id):
    preschooler = get_object_or_404(Preschooler, preschooler_id=preschooler_id)

    if request.method == 'POST' and 'profile_photo' in request.FILES:
        preschooler.profile_photo = request.FILES['profile_photo']
        preschooler.save()
        return JsonResponse({
            'success': True,
            'new_photo_url': preschooler.profile_photo.url
        })

    return JsonResponse({'success': False}, status=400)

from django.db.models import Prefetch
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Prefetch
from .models import Preschooler, BMI, Temperature
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Prefetch
from .models import Preschooler, BMI, Temperature

from datetime import date
from django.shortcuts import get_object_or_404, render
from django.db.models import Prefetch
from django.core.paginator import Paginator
import json

def auto_archive_aged_preschoolers():
    """
    Simple auto-archive function - just sets is_archived=True for 60+ month olds
    """
    # Get all active preschoolers
    active_preschoolers = Preschooler.objects.filter(is_archived=False)
    archived_count = 0
    today = date.today()
    
    for preschooler in active_preschoolers:
        # Use the model's age_in_months property
        age_in_months = preschooler.age_in_months
        
        # Archive if 60+ months old
        if age_in_months and age_in_months >= 60:
            preschooler.is_archived = True
            preschooler.save()
            
            print("AUTO-ARCHIVED: {preschooler.first_name} {preschooler.last_name} - Age: {age_in_months} months")
            archived_count += 1
    
    return archived_count


def preschoolers(request):
    user_email = request.session.get('email')
    raw_role = (request.session.get('user_role') or '').strip().lower()

    print("=== PRESCHOOLERS VIEW DEBUG ===")
    print("Email: '{user_email}'")
    print("Raw Role: '{raw_role}'")
    print("Session data: {dict(request.session)}")

    # Get current account
    account = get_object_or_404(Account, email=user_email)

    # AUTO-ARCHIVE CHECK - Run this every time the view is accessed
    auto_archived_count = auto_archive_aged_preschoolers()
    if auto_archived_count > 0:
        print("AUTO-ARCHIVED: {auto_archived_count} preschoolers aged out (60+ months)")

    # Query preschoolers (now excluding newly auto-archived ones)
    if raw_role == 'admin':
        preschoolers_qs = Preschooler.objects.filter(is_archived=False)
        barangay_name = "All Barangays"
    else:
        preschoolers_qs = Preschooler.objects.filter(
            is_archived=False,
            barangay=account.barangay
        )
        barangay_name = account.barangay.name if account.barangay else "No Barangay"
        print("Showing preschoolers for barangay: {barangay_name}")

    preschoolers_qs = preschoolers_qs.select_related('parent_id', 'barangay') \
        .prefetch_related(
            Prefetch('bmi_set', queryset=BMI.objects.order_by('-date_recorded'), to_attr='bmi_records'),
            Prefetch('temperature_set', queryset=Temperature.objects.order_by('-date_recorded'), to_attr='temp_records')
        )

    print("Found {preschoolers_qs.count()} preschoolers")

    # Pagination
    paginator = Paginator(preschoolers_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Process nutritional status, delivery place color coding, and age in months
    for p in page_obj.object_list:
        # Get latest BMI
        latest_bmi = None
        if hasattr(p, 'bmi_records') and p.bmi_records:
            latest_bmi = p.bmi_records[0]
        else:
            latest_bmi = p.bmi_set.order_by('-date_recorded').first()

        # Nutritional status (using z-score)
        if latest_bmi and latest_bmi.bmi_value:
            try:
                # Use the model's age_in_months property
                total_age_months = p.age_in_months

                # Compute z-score & classify
                z = bmi_zscore(p.sex, total_age_months, latest_bmi.bmi_value)
                p.nutritional_status = classify_bmi_for_age(z)
            except Exception as e:
                print("Error computing BMI classification for {p.first_name}: {e}")
                p.nutritional_status = "Error"
        else:
            p.nutritional_status = None

        # Delivery place color coding
        delivery_place = getattr(p, 'place_of_delivery', None)
        print("Debug: {p.first_name} {p.last_name} - Place of delivery: '{delivery_place}'")

        if delivery_place == 'Home':
            p.delivery_class = 'delivery-home'
        elif delivery_place == 'Lying-in':
            p.delivery_class = 'delivery-lying-in'
        elif delivery_place == 'Hospital':
            p.delivery_class = 'delivery-hospital'
        elif delivery_place == 'Others':
            p.delivery_class = 'delivery-others'
        else:
            p.delivery_class = 'delivery-na'

        print("Debug: Assigned class: '{p.delivery_class}'")

    # Determine user role for template
    if raw_role in ['bhw', 'bns', 'midwife', 'nurse']:
        template_user_role = 'health_worker'
    else:
        template_user_role = raw_role

    context = {
        'preschoolers': page_obj,
        'user_email': user_email,
        'user_role': template_user_role,
        'original_role': raw_role,
        'barangay_name': barangay_name,
    }

    print("Template context:")
    print("  - user_role: '{template_user_role}'")
    print("  - original_role: '{raw_role}'")
    print("  - preschoolers count: {len(page_obj.object_list)}")
    print("  - barangay: '{barangay_name}'")
    print("=== END PRESCHOOLERS DEBUG ===")

    return render(request, 'HTML/preschoolers.html', context)

@login_required
def profile(request):
    if not request.user.is_authenticated:
        return redirect('login')

    try:
        account = Account.objects.select_related('profile_photo', 'barangay').get(email=request.user.email)
    except Account.DoesNotExist:
        messages.error(request, "Account not found. Please contact administrator.")
        return redirect('login')

    # ✅ SIMPLIFIED ADDRESS BUILDING FUNCTION
    def build_complete_address(account):
        """Build complete address from Account model individual fields"""
        address_parts = []
        
        # Check if there's already an editable_address
        if hasattr(account, 'editable_address') and account.editable_address and account.editable_address.strip():
            if account.editable_address.strip().lower() not in ['n/a', 'none', 'no address provided']:
                return account.editable_address.strip()
        
        invalid_values = {'na', 'n/a', 'none', ''}

        address_parts = []
        if account.house_number and str(account.house_number).strip().lower() not in invalid_values:
            address_parts.append("House {account.house_number}")
        if account.block and str(account.block).strip().lower() not in invalid_values:
            address_parts.append("Block {account.block}")
        if account.lot and str(account.lot).strip().lower() not in invalid_values:
            address_parts.append("Lot {account.lot}")
        if account.phase and str(account.phase).strip().lower() not in invalid_values:
            address_parts.append("Phase {account.phase}")
        if account.street and str(account.street).strip().lower() not in invalid_values:
            address_parts.append(account.street.strip())
        if account.subdivision and str(account.subdivision).strip().lower() not in invalid_values:
            address_parts.append(account.subdivision.strip())
        if account.city and str(account.city).strip().lower() not in invalid_values:
            address_parts.append(account.city.strip())
        if account.province and str(account.province).strip().lower() not in invalid_values:
            address_parts.append(account.province.strip())

        if address_parts:
            built_address = ", ".join(address_parts)
            if not account.editable_address:
                account.editable_address = built_address
                account.save()
            return built_address

        
        # ✅ FOR PARENTS, CHECK PARENT MODEL AS FALLBACK
        if account.user_role and account.user_role.lower() == 'parent':
            try:
                parent = Parent.objects.get(email=account.email)
                if parent.address and parent.address.strip():
                    parent_address = parent.address.strip()
                    # Also update the account's editable_address
                    if not account.editable_address:
                        account.editable_address = parent_address
                        account.save()
                    return parent_address
            except Parent.DoesNotExist:
                pass
        
        return "No address provided"

    # ✅ SET COMPLETE ADDRESS
    account.complete_address = build_complete_address(account)

    if request.method == 'POST':
        if 'photo' in request.FILES:
            photo_file = request.FILES['photo']
            if hasattr(account, 'profile_photo') and account.profile_photo:
                account.profile_photo.image = photo_file
                account.profile_photo.save()
            else:
                ProfilePhoto.objects.create(account=account, image=photo_file)
            messages.success(request, "Profile photo updated successfully.")
            return redirect('profile')

        # Get form data
        full_name = request.POST.get('full_name')
        address = request.POST.get('address')
        contact = request.POST.get('contact_number')
        birthdate = request.POST.get('birthdate')
        barangay_id = request.POST.get('barangay')

        # ✅ Validate contact number
        if contact and (not contact.isdigit() or len(contact) != 11):
            messages.error(request, "Contact number must be exactly 11 digits.")
            return redirect('profile')

        # Update account fields
        if full_name:
            account.full_name = full_name
        if contact:
            account.contact_number = contact
        if birthdate:
            account.birthdate = birthdate or None

        # ✅ UPDATE ADDRESS - Store in both editable_address and complete_address
        if address is not None and address.strip():
            account.editable_address = address.strip()
            account.complete_address = address.strip()
            
            # If you want to update the parent model too for parent users
            if account.user_role and account.user_role.lower() == 'parent':
                try:
                    parent = Parent.objects.get(email=account.email)
                    parent.address = address.strip()
                    parent.save()
                except Parent.DoesNotExist:
                    pass

        # ✅ Handle barangay selection
        if barangay_id:
            try:
                barangay = Barangay.objects.get(id=barangay_id)
                if account.barangay != barangay:
                    old_barangay = account.barangay
                    account.barangay = barangay

                    if account.user_role.lower() == 'parent':
                        try:
                            parent = Parent.objects.get(email=account.email)
                            parent.barangay = barangay
                            parent.save()

                            # Update preschoolers
                            Preschooler.objects.filter(parent_id=parent).update(barangay=barangay)

                            # Log transfer
                            if old_barangay:  
                                ParentActivityLog.objects.create(
                                    parent=parent,
                                    activity="Transferred to {barangay.name}",
                                    barangay=old_barangay,
                                    timestamp=timezone.now()
                                )
                                ParentActivityLog.objects.create(
                                    parent=parent,
                                    activity="Recently transferred from {old_barangay.name}",
                                    barangay=barangay,
                                    timestamp=timezone.now()
                                )

                                for p in Preschooler.objects.filter(parent_id=parent):
                                    PreschoolerActivityLog.objects.create(
                                        preschooler_name="{p.first_name} {p.last_name}",
                                        performed_by=parent.full_name,
                                        activity="Transferred to {barangay.name}",
                                        barangay=old_barangay,
                                        timestamp=timezone.now()
                                    )
                                    PreschoolerActivityLog.objects.create(
                                        preschooler_name="{p.first_name} {p.last_name}",
                                        performed_by=parent.full_name,
                                        activity="Recently transferred from {old_barangay.name}",
                                        barangay=barangay,
                                        timestamp=timezone.now()
                                    )
                        except Parent.DoesNotExist:
                            pass
            except Barangay.DoesNotExist:
                messages.error(request, "Selected barangay does not exist.")
                return redirect('profile')

        # ✅ SAVE THE ACCOUNT - This was missing!
        account.save()
        
        # Refresh the complete address after saving
        account.complete_address = build_complete_address(account)

        messages.success(request, "Profile updated successfully.")
        return redirect('profile')

    # Get dashboard URL based on role
    role = account.user_role.lower() if account.user_role else ''
    if role == 'parent':
        dashboard_url = reverse('parent_dashboard')
    elif role == 'admin':
        dashboard_url = reverse('Admindashboard') 
    else:
        dashboard_url = reverse('dashboard')

    barangays = Barangay.objects.all()

    return render(request, 'HTML/profile.html', {
        'account': account,
        'dashboard_url': dashboard_url,
        'barangays': barangays,
    })

def registered_parents(request):
    # ✅ Redirect if not authenticated
    if not request.user.is_authenticated:
        return redirect('login')

    # ✅ Get the current user's account
    account = get_object_or_404(Account, email=request.user.email)
    raw_role = (account.user_role or '').strip().lower()

    print("=== REGISTERED PARENTS VIEW DEBUG ===")
    print("User: {account.full_name} ({account.user_role})")

    # ✅ Query parents
    if raw_role == 'admin':
        parents_qs = Parent.objects.all().order_by('-created_at')
        barangay_name = "All Barangays"
    else:
        parents_qs = Parent.objects.filter(
            barangay=account.barangay
        ).order_by('-created_at')
        barangay_name = account.barangay.name if account.barangay else "No Barangay"
        print("Showing parents for barangay: {barangay_name}")

    # ✅ Pagination
    paginator = Paginator(parents_qs, 10)  # 10 parents per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # ✅ Compute children + age
    today = date.today()
    for parent in page_obj:
        preschoolers = Preschooler.objects.filter(parent_id=parent)
        for child in preschoolers:
            years = today.year - child.birth_date.year
            months = today.month - child.birth_date.month
            if today.day < child.birth_date.day:
                months -= 1
            if months < 0:
                years -= 1
                months += 12
            child.age_display = "{years} year(s) and {months} month(s)"
        parent.children = preschoolers

    context = {
        'account': account,
        'parents': page_obj,
        'barangay_name': barangay_name,
        'has_parents': parents_qs.exists(),  # ✅ para sa "No parents registered"
    }

    print("Parents count: {parents_qs.count()}")
    print("=== END REGISTERED PARENTS DEBUG ===")

    return render(request, 'HTML/registered_parent.html', context)

def register(request):
    if request.method == 'POST':
        first_name   = request.POST.get("firstName")
        middle_name  = request.POST.get("middleName")  # New field
        suffix       = request.POST.get("suffix")      # New field
        last_name    = request.POST.get("lastName")
        email        = request.POST.get("email")
        contact      = request.POST.get("contact")
        password     = request.POST.get("password")
        confirm      = request.POST.get("confirm")
        birthdate    = request.POST.get("birthdate")
        house_number = request.POST.get("house_number")   
        block        = request.POST.get("block")
        lot          = request.POST.get("lot")
        phase        = request.POST.get("phase")
        street       = request.POST.get("street")
        subdivision  = request.POST.get("city")
        city         = request.POST.get("subdivision")
        province     = request.POST.get("province")
        barangay_id  = request.POST.get("barangay_id")   # already snake_case in HTML
        role         = request.POST.get("role")

        print("[DEBUG] Registration attempt for: {first_name, last_name} ({role})")

        # --- VALIDATIONS ---
        if not all([first_name, last_name, email, contact, password, confirm, birthdate, house_number, block , lot, phase, street, subdivision, city , province , barangay_id, role]):
            messages.error(request, "Please fill out all required fields.")
            return render(request, 'HTML/register.html', {'barangays': Barangay.objects.all()})

        if password != confirm:
            messages.error(request, "Passwords do not match.")
            return render(request, 'HTML/register.html', {'barangays': Barangay.objects.all()})

        if User.objects.filter(username=email).exists() or Account.objects.filter(email=email).exists():
            messages.error(request, "This email is already registered.")
            return render(request, 'HTML/register.html', {'barangays': Barangay.objects.all()})

        # Convert birthdate string to date object
        try:
            birthdate_obj = datetime.strptime(birthdate, '%Y-%m-%d').date()
            print("[DEBUG] Birthdate converted: {birthdate} -> {birthdate_obj}")
        except ValueError as e:
            print("[DEBUG] ❌ Birthdate conversion error: {e}")
            messages.error(request, "Invalid birthdate format. Please try again.")
            return render(request, 'HTML/register.html', {'barangays': Barangay.objects.all()})

        try:
            # Step 1: Create Django User (for authentication)
            print("[DEBUG] Creating Django User...")
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            print("[DEBUG] ✅ Django User created: {user.id}")

            # Step 2: Get Barangay
            barangay = Barangay.objects.get(id=int(barangay_id))
            print("[DEBUG] ✅ Barangay found: {barangay.name}")

            # Step 3: Create Account
            print("[DEBUG] Creating Account with all info...")
            account = Account.objects.create(
                first_name=first_name,
                middle_name=middle_name,  # New field
                suffix=suffix,            # New field
                last_name=last_name,
                email=email,
                contact_number=contact,
                house_number = house_number,
                block = block,
                lot = lot,
                phase = phase,
                street = street,
                subdivision = subdivision,
                city = city,
                province = province,
                birthdate=birthdate_obj,
                password=make_password(password),
                user_role=role,
                is_validated=False,
                is_rejected=False,
                barangay=barangay
            )
            print("[DEBUG] ✅ Account created successfully: {account.account_id}")
            print("[DEBUG] 🎉 REGISTRATION COMPLETED! Role: {role}")

        except Barangay.DoesNotExist:
            print("[DEBUG] ❌ Barangay not found: {barangay_id}")
            messages.error(request, "Invalid barangay selected.")
            return render(request, 'HTML/register.html', {'barangays': Barangay.objects.all()})
            
        except Exception as e:
            print("[DEBUG] ❌ Registration error: {e}")
            messages.error(request, "Registration failed: {str(e)}")
            return render(request, 'HTML/register.html', {'barangays': Barangay.objects.all()})

        # Send Clean Email Confirmation
        try:
            # ✅ FIX 1: Create full_name variable
            full_name_parts = [first_name]
            if middle_name:
                full_name_parts.append(middle_name)
            full_name_parts.append(last_name)
            if suffix:
                full_name_parts.append(suffix)
            full_name = " ".join(full_name_parts)
            
            # Role-specific badge classes
            role_classes = {
                'BHW': 'bhw',
                'BNS': 'bns', 
                'Midwife': 'midwife'
            }
            role_class = role_classes.get(role, 'bhw')
            
            # Role display names
            role_display = {
                'BHW': 'BHW (Barangay Health Worker)',
                'BNS': 'BNS (Barangay Nutrition Scholar)',
                'Midwife': 'Midwife'
            }
            role_name = role_display.get(role, role)
            
            # Get current date
            current_date = datetime.now().strftime('%B %d, %Y')
            
            subject = f'PPMS Registration Confirmation - {role}'
            
            html_message = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>PPMS Registration Confirmation</title>
                <style>
                    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
                    
                    body {{
                        font-family: 'Inter', Arial, sans-serif;
                        background-color: #f9fafb;
                        padding: 40px 20px;
                        color: #334155;
                        line-height: 1.6;
                    }}
                    
                    .container {{
                        max-width: 560px;
                        margin: 0 auto;
                        background: white;
                        border-radius: 12px;
                        overflow: hidden;
                        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                    }}
                    
                    /* ✅ Simple header without background color */
                    .header {{
                        padding: 24px 32px;
                        text-align: center;
                        color: #111827;
                        border-bottom: 4px solid #198754;
                    }}
                    .header h1 {{
                        font-size: 24px;
                        font-weight: 600;
                        margin: 0;
                        color: #111827;
                    }}
                    .header p {{
                        font-size: 16px;
                        margin: 4px 0 0 0;
                        color: #6b7280;
                    }}
                    
                    .content {{
                        padding: 32px;
                    }}
                    
                    .greeting {{
                        font-size: 18px;
                        margin-bottom: 24px;
                        color: #1e293b;
                    }}
                    
                    .message {{
                        font-size: 16px;
                        margin-bottom: 32px;
                        color: #64748b;
                    }}
                    
                    .status {{
                        background: #fef3c7;
                        border: 1px solid #f59e0b;
                        border-radius: 8px;
                        padding: 20px;
                        margin-bottom: 32px;
                        text-align: center;
                    }}
                    
                    .status-icon {{
                        font-size: 32px;
                        margin-bottom: 12px;
                    }}
                    
                    .status h3 {{
                        font-size: 18px;
                        font-weight: 600;
                        color: #92400e;
                        margin-bottom: 8px;
                    }}
                    
                    .status p {{
                        font-size: 14px;
                        color: #92400e;
                    }}
                    
                    /* ✅ Registration Summary - Clean Style */
                    .details {{
                        background: #ecfdf5;
                        border: 1px solid #10b981;
                        padding: 24px;
                        border-radius: 6px;
                        margin: 24px 0;
                    }}
                    
                    .details h4 {{
                        margin-bottom: 16px;
                        font-size: 16px;
                        font-weight: 600;
                        color: #065f46;
                    }}
                    
                    .detail-item {{
                        margin-bottom: 12px;
                        line-height: 1.6;
                    }}
                    
                    .detail-item:last-child {{
                        margin-bottom: 0;
                    }}
                    
                    .detail-label {{
                        font-weight: bold;
                        color: #065f46;
                        display: inline;
                    }}
                    
                    .detail-value {{
                        color: #065f46;
                        display: inline;
                        margin-left: 4px;
                    }}
                    
                    .role-badge {{
                        display: inline-block;
                        background: #6366f1;
                        color: white;
                        padding: 4px 12px;
                        border-radius: 20px;
                        font-size: 12px;
                        font-weight: 500;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                    }}
                    
                    .role-badge.bhw {{ background: #10b981; }}
                    .role-badge.bns {{ background: #3b82f6; }}
                    .role-badge.midwife {{ background: #ec4899; }}
                    
                    .footer {{
                        background: #f1f5f9;
                        padding: 32px;
                        text-align: center;
                        border-top: 1px solid #e2e8f0;
                    }}
                    
                    .footer h3 {{
                        font-size: 18px;
                        font-weight: 600;
                        color: #1e293b;
                        margin-bottom: 8px;
                    }}
                    
                    .footer p {{
                        font-size: 14px;
                        color: #64748b;
                        margin-bottom: 4px;
                    }}
                    
                    .footer-divider {{
                        margin: 24px 0;
                        height: 1px;
                        background: #e2e8f0;
                    }}
                    
                    .footer-small {{
                        font-size: 12px;
                        color: #94a3b8;
                    }}
                    
                    @media (max-width: 600px) {{
                        .content {{ 
                            padding: 28px 20px; 
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <!-- Header -->
                    <div class="header">
                        <h1>PPMS Cluster 4</h1>
                        <p>Imus City Healthcare Management</p>
                    </div>
                    
                    <!-- Content -->
                    <div class="content">
                        <div class="greeting">
                            Hello <strong>{full_name}</strong>,
                        </div>
                        
                        <div class="message">
                            Thank you for registering with PPMS Cluster 4. We've received your application to join our healthcare team as a <span class="role-badge {role_class}">{role}</span>.
                        </div>
                        
                        <!-- Status -->
                        <div class="status">
                            <div class="status-icon">⏳</div>
                            <h3>Pending Approval</h3>
                            <p>Your account is under review by our admin team</p>
                        </div>
                        
                        <!-- ✅ Registration Summary - Clean Style -->
                        <div class="details">
                            <h4>Registration Summary</h4>
                            <div class="detail-item">
                                <span class="detail-label">Full Name:</span>
                                <span class="detail-value">{full_name}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Email:</span>
                                <span class="detail-value">{email}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Role:</span>
                                <span class="detail-value">{role_name}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Barangay:</span>
                                <span class="detail-value">{barangay.name}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Date Submitted:</span>
                                <span class="detail-value">{current_date}</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Footer -->
                    <div class="footer">
                        <h3>PPMS Cluster 4</h3>
                        <p>Imus City Healthcare Management</p>
                        <div class="footer-divider"></div>
                        <p class="footer-small">
                            This is an automated message. Please do not reply.<br>
                            © 2025 PPMS Cluster 4. All rights reserved.
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """

            plain_message = """
PPMS Registration Confirmation

Hello {full_name},

Thank you for registering with PPMS Cluster 4. We've received your application to join our healthcare team as a {role}.

STATUS: Pending Approval
Your account is under review by our admin team.

Registration Summary:
- Full Name: {full_name}
- Email: {email}
- Role: {role_name}
- Barangay: {barangay.name}
- Date Submitted: {current_date}

PPMS Cluster 4
Imus City Healthcare Management

This is an automated message. Please do not reply.
© 2025 PPMS Cluster 4. All rights reserved.
            """

            # ✅ FIX 2: Enhanced error handling and debug info
            print("[DEBUG] 📧 Attempting to send email to: {email}")
            print("[DEBUG] 📧 Email settings: {settings.EMAIL_BACKEND}")
            print("[DEBUG] 📧 From email: {settings.DEFAULT_FROM_EMAIL}")
            
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                html_message=html_message,
                fail_silently=False,  # ✅ Changed to False to see actual errors
            )
            print("[DEBUG] ✅ Clean email sent successfully to {email}")

        except Exception as email_error:
            print("[DEBUG] ❌ Email error: {email_error}")
            print("[DEBUG] ❌ Email error type: {type(email_error).__name__}")
            # Don't fail registration if email fails
            pass

        # Success!
        messages.success(request, "{role} registration successful. Pending admin approval.")
        return redirect('login')

    return render(request, 'HTML/register.html', {'barangays': Barangay.objects.all()})


def register_preschooler(request):
    """Register preschooler with proper barangay filtering - only allows registration in user's barangay"""
    
    if not request.user.is_authenticated:
        return redirect('login')
    
        # AUTO-ARCHIVE CHECK - Run before showing registration
    auto_archived_count = auto_archive_aged_preschoolers()
    if auto_archived_count > 0:
        print("AUTO-ARCHIVED: {auto_archived_count} preschoolers during registration view")

    # Get user's barangay using consistent logic
    user_barangay = get_user_barangay(request.user)
    current_user_info = None
    
    print("DEBUG: Current user email: {request.user.email}")
    print("DEBUG: User authenticated: {request.user.is_authenticated}")
    
    if request.user.is_authenticated:
        # Try each model to find the user and get their info
        try:
            # Try Account model first
            account = Account.objects.select_related('barangay').get(email=request.user.email)
            current_user_info = {
                'model': 'Account',
                'name': account.full_name,
                'role': account.user_role,
                'object': account
            }
            print("DEBUG: Found in Account: {account.email}, Role: {account.user_role}, Barangay: {user_barangay}")
        except Account.DoesNotExist:
            try:
                # Try BHW model
                bhw = BHW.objects.select_related('barangay').get(email=request.user.email)
                current_user_info = {
                    'model': 'BHW',
                    'name': bhw.full_name,
                    'role': 'BHW',
                    'object': bhw
                }
                print("DEBUG: Found in BHW: {bhw.email}, Barangay: {user_barangay}")
            except BHW.DoesNotExist:
                try:
                    # Try BNS model
                    bns = BNS.objects.select_related('barangay').get(email=request.user.email)
                    current_user_info = {
                        'model': 'BNS',
                        'name': bns.full_name,
                        'role': 'BNS',
                        'object': bns
                    }
                    print("DEBUG: Found in BNS: {bns.email}, Barangay: {user_barangay}")
                except BNS.DoesNotExist:
                    try:
                        # Try Midwife model
                        midwife = Midwife.objects.select_related('barangay').get(email=request.user.email)
                        current_user_info = {
                            'model': 'Midwife',
                            'name': midwife.full_name,
                            'role': 'Midwife',
                            'object': midwife
                        }
                        print("DEBUG: Found in Midwife: {midwife.email}, Barangay: {user_barangay}")
                    except Midwife.DoesNotExist:
                        try:
                            # Try Nurse model
                            nurse = Nurse.objects.select_related('barangay').get(email=request.user.email)
                            current_user_info = {
                                'model': 'Nurse',
                                'name': nurse.full_name,
                                'role': 'Nurse',
                                'object': nurse
                            }
                            print("DEBUG: Found in Nurse: {nurse.email}, Barangay: {user_barangay}")
                        except Nurse.DoesNotExist:
                            print("DEBUG: User not found in any authorized user model")

    # Validate that user exists and has proper authorization
    if not current_user_info:
        messages.error(request, "You are not authorized to register preschoolers. Please contact the administrator.")
        return redirect('dashboard')

    # Validate that user has a barangay assigned
    if not user_barangay:
        messages.error(request, "No barangay assigned to your {current_user_info['role']} account. Please contact the administrator to assign a barangay before registering preschoolers.")
        return redirect('dashboard')

    # Validate user role permissions (only for Account model)
    if current_user_info['model'] == 'Account':
        user_role_lower = current_user_info['role'].lower()
        is_authorized = (
            'bhw' in user_role_lower or 
            'health worker' in user_role_lower or
            'bns' in user_role_lower or 
            'nutritional' in user_role_lower or 
            'nutrition' in user_role_lower or
            'scholar' in user_role_lower or
            'midwife' in user_role_lower or
            'admin' in user_role_lower
        )
        
        if not is_authorized:
            messages.error(request, "Your role '{current_user_info['role']}' is not authorized to register preschoolers. Only BHW, BNS, Midwife, or Admin roles can register preschoolers.")
            return redirect('dashboard')

    print("DEBUG: Authorization passed - Role: {current_user_info['role']}, Barangay: {user_barangay}")

    # Get parents from the SAME barangay only - no cross-barangay registration
    parents_qs = Parent.objects.filter(barangay=user_barangay).order_by('-created_at')
    print("DEBUG: Found {parents_qs.count()} parents in {user_barangay}")

    # Debug: Show which parents were found
    for parent in parents_qs[:5]:  # Show first 5 for debugging
        print("DEBUG: Parent: {parent.full_name} ({parent.email}) - Barangay: {parent.barangay}")

    # Pagination
    paginator = Paginator(parents_qs, 10)  # Show 10 parents per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'HTML/register_preschooler.html', {
        'account': current_user_info['object'],
        'parents': page_obj,
        'user_barangay': user_barangay,
        'current_user_info': current_user_info,  # For debugging if needed
    })

@csrf_exempt
def register_preschooler_entry(request):
    """Create preschooler entry with barangay validation and WHO BMI integration"""
    
    if request.method == 'POST':
        try:
            # Required fields
            parent_id = request.POST.get('parent_id')
            first_name = request.POST.get('first_name', '').strip()
            middle_name = request.POST.get('middle_name', '').strip() or None  # ✅ save as None if blank
            last_name = request.POST.get('last_name', '').strip()
            suffix = request.POST.get('suffix', '').strip() or None            # ✅ save as None if blank
            birthdate = request.POST.get('birthdate')
            gender = request.POST.get('gender')

            # Validate required fields
            if not all([parent_id, first_name, last_name, birthdate, gender]):
                return JsonResponse({'status': 'error', 'message': 'All required fields must be filled.'})

            # Convert gender to WHO format (M/F)
            if gender.lower() in ['male', 'boy', 'm']:
                sex = 'M'
            elif gender.lower() in ['female', 'girl', 'f']:
                sex = 'F'
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid gender value. Must be Male or Female.'})

            # Get the registering user's barangay for validation
            user_barangay = get_user_barangay(request.user)
            if not user_barangay:
                return JsonResponse({'status': 'error', 'message': 'No barangay assigned to your account. Please contact administrator.'})

            # Get parent object and validate it's in the same barangay
            try:
                parent = Parent.objects.get(pk=parent_id, barangay=user_barangay)
            except Parent.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Parent not found in your barangay. You can only register preschoolers for parents in your assigned barangay.'})

            # Parse and validate birthdate
            birth_date = datetime.strptime(birthdate, '%Y-%m-%d').date()
            today = date.today()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

            if age < 0 or age > 6:
                return JsonResponse({'status': 'error', 'message': 'Invalid age for preschooler registration. Age must be between 0-6 years.'})

            # Create preschooler (model.save() will build full_name automatically)
            preschooler = Preschooler.objects.create(
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name,
                suffix=suffix,
                sex=sex,
                birth_date=birth_date,
                age=age,
                address=parent.address,
                parent_id=parent,
                barangay=user_barangay,
                place_of_birth=request.POST.get('place_of_birth') or None,
                birth_weight=request.POST.get('birth_weight') or None,
                birth_height=request.POST.get('birth_length') or None,
                time_of_birth=request.POST.get('time_of_birth') or None,
                type_of_birth=request.POST.get('type_of_birth') or None,
                place_of_delivery=request.POST.get('place_of_delivery') or None,
            )

            parent.registered_preschoolers.add(preschooler)

            print("DEBUG: Successfully registered preschooler {preschooler.full_name} for parent {parent.full_name} in barangay {user_barangay}")

            return JsonResponse({
                'status': 'success', 
                'message': f'Preschooler {preschooler.full_name} registered successfully in {user_barangay.name}!',
                'data': {
                    'preschooler_id': preschooler.preschooler_id,
                    'name': preschooler.full_name,
                    'sex': sex,
                    'age_months': preschooler.age_in_months,
                    'barangay': str(user_barangay)
                }
            })

        except ValueError as e:
            return JsonResponse({'status': 'error', 'message': f'Invalid date format: {str(e)}'})
        except Exception as e:
            print("DEBUG: Error in preschooler registration: {e}")
            return JsonResponse({'status': 'error', 'message': f'Registration failed: {str(e)}'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

    
# Additional helper function to get preschoolers by barangay
def get_preschoolers_by_barangay(request):
    """Get preschoolers filtered by user's barangay"""
    user_barangay = get_user_barangay(request.user)
    
    if not user_barangay:
        return Preschooler.objects.none()  # Return empty queryset
    
    return Preschooler.objects.filter(barangay=user_barangay).select_related('parent_id', 'barangay')

def registered_bhw(request):
    # Use same filter pattern as validate function
    bhw_list = Account.objects.filter(
        Q(user_role__iexact='healthworker') | Q(user_role__iexact='BHW'),
        is_validated=True
    )

    # Debug: Print what we found
    print("Found {bhw_list.count()} validated BHW accounts:")
    for bhw in bhw_list:
        print("- {bhw.full_name} (role: '{bhw.user_role}', validated: {bhw.is_validated})")

    for bhw in bhw_list:
        bhw.bhw_data = BHW.objects.filter(email=bhw.email).first()

        if bhw.last_activity:
            if timezone.now() - bhw.last_activity <= timedelta(minutes=1):
                bhw.last_activity_display = "🟢 Online"
            else:
                time_diff = timesince(bhw.last_activity, timezone.now())
                bhw.last_activity_display = "{time_diff} ago"
        else:
            bhw.last_activity_display = "No activity"

    # Get all barangays for the filter dropdown
    barangays = Barangay.objects.all().order_by('name')

    paginator = Paginator(bhw_list, 10)  # 10 BHWs per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'HTML/registered_bhw.html', {
        'bhws': page_obj,
        'barangays': barangays,  # Added this for the filter dropdown
        'total_bhw_count': bhw_list.count()  # Para makita ninyo ang total
    })


def registered_bns(request):
    # Use the same filter pattern as validate function
    bns_list = Account.objects.filter(
        Q(user_role__iexact='bns') | 
        Q(user_role__iexact='BNS') |
        Q(user_role__iexact='Barangay Nutritional Scholar'),
        is_validated=True
    )

    # Debug: Print what we found
    print("Found {bns_list.count()} validated BNS accounts:")
    for bns in bns_list:
        print("- {bns.full_name} (role: '{bns.user_role}', validated: {bns.is_validated})")

    for bns in bns_list:
        if bns.last_activity:
            if timezone.now() - bns.last_activity <= timedelta(minutes=1):
                bns.last_activity_display = "🟢 Online"
            else:
                time_diff = timesince(bns.last_activity, timezone.now())
                bns.last_activity_display = "{time_diff} ago"
        else:
            bns.last_activity_display = "No activity"

    paginator = Paginator(bns_list, 10)  # 10 BNS per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'HTML/registered_bns.html', {
        'bnss': page_obj,
        'total_bns_count': bns_list.count()  # Para makita ninyo ang total
    })

def registered_preschoolers(request):
    preschoolers_qs = Preschooler.objects.filter(is_archived=False) \
        .select_related('parent_id', 'barangay') \
        .prefetch_related(
            Prefetch('bmi_set', queryset=BMI.objects.order_by('-date_recorded'), to_attr='bmi_records'),
            Prefetch('temperature_set', queryset=Temperature.objects.order_by('-date_recorded'), to_attr='temp_records')
        )

    today = date.today()

    # Process nutritional status and delivery place color coding
    for p in preschoolers_qs:
        latest_bmi = p.bmi_records[0] if hasattr(p, 'bmi_records') and p.bmi_records else None

        if latest_bmi:
            try:
                # --- Compute age in months ---
                birth_date = p.birth_date
                age_years = today.year - birth_date.year
                age_months = today.month - birth_date.month
                if today.day < birth_date.day:
                    age_months -= 1
                if age_months < 0:
                    age_years -= 1
                    age_months += 12
                total_age_months = age_years * 12 + age_months

                # --- Compute BMI and classify using WHO ---
                bmi_value = calculate_bmi(latest_bmi.weight, latest_bmi.height)
                z = bmi_zscore(p.sex, total_age_months, bmi_value)
                p.nutritional_status = classify_bmi_for_age(z)

            except Exception as e:
                print("⚠️ BMI classification error for preschooler {p.id}: {e}")
                p.nutritional_status = "N/A"
        else:
            p.nutritional_status = "N/A"

        # --- Add color coding for place of delivery ---
        delivery_place = getattr(p, 'place_of_delivery', None)
        if delivery_place == 'Home':
            p.delivery_class = 'delivery-home'
        elif delivery_place == 'Lying-in':
            p.delivery_class = 'delivery-lying-in'
        elif delivery_place == 'Hospital':
            p.delivery_class = 'delivery-hospital'
        elif delivery_place == 'Others':
            p.delivery_class = 'delivery-others'
        else:
            p.delivery_class = 'delivery-na'

    paginator = Paginator(preschoolers_qs, 10)  # 10 preschoolers per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    barangays = Barangay.objects.all()

    return render(request, 'HTML/registered_preschoolers.html', {
        'preschoolers': page_obj,
        'barangays': barangays,
    })


def reportTemplate(request):
    # Check if this is a PDF generation request (from admin dashboard)
    if request.GET.get('generate_pdf') == 'true':
        # Get all barangays and their data for admin report
        barangays = Barangay.objects.all()
        
        # Overall summary across all barangays
        overall_summary = {
            'Severely Wasted': 0,
            'Wasted': 0,
            'Normal': 0,
            'Overweight': 0,
            'Obese': 0,
        }
        
        barangay_details = []
        total_preschoolers = 0
        
        for barangay in barangays:
            preschoolers = Preschooler.objects.filter(
                barangay=barangay,
                is_archived=False
            ).prefetch_related(
                Prefetch('bmi_set', queryset=BMI.objects.order_by('-date_recorded'), to_attr='bmi_records')
            )
            
            # Barangay-specific summary
            barangay_summary = {
                'severely_underweight': 0,
                'underweight': 0,
                'normal': 0,
                'overweight': 0,
                'obese': 0,
            }
            
            barangay_count = preschoolers.count()
            total_preschoolers += barangay_count
            
            for p in preschoolers:
                latest_bmi = p.bmi_records[0] if hasattr(p, 'bmi_records') and p.bmi_records else None
                
                if latest_bmi and latest_bmi.bmi_value:
                    bmi = latest_bmi.bmi_value
                    if bmi < 13:
                        barangay_summary['severely_wasted'] += 1
                        overall_summary['severely_wasted'] += 1
                    elif 13 <= bmi < 14.9:
                        barangay_summary['wasted'] += 1
                        overall_summary['Wasted'] += 1
                    elif 14.9 <= bmi <= 17.5:
                        barangay_summary['normal'] += 1
                        overall_summary['Normal'] += 1
                    elif 17.6 <= bmi <= 18.9:
                        barangay_summary['overweight'] += 1
                        overall_summary['Overweight'] += 1
                    else:
                        barangay_summary['obese'] += 1
                        overall_summary['Obese'] += 1
            
            # Calculate at-risk percentage (severely underweight + underweight + obese)
            at_risk_count = barangay_summary['severely_wasted'] + barangay_summary['underweight'] + barangay_summary['obese']
            at_risk_percentage = (at_risk_count / barangay_count * 100) if barangay_count > 0 else 0
            
            barangay_details.append({
                'name': barangay.name,
                'total_preschoolers': barangay_count,
                'severely_wasted': barangay_summary['severely_wasted'],
                'underweight': barangay_summary['underweight'],
                'normal': barangay_summary['normal'],
                'overweight': barangay_summary['overweight'],
                'obese': barangay_summary['obese'],
                'at_risk_percentage': round(at_risk_percentage, 1)
            })
        
        # Find highest count barangay
        highest_barangay = max(barangay_details, key=lambda x: x['total_preschoolers']) if barangay_details else None
        
        # Calculate total at-risk children
        total_at_risk = overall_summary['Severely Wasted'] + overall_summary['Underweight'] + overall_summary['Obese']
        
        # Get current account - handle both authenticated and anonymous users
        account = None
        if request.user.is_authenticated:
            try:
                account = Account.objects.get(email=request.user.email)
            except Account.DoesNotExist:
                # Create a default account info for display
                account = type('obj', (object,), {
                    'full_name': 'System Administrator',
                    'email': 'admin@system.local'
                })()
        else:
            # Create a default account info for anonymous users
            account = type('obj', (object,), {
                'full_name': 'System Administrator',
                'email': 'admin@system.local'
            })()
        
        # Render HTML for PDF
        html_string = render_to_string('HTML/reportTemplate.html', {
            'account': account,
            'barangay_details': barangay_details,
            'overall_summary': overall_summary,
            'total_barangays': barangays.count(),
            'total_preschoolers': total_preschoolers,
            'highest_barangay': highest_barangay,
            'total_at_risk': total_at_risk,
            'is_admin_report': True,
        })
        
        html = HTML(string=html_string, base_url=request.build_absolute_uri())
        pdf = html.write_pdf()
        
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="Overall-Barangay-Summary-Report.pd"'
        return response
    
    # Default behavior - just render the template for preview
    return render(request, 'HTML/reportTemplate.html')




def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        # Validate email
        if not email:
            messages.error(request, 'Email address is required.')
            return render(request, 'HTML/forgot_password.html')
        
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Please enter a valid email address.')
            return render(request, 'HTML/forgot_password.html')
        
        # Check if user exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, 'No account found with this email address.')
            return render(request, 'HTML/forgot_password.html')
        
        # Delete existing OTPs
        PasswordResetOTP.objects.filter(user=user, is_used=False).delete()
        
        # Create new OTP
        otp_instance = PasswordResetOTP.objects.create(user=user)
        
        # Compose email
        subject = '🔐 Password Reset OTP - PPMS Cluster 4'

        text_message = f"""
        Hello {user.first_name or user.username},

        You requested a password reset. Your OTP code is: {otp_instance.otp_code}

        This code will expire in 10 minutes.

        If you didn't request this, please ignore this email.
        """

        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="UTF-8">
          <style>
            body {{
              font-family: Arial, sans-serif;
              background-color: #f9f9f9;
              padding: 20px;
              color: #333;
            }}
            .container {{
              background-color: #fff;
              padding: 20px;
              border-radius: 10px;
              max-width: 600px;
              margin: auto;
              box-shadow: 0 4px 10px rgba(0,0,0,0.1);
            }}
            .header {{
              background-color: #007bff;
              padding: 10px 20px;
              border-radius: 10px 10px 0 0;
              color: white;
              text-align: center;
            }}
            .otp {{
              font-size: 28px;
              font-weight: bold;
              color: #007bff;
              text-align: center;
              margin: 30px 0;
            }}
            .footer {{
              font-size: 12px;
              text-align: center;
              color: #777;
              margin-top: 30px;
            }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h2>PPMS Cluster 4 – Password Reset</h2>
            </div>

            <p>Hello <strong>{user.first_name or user.username}</strong>,</p>

            <p>You requested to reset your password. Please use the following OTP:</p>

            <div class="otp">{otp_instance.otp_code}</div>

            <p>This OTP is valid for <strong>10 minutes</strong>.</p>

            <p>If you did not make this request, you can safely ignore this email.</p>

            <div class="footer">
              &copy; 2025 PPMS Cluster 4 Imus City
            </div>
          </div>
        </body>
        </html>
        """

        try:
            email_msg = EmailMultiAlternatives(
                subject=subject,
                body=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email]
            )
            email_msg.attach_alternative(html_message, "text/html")
            email_msg.send()

            messages.success(request, 'OTP sent to your email address.')
            return redirect('verify_otp', user_id=user.id)
        except Exception as e:
            print(f"[ERROR] Email send failed: {e}")
            messages.error(request, 'Failed to send email. Please try again.')

    return render(request, 'HTML/forgot_password.html')


def admin_registered_parents(request):
    # Ensure user is authenticated and is admin
    user_email = request.session.get('email')
    user_role = request.session.get('user_role', '').lower()

    if user_role != 'admin':
        return render(request, 'unauthorized.html')

    # Fetch all parents
    parents_qs = Parent.objects.select_related('barangay').order_by('-created_at')

    paginator = Paginator(parents_qs, 10)  # Show 10 parents per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'HTML/admin_registeredparents.html', {
        'parents': page_obj,
        'user_email': user_email,
        'user_role': user_role
    })

def verify_otp(request, user_id):
    user = get_object_or_404(User, id=user_id)

    # ✅ If resend is requested, generate a new OTP
    if request.method == 'GET' and request.GET.get('resend') == '1':
        # Mark any previous OTPs as used
        PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)

        # Generate and save new OTP
        new_otp = get_random_string(length=6, allowed_chars='0123456789')
        PasswordResetOTP.objects.create(user=user, otp_code=new_otp)

        # (Optional) Send the OTP to user's email here
        # send_mail(...)

        messages.success(request, 'A new OTP has been sent to your email.')

    # Existing POST logic
    if request.method == 'POST':
        otp_code = request.POST.get('otp_code', '').strip()

        if not otp_code:
            messages.error(request, 'OTP code is required.')
            return render(request, 'HTML/verify_otp.html', {'user': user})

        if len(otp_code) != 6 or not otp_code.isdigit():
            messages.error(request, 'OTP must be exactly 6 digits.')
            return render(request, 'HTML/verify_otp.html', {'user': user})

        try:
            otp_instance = PasswordResetOTP.objects.get(
                user=user,
                otp_code=otp_code,
                is_used=False
            )

            if otp_instance.is_expired():
                messages.error(request, 'OTP has expired. Please request a new one.')
                return redirect('verify_otp', user_id=user.id)

            otp_instance.is_used = True
            otp_instance.save()

            messages.success(request, 'OTP verified successfully.')
            return redirect('reset_password', user_id=user.id)

        except PasswordResetOTP.DoesNotExist:
            messages.error(request, 'Invalid OTP. Please try again.')

    return render(request, 'HTML/verify_otp.html', {'user': user})

def reset_password(request, user_id):
    user = get_object_or_404(User, id=user_id)
    
    # Check if there's a recent used OTP for this user
    recent_otp = PasswordResetOTP.objects.filter(
        user=user,
        is_used=True,
        created_at__gte=timezone.now() - timezone.timedelta(minutes=15)
    ).first()
    
    if not recent_otp:
        messages.error(request, 'Session expired. Please start the process again.')
        return redirect('forgot_password')
    
    if request.method == 'POST':
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        
        # Validate passwords
        if not password1 or not password2:
            messages.error(request, 'Both password fields are required.')
            return render(request, 'HTML/reset_password.html', {'user': user})
        
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'HTML/reset_password.html', {'user': user})
        
        if len(password1) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'HTML/reset_password.html', {'user': user})
        
        # Additional password validation (optional)
        try:
            validate_password(password1, user)
        except ValidationError as e:
            for error in e.messages:
                messages.error(request, error)
            return render(request, 'HTML/reset_password.html', {'user': user})
        
        # Set new password
        user.set_password(password1)
        user.save()
        
        messages.success(request, 'Password reset successfully. You can now login with your new password.')
        return redirect('login')  # Replace with your login URL name
    
    return render(request, 'HTML/reset_password.html', {'user': user})
    
def remove_bns(request, account_id):
    if request.method == 'POST':
        try:
            bns = get_object_or_404(Account, pk=account_id)
            
            # Safety check for BNS role
            bns_role_keywords = ['bns', 'nutritional', 'scholar']
            if not any(keyword in bns.user_role.lower() for keyword in bns_role_keywords):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Not a BNS worker'})
                messages.error(request, "Cannot remove {bns.full_name}: Not a BNS worker.")
                return redirect('healthcare_workers')
            
            name = bns.full_name
            email = bns.email
            
            # Get current date
            current_date = datetime.now().strftime('%B %d, %Y')
            
            # Prepare email
            subject = 'PPMS Cluster 4 – Account Removal Notification'
            
            html_message = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>PPMS Account Removal Notification</title>
                <style>
                    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
                    
                    body {{
                        font-family: 'Inter', Arial, sans-serif;
                        background-color: #f9fafb;
                        padding: 40px 20px;
                        color: #334155;
                        line-height: 1.6;
                        margin: 0;
                    }}
                    
                    .container {{
                        max-width: 560px;
                        margin: 0 auto;
                        background: white;
                        border-radius: 12px;
                        overflow: hidden;
                        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                    }}
                    
                    .header {{
                        padding: 24px 32px;
                        text-align: center;
                        color: #111827;
                        border-bottom: 4px solid #dc3545;
                    }}
                    .header h1 {{
                        font-size: 24px;
                        font-weight: 600;
                        margin: 0;
                        color: #111827;
                    }}
                    .header p {{
                        font-size: 16px;
                        margin: 4px 0 0 0;
                        color: #6b7280;
                    }}
                    
                    .content {{
                        padding: 32px;
                    }}
                    
                    .greeting {{
                        font-size: 18px;
                        margin-bottom: 24px;
                        color: #1e293b;
                    }}
                    
                    .message {{
                        font-size: 16px;
                        margin-bottom: 24px;
                        color: #64748b;
                    }}
                    
                    .details {{
                        background: #fef2f2;
                        border: 1px solid #ef4444;
                        padding: 24px;
                        border-radius: 6px;
                        margin: 24px 0;
                    }}
                    
                    .details h4 {{
                        margin-bottom: 16px;
                        font-size: 16px;
                        font-weight: 600;
                        color: #7f1d1d;
                    }}
                    
                    .detail-item {{
                        margin-bottom: 12px;
                        line-height: 1.6;
                    }}
                    
                    .detail-item:last-child {{
                        margin-bottom: 0;
                    }}
                    
                    .detail-label {{
                        font-weight: bold;
                        color: #7f1d1d;
                        display: inline;
                    }}
                    
                    .detail-value {{
                        color: #7f1d1d;
                        display: inline;
                        margin-left: 4px;
                    }}
                    
                    .notice {{
                        background: #fef3c7;
                        border: 1px solid #f59e0b;
                        border-radius: 8px;
                        padding: 20px;
                        margin-bottom: 32px;
                        text-align: center;
                    }}
                    
                    .notice h3 {{
                        font-size: 18px;
                        font-weight: 600;
                        color: #92400e;
                        margin-bottom: 8px;
                    }}
                    
                    .notice p {{
                        font-size: 14px;
                        color: #92400e;
                        margin: 0;
                    }}
                    
                    .footer {{
                        background: #f1f5f9;
                        padding: 32px;
                        text-align: center;
                        border-top: 1px solid #e2e8f0;
                    }}
                    
                    .footer h3 {{
                        font-size: 18px;
                        font-weight: 600;
                        color: #1e293b;
                        margin-bottom: 8px;
                    }}
                    
                    .footer p {{
                        font-size: 14px;
                        color: #64748b;
                        margin-bottom: 4px;
                    }}
                    
                    .footer-divider {{
                        margin: 24px 0;
                        height: 1px;
                        background: #e2e8f0;
                    }}
                    
                    .footer-small {{
                        font-size: 12px;
                        color: #94a3b8;
                    }}
                    
                    @media (max-width: 600px) {{
                        .content {{ 
                            padding: 28px 20px; 
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Account Removed</h1>
                        <p>PPMS Cluster 4 - Imus City Healthcare Management</p>
                    </div>
                    
                    <div class="content">
                        <div class="greeting">
                            Hello <strong>{name}</strong>,
                        </div>
                        
                        <div class="message">
                            We would like to inform you that your BNS account has been removed from the PPMS Cluster 4 system.
                        </div>
                        
                        <div class="notice">
                            <h3>Important Notice</h3>
                            <p>If you believe this was a mistake or have any questions, please contact the system administrator.</p>
                        </div>
                        
                        <div class="details">
                            <h4>Account Information</h4>
                            <div class="detail-item">
                                <span class="detail-label">Full Name:</span>
                                <span class="detail-value">{name}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Email:</span>
                                <span class="detail-value">{email}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Date Removed:</span>
                                <span class="detail-value">{current_date}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="footer">
                        <h3>PPMS Cluster 4</h3>
                        <p>Imus City Healthcare Management</p>
                        <div class="footer-divider"></div>
                        <p class="footer-small">
                            This is an automated message. Please do not reply.<br>
                            © 2025 PPMS Cluster 4. All rights reserved.
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """

            plain_message = """
PPMS Account Removal Notification

Hello {name},

We would like to inform you that your BNS account has been removed from the PPMS Cluster 4 system.

IMPORTANT NOTICE:
If you believe this was a mistake or have any questions, please contact the system administrator.

Account Information:
- Full Name: {name}
- Email: {email}
- Date Removed: {current_date}

PPMS Cluster 4
Imus City Healthcare Management

This is an automated message. Please do not reply.
© 2025 PPMS Cluster 4. All rights reserved.
            """

            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                html_message=html_message,
                fail_silently=True,
            )
            print("[DEBUG] ✅ Removal email sent to {email}")

            # Delete account
            bns.delete()
            
            # Return JSON for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'name': name, 'type': 'BNS'})
            
            # Fallback for regular form submission
            messages.success(request, "{name} has been successfully removed and notified via email.")
            
        except Account.DoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Worker no longer exists'})
            messages.error(request, "The worker you're trying to remove no longer exists.")
        except Exception as e:
            print("[ERROR] Failed to remove BNS: {e}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'An error occurred while removing the worker'})
            messages.error(request, "An error occurred while removing the BNS.")

    return redirect('healthcare_workers')

def remove_bhw(request, account_id):
    if request.method == 'POST':
        try:
            bhw = get_object_or_404(Account, pk=account_id)
            
            # Safety check for BHW role
            bhw_role_keywords = ['bhw', 'healthworker', 'health worker']
            if not any(keyword in bhw.user_role.lower() for keyword in bhw_role_keywords):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Not a BHW worker'})
                messages.error(request, "Cannot remove {bhw.full_name}: Not a BHW worker.")
                return redirect('healthcare_workers')
            
            name = bhw.full_name
            email = bhw.email
            
            # Get current date
            current_date = datetime.now().strftime('%B %d, %Y')
            
            # Prepare email
            subject = 'PPMS Cluster 4 – Account Removal Notification'
            
            html_message = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>PPMS Account Removal Notification</title>
                <style>
                    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
                    
                    body {{
                        font-family: 'Inter', Arial, sans-serif;
                        background-color: #f9fafb;
                        padding: 40px 20px;
                        color: #334155;
                        line-height: 1.6;
                        margin: 0;
                    }}
                    
                    .container {{
                        max-width: 560px;
                        margin: 0 auto;
                        background: white;
                        border-radius: 12px;
                        overflow: hidden;
                        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                    }}
                    
                    .header {{
                        padding: 24px 32px;
                        text-align: center;
                        color: #111827;
                        border-bottom: 4px solid #dc3545;
                    }}
                    .header h1 {{
                        font-size: 24px;
                        font-weight: 600;
                        margin: 0;
                        color: #111827;
                    }}
                    .header p {{
                        font-size: 16px;
                        margin: 4px 0 0 0;
                        color: #6b7280;
                    }}
                    
                    .content {{
                        padding: 32px;
                    }}
                    
                    .greeting {{
                        font-size: 18px;
                        margin-bottom: 24px;
                        color: #1e293b;
                    }}
                    
                    .message {{
                        font-size: 16px;
                        margin-bottom: 24px;
                        color: #64748b;
                    }}
                    
                    .details {{
                        background: #fef2f2;
                        border: 1px solid #ef4444;
                        padding: 24px;
                        border-radius: 6px;
                        margin: 24px 0;
                    }}
                    
                    .details h4 {{
                        margin-bottom: 16px;
                        font-size: 16px;
                        font-weight: 600;
                        color: #7f1d1d;
                    }}
                    
                    .detail-item {{
                        margin-bottom: 12px;
                        line-height: 1.6;
                    }}
                    
                    .detail-item:last-child {{
                        margin-bottom: 0;
                    }}
                    
                    .detail-label {{
                        font-weight: bold;
                        color: #7f1d1d;
                        display: inline;
                    }}
                    
                    .detail-value {{
                        color: #7f1d1d;
                        display: inline;
                        margin-left: 4px;
                    }}
                    
                    .notice {{
                        background: #fef3c7;
                        border: 1px solid #f59e0b;
                        border-radius: 8px;
                        padding: 20px;
                        margin-bottom: 32px;
                        text-align: center;
                    }}
                    
                    .notice h3 {{
                        font-size: 18px;
                        font-weight: 600;
                        color: #92400e;
                        margin-bottom: 8px;
                    }}
                    
                    .notice p {{
                        font-size: 14px;
                        color: #92400e;
                        margin: 0;
                    }}
                    
                    .footer {{
                        background: #f1f5f9;
                        padding: 32px;
                        text-align: center;
                        border-top: 1px solid #e2e8f0;
                    }}
                    
                    .footer h3 {{
                        font-size: 18px;
                        font-weight: 600;
                        color: #1e293b;
                        margin-bottom: 8px;
                    }}
                    
                    .footer p {{
                        font-size: 14px;
                        color: #64748b;
                        margin-bottom: 4px;
                    }}
                    
                    .footer-divider {{
                        margin: 24px 0;
                        height: 1px;
                        background: #e2e8f0;
                    }}
                    
                    .footer-small {{
                        font-size: 12px;
                        color: #94a3b8;
                    }}
                    
                    @media (max-width: 600px) {{
                        .content {{ 
                            padding: 28px 20px; 
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Account Removed</h1>
                        <p>PPMS Cluster 4 - Imus City Healthcare Management</p>
                    </div>
                    
                    <div class="content">
                        <div class="greeting">
                            Hello <strong>{name}</strong>,
                        </div>
                        
                        <div class="message">
                            We would like to inform you that your BHW account has been removed from the PPMS Cluster 4 system.
                        </div>
                        
                        <div class="notice">
                            <h3>Important Notice</h3>
                            <p>If you believe this was a mistake or have any questions, please contact the system administrator.</p>
                        </div>
                        
                        <div class="details">
                            <h4>Account Information</h4>
                            <div class="detail-item">
                                <span class="detail-label">Full Name:</span>
                                <span class="detail-value">{name}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Email:</span>
                                <span class="detail-value">{email}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Date Removed:</span>
                                <span class="detail-value">{current_date}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="footer">
                        <h3>PPMS Cluster 4</h3>
                        <p>Imus City Healthcare Management</p>
                        <div class="footer-divider"></div>
                        <p class="footer-small">
                            This is an automated message. Please do not reply.<br>
                            © 2025 PPMS Cluster 4. All rights reserved.
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """

            plain_message = """
PPMS Account Removal Notification

Hello {name},

We would like to inform you that your BHW account has been removed from the PPMS Cluster 4 system.

IMPORTANT NOTICE:
If you believe this was a mistake or have any questions, please contact the system administrator.

Account Information:
- Full Name: {name}
- Email: {email}
- Date Removed: {current_date}

PPMS Cluster 4
Imus City Healthcare Management

This is an automated message. Please do not reply.
© 2025 PPMS Cluster 4. All rights reserved.
            """

            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                html_message=html_message,
                fail_silently=True,
            )
            print("[DEBUG] ✅ Removal email sent to {email}")

            # Delete account
            bhw.delete()
            
            # Return JSON for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'name': name, 'type': 'BHW'})
            
            # Fallback for regular form submission
            messages.success(request, "{name} has been successfully removed and notified via email.")
            
        except Account.DoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Worker no longer exists'})
            messages.error(request, "The worker you're trying to remove no longer exists.")
        except Exception as e:
            print("[ERROR] Failed to remove BHW: {e}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'An error occurred while removing the worker'})
            messages.error(request, "An error occurred while removing the BHW.")

    return redirect('healthcare_workers')


def registered_midwife(request):
    midwife_list = Account.objects.filter(user_role='midwife', is_validated=True)

    for midwife in midwife_list:
        # Assuming you have a Midwife model similar to BHW
        midwife.midwife_data = Midwife.objects.filter(email=midwife.email).first()

        if midwife.last_activity:
            if timezone.now() - midwife.last_activity <= timedelta(minutes=1):
                midwife.last_activity_display = "🟢 Online"
            else:
                time_diff = timesince(midwife.last_activity, timezone.now())
                midwife.last_activity_display = "{time_diff} ago"
        else:
            midwife.last_activity_display = "No activity"

    paginator = Paginator(midwife_list, 10)  # 10 midwives per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'HTML/registered_midwife.html', {'midwives': page_obj})

def remove_midwife(request, account_id):
    if request.method == 'POST':
        try:
            midwife = get_object_or_404(Account, pk=account_id)
            
            # Safety check for Midwife role
            if 'midwife' not in midwife.user_role.lower():
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Not a Midwife worker'})
                messages.error(request, "Cannot remove {midwife.full_name}: Not a Midwife worker.")
                return redirect('healthcare_workers')
            
            name = midwife.full_name
            email = midwife.email
            
            # Get current date
            current_date = datetime.now().strftime('%B %d, %Y')
            
            # Prepare email
            subject = 'PPMS Cluster 4 – Account Removal Notification'
            
            html_message = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>PPMS Account Removal Notification</title>
                <style>
                    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
                    
                    body {{
                        font-family: 'Inter', Arial, sans-serif;
                        background-color: #f9fafb;
                        padding: 40px 20px;
                        color: #334155;
                        line-height: 1.6;
                        margin: 0;
                    }}
                    
                    .container {{
                        max-width: 560px;
                        margin: 0 auto;
                        background: white;
                        border-radius: 12px;
                        overflow: hidden;
                        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                    }}
                    
                    .header {{
                        padding: 24px 32px;
                        text-align: center;
                        color: #111827;
                        border-bottom: 4px solid #dc3545;
                    }}
                    .header h1 {{
                        font-size: 24px;
                        font-weight: 600;
                        margin: 0;
                        color: #111827;
                    }}
                    .header p {{
                        font-size: 16px;
                        margin: 4px 0 0 0;
                        color: #6b7280;
                    }}
                    
                    .content {{
                        padding: 32px;
                    }}
                    
                    .greeting {{
                        font-size: 18px;
                        margin-bottom: 24px;
                        color: #1e293b;
                    }}
                    
                    .message {{
                        font-size: 16px;
                        margin-bottom: 24px;
                        color: #64748b;
                    }}
                    
                    .details {{
                        background: #fef2f2;
                        border: 1px solid #ef4444;
                        padding: 24px;
                        border-radius: 6px;
                        margin: 24px 0;
                    }}
                    
                    .details h4 {{
                        margin-bottom: 16px;
                        font-size: 16px;
                        font-weight: 600;
                        color: #7f1d1d;
                    }}
                    
                    .detail-item {{
                        margin-bottom: 12px;
                        line-height: 1.6;
                    }}
                    
                    .detail-item:last-child {{
                        margin-bottom: 0;
                    }}
                    
                    .detail-label {{
                        font-weight: bold;
                        color: #7f1d1d;
                        display: inline;
                    }}
                    
                    .detail-value {{
                        color: #7f1d1d;
                        display: inline;
                        margin-left: 4px;
                    }}
                    
                    .notice {{
                        background: #fef3c7;
                        border: 1px solid #f59e0b;
                        border-radius: 8px;
                        padding: 20px;
                        margin-bottom: 32px;
                        text-align: center;
                    }}
                    
                    .notice h3 {{
                        font-size: 18px;
                        font-weight: 600;
                        color: #92400e;
                        margin-bottom: 8px;
                    }}
                    
                    .notice p {{
                        font-size: 14px;
                        color: #92400e;
                        margin: 0;
                    }}
                    
                    .footer {{
                        background: #f1f5f9;
                        padding: 32px;
                        text-align: center;
                        border-top: 1px solid #e2e8f0;
                    }}
                    
                    .footer h3 {{
                        font-size: 18px;
                        font-weight: 600;
                        color: #1e293b;
                        margin-bottom: 8px;
                    }}
                    
                    .footer p {{
                        font-size: 14px;
                        color: #64748b;
                        margin-bottom: 4px;
                    }}
                    
                    .footer-divider {{
                        margin: 24px 0;
                        height: 1px;
                        background: #e2e8f0;
                    }}
                    
                    .footer-small {{
                        font-size: 12px;
                        color: #94a3b8;
                    }}
                    
                    @media (max-width: 600px) {{
                        .content {{ 
                            padding: 28px 20px; 
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Account Removed</h1>
                        <p>PPMS Cluster 4 - Imus City Healthcare Management</p>
                    </div>
                    
                    <div class="content">
                        <div class="greeting">
                            Hello <strong>{name}</strong>,
                        </div>
                        
                        <div class="message">
                            We would like to inform you that your Midwife account has been removed from the PPMS Cluster 4 system.
                        </div>
                        
                        <div class="notice">
                            <h3>Important Notice</h3>
                            <p>If you believe this was a mistake or have any questions, please contact the system administrator.</p>
                        </div>
                        
                        <div class="details">
                            <h4>Account Information</h4>
                            <div class="detail-item">
                                <span class="detail-label">Full Name:</span>
                                <span class="detail-value">{name}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Email:</span>
                                <span class="detail-value">{email}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Date Removed:</span>
                                <span class="detail-value">{current_date}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="footer">
                        <h3>PPMS Cluster 4</h3>
                        <p>Imus City Healthcare Management</p>
                        <div class="footer-divider"></div>
                        <p class="footer-small">
                            This is an automated message. Please do not reply.<br>
                            © 2025 PPMS Cluster 4. All rights reserved.
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """

            plain_message = """
PPMS Account Removal Notification

Hello {name},

We would like to inform you that your Midwife account has been removed from the PPMS Cluster 4 system.

IMPORTANT NOTICE:
If you believe this was a mistake or have any questions, please contact the system administrator.

Account Information:
- Full Name: {name}
- Email: {email}
- Date Removed: {current_date}

PPMS Cluster 4
Imus City Healthcare Management

This is an automated message. Please do not reply.
© 2025 PPMS Cluster 4. All rights reserved.
            """

            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                html_message=html_message,
                fail_silently=True,
            )
            print("[DEBUG] ✅ Removal email sent to {email}")

            # Delete account
            midwife.delete()
            
            # Return JSON for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'name': name, 'type': 'Midwife'})
            
            # Fallback for regular form submission
            messages.success(request, "{name} has been successfully removed and notified via email.")
            
        except Account.DoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Worker no longer exists'})
            messages.error(request, "The worker you're trying to remove no longer exists.")
        except Exception as e:
            print("[ERROR] Failed to remove Midwife: {e}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'An error occurred while removing the worker'})
            messages.error(request, "An error occurred while removing the midwife.")

    return redirect('healthcare_workers')

def validate(request):
    """Display BHW, BNS, Midwife, and Nurse accounts - focusing on pending validation by default"""
    # Get filter parameters
    role_filter = request.GET.get('role', 'all')
    status_filter = request.GET.get('status', 'pending')  # Default to pending only
    
    # Base queryset - BHW, BNS, Midwife, and Nurse accounts
    accounts = Account.objects.filter(
        Q(user_role__iexact='BHW') | 
        Q(user_role__iexact='healthworker') |
        Q(user_role__iexact='BNS') | 
        Q(user_role__iexact='bns') | 
        Q(user_role__iexact='Barangay Nutritional Scholar') |
        Q(user_role__iexact='Midwife') |
        Q(user_role__iexact='Nurse')  # Added Nurse here
    )
    
    # Apply status filter
    if status_filter == 'pending':
        accounts = accounts.filter(is_validated=False, is_rejected=False)
    elif status_filter == 'validated':
        accounts = accounts.filter(is_validated=True)
    elif status_filter == 'rejected':
        accounts = accounts.filter(is_rejected=True)
    # If status_filter == 'all', show all accounts
    
    # Apply role filter if specified
    if role_filter and role_filter != 'all':
        if role_filter.lower() == 'bns':
            accounts = accounts.filter(
                Q(user_role__iexact='bns') | 
                Q(user_role__iexact='BNS') |
                Q(user_role__iexact='Barangay Nutritional Scholar')
            )
        elif role_filter.lower() == 'healthworker':
            accounts = accounts.filter(
                Q(user_role__iexact='healthworker') |
                Q(user_role__iexact='BHW')
            )
        elif role_filter.lower() == 'midwife':
            accounts = accounts.filter(user_role__iexact='Midwife')
        elif role_filter.lower() == 'nurse':  # Added nurse filter
            accounts = accounts.filter(user_role__iexact='Nurse')
        else:
            accounts = accounts.filter(user_role=role_filter)
    
    accounts = accounts.order_by('-created_at')
    
    # Paginate results
    paginator = Paginator(accounts, 10)  # Show 10 accounts per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Count statistics for display
    base_filter = (
        Q(user_role__iexact='BHW') | Q(user_role__iexact='healthworker') | 
        Q(user_role__iexact='BNS') | Q(user_role__iexact='bns') | 
        Q(user_role__iexact='Barangay Nutritional Scholar') | 
        Q(user_role__iexact='Midwife') |
        Q(user_role__iexact='Nurse')  # Added Nurse here
    )
    
    total_pending = Account.objects.filter(
        base_filter,
        is_validated=False,
        is_rejected=False
    ).count()
    
    bhw_pending = Account.objects.filter(
        Q(user_role__iexact='healthworker') | Q(user_role__iexact='BHW'),
        is_validated=False,
        is_rejected=False
    ).count()
    
    bns_pending = Account.objects.filter(
        Q(user_role__iexact='bns') | Q(user_role__iexact='BNS') | Q(user_role__iexact='Barangay Nutritional Scholar'),
        is_validated=False,
        is_rejected=False
    ).count()
    
    midwife_pending = Account.objects.filter(
        user_role__iexact='Midwife',
        is_validated=False,
        is_rejected=False
    ).count()
    
    nurse_pending = Account.objects.filter(  # Added nurse pending count
        user_role__iexact='Nurse',
        is_validated=False,
        is_rejected=False
    ).count()
    
    total_validated = Account.objects.filter(
        base_filter,
        is_validated=True
    ).count()
    
    total_rejected = Account.objects.filter(
        base_filter,
        is_rejected=True
    ).count()
    
    context = {
        'accounts': page_obj,
        'page_obj': page_obj,
        'current_filter': role_filter,
        'current_status': status_filter,
        'total_pending': total_pending,
        'bhw_pending': bhw_pending,
        'bns_pending': bns_pending,
        'midwife_pending': midwife_pending,
        'nurse_pending': nurse_pending,  # Pass nurse count to template
        'total_validated': total_validated,
        'total_rejected': total_rejected,
    }
    
    return render(request, 'HTML/validate.html', context)

@csrf_exempt
def validate_account(request, account_id):
    if request.method == 'POST':
        account = get_object_or_404(Account, pk=account_id)
        account.is_validated = True
        account.is_rejected = False
        account.save()

        if account.email:
            from datetime import datetime
            current_date = datetime.now().strftime('%B %d, %Y')

            subject = 'Account Validated - PPMS Cluster 4'

            html_message = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        background-color: #f9f9f9;
                        padding: 20px;
                        color: #333;
                    }}
                    .container {{
                        background-color: #fff;
                        padding: 0;
                        border-radius: 10px;
                        max-width: 600px;
                        margin: auto;
                        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
                        overflow: hidden;
                    }}
                    .header {{
                        padding: 20px;
                        text-align: center;
                        font-size: 22px;
                        font-weight: bold;
                        color: #111827;
                    }}
                    .divider {{
                        height: 4px;
                        background-color: #198754; /* ✅ Green divider */
                    }}
                    .content {{
                        padding: 32px;
                    }}
                    .content p {{
                        margin-bottom: 16px;
                        font-size: 15px;
                    }}
                    .details {{
                        background: #ecfdf5;
                        border: 1px solid #10b981;
                        padding: 16px;
                        border-radius: 6px;
                        margin: 24px 0;
                    }}
                    .details h4 {{
                        margin-bottom: 12px;
                        font-size: 16px;
                        font-weight: 600;
                        color: #065f46;
                    }}
                    .footer {{
                        text-align: center;
                        font-size: 12px;
                        color: #777;
                        margin-top: 30px;
                        border-top: 1px solid #e2e8f0;
                        padding: 12px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        Account Validated
                    </div>
                    <div class="divider"></div>
                    <div class="content">
                        <p>Hello <strong>{account.full_name}</strong>,</p>
                        <p>Your PPMS account has been successfully 
                        <strong>validated</strong>. You can now log in using your registered email address.</p>

                        <div class="details">
                            <h4>Account Details</h4>
                            <p><strong>Role:</strong> {account.user_role}</p>
                            <p><strong>Barangay:</strong> {account.barangay.name if account.barangay else "N/A"}</p>
                            <p><strong>Email:</strong> {account.email}</p>
                            <p><strong>Date Validated:</strong> {current_date}</p>
                        </div>

                        <p>Thank you for being part of the Preschooler Profiling and Monitoring System (PPMS).</p>
                    </div>
                    <div class="footer">
                        &copy; 2025 PPMS Cluster 4 - Imus City Healthcare Management<br>
                        This is an automated message. Please do not reply.
                    </div>
                </div>
            </body>
            </html>
            """

            plain_message = """
Hello {account.full_name},

Your PPMS account has been successfully validated. 
You can now log in using your registered email address.

Account Details:
- Role: {account.user_role}
- Barangay: {account.barangay.name if account.barangay else "N/A"}
- Email: {account.email}
- Date Validated: {current_date}

Thank you for being part of the Preschooler Profiling and Monitoring System (PPMS).
"""

            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [account.email],
                html_message=html_message,
                fail_silently=True,
            )

        messages.success(
            request,
            "{account.full_name} ({account.user_role}) has been validated and notified."
        )
        return redirect('validate')

@csrf_exempt
def reject_account(request, account_id):
    account = get_object_or_404(Account, pk=account_id)

    account.is_validated = False
    account.is_rejected = True
    account.save()

    if account.email:
        from datetime import datetime
        current_date = datetime.now().strftime('%B %d, %Y')

        subject = 'PPMS Account Rejected'

        plain_message = """
Hello {account.full_name},

We regret to inform you that your registration to the PPMS Cluster 4 Imus City platform has been rejected.

If you believe this was a mistake, please contact the system administrator.

Date Rejected: {current_date}

Thank you,
PPMS Admin
        """

        html_message = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f9fafb;
                    padding: 20px;
                    color: #334155;
                    line-height: 1.6;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background: #ffffff;
                    border-radius: 8px;
                    padding: 0;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                .header {{
                    padding: 20px;
                    text-align: center;
                    font-size: 22px;
                    font-weight: bold;
                    color: #111827;
                }}
                .divider {{
                    height: 4px;
                    background-color: #dc3545; /* 🔴 Red divider for rejected */
                }}
                .content {{
                    padding: 32px;
                }}
                .content p {{
                    margin-bottom: 16px;
                    font-size: 16px;
                }}
                .details {{
                    background: #fef2f2;
                    border: 1px solid #f87171;
                    padding: 16px;
                    border-radius: 6px;
                    margin: 24px 0;
                }}
                .details h4 {{
                    margin-bottom: 12px;
                    font-size: 16px;
                    font-weight: 600;
                    color: #991b1b;
                }}
                .footer {{
                    text-align: center;
                    font-size: 13px;
                    color: #94a3b8;
                    margin-top: 32px;
                    border-top: 1px solid #e2e8f0;
                    padding: 16px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    Account Rejected
                </div>
                <div class="divider"></div>
                <div class="content">
                    <p>Hello <strong>{account.full_name}</strong>,</p>
                    <p>We regret to inform you that your registration to the PPMS Cluster 4 Imus City platform has been 
                    <strong>rejected</strong>.</p>

                    <div class="details">
                        <h4>Rejection Details</h4>
                        <p><strong>Email:</strong> {account.email}</p>
                        <p><strong>Date Rejected:</strong> {current_date}</p>
                    </div>

                    <p>If you believe this was a mistake, please contact the system administrator.</p>
                </div>
                <div class="footer">
                    © 2025 PPMS Cluster 4 - Imus City Healthcare Management<br>
                    This is an automated message. Please do not reply.
                </div>
            </div>
        </body>
        </html>
        """

        try:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [account.email],
                html_message=html_message,
                fail_silently=True,
            )
        except Exception as e:
            print("[EMAIL ERROR]", e)

    messages.success(request, "{account.full_name} has been rejected and notified.")
    return redirect('validate')

def registered_nurse(request):
    nurse_list = Account.objects.filter(user_role='nurse', is_validated=True)
    for nurse in nurse_list:
        # Assuming you have a Nurse model similar to Midwife
        nurse.nurse_data = Nurse.objects.filter(email=nurse.email).first()
        if nurse.last_activity:
            if timezone.now() - nurse.last_activity <= timedelta(minutes=1):
                nurse.last_activity_display = "🟢 Online"
            else:
                time_diff = timesince(nurse.last_activity, timezone.now())
                nurse.last_activity_display = "{time_diff} ago"
        else:
            nurse.last_activity_display = "No activity"
    paginator = Paginator(nurse_list, 10)  # 10 nurses per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'HTML/registered_nurse.html', {'nurses': page_obj})


def remove_nurse(request, account_id):
    if request.method == 'POST':
        try:
            nurse = get_object_or_404(Account, pk=account_id)
            
            # Safety check for Nurse role
            if 'nurse' not in nurse.user_role.lower():
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Not a Nurse worker'})
                messages.error(request, "Cannot remove {nurse.full_name}: Not a Nurse worker.")
                return redirect('healthcare_workers')
            
            name = nurse.full_name
            email = nurse.email
            
            # Get current date
            current_date = datetime.now().strftime('%B %d, %Y')
            
            # Prepare email
            subject = 'PPMS Cluster 4 – Account Removal Notification'
            
            html_message = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>PPMS Account Removal Notification</title>
                <style>
                    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
                    
                    body {{
                        font-family: 'Inter', Arial, sans-serif;
                        background-color: #f9fafb;
                        padding: 40px 20px;
                        color: #334155;
                        line-height: 1.6;
                        margin: 0;
                    }}
                    
                    .container {{
                        max-width: 560px;
                        margin: 0 auto;
                        background: white;
                        border-radius: 12px;
                        overflow: hidden;
                        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                    }}
                    
                    .header {{
                        padding: 24px 32px;
                        text-align: center;
                        color: #111827;
                        border-bottom: 4px solid #dc3545;
                    }}
                    .header h1 {{
                        font-size: 24px;
                        font-weight: 600;
                        margin: 0;
                        color: #111827;
                    }}
                    .header p {{
                        font-size: 16px;
                        margin: 4px 0 0 0;
                        color: #6b7280;
                    }}
                    
                    .content {{
                        padding: 32px;
                    }}
                    
                    .greeting {{
                        font-size: 18px;
                        margin-bottom: 24px;
                        color: #1e293b;
                    }}
                    
                    .message {{
                        font-size: 16px;
                        margin-bottom: 24px;
                        color: #64748b;
                    }}
                    
                    .details {{
                        background: #fef2f2;
                        border: 1px solid #ef4444;
                        padding: 24px;
                        border-radius: 6px;
                        margin: 24px 0;
                    }}
                    
                    .details h4 {{
                        margin-bottom: 16px;
                        font-size: 16px;
                        font-weight: 600;
                        color: #7f1d1d;
                    }}
                    
                    .detail-item {{
                        margin-bottom: 12px;
                        line-height: 1.6;
                    }}
                    
                    .detail-item:last-child {{
                        margin-bottom: 0;
                    }}
                    
                    .detail-label {{
                        font-weight: bold;
                        color: #7f1d1d;
                        display: inline;
                    }}
                    
                    .detail-value {{
                        color: #7f1d1d;
                        display: inline;
                        margin-left: 4px;
                    }}
                    
                    .notice {{
                        background: #fef3c7;
                        border: 1px solid #f59e0b;
                        border-radius: 8px;
                        padding: 20px;
                        margin-bottom: 32px;
                        text-align: center;
                    }}
                    
                    .notice h3 {{
                        font-size: 18px;
                        font-weight: 600;
                        color: #92400e;
                        margin-bottom: 8px;
                    }}
                    
                    .notice p {{
                        font-size: 14px;
                        color: #92400e;
                        margin: 0;
                    }}
                    
                    .footer {{
                        background: #f1f5f9;
                        padding: 32px;
                        text-align: center;
                        border-top: 1px solid #e2e8f0;
                    }}
                    
                    .footer h3 {{
                        font-size: 18px;
                        font-weight: 600;
                        color: #1e293b;
                        margin-bottom: 8px;
                    }}
                    
                    .footer p {{
                        font-size: 14px;
                        color: #64748b;
                        margin-bottom: 4px;
                    }}
                    
                    .footer-divider {{
                        margin: 24px 0;
                        height: 1px;
                        background: #e2e8f0;
                    }}
                    
                    .footer-small {{
                        font-size: 12px;
                        color: #94a3b8;
                    }}
                    
                    @media (max-width: 600px) {{
                        .content {{ 
                            padding: 28px 20px; 
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Account Removed</h1>
                        <p>PPMS Cluster 4 - Imus City Healthcare Management</p>
                    </div>
                    
                    <div class="content">
                        <div class="greeting">
                            Hello <strong>{name}</strong>,
                        </div>
                        
                        <div class="message">
                            We would like to inform you that your Nurse account has been removed from the PPMS Cluster 4 system.
                        </div>
                        
                        <div class="notice">
                            <h3>Important Notice</h3>
                            <p>If you believe this was a mistake or have any questions, please contact the system administrator.</p>
                        </div>
                        
                        <div class="details">
                            <h4>Account Information</h4>
                            <div class="detail-item">
                                <span class="detail-label">Full Name:</span>
                                <span class="detail-value">{name}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Email:</span>
                                <span class="detail-value">{email}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Date Removed:</span>
                                <span class="detail-value">{current_date}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="footer">
                        <h3>PPMS Cluster 4</h3>
                        <p>Imus City Healthcare Management</p>
                        <div class="footer-divider"></div>
                        <p class="footer-small">
                            This is an automated message. Please do not reply.<br>
                            © 2025 PPMS Cluster 4. All rights reserved.
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """

            plain_message = """
PPMS Account Removal Notification

Hello {name},

We would like to inform you that your Nurse account has been removed from the PPMS Cluster 4 system.

IMPORTANT NOTICE:
If you believe this was a mistake or have any questions, please contact the system administrator.

Account Information:
- Full Name: {name}
- Email: {email}
- Date Removed: {current_date}

PPMS Cluster 4
Imus City Healthcare Management

This is an automated message. Please do not reply.
© 2025 PPMS Cluster 4. All rights reserved.
            """

            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                html_message=html_message,
                fail_silently=True,
            )
            print("[DEBUG] ✅ Removal email sent to {email}")

            # Delete account
            nurse.delete()
            
            # Return JSON for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'name': name, 'type': 'Nurse'})
            
            # Fallback for regular form submission
            messages.success(request, "{name} has been successfully removed and notified via email.")
            
        except Account.DoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Worker no longer exists'})
            messages.error(request, "The worker you're trying to remove no longer exists.")
        except Exception as e:
            print("[ERROR] Failed to remove Nurse: {e}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'An error occurred while removing the worker'})
            messages.error(request, "An error occurred while removing the nurse.")

    return redirect('healthcare_workers')

def fix_existing_bns_records():
    """
    Run this once to fix any existing BNS records that might have wrong role names
    You can call this from Django shell or create a management command
    """
    try:
        # Find accounts that might be BNS but have wrong role
        bns_accounts = Account.objects.filter(
            Q(user_role__icontains='BNS') | 
            Q(user_role__icontains='bns') |
            Q(user_role='BNS')
        )
        
        count = 0
        for account in bns_accounts:
            if account.user_role != 'Barangay Nutritional Scholar':
                account.user_role = 'Barangay Nutritional Scholar'
                account.save()
                count += 1
                print("Fixed account: {account.full_name} - {account.email}")
        
        print("Fixed {count} BNS accounts")
        return count
        
    except Exception as e:
        print("Error fixing BNS records: {e}")
        return 0
    


@login_required #dinagadag
def add_vaccination_schedule(request, preschooler_id):
    preschooler = get_object_or_404(Preschooler, pk=preschooler_id)

    if request.method == "POST":
        vaccine_name = request.POST.get("vaccine_name")
        doses = request.POST.get("vaccine_doses")
        required_doses = request.POST.get("required_doses")
        scheduled_date = request.POST.get("immunization_date")
        next_schedule = request.POST.get("next_vaccine_schedule")

        # Assuming BHW is logged in via request.user.account
        bhw = get_object_or_404(BHW, email=request.user.email)

        VaccinationSchedule.objects.create(
            preschooler=preschooler,
            vaccine_name=vaccine_name,
            doses=doses,
            required_doses=required_doses,
            scheduled_date=scheduled_date,
            next_vaccine_schedule=next_schedule,
            administered_by=bhw  # Optional, can leave null initially
        )

        messages.success(request, "Vaccination schedule has been saved successfully.")
        return redirect("preschooler_details", preschooler_id=preschooler_id)

    return redirect("preschooler_details", preschooler_id=preschooler_id)


from .who_lms import WHO_BMI_LMS
from .models import classify_bmi_for_age, calculate_bmi,bmi_zscore

@csrf_exempt
def submit_bmi(request):
    if request.method == 'POST':
        preschooler_id = request.POST.get('preschooler_id')
        weight = request.POST.get('weight')
        height_cm = request.POST.get('height')
        temperature = request.POST.get('temperature')

        preschooler = get_object_or_404(Preschooler, pk=preschooler_id)

        if not weight or not height_cm or not temperature:
            return JsonResponse({
                'status': 'error',
                'message': 'All fields are required'
            })

        try:
            # calculate BMI
            weight = float(weight)
            height_m = float(height_cm) / 100
            bmi_value = weight / (height_m ** 2)

            # save BMI
            today = date.today()
            BMI.objects.update_or_create(
                preschooler_id=preschooler,
                date_recorded=today,
                defaults={'weight': weight, 'height': height_cm, 'bmi_value': bmi_value}
            )

            # save Temperature
            Temperature.objects.update_or_create(
                preschooler_id=preschooler,
                date_recorded=today,
                defaults={'temperature_value': temperature}
            )

            return JsonResponse({
                'status': 'success',
                'message': f'BMI & Temperature successfully recorded for {preschooler.first_name}!',
                'data': {
                    'preschooler_name': f'{preschooler.first_name} {preschooler.last_name}',
                    'weight': weight,
                    'height': height_cm,
                    'temperature': temperature,
                    'bmi': round(bmi_value, 2)
                }
            })

        except ValueError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid number format. Please enter valid numbers.'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            })

    # If GET → redirect to preschoolers
    return redirect('preschoolers')


    

def bmi_form(request, preschooler_id):
    preschooler = get_object_or_404(Preschooler, pk=preschooler_id)
    return render(request, 'HTML/bmi_form.html', {'preschooler': preschooler})

@csrf_exempt
def remove_preschooler(request):
    if request.method == 'POST':
        preschooler_id = request.POST.get('preschooler_id')
        try:
            preschooler = Preschooler.objects.get(pk=preschooler_id)
            preschooler.is_archived = True
            preschooler.save()
            return JsonResponse({'status': 'success'})
        except Preschooler.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Preschooler not found.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})


def archived_preschoolers(request):
    search_query = request.GET.get('q', '').strip()

    archived = Preschooler.objects.filter(is_archived=True)

    # filter by name kung may hinanap
    if search_query:
        archived = archived.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )

    archived = archived.order_by('-date_registered')

    # pagination (10 rows per page)
    paginator = Paginator(archived, 10)
    page_number = request.GET.get('page')
    archived_page = paginator.get_page(page_number)

    return render(request, 'HTML/archived.html', {
        'archived_preschoolers': archived_page,
        'search_query': search_query
    })

@require_POST
def update_child_info(request, preschooler_id):
    preschooler = get_object_or_404(Preschooler, pk=preschooler_id)

    preschooler.place_of_birth = request.POST.get('place_of_birth') or ''
    preschooler.birth_weight = request.POST.get('birth_weight') or None
    preschooler.birth_height = request.POST.get('birth_height') or None
    preschooler.address = request.POST.get('address') or ''
    preschooler.save()

    if preschooler.parent_id:
        parent = preschooler.parent_id
        parent.mother_name = request.POST.get('mother_name') or ''
        parent.father_name = request.POST.get('father_name') or ''
        parent.save()

    messages.success(request, "Child information successfully updated.")
    return redirect('preschooler_detail', preschooler_id=preschooler.preschooler_id)




@login_required
def register_parent(request):
    """Register parent with proper barangay filtering - only allows registration in user's barangay"""
    
    if request.method == 'POST':
        try:
            # Get and validate form data
            first_name = request.POST.get('firstName', '').strip()
            middle_name = request.POST.get('middleName', '').strip()
            last_name = request.POST.get('lastName', '').strip()    
            suffix = request.POST.get('suffix', '').strip()
            email = request.POST.get('email', '').strip()
            contact_number = request.POST.get('contact_number', '').strip()
            birthdate = request.POST.get('birthdate', '').strip()
            
            # Basic validation
            if not all([first_name, last_name, email, contact_number, birthdate]):
                messages.error(request, "All required fields must be filled.")
                return redirect('register_parent')
            
            # Email validation
            if not email or '@' not in email:
                messages.error(request, "Please enter a valid email address.")
                return redirect('register_parent')
            
            # Address fields
            house_number = request.POST.get('houseNumber', '').strip()
            block = request.POST.get('block', '').strip()  
            lot = request.POST.get('lot', '').strip()
            phase = request.POST.get('phase', '').strip()
            street = request.POST.get('street', '').strip()
            subdivision = request.POST.get('subdivision', '').strip()
            city = request.POST.get('city', '').strip()
            province = request.POST.get('province', '').strip()

            # Build complete address
            address_parts = []
            if house_number and house_number.lower() != 'n/a':
                address_parts.append("House {house_number}")
            if block and block.lower() != 'n/a':
                address_parts.append("Block {block}")
            if lot and lot.lower() != 'n/a':
                address_parts.append("Lot {lot}")
            if phase and phase.lower() != 'n/a':
                address_parts.append("Phase {phase}")
            if street:
                address_parts.append(street)
            if subdivision:
                address_parts.append(subdivision)
            if city:
                address_parts.append(city)
            if province:
                address_parts.append(province)

            address = ", ".join(address_parts) if address_parts else "No address provided"
            middle_name = request.POST.get('middleName', '').strip()
            suffix = request.POST.get('suffix', '').strip()
            
            name_parts = []
            if first_name:
                name_parts.append(first_name)
            if middle_name:
                name_parts.append(middle_name)
            if last_name:
                name_parts.append(last_name)
            if suffix and suffix.lower() not in ['na', 'n/a']:
                name_parts.append(suffix)
            
            full_name = " ".join(name_parts).strip()

            # Get user's barangay
            user_barangay = get_user_barangay(request.user)
            current_user_info = None
            
            logger.info("Registration attempt by user: {request.user.email}")
            
            if request.user.is_authenticated:
                # Try each model to find the user and their barangay
                try:
                    account = Account.objects.select_related('barangay').get(email=request.user.email)
                    current_user_info = {
                        'model': 'Account',
                        'name': account.full_name,
                        'role': account.user_role
                    }
                except Account.DoesNotExist:
                    try:
                        bhw = BHW.objects.select_related('barangay').get(email=request.user.email)
                        current_user_info = {
                            'model': 'BHW',
                            'name': bhw.full_name,
                            'role': 'BHW'
                        }
                    except BHW.DoesNotExist:
                        try:
                            bns = BNS.objects.select_related('barangay').get(email=request.user.email)
                            current_user_info = {
                                'model': 'BNS',
                                'name': bns.full_name,
                                'role': 'BNS'
                            }
                        except BNS.DoesNotExist:
                            try:
                                midwife = Midwife.objects.select_related('barangay').get(email=request.user.email)
                                current_user_info = {
                                    'model': 'Midwife',
                                    'name': midwife.full_name,
                                    'role': 'Midwife'
                                }
                            except Midwife.DoesNotExist:
                                try:
                                    nurse = Nurse.objects.select_related('barangay').get(email=request.user.email)
                                    current_user_info = {
                                        'model': 'Nurse',
                                        'name': nurse.full_name,
                                        'role': 'Nurse'
                                    }
                                except Nurse.DoesNotExist:
                                    logger.error("User not found in any authorized user model")

            # Validate that user exists and has proper authorization
            if not current_user_info:
                logger.error("Unauthorized registration attempt by {request.user.email}")
                messages.error(request, "You are not authorized to register parents. Please contact the administrator.")
                return redirect('register_parent')

            # Validate that user has a barangay assigned
            if not user_barangay:
                logger.error("No barangay assigned to user {request.user.email}")
                messages.error(request, "No barangay assigned to your {current_user_info['role']} account. Please contact the administrator.")
                return redirect('register_parent')

            # Validate user role permissions (only for Account model)
            if current_user_info['model'] == 'Account':
                allowed_roles = ['bhw', 'bns', 'barangay nutritional scholar', 'barangay nutrition scholar', 
                               'nutritional scholar', 'nutrition scholar', 'midwife', 'nurse', 'admin', 'administrator']
                if current_user_info['role'].lower() not in [role.lower() for role in allowed_roles]:
                    logger.error("Unauthorized role: {current_user_info['role']}")
                    messages.error(request, "Your role '{current_user_info['role']}' is not authorized to register parents.")
                    return redirect('register_parent')

            logger.info("Authorization passed - Role: {current_user_info['role']}, Barangay: {user_barangay}")

            # Check if email already exists
            if Parent.objects.filter(email__iexact=email).exists():
                messages.error(request, "A parent with this email already exists.")
                return redirect('register_parent')
                
            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, "A user with this email already exists.")
                return redirect('register_parent')

            # Check if contact number already exists in same barangay
            if Parent.objects.filter(contact_number=contact_number, barangay=user_barangay).exists():
                messages.error(request, "A parent with this contact number already exists in {user_barangay.name}.")
                return redirect('register_parent')

            # Parse and validate birthdate
            try:
                birthdate_obj = datetime.strptime(birthdate, '%Y-%m-%d').date()
                logger.info("Birthdate parsed successfully: {birthdate_obj}")
            except ValueError as e:
                logger.error("Birthdate parsing error: {e}")
                messages.error(request, "Invalid birthdate format.")
                return redirect('register_parent')

            # Generate password
            raw_password = generate_password()

            # Use database transaction for atomicity
            with transaction.atomic():
                logger.info("Starting database transaction for {full_name}")
                
                # Create Django User with hashed password
                logger.info("Creating Django User for {email}")
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=raw_password
                )
                logger.info("Django User created successfully")

                # Create Parent with correct field names
                logger.info("Creating Parent record")
                parent = Parent.objects.create(
                    first_name=first_name,
                    middle_name=middle_name,
                    suffix=suffix,
                    last_name=last_name,
                    email=email,
                    contact_number=contact_number,
                    birthdate=birthdate_obj,
                    address=address,
                    barangay=user_barangay,
                    must_change_password=True,
                    password=raw_password,
                    created_at=timezone.now()
                )
                logger.info("Parent created successfully")

                # Create Account - also assign to same barangay
                logger.info("Creating Account record")
                account = Account.objects.create(
                    email=email,
                    first_name=first_name,
                    middle_name=middle_name,
                    suffix=suffix,
                    last_name=last_name,
                    contact_number=contact_number,
                    birthdate=birthdate_obj,
                    user_role='parent',
                    barangay=user_barangay,
                    is_validated=False,
                    is_rejected=False,
                    last_activity=timezone.now(),
                    password=raw_password,
                    must_change_password=True
                )
                logger.info("Account created successfully")

            # Send email (outside transaction to prevent rollback on email failure)
            try:
                subject = "PPMS Cluster 4 – Parent Registration Successful"
                
                html_message = """
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; background-color: #f9fafb; padding: 20px; }}
                        .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                        .header {{ text-align: center; margin-bottom: 30px; }}
                        .credentials {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                        .credential-row {{ margin: 10px 0; font-size: 16px; }}
                        .credential-label {{ font-weight: bold; color: #28a745; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h1>Registration Successful!</h1>
                            <p>PPMS Cluster 4 - Imus City Healthcare Management</p>
                        </div>
                        <p>Hello <strong>{full_name}</strong>,</p>
                        <p>Welcome to PPMS Cluster 4! Your parent account has been successfully registered for <strong>{user_barangay.name}</strong>.</p>
                        
                        <div class="credentials">
                            <h3>Your Login Credentials</h3>
                            <div class="credential-row">
                                <span class="credential-label">Email:</span> {email}
                            </div>
                            <div class="credential-row">
                                <span class="credential-label">Password:</span> {raw_password}
                            </div>
                        </div>
                        
                        <p><strong>Important:</strong> Please keep this information safe. You will be required to change your password on first login.</p>
                        
                        <hr>
                        <p><small>This is an automated message. Please do not reply.<br>© 2025 PPMS Cluster 4. All rights reserved.</small></p>
                    </div>
                </body>
                </html>
                """

                plain_message = """
PPMS Parent Registration Successful

Hello {full_name},

Welcome to PPMS Cluster 4! Your account has been registered for {user_barangay.name}.

Login Credentials:
Email: {email}
Password: {raw_password}

Important: You must change your password on first login.

PPMS Cluster 4 - Imus City Healthcare Management
                """

                send_mail(
                    subject,
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    html_message=html_message,
                    fail_silently=True,
                )
                logger.info("Email sent successfully to {email}")

            except Exception as email_error:
                logger.warning("Email sending failed (non-critical): {email_error}")

            # Success message
            messages.success(request, "Parent '{full_name}' registered successfully in {user_barangay.name}!\nEmail: {email}\nPassword: {raw_password}")
            return redirect('register_parent')

        except IntegrityError as e:
            logger.error("IntegrityError: {e}")
            messages.error(request, "Registration failed due to duplicate data. Please check email and contact number.")
            return redirect('register_parent')
        
        except Exception as e:
            logger.error("Unexpected error during registration: {e}")
            messages.error(request, "An unexpected error occurred during registration. Please try again.")
            return redirect('register_parent')

    # For GET request
    context = {}
    if request.user.is_authenticated:
        user_barangay = get_user_barangay(request.user)
        if user_barangay:
            context['user_barangay'] = user_barangay

        try:
            account = Account.objects.get(email=request.user.email)
            context['account'] = account
        except Account.DoesNotExist:
            account = None

    return render(request, 'HTML/register_parent.html', context)

def get_user_barangay(user):
    """Helper function to get user's barangay from any user model"""
    if not user.is_authenticated:
        return None
    
    # Try each model in order
    models_to_check = [
        (Account, 'email'),
        (BHW, 'email'), 
        (BNS, 'email'),
        (Midwife, 'email'),
        (Nurse, 'email'),
        (Parent, 'email'),
    ]
    
    for model_class, field_name in models_to_check:
        try:
            obj = model_class.objects.get(**{field_name: user.email})
            return obj.barangay
        except model_class.DoesNotExist:
            continue
    
    return None

def generate_password(length=8):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def change_password_first(request):
    if request.method == 'POST':
        email = request.session.get('email', '').strip()
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not email:
            messages.error(request, "Session expired. Please log in again.")
            return redirect('login')

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('change_password_first')

        try:
            user = User.objects.get(username=email)
            user.set_password(new_password)
            user.save()

            parent = Parent.objects.get(email=email)
            parent.must_change_password = False
            parent.save()

            messages.success(request, "Password updated successfully! You can now log in.")
            return redirect('login')

        except User.DoesNotExist:
            messages.error(request, "User not found.")
        except Parent.DoesNotExist:
            messages.error(request, "Parent record not found.")

        return redirect('change_password_first')

    return render(request, 'HTML/parent_change_password.html')


def growth_checker(request):
    return render(request, 'HTML/growthcheck.html')


def growth_chart(request):
    return render(request, 'HTML/growth_chart.html')

@login_required
def history(request):
    """History view with proper barangay filtering - only shows logs from user's barangay"""
    
    # Get user's barangay using consistent logic
    user_barangay = get_user_barangay(request.user)
    current_user_info = None
    
    print("DEBUG: History - Current user email: {request.user.email}")
    
    if request.user.is_authenticated:
        # Try each model to find the user
        try:
            # Try Account model first
            account = Account.objects.select_related('barangay').get(email=request.user.email)
            current_user_info = {
                'model': 'Account',
                'name': account.full_name,
                'role': account.user_role,
                'object': account
            }
            print("DEBUG: Found in Account: {account.email}, Barangay: {user_barangay}")
        except Account.DoesNotExist:
            try:
                # Try BHW model
                bhw = BHW.objects.select_related('barangay').get(email=request.user.email)
                current_user_info = {
                    'model': 'BHW',
                    'name': bhw.full_name,
                    'role': 'BHW',
                    'object': bhw
                }
                print("DEBUG: Found in BHW: {bhw.email}, Barangay: {user_barangay}")
            except BHW.DoesNotExist:
                try:
                    # Try BNS model
                    bns = BNS.objects.select_related('barangay').get(email=request.user.email)
                    current_user_info = {
                        'model': 'BNS',
                        'name': bns.full_name,
                        'role': 'BNS',
                        'object': bns
                    }
                    print("DEBUG: Found in BNS: {bns.email}, Barangay: {user_barangay}")
                except BNS.DoesNotExist:
                    try:
                        # Try Midwife model
                        midwife = Midwife.objects.select_related('barangay').get(email=request.user.email)
                        current_user_info = {
                            'model': 'Midwife',
                            'name': midwife.full_name,
                            'role': 'Midwife',
                            'object': midwife
                        }
                        print("DEBUG: Found in Midwife: {midwife.email}, Barangay: {user_barangay}")
                    except Midwife.DoesNotExist:
                        try:
                            # Try Nurse model
                            nurse = Nurse.objects.select_related('barangay').get(email=request.user.email)
                            current_user_info = {
                                'model': 'Nurse',
                                'name': nurse.full_name,
                                'role': 'Nurse',
                                'object': nurse
                            }
                            print("DEBUG: Found in Nurse: {nurse.email}, Barangay: {user_barangay}")
                        except Nurse.DoesNotExist:
                            try:
                                # Try Parent model
                                parent = Parent.objects.select_related('barangay').get(email=request.user.email)
                                current_user_info = {
                                    'model': 'Parent',
                                    'name': parent.full_name,
                                    'role': 'Parent',
                                    'object': parent
                                }
                                print("DEBUG: Found in Parent: {parent.email}, Barangay: {user_barangay}")
                            except Parent.DoesNotExist:
                                print("DEBUG: User not found in any model")

    # If no user found or no barangay assigned, show empty history
    if not current_user_info or not user_barangay:
        print("DEBUG: No user info or barangay found. User info: {current_user_info}, Barangay: {user_barangay}")
        return render(request, 'HTML/history.html', {
            'account': None,
            'parent_logs': [],
            'preschooler_logs': [],
            'user_barangay': user_barangay,
            'error_message': 'No barangay assigned to your account or user not found.'
        })

    print("DEBUG: History access authorized for {current_user_info['role']} in {user_barangay}")

    # Calculate time boundaries for log cleanup
    now = timezone.now()
    yesterday = now - timedelta(days=1)

    # Optional: delete old logs (only for current user's barangay)
    deleted_parent_logs = ParentActivityLog.objects.filter(barangay=user_barangay, timestamp__lt=yesterday).delete()
    deleted_preschooler_logs = PreschoolerActivityLog.objects.filter(barangay=user_barangay, timestamp__lt=yesterday).delete()
    
    if deleted_parent_logs[0] > 0 or deleted_preschooler_logs[0] > 0:
        print("DEBUG: Cleaned up {deleted_parent_logs[0]} parent logs and {deleted_preschooler_logs[0]} preschooler logs older than yesterday")

    # Get logs ONLY from user's barangay
    parent_logs = ParentActivityLog.objects.filter(barangay=user_barangay).select_related('parent', 'barangay').order_by('-timestamp')
    preschooler_logs = PreschoolerActivityLog.objects.filter(barangay=user_barangay).select_related('barangay').order_by('-timestamp')

    print("DEBUG: Found {parent_logs.count()} parent logs and {preschooler_logs.count()} preschooler logs for {user_barangay}")

    # Debug: Show some sample logs
    for log in parent_logs[:3]:
        print("DEBUG: Parent log: {log.activity} - {log.timestamp} - Barangay: {log.barangay}")
    
    for log in preschooler_logs[:3]:
        print("DEBUG: Preschooler log: {log.activity} - {log.timestamp} - Barangay: {log.barangay}")

    # Paginate each log type
    parent_paginator = Paginator(parent_logs, 10)
    preschooler_paginator = Paginator(preschooler_logs, 10)

    parent_page_number = request.GET.get('parent_page')
    preschooler_page_number = request.GET.get('preschooler_page')

    parent_logs_page = parent_paginator.get_page(parent_page_number)
    preschooler_logs_page = preschooler_paginator.get_page(preschooler_page_number)

    return render(request, 'HTML/history.html', {
        'account': current_user_info['object'],
        'parent_logs': parent_logs_page,
        'preschooler_logs': preschooler_logs_page,
        'user_barangay': user_barangay,
        'current_user_info': current_user_info,
        'total_parent_logs': parent_logs.count(),
        'total_preschooler_logs': preschooler_logs.count(),
    })


# Additional helper function to create activity logs with barangay validation
def create_parent_activity_log(parent, activity, performed_by_user):
    """Create parent activity log with barangay validation"""
    user_barangay = get_user_barangay(performed_by_user)
    
    # Only create log if parent and user are in same barangay
    if user_barangay and parent.barangay == user_barangay:
        try:
            # Get user info for logging
            user_info = None
            try:
                account = Account.objects.get(email=performed_by_user.email)
                user_info = "{account.full_name} ({account.user_role})"
            except Account.DoesNotExist:
                # Try other user models
                for model_class in [BHW, BNS, Midwife, Nurse]:
                    try:
                        user_obj = model_class.objects.get(email=performed_by_user.email)
                        user_info = "{user_obj.full_name} ({model_class.__name__})"
                        break
                    except model_class.DoesNotExist:
                        continue
            
            if not user_info:
                user_info = performed_by_user.email
            
            ParentActivityLog.objects.create(
                parent=parent,
                barangay=user_barangay,
                activity=activity,
                performed_by=user_info  # Assuming you have this field
            )
            print("DEBUG: Created parent activity log: {activity} for {parent.full_name} in {user_barangay}")
        except Exception as e:
            print("DEBUG: Error creating parent activity log: {e}")


def create_preschooler_activity_log(preschooler, activity, performed_by_user):
    """Create preschooler activity log with barangay validation"""
    user_barangay = get_user_barangay(performed_by_user)
    
    # Only create log if preschooler and user are in same barangay
    if user_barangay and preschooler.barangay == user_barangay:
        try:
            # Get user info for logging
            user_info = None
            try:
                account = Account.objects.get(email=performed_by_user.email)
                user_info = "{account.full_name} ({account.user_role})"
            except Account.DoesNotExist:
                # Try other user models
                for model_class in [BHW, BNS, Midwife, Nurse]:
                    try:
                        user_obj = model_class.objects.get(email=performed_by_user.email)
                        user_info = "{user_obj.full_name} ({model_class.__name__})"
                        break
                    except model_class.DoesNotExist:
                        continue
            
            if not user_info:
                user_info = performed_by_user.email
            
            PreschoolerActivityLog.objects.create(
                preschooler_name="{preschooler.first_name} {preschooler.last_name}",
                barangay=user_barangay,
                activity=activity,
                performed_by=user_info
            )
            print("DEBUG: Created preschooler activity log: {activity} for {preschooler.first_name} {preschooler.last_name} in {user_barangay}")
        except Exception as e:
            print("DEBUG: Error creating preschooler activity log: {e}")


def admin_logs(request):
    if request.session.get('user_role') != 'admin':
        return redirect('login')

    now = timezone.now()
    yesterday = now - timedelta(days=1)

    # Delete logs older than 1 day
    ParentActivityLog.objects.filter(timestamp__lt=yesterday).delete()
    PreschoolerActivityLog.objects.filter(timestamp__lt=yesterday).delete()

    parent_logs_all = ParentActivityLog.objects.select_related('parent', 'barangay').order_by('-timestamp')
    preschooler_logs_all = PreschoolerActivityLog.objects.select_related('barangay').order_by('-timestamp')

    # Paginate
    parent_paginator = Paginator(parent_logs_all, 10)  # 10 per page
    preschooler_paginator = Paginator(preschooler_logs_all, 20)

    parent_page = request.GET.get('parent_page')
    preschooler_page = request.GET.get('preschooler_page')

    context = {
        'parent_logs': parent_paginator.get_page(parent_page),
        'preschooler_logs': preschooler_paginator.get_page(preschooler_page),
    }

    return render(request, 'HTML/admin_logs.html', context)

from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User  # your Django User model

@method_decorator(csrf_exempt, name='dispatch')
class LoginAPIView(APIView):
    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        user = authenticate(request, username=email, password=password)
        account = None

        if user is None:
            # Fallback to raw password
            try:
                account = Account.objects.get(email=email)
                if account.password != password:
                    return Response({"error": "Invalid email or password"}, status=status.HTTP_401_UNAUTHORIZED)
            except Account.DoesNotExist:
                return Response({"error": "Account not found"}, status=status.HTTP_404_NOT_FOUND)

            # 👇 if raw password matched, generate a token for mobile
            # pick some user to tie the JWT to
            # (better: ensure each Account links to an auth.User)
            user = User.objects.first()  

        else:
            # normal auth user matched
            try:
                account = Account.objects.get(email=email)
            except Account.DoesNotExist:
                return Response({"error": "Account not found"}, status=status.HTTP_404_NOT_FOUND)

        # ✅ issue tokens (works for both raw + auth)
        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "Login successful",
            "account_id": account.account_id,
            "full_name": account.full_name,
            "user_role": account.user_role,
            "is_validated": account.is_validated,
            "email": account.email,
            "must_change_password": getattr(account, "must_change_password", False),

            # 🔑 tokens for mobile
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }, status=status.HTTP_200_OK)




@method_decorator(csrf_exempt, name='dispatch')
class RegisterAPIView(APIView):
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        # Force JSON parsing
        if hasattr(request, '_body'):
            import json
            try:
                json_data = json.loads(request.body)
                request._full_data = json_data
            except:
                pass
        
        serializer = RegisterSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                account = serializer.save()
                return Response({
                    'message': 'Account created successfully',
                    'account': serializer.data
                }, status=status.HTTP_201_CREATED)
            
            except Exception as e:
                return Response({
                    'error': 'Failed to create account',
                    'details': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'error': 'Validation failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
@api_view(['GET'])
def admin_dashboard_stats(request):
    """Get admin dashboard statistics"""
    try:
        # Total registered users (all accounts)
        total_registered = Account.objects.count()
        
        # Health workers count
        health_workers = Account.objects.filter(
            user_role__iexact='healthworker', 
            is_validated=True
        ).count()
        
        # Total preschoolers (not archived)
        total_preschoolers = Preschooler.objects.filter(is_archived=False).count()
        
        # Total barangays
        barangay_count = Barangay.objects.count()
        
        return Response({
            'total_registered': total_registered,
            'health_workers': health_workers,
            'total_preschoolers': total_preschoolers,
            'barangay_count': barangay_count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Failed to load dashboard stats: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def admin_recent_activity(request):
    """Get recent activity for admin dashboard"""
    try:
        activities = []
        
        # Get recent account registrations (last 7 days)
        recent_accounts = Account.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-created_at')[:10]
        
        for acc in recent_accounts:
            activities.append({
                'id': acc.account_id,
                'title': 'New Account Registration',
                'description': f'{acc.full_name} registered as {acc.user_role}',
                'timestamp': acc.created_at.isoformat(),
                'type': 'account'
            })
        
        # Get recent preschooler registrations
        recent_preschoolers = Preschooler.objects.filter(
            date_registered__gte=timezone.now() - timedelta(days=7),
            is_archived=False
        ).order_by('-date_registered')[:10]
        
        for child in recent_preschoolers:
            activities.append({
                'id': child.preschooler_id,
                'title': 'New Preschooler Registration',
                'description': f'{child.first_name} {child.last_name} registered in {child.barangay.name if child.barangay else "Unknown"}',
                'timestamp': child.date_registered.isoformat(),
                'type': 'preschooler'
            })
        
        # Get recent vaccinations (confirmed schedules)
        recent_vaccinations = VaccinationSchedule.objects.filter(
            confirmed_by_parent=True,
            administered_date__gte=timezone.now().date() - timedelta(days=7)
        ).order_by('-administered_date')[:5]
        
        for vax in recent_vaccinations:
            activities.append({
                'id': vax.id,
                'title': 'Vaccination Completed',
                'description': f'{vax.vaccine_name} administered to {vax.preschooler.first_name} {vax.preschooler.last_name}',
                'timestamp': timezone.make_aware(
                    timezone.datetime.combine(vax.administered_date, timezone.datetime.min.time())
                ).isoformat(),
                'type': 'vaccination'
            })
        
        # Sort all activities by timestamp (most recent first)
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return Response({
            'activities': activities[:15]  # Return top 15 activities
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Failed to load recent activity: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def admin_nutritional_overview(request):
    """Get nutritional status overview for admin dashboard using WHO BMI-for-age Z-scores"""
    try:
        preschoolers = Preschooler.objects.filter(is_archived=False).prefetch_related('bmi_set')

        nutritional_summary = {
            'severely_wasted': 0,
            'wasted': 0,
            'normal': 0,
            'risk_of_overweight': 0,
            'overweight': 0,
            'obese': 0,
        }

        total_with_records = 0
        today = date.today()

        for p in preschoolers:
            latest_bmi = p.bmi_set.order_by('-date_recorded').first()
            if latest_bmi:
                try:
                    # --- Compute age in months ---
                    birth_date = p.birth_date
                    age_years = today.year - birth_date.year
                    age_months = today.month - birth_date.month
                    if today.day < birth_date.day:
                        age_months -= 1
                    if age_months < 0:
                        age_years -= 1
                        age_months += 12
                    total_age_months = age_years * 12 + age_months

                    # --- Compute BMI & Z-score classification ---
                    bmi_value = calculate_bmi(latest_bmi.weight, latest_bmi.height)
                    z = bmi_zscore(p.sex, total_age_months, bmi_value)
                    category = classify_bmi_for_age(z)

                    total_with_records += 1
                    if category == "Severely wasted":
                        nutritional_summary['severely_wasted'] += 1
                    elif category == "Wasted":
                        nutritional_summary['wasted'] += 1
                    elif category == "Normal":
                        nutritional_summary['normal'] += 1
                    elif category == "Risk of overweight":
                        nutritional_summary['risk_of_overweight'] += 1
                    elif category == "Overweight":
                        nutritional_summary['overweight'] += 1
                    elif category == "Obese":
                        nutritional_summary['obese'] += 1

                except Exception as e:
                    print("⚠️ Error processing preschooler {p.id}: {e}")
                    continue

        return Response({
            'nutritional_status': nutritional_summary,
            'total_with_records': total_with_records
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'error': f'Failed to load nutritional overview: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def admin_notifications(request):
    """Get notifications for admin dashboard"""
    try:
        notifications = []
        unread_count = 0
        
        # Pending account validations
        pending_accounts = Account.objects.filter(
            is_validated=False,
            is_rejected=False,
            user_role__iexact='healthworker'
        ).order_by('-created_at')
        
        for acc in pending_accounts:
            notifications.append({
                'id': acc.account_id,
                'type': 'validation_required',
                'title': 'Account Validation Required',
                'message': f'{acc.full_name} needs account validation',
                'timestamp': acc.created_at.isoformat(),
                'is_read': False
            })
            unread_count += 1
        
        # Recent preschooler registrations that need attention
        recent_preschoolers = Preschooler.objects.filter(
            date_registered__gte=timezone.now() - timedelta(days=3),
            is_archived=False,
            is_notif_read=False
        ).order_by('-date_registered')[:10]
        
        for child in recent_preschoolers:
            notifications.append({
                'id': child.preschooler_id,
                'type': 'new_registration',
                'title': 'New Preschooler Registration',
                'message': f'{child.first_name} {child.last_name} registered in {child.barangay.name if child.barangay else "Unknown"}',
                'timestamp': child.date_registered.isoformat(),
                'is_read': child.is_notif_read
            })
            if not child.is_notif_read:
                unread_count += 1
        
        # Low vaccine stock alerts (if applicable)
        try:
            from WebApp.models import VaccineStock
            low_stock = VaccineStock.objects.filter(available_stock__lt=10)
            
            for stock in low_stock:
                notifications.append({
                    'id': f'stock_{stock.id}',
                    'type': 'low_stock',
                    'title': 'Low Vaccine Stock',
                    'message': f'{stock.vaccine_name} in {stock.barangay.name if stock.barangay else "system"} is running low ({stock.available_stock} remaining)',
                    'timestamp': stock.last_updated.isoformat(),
                    'is_read': False
                })
                unread_count += 1
        except:
            pass  # VaccineStock model might not exist in all implementations
        
        # Sort notifications by timestamp (most recent first)
        notifications.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return Response({
            'notifications': notifications[:20],  # Return top 20 notifications
            'unread_count': unread_count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Failed to load notifications: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@csrf_exempt
def get_user_profile(request):
    """Get current user's profile data"""
    try:
        # Get email from query parameter with validation
        email = request.GET.get('email', '').strip()
        
        if not email:
            logger.warning("Profile request without email parameter")
            return Response({
                'success': False,
                'error': 'Email parameter required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate email format
        import re
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            logger.warning("Invalid email format: {email}")
            return Response({
                'success': False,
                'error': 'Invalid email format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Fetch account with related data
        account = Account.objects.select_related('barangay', 'profile_photo').get(email=email)
        
        serializer = ProfileSerializer(account, context={'request': request})
        
        response_data = {
            'success': True,
            'data': {
                'account_id': account.account_id,
                'full_name': account.full_name or "",
                'email': account.email or "",
                'contact_number': account.contact_number or "",
                'address': account.address or "",
                'birthdate': account.birthdate.isoformat() if account.birthdate else None,
                'user_role': account.user_role or "",
                'barangay': {
                    'id': account.barangay.id if account.barangay else None,
                    'name': account.barangay.name if account.barangay else None,
                    'location': account.barangay.location if account.barangay else None,
                } if account.barangay else None,
                'profile_photo_url': serializer.get_profile_photo_url(account),
                'is_validated': account.is_validated,
                'created_at': account.created_at.isoformat() if account.created_at else None
            }
        }
        
        logger.info("Profile retrieved successfully for email: {email}")
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Account.DoesNotExist:
        logger.warning("Account not found for email: {email}")
        return Response({
            'success': False,
            'error': 'Account not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Error retrieving profile for {email}: {str(e)}")
        return Response({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@csrf_exempt
def update_user_profile(request):
    """Update user profile with enhanced validation + token + email fallback"""
    try:
        # ---------------- AUTHORIZATION ----------------
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({
                'success': False,
                'error': 'Authorization token required'
            }, status=status.HTTP_401_UNAUTHORIZED)

        token = auth_header.split(' ')[1]
        # TODO: Add your token validation logic here (e.g., decode JWT)

        # ---------------- REQUEST DATA ----------------
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        # Email can come from query params or request body
        email = request.GET.get('email', '').strip()
        if not email:
            email = data.get('email', '').strip() if data.get('email') else ""

        if not email:
            logger.warning("Profile update request without email")
            return Response({
                'success': False,
                'error': 'Email is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # ---------------- EMAIL VALIDATION ----------------
        import re
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            logger.warning("Invalid email format in update: {email}")
            return Response({
                'success': False,
                'error': 'Invalid email format'
            }, status=status.HTTP_400_BAD_REQUEST)

        account = Account.objects.select_related('barangay').get(email=email)

        # ---------------- VALIDATIONS ----------------
        validation_errors = []

        # Full name validation
        if 'full_name' in data:
            full_name = str(data['full_name']).strip()
            if not full_name:
                validation_errors.append('Full name cannot be empty')
            elif len(full_name) > 100:
                validation_errors.append('Full name must be less than 100 characters')
            else:
                account.full_name = full_name

        # Address validation
        if 'address' in data:
            address = str(data['address']).strip() if data['address'] else ""
            if len(address) > 255:
                validation_errors.append('Address must be less than 255 characters')
            else:
                account.address = address

        # Contact number validation
        if 'contact_number' in data:
            contact = str(data['contact_number']).strip() if data['contact_number'] else ""
            if contact:  # Only validate if not empty
                if len(contact) not in [11, 12]:
                    validation_errors.append('Contact number must be 11 or 12 digits')
                elif not contact.isdigit():
                    validation_errors.append('Contact number must contain only digits')
                elif not (contact.startswith('09') or contact.startswith('639')):
                    validation_errors.append('Contact number must start with 09 or 639')
                else:
                    account.contact_number = contact
            else:
                account.contact_number = ""

        # Birthdate validation
        if 'birthdate' in data:
            birthdate_str = data['birthdate']
            if birthdate_str:
                try:
                    from datetime import datetime, date
                    birthdate = datetime.strptime(birthdate_str, '%Y-%m-%d').date()
                    if birthdate > date.today():
                        validation_errors.append('Birthdate cannot be in the future')
                    else:
                        account.birthdate = birthdate
                except ValueError:
                    validation_errors.append('Invalid birthdate format. Use YYYY-MM-DD')
            else:
                account.birthdate = None

        # Stop early if validation fails
        if validation_errors:
            logger.warning("Validation errors for {email}: {validation_errors}")
            return Response({
                'success': False,
                'error': '; '.join(validation_errors)
            }, status=status.HTTP_400_BAD_REQUEST)

        # ---------------- BARANGAY HANDLING ----------------
        if 'barangay_id' in data and data['barangay_id']:
            try:
                barangay = Barangay.objects.get(id=int(data['barangay_id']))
                old_barangay = account.barangay
                account.barangay = barangay

                if account.user_role and account.user_role.lower() == 'parent':
                    try:
                        parent = Parent.objects.get(email=account.email)
                        parent.barangay = barangay
                        parent.save()
                        Preschooler.objects.filter(parent_id=parent).update(barangay=barangay)
                        logger.info("Updated barangay for parent and children: {email}")
                    except Parent.DoesNotExist:
                        logger.warning("Parent record not found for account: {email}")
                        pass
            except (Barangay.DoesNotExist, ValueError, TypeError):
                logger.warning("Invalid barangay_id: {data.get('barangay_id')}")
                return Response({
                    'success': False,
                    'error': 'Selected barangay does not exist'
                }, status=status.HTTP_400_BAD_REQUEST)

        # ---------------- SAVE ----------------
        account.save()
        logger.info("Profile updated successfully for: {email}")

        # Serialize updated account
        serializer = ProfileSerializer(account, context={'request': request})

        response_data = {
            'success': True,
            'message': 'Profile updated successfully',
            'data': {
                'account_id': account.account_id,
                'full_name': account.full_name or "",
                'email': account.email or "",
                'contact_number': account.contact_number or "",
                'address': account.address or "",
                'birthdate': account.birthdate.isoformat() if account.birthdate else None,
                'user_role': account.user_role or "",
                'barangay': {
                    'id': account.barangay.id if account.barangay else None,
                    'name': account.barangay.name if account.barangay else None,
                    'location': account.barangay.location if account.barangay else None,
                } if account.barangay else None,
                'profile_photo_url': serializer.get_profile_photo_url(account),
                'is_validated': account.is_validated,
                'created_at': account.created_at.isoformat() if account.created_at else None
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Account.DoesNotExist:
        logger.warning("Account not found for update: {request.GET.get('email', data.get('email', 'unknown'))}")
        return Response({
            'success': False,
            'error': 'Account not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return Response({
            'success': False,
            'error': 'Invalid JSON format'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Unexpected error updating profile: {str(e)}")
        return Response({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@csrf_exempt
def get_barangays(request):
    """Get list of all barangays"""
    try:
        barangays = Barangay.objects.all().order_by('name')
        barangay_list = []
        
        for barangay in barangays:
            barangay_list.append({
                'id': barangay.id,
                'name': barangay.name,
                'location': barangay.location or ''
            })
        
        return Response({
            'success': True,
            'barangays': barangay_list
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['GET'])
def parent_dashboard_api(request):
    """Get parent dashboard data with WHO BMI-for-age classification"""
    try:
        # ✅ Get parent by email
        parent = get_object_or_404(Parent, email=request.user.email)

        preschoolers_data = []
        preschoolers_raw = Preschooler.objects.filter(
            parent_id=parent,
            is_archived=False
        ).prefetch_related('bmi_set', 'temperature_set')

        today = date.today()

        for p in preschoolers_raw:
            # --- Calculate exact age in months ---
            birth_date = p.birth_date
            age_years = today.year - birth_date.year
            age_months = today.month - birth_date.month
            if today.day < birth_date.day:
                age_months -= 1
            if age_months < 0:
                age_years -= 1
                age_months += 12
            total_age_months = age_years * 12 + age_months

            # --- Get latest BMI and temperature ---
            latest_bmi = p.bmi_set.order_by('-date_recorded').first()
            latest_temp = p.temperature_set.order_by('-date_recorded').first()

            # --- Determine nutritional status (WHO Z-score based) ---
            nutritional_status = "N/A"
            if latest_bmi:
                try:
                    bmi_value = calculate_bmi(latest_bmi.weight, latest_bmi.height)
                    z = bmi_zscore(p.sex, total_age_months, bmi_value)
                    nutritional_status = classify_bmi_for_age(z)
                except Exception as e:
                    print("⚠️ Error classifying preschooler {p.id}: {e}")
                    nutritional_status = "N/A"

            preschooler_data = {
                'preschooler_id': p.preschooler_id,
                'first_name': p.first_name,
                'last_name': p.last_name,
                'sex': p.sex,
                'birth_date': p.birth_date.strftime('%Y-%m-%d'),
                'age': age_years,
                'age_months': age_months,
                'address': p.address,
                'nutritional_status': nutritional_status,
                'barangay': p.barangay.name if p.barangay else None,
                'profile_photo': p.profile_photo.url if p.profile_photo else None,
                'latest_bmi': {
                    'bmi_id': latest_bmi.bmi_id,
                    'weight': latest_bmi.weight,
                    'height': latest_bmi.height,
                    'bmi_value': latest_bmi.bmi_value,
                    'date_recorded': latest_bmi.date_recorded.strftime('%Y-%m-%d')
                } if latest_bmi else None,
                'latest_temperature': {
                    'temperature_id': latest_temp.temperature_id,
                    'temperature_value': latest_temp.temperature_value,
                    'date_recorded': latest_temp.date_recorded.strftime('%Y-%m-%d')
                } if latest_temp else None
            }
            preschoolers_data.append(preschooler_data)

        # ✅ Upcoming vaccination schedules
        upcoming_schedules = VaccinationSchedule.objects.filter(
            preschooler__in=preschoolers_raw,
            confirmed_by_parent=False,
            scheduled_date__gte=timezone.now().date()
        ).select_related('preschooler').order_by('scheduled_date')

        schedules_data = []
        for schedule in upcoming_schedules:
            schedules_data.append({
                'id': schedule.id,
                'preschooler': {
                    'preschooler_id': schedule.preschooler.preschooler_id,
                    'first_name': schedule.preschooler.first_name,
                    'last_name': schedule.preschooler.last_name
                },
                'vaccine_name': schedule.vaccine_name,
                'doses': schedule.doses,
                'required_doses': schedule.required_doses,
                'scheduled_date': schedule.scheduled_date.strftime('%Y-%m-%d'),
                'next_vaccine_schedule': schedule.next_vaccine_schedule.strftime('%Y-%m-%d') if schedule.next_vaccine_schedule else None,
                'confirmed_by_parent': schedule.confirmed_by_parent,
                'administered_date': schedule.administered_date.strftime('%Y-%m-%d') if schedule.administered_date else None,
                'lapsed': schedule.lapsed
            })

        # ✅ Parent info
        parent_info = {
            'full_name': parent.full_name,
            'email': parent.email,
            'contact_number': parent.contact_number,
            'barangay': parent.barangay.name if parent.barangay else None
        }

        return Response({
            'preschoolers': preschoolers_data,
            'upcoming_schedules': schedules_data,
            'parent_info': parent_info
        }, status=status.HTTP_200_OK)

    except Parent.DoesNotExist:
        return Response({
            'error': 'Parent not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': f'Failed to load dashboard data: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def confirm_vaccination_api(request):
    """Confirm vaccination schedule"""
    try:
        schedule_id = request.data.get('schedule_id')
        if not schedule_id:
            return Response({
                'success': False,
                'error': 'Schedule ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get the schedule and verify it belongs to the parent
        schedule = get_object_or_404(VaccinationSchedule, id=schedule_id)
        
        # Verify the schedule belongs to this parent
        if schedule.preschooler.parent_id.email != request.user.email:
            return Response({
                'success': False,
                'error': 'Unauthorized access'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Confirm the schedule
        schedule.confirmed_by_parent = True
        schedule.administered_date = timezone.now().date()
        schedule.save()
        
        # Create next dose if needed
        if (schedule.next_vaccine_schedule and 
            schedule.doses < schedule.required_doses):
            
            # Check if next dose already exists
            existing = VaccinationSchedule.objects.filter(
                preschooler=schedule.preschooler,
                vaccine_name=schedule.vaccine_name,
                doses=schedule.doses + 1
            ).exists()
            
            if not existing:
                VaccinationSchedule.objects.create(
                    preschooler=schedule.preschooler,
                    vaccine_name=schedule.vaccine_name,
                    doses=schedule.doses + 1,
                    required_doses=schedule.required_doses,
                    scheduled_date=schedule.next_vaccine_schedule,
                    scheduled_by=schedule.scheduled_by,
                    confirmed_by_parent=False
                )
        
        return Response({
            'success': True,
            'message': 'Vaccination confirmed successfully'
        }, status=status.HTTP_200_OK)
        
    except VaccinationSchedule.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Vaccination schedule not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Failed to confirm vaccination: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def preschooler_detail_api(request, preschooler_id):
    """Get detailed preschooler information (with WHO BMI-for-age classification)"""
    try:
        # ✅ Get preschooler and verify it belongs to the parent
        preschooler = get_object_or_404(
            Preschooler,
            preschooler_id=preschooler_id,
            parent_id__email=request.user.email,
            is_archived=False
        )

        # ✅ Calculate exact age
        today = date.today()
        birth_date = preschooler.birth_date
        age_years = today.year - birth_date.year
        age_months = today.month - birth_date.month
        if today.day < birth_date.day:
            age_months -= 1
        if age_months < 0:
            age_years -= 1
            age_months += 12
        total_age_months = age_years * 12 + age_months

        # ✅ Get BMI history
        bmi_history = []
        for bmi in preschooler.bmi_set.order_by('-date_recorded')[:10]:
            bmi_history.append({
                'bmi_id': bmi.bmi_id,
                'weight': bmi.weight,
                'height': bmi.height,
                'bmi_value': bmi.bmi_value,
                'date_recorded': bmi.date_recorded.strftime('%Y-%m-%d')
            })

        # ✅ Get temperature history
        temp_history = []
        for temp in preschooler.temperature_set.order_by('-date_recorded')[:10]:
            temp_history.append({
                'temperature_id': temp.temperature_id,
                'temperature_value': temp.temperature_value,
                'date_recorded': temp.date_recorded.strftime('%Y-%m-%d')
            })

        # ✅ Get vaccination history
        vaccination_history = []
        for vax in preschooler.vaccination_schedules.all().order_by('-scheduled_date'):
            vaccination_history.append({
                'id': vax.id,
                'vaccine_name': vax.vaccine_name,
                'doses': vax.doses,
                'required_doses': vax.required_doses,
                'scheduled_date': vax.scheduled_date.strftime('%Y-%m-%d'),
                'confirmed_by_parent': vax.confirmed_by_parent,
                'administered_date': vax.administered_date.strftime('%Y-%m-%d') if vax.administered_date else None
            })

        # ✅ Nutritional status using WHO Z-score
        latest_bmi = preschooler.bmi_set.order_by('-date_recorded').first()
        nutritional_status = "N/A"
        if latest_bmi:
            try:
                bmi_value = calculate_bmi(latest_bmi.weight, latest_bmi.height)
                z = bmi_zscore(preschooler.sex, total_age_months, bmi_value)
                nutritional_status = classify_bmi_for_age(z)
            except Exception as e:
                print("⚠️ Error classifying preschooler {preschooler.preschooler_id}: {e}")
                nutritional_status = "N/A"

        preschooler_data = {
            'preschooler_id': preschooler.preschooler_id,
            'first_name': preschooler.first_name,
            'last_name': preschooler.last_name,
            'sex': preschooler.sex,
            'birth_date': preschooler.birth_date.strftime('%Y-%m-%d'),
            'age': age_years,
            'age_months': age_months,
            'address': preschooler.address,
            'nutritional_status': nutritional_status,
            'barangay': preschooler.barangay.name if preschooler.barangay else None,
            'profile_photo': preschooler.profile_photo.url if preschooler.profile_photo else None,
            'place_of_birth': preschooler.place_of_birth,
            'birth_weight': preschooler.birth_weight,
            'birth_height': preschooler.birth_height
        }

        return Response({
            'preschooler': preschooler_data,
            'vaccination_history': vaccination_history,
            'bmi_history': bmi_history,
            'temperature_history': temp_history
        }, status=status.HTTP_200_OK)

    except Preschooler.DoesNotExist:
        return Response({
            'error': 'Preschooler not found or access denied'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': f'Failed to load preschooler details: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
def manage_announcements(request):
    """
    View to display all announcements with options to add, edit, delete
    """
    try:
        announcements = Announcement.objects.all().order_by('-created_at')
    except Exception as e:
        messages.error(request, 'Error loading announcements. Please ensure the database is properly set up.')
        announcements = []
    
    context = {
        'announcements': announcements,
        'account': request.user,
    }
    
    return render(request, 'HTML/manage_announcements.html', context)

def add_announcement(request):
    """
    View to add a new announcement with manual user handling
    """
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        is_active = request.POST.get('is_active') == 'on'
        image = request.FILES.get('image', None)
        
        if title and content:
            try:
                # Manual user retrieval
                if hasattr(request, 'user') and request.user.is_authenticated:
                    # Get the actual User object from the database
                    user_obj = User.objects.get(id=request.user.id)
                    created_by = user_obj
                else:
                    created_by = None
                
                announcement = Announcement.objects.create(
                    title=title,
                    content=content,
                    image=image,
                    is_active=is_active,
                    created_by=created_by,
                    created_at=timezone.now()
                )
                messages.success(request, 'Announcement added successfully!')
                
            except User.DoesNotExist:
                messages.error(request, 'User not found. Please log in again.')
            except Exception as e:
                messages.error(request, f'Error creating announcement: {str(e)}')
        else:
            messages.error(request, 'Title and content are required!')
    
    return redirect('manage_announcements')

def edit_announcement(request, announcement_id):
    """
    View to edit an existing announcement with image replacement support
    """
    announcement = get_object_or_404(Announcement, id=announcement_id)
    
    if request.method == 'POST':
        announcement.title = request.POST.get('title')
        announcement.content = request.POST.get('content')
        announcement.priority = request.POST.get('priority', 'normal')
        announcement.is_active = request.POST.get('is_active') == 'on'
        announcement.updated_at = timezone.now()
        
        # Handle image replacement
        new_image = request.FILES.get('image', None)
        if new_image:
            # Delete old image if it exists
            if announcement.image:
                try:
                    # Delete the old image file from storage
                    import os
                    if os.path.exists(announcement.image.path):
                        os.remove(announcement.image.path)
                except Exception as e:
                    # Log the error but don't fail the update
                    print("Error deleting old image: {str(e)}")
            
            # Assign new image
            announcement.image = new_image
        
        if announcement.title and announcement.content:
            try:
                announcement.save()
                messages.success(request, 'Announcement updated successfully!')
            except Exception as e:
                messages.error(request, f'Error updating announcement: {str(e)}')
        else:
            messages.error(request, 'Title and content are required!')
    
    return redirect('manage_announcements')

def delete_announcement(request, announcement_id):
    """
    View to delete an announcement
    """
    if request.method == 'POST':
        try:
            announcement = get_object_or_404(Announcement, id=announcement_id)
            
            # Delete associated image file if it exists
            if announcement.image:
                try:
                    import os
                    if os.path.exists(announcement.image.path):
                        os.remove(announcement.image.path)
                except Exception as e:
                    print("Error deleting image file: {str(e)}")
            
            announcement.delete()
            messages.success(request, 'Announcement deleted successfully!')
        except Exception as e:
            messages.error(request, f'Error deleting announcement: {str(e)}')
    
    return redirect('manage_announcements')



from django.db.models import Count, Q

def registered_barangays(request):
    query = request.GET.get("search", "").strip()

    barangays = (
        Barangay.objects
        .annotate(
            preschooler_count=Count("preschooler", distinct=True),
            parent_count=Sum(
                Case(
                    When(account__user_role="Parent", then=1),
                    output_field=IntegerField(),
                )
            ),
            bhw_bns_count=Sum(  # merged column
                Case(
                    When(account__user_role="BHW", then=1),
                    When(account__user_role="Barangay Nutritional Scholar", then=1),
                    output_field=IntegerField(),
                )
            ),
        )
        .order_by("name")
    )

    for b in barangays:
        b.preschooler_count = b.preschooler_count or 0
        b.parent_count = b.parent_count or 0
        b.bhw_bns_count = b.bhw_bns_count or 0

    if query:
        barangays = barangays.filter(
            Q(name__icontains=query) |
            Q(phone_number__icontains=query) |
            Q(hall_address__icontains=query)
        )

    paginator = Paginator(barangays, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "HTML/barangay_list.html", {"barangays": page_obj})


def healthcare_workers(request):
    """Improved healthcare workers view with better BNS handling"""
    from django.utils import timezone
    from django.utils.timesince import timesince
    from django.db.models import Q
    from datetime import timedelta
    
    # Get all barangays for the filter dropdown
    barangays = Barangay.objects.all().order_by('name')
    print("DEBUG: Found {barangays.count()} barangays")
    
    # ===== BHW DATA =====
    bhw_list = Account.objects.filter(
        Q(user_role__iexact='healthworker') | Q(user_role__iexact='BHW'),
        is_validated=True
    ).select_related('barangay')
    
    print("DEBUG: Found {bhw_list.count()} BHW accounts")
    
    for bhw in bhw_list:
        try:
            bhw.bhw_data = BHW.objects.filter(email=bhw.email).first()
        except Exception as e:
            print("Error getting BHW data for {bhw.full_name}: {str(e)}")
            bhw.bhw_data = None
        
        # Activity status
        set_activity_status(bhw)
    
    # ===== BNS DATA - COMPREHENSIVE APPROACH =====
    print("\n=== BNS DEBUGGING - COMPREHENSIVE ===")
    
    # First, let's see what user_role values actually exist
    all_user_roles = Account.objects.filter(
        is_validated=True
    ).values_list('user_role', flat=True).distinct()
    print("All user roles in validated accounts:")
    for role in all_user_roles:
        print("  - '{role}'")
    
    # Try multiple query strategies
    bns_queries = [
        # Strategy 1: Exact matches
        Q(user_role__iexact='bns'),
        Q(user_role__iexact='BNS'),
        Q(user_role__iexact='Barangay Nutritional Scholar'),
        
        # Strategy 2: Contains/partial matches
        Q(user_role__icontains='BNS'),
        Q(user_role__icontains='Nutritional'),
        Q(user_role__icontains='Scholar'),
        
        # Strategy 3: Case-insensitive partial matches
        Q(user_role__icontains='bns'),
        Q(user_role__icontains='nutritional'),
        Q(user_role__icontains='scholar'),
    ]
    
    # Combine all queries with OR
    combined_query = bns_queries[0]
    for query in bns_queries[1:]:
        combined_query |= query
    
    bns_list = Account.objects.filter(
        combined_query,
        is_validated=True
    ).select_related('barangay').distinct()  # Use distinct to avoid duplicates
    
    print("DEBUG: Found {bns_list.count()} BNS accounts with comprehensive query")
    
    # Debug: Show what we found
    for bns in bns_list:
        print("  - {bns.full_name} (role: '{bns.user_role}')")
    
    # If still no results, let's check if there are ANY BNS records in the BNS table
    if bns_list.count() == 0:
        print("\nNo BNS found in Account table. Checking BNS table directly...")
        direct_bns = BNS.objects.all()
        print("Direct BNS table has {direct_bns.count()} records:")
        for bns in direct_bns[:5]:  # Show first 5
            print("  - {bns.full_name} | {bns.email}")
            # Try to find corresponding Account
            account = Account.objects.filter(
                Q(email=bns.email) | Q(full_name__iexact=bns.full_name),
                is_validated=True
            ).first()
            if account:
                print("    -> Found Account: {account.user_role}")
            else:
                print("    -> No matching validated Account found")
    
    # Process BNS data
    for bns in bns_list:
        try:
            # Try multiple ways to find BNS profile
            bns.bns_data = None
            
            # Method 1: By email
            try:
                bns.bns_data = BNS.objects.get(email=bns.email)
                print("Found BNS data by email for {bns.full_name}")
            except BNS.DoesNotExist:
                # Method 2: By name
                try:
                    bns.bns_data = BNS.objects.get(full_name__iexact=bns.full_name)
                    print("Found BNS data by name for {bns.full_name}")
                except BNS.DoesNotExist:
                    # Method 3: Partial name match
                    bns.bns_data = BNS.objects.filter(
                        Q(full_name__icontains=bns.full_name.split()[0]) |  # First name
                        Q(full_name__icontains=bns.full_name.split()[-1])   # Last name
                    ).first()
                    if bns.bns_data:
                        print("Found BNS data by partial name match for {bns.full_name}")
                except BNS.MultipleObjectsReturned:
                    bns.bns_data = BNS.objects.filter(full_name__iexact=bns.full_name).first()
                    print("Multiple BNS found by name for {bns.full_name}, using first")
            except BNS.MultipleObjectsReturned:
                bns.bns_data = BNS.objects.filter(email=bns.email).first()
                print("Multiple BNS found by email for {bns.full_name}, using first")
                
        except Exception as e:
            print("Error processing BNS {bns.full_name}: {str(e)}")
            bns.bns_data = None
        
        # Activity status
        set_activity_status(bns)
    
    # ===== MIDWIFE DATA =====
    midwife_list = Account.objects.filter(
        Q(user_role__iexact='midwife') | Q(user_role__iexact='Midwife'),
        is_validated=True
    ).select_related('barangay')
    
    print("DEBUG: Found {midwife_list.count()} Midwife accounts")
    
    for midwife in midwife_list:
        try:
            midwife.midwife_data = Midwife.objects.filter(email=midwife.email).first()
        except Exception as e:
            print("Error getting Midwife data for {midwife.full_name}: {str(e)}")
            midwife.midwife_data = None
        
        set_activity_status(midwife)
    
    # ===== NURSE DATA =====
    nurse_list = Account.objects.filter(
        Q(user_role__iexact='nurse') | Q(user_role__iexact='Nurse'),
        is_validated=True
    ).select_related('barangay')
    
    print("DEBUG: Found {nurse_list.count()} Nurse accounts")
    
    for nurse in nurse_list:
        try:
            nurse.nurse_data = Nurse.objects.filter(email=nurse.email).first()
        except Exception as e:
            print("Error getting Nurse data for {nurse.full_name}: {str(e)}")
            nurse.nurse_data = None
        
        set_activity_status(nurse)
    
    # ===== FINAL SUMMARY =====
    print("\n=== FINAL SUMMARY ===")
    print("Total BHWs: {bhw_list.count()}")
    print("Total BNS: {bns_list.count()}")  
    print("Total Midwives: {midwife_list.count()}")
    print("Total Nurses: {nurse_list.count()}")
    print("Total Barangays: {barangays.count()}")
    
    context = {
        'barangays': barangays,
        'bhws': bhw_list,
        'bnss': bns_list,
        'midwives': midwife_list,
        'nurses': nurse_list,
    }
    
    return render(request, 'HTML/healthcare_workers.html', context)


def set_activity_status(user):
    """Helper function to set activity status for any user"""
    from django.utils import timezone
    from django.utils.timesince import timesince
    from datetime import timedelta
    
    if hasattr(user, 'last_activity') and user.last_activity:
        if timezone.now() - user.last_activity <= timedelta(minutes=1):
            user.last_activity_display = "🟢 Online"
        else:
            time_diff = timesince(user.last_activity, timezone.now())
            user.last_activity_display = "{time_diff} ago"
    else:
        user.last_activity_display = "No activity"

@csrf_exempt
def get_announcement_data(request, announcement_id):
    """
    API endpoint to get announcement data for editing (AJAX)
    """
    if request.method == 'GET':
        try:
            announcement = get_object_or_404(Announcement, id=announcement_id)
            data = {
                'id': announcement.id,
                'title': announcement.title,
                'content': announcement.content,
                'priority': announcement.priority,
                'is_active': announcement.is_active,
                'image_url': announcement.image.url if announcement.image else None,
            }
            return JsonResponse({'status': 'success', 'data': data})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

def get_latest_weight(request):
    """Return the latest weight data from hardware"""
    try:
        
        latest_weight = 0.0  # Get from your hardware source
        
        return JsonResponse({'weight': latest_weight})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_latest_temp(request):
    """Return the latest temperature data from hardware"""
    try:
        # Replace this with your actual logic to get temperature from hardware/database
        latest_temp = 0.0  # Get from your hardware source
        
        return JsonResponse({'temperature': latest_temp})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_latest_distance(request):
    """Return the latest distance data from hardware"""
    try:
        # Replace this with your actual logic to get distance from hardware/database
        latest_distance = 0.0  # Get from your hardware source
        
        return JsonResponse({'distance': latest_distance})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    







# ✅ API: Change Password on First Login
@api_view(['POST'])
@permission_classes([AllowAny])
def api_change_password_first(request):
    email = request.data.get('email', '').strip()
    new_password = request.data.get('new_password')
    confirm_password = request.data.get('confirm_password')

    if not email or not new_password or not confirm_password:
        return Response({"error": "All fields are required"}, status=status.HTTP_400_BAD_REQUEST)

    if new_password != confirm_password:
        return Response({"error": "Passwords do not match"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # ✅ Update Django User password
        user = User.objects.get(username=email)
        user.set_password(new_password)
        user.save()

        # ✅ Update Account must_change_password flag
        try:
            account = Account.objects.get(email=email, user_role="parent")
            account.must_change_password = False
            account.password = make_password(new_password)  # keep sync
            account.save()
        except Account.DoesNotExist:
            pass

        return Response({"message": "Password updated successfully"}, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
    



@api_view(["GET"])
@permission_classes([AllowAny])
def get_preschoolers(request):
    print("Request reached get_preschoolers:", request.method)
    preschoolers = Preschooler.objects.all()
    serializer = PreschoolerResponseSerializer(preschoolers, many=True)
    return Response(serializer.data)



@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_profile_photo(request):
    account = request.user.account
    if 'image' in request.FILES:
        photo, created = ProfilePhoto.objects.get_or_create(account=account)
        photo.image = request.FILES['image']
        photo.save()
        return Response({"success": True, "image_url": photo.image.url})
    return Response({"success": False, "error": "No image provided"}, status=400)



import traceback
@csrf_exempt
def generate_report(request):
    print("=== GENERATE REPORT DEBUG ===")
    print("User: {request.user}")
    print("Method: {request.method}")
    
    try:
        # Check if WeasyPrint is available
        try:
            from weasyprint import HTML
            print("✓ WeasyPrint imported successfully")
        except ImportError as e:
            print("✗ WeasyPrint import failed: {e}")
            messages.error(request, "WeasyPrint is not installed. Please install it with: pip install weasyprint")
            return redirect('Admindashboard')
        
        # Handle hardcoded admin account
        user = request.user
        account = None
        
        if user.is_authenticated:
            try:
                account = Account.objects.select_related('barangay').get(email=user.email)
                print("✓ Account found from authenticated user: {account.email}")
            except Account.DoesNotExist:
                print("✗ Account not found for authenticated user: {user.email}")
        
        if not account:
            class MockAccount:
                def __init__(self):
                    self.first_name = "Admin"
                    self.last_name = "User"
                    self.email = "admin@ppms.com"
                    self.barangay = None
                
                @property
                def full_name(self):
                    return "{self.first_name} {self.last_name}"
            
            account = MockAccount()
            print("✓ Using hardcoded admin account")

        # Get all barangays and their data
        barangays = Barangay.objects.all()
        print("✓ Found {barangays.count()} barangays")
        
        # Overall summary counters - matching template expectations
        overall_summary = {
            'Severely_Underweight': 0,
            'Underweight': 0,
            'Normal': 0,
            'Overweight': 0,
            'Obese': 0,
        }

        # Barangay detail data for the template
        barangay_details = []
        total_preschoolers = 0
        total_at_risk = 0
        highest_barangay = None
        highest_count = 0
        
        today = date.today()
        
        for brgy in barangays:
            preschoolers = Preschooler.objects.filter(
                barangay=brgy,
                is_archived=False
            ).prefetch_related('bmi_set')

            nutritional_counts = {
                'severely_underweight': 0,
                'underweight': 0,
                'normal': 0,
                'overweight': 0,
                'obese': 0,
            }

            preschoolers_with_bmi = 0
            preschooler_count = preschoolers.count()
            total_preschoolers += preschooler_count

            for p in preschoolers:
                latest_bmi = p.bmi_set.order_by('-date_recorded').first()
                if latest_bmi:
                    try:
                        # Calculate age in months
                        birth_date = p.birth_date
                        age_years = today.year - birth_date.year
                        age_months = today.month - birth_date.month
                        if today.day < birth_date.day:
                            age_months -= 1
                        if age_months < 0:
                            age_years -= 1
                            age_months += 12
                        total_age_months = age_years * 12 + age_months

                        # Calculate BMI and classify
                        bmi_value = calculate_bmi(latest_bmi.weight, latest_bmi.height)
                        z = bmi_zscore(p.sex, total_age_months, bmi_value)
                        category = classify_bmi_for_age(z)

                        preschoolers_with_bmi += 1
                        
                        # Map categories to match template expectations
                        if category == "Severely Wasted":
                            nutritional_counts['severely_underweight'] += 1
                            overall_summary['Severely_Underweight'] += 1
                        elif category == "Wasted":
                            nutritional_counts['underweight'] += 1
                            overall_summary['Underweight'] += 1
                        elif category == "Normal":
                            nutritional_counts['normal'] += 1
                            overall_summary['Normal'] += 1
                        elif category in ["Risk of overweight", "Overweight"]:
                            nutritional_counts['overweight'] += 1
                            overall_summary['Overweight'] += 1
                        elif category == "Obese":
                            nutritional_counts['obese'] += 1
                            overall_summary['Obese'] += 1

                    except Exception as e:
                        print("⚠️ BMI classification error for preschooler {p.id}: {e}")

            # Calculate at-risk percentage (severely underweight + underweight + obese)
            at_risk_count = (nutritional_counts['severely_underweight'] + 
                           nutritional_counts['underweight'] + 
                           nutritional_counts['obese'])
            at_risk_percentage = round((at_risk_count / preschooler_count * 100), 1) if preschooler_count > 0 else 0
            total_at_risk += at_risk_count

            # Track highest count barangay
            if preschooler_count > highest_count:
                highest_count = preschooler_count
                highest_barangay = brgy

            barangay_details.append({
                'name': brgy.name,
                'total_preschoolers': preschooler_count,
                'severely_underweight': nutritional_counts['severely_underweight'],
                'underweight': nutritional_counts['underweight'],
                'normal': nutritional_counts['normal'],
                'overweight': nutritional_counts['overweight'],
                'obese': nutritional_counts['obese'],
                'at_risk_percentage': at_risk_percentage,
            })

        print("✓ Processed {len(barangay_details)} barangays")
        print("✓ Overall summary: {overall_summary}")

        # Total barangays count
        total_barangays = barangays.count()

        # Context for template - matching reportTemplate.html expectations
        context = {
            'account': account,
            'report_date': date.today().strftime('%B %d, %Y'),
            'total_preschoolers': total_preschoolers,
            'total_barangays': total_barangays,
            'total_at_risk': total_at_risk,
            'highest_barangay': highest_barangay,
            'barangay_details': barangay_details,
            'overall_summary': overall_summary,
        }

        print("✓ Context prepared")

        # Use the new comprehensive template
        template_path = 'HTML/reportTemplate.html'  # Updated to use your new template
        try:
            html_string = render_to_string(template_path, context)
            print("✓ Template rendered successfully, length: {len(html_string)}")
        except Exception as e:
            print("✗ Template rendering failed: {e}")
            # Fall back to the admin comprehensive report
            template_path = 'HTML/admin_comprehensive_report.html'
            try:
                html_string = render_to_string(template_path, context)
                print("✓ Fallback template rendered, length: {len(html_string)}")
            except Exception as e2:
                print("✗ Fallback template also failed: {e2}")
                messages.error(request, "Template rendering failed: {e}")
                return redirect('Admindashboard')
        
        # Generate PDF with better error handling
        try:
            print("→ Starting PDF generation...")
            html = HTML(string=html_string, base_url=request.build_absolute_uri())
            print("→ HTML object created")
            
            # Add CSS for better PDF rendering
            pdf = html.write_pdf(stylesheets=[])
            print("✓ PDF generated successfully, size: {len(pdf)} bytes")
        except Exception as e:
            print("✗ PDF generation failed: {e}")
            print("Error type: {type(e)}")
            print("Traceback: {traceback.format_exc()}")
            
            # Try to provide more specific error info
            if "font" in str(e).lower():
                messages.error(request, "PDF generation failed due to font issues. Please check server fonts.")
            elif "css" in str(e).lower():
                messages.error(request, "PDF generation failed due to CSS issues.")
            else:
                messages.error(request, "PDF generation failed: {e}")
            return redirect('Admindashboard')

        # Create response
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = "PPMS-Cluster4-Overall-Barangay-Report-{date.today().strftime('%Y%m%d')}.pd"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        print("✓ Response created with filename: {filename}")
        print("=== DEBUG COMPLETE ===")
        return response

    except Exception as e:
        print("✗ Unexpected error: {str(e)}")
        print("Traceback: {traceback.format_exc()}")
        logger.error("Error generating report: {str(e)}")
        messages.error(request, "Error generating report: {str(e)}")
        return redirect('Admindashboard')
    
from openpyxl import Workbook
from io import BytesIO
from openpyxl.utils import get_column_letter

@login_required
def generate_nutrition_excel(request):
    """Generate Excel file with nutrition report data - Direct download with barangay filtering"""
    month = request.GET.get("month")
    
    # Get user's barangay using consistent logic
    user_barangay = get_user_barangay(request.user)
    current_user_info = None
    
    print("DEBUG: Nutrition Excel - Current user email: {request.user.email}")
    
    if request.user.is_authenticated:
        # Try each model to find the user
        try:
            # Try Account model first
            account = Account.objects.select_related('barangay').get(email=request.user.email)
            current_user_info = {
                'model': 'Account',
                'name': account.full_name,
                'role': account.user_role,
                'object': account
            }
            print("DEBUG: Found in Account: {account.email}, Barangay: {user_barangay}")
        except Account.DoesNotExist:
            try:
                # Try BHW model
                bhw = BHW.objects.select_related('barangay').get(email=request.user.email)
                current_user_info = {
                    'model': 'BHW',
                    'name': bhw.full_name,
                    'role': 'BHW',
                    'object': bhw
                }
                print("DEBUG: Found in BHW: {bhw.email}, Barangay: {user_barangay}")
            except BHW.DoesNotExist:
                try:
                    # Try BNS model
                    bns = BNS.objects.select_related('barangay').get(email=request.user.email)
                    current_user_info = {
                        'model': 'BNS',
                        'name': bns.full_name,
                        'role': 'BNS',
                        'object': bns
                    }
                    print("DEBUG: Found in BNS: {bns.email}, Barangay: {user_barangay}")
                except BNS.DoesNotExist:
                    try:
                        # Try Midwife model
                        midwife = Midwife.objects.select_related('barangay').get(email=request.user.email)
                        current_user_info = {
                            'model': 'Midwife',
                            'name': midwife.full_name,
                            'role': 'Midwife',
                            'object': midwife
                        }
                        print("DEBUG: Found in Midwife: {midwife.email}, Barangay: {user_barangay}")
                    except Midwife.DoesNotExist:
                        try:
                            # Try Nurse model
                            nurse = Nurse.objects.select_related('barangay').get(email=request.user.email)
                            current_user_info = {
                                'model': 'Nurse',
                                'name': nurse.full_name,
                                'role': 'Nurse',
                                'object': nurse
                            }
                            print("DEBUG: Found in Nurse: {nurse.email}, Barangay: {user_barangay}")
                        except Nurse.DoesNotExist:
                            try:
                                # Try Parent model
                                parent = Parent.objects.select_related('barangay').get(email=request.user.email)
                                current_user_info = {
                                    'model': 'Parent',
                                    'name': parent.full_name,
                                    'role': 'Parent',
                                    'object': parent
                                }
                                print("DEBUG: Found in Parent: {parent.email}, Barangay: {user_barangay}")
                            except Parent.DoesNotExist:
                                print("DEBUG: User not found in any model")

    # Validate user and barangay
    if not current_user_info or not user_barangay:
        # Return error response or redirect
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Access denied: No barangay assigned to your account or user not found.")

    print("DEBUG: Excel generation authorized for {current_user_info['role']} in {user_barangay}")
    
    # Parse month if provided
    selected_month = None
    selected_year = None
    month_name = "All Time"
    
    if month:
        try:
            selected_year, selected_month = map(int, month.split('-'))
            month_name = "{calendar.month_name[selected_month]} {selected_year}"
        except (ValueError, IndexError):
            month = None
    
    # Filter preschoolers ONLY from user's barangay
    preschoolers_query = Preschooler.objects.filter(
        is_archived=False,
        barangay=user_barangay  # Only preschoolers from user's barangay
    )
    
    print("DEBUG: Base query found {preschoolers_query.count()} preschoolers in {user_barangay}")
    
    if month and selected_month and selected_year:
        preschoolers_query = preschoolers_query.filter(
            bmi__date_recorded__year=selected_year,
            bmi__date_recorded__month=selected_month
        ).distinct()
        print("DEBUG: After month filter: {preschoolers_query.count()} preschoolers")
    
    # Use correct relationship with barangay filtering
    preschoolers = preschoolers_query.prefetch_related('bmi_set').select_related('parent_id', 'barangay')
    
    # Create workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Nutrition Report"
    
    # Define styles
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="007b9e", end_color="007b9e", fill_type="solid")
    center_alignment = Alignment(horizontal="center", vertical="center")
    border = Border(
        left=Side(border_style="thin"),
        right=Side(border_style="thin"),
        top=Side(border_style="thin"),
        bottom=Side(border_style="thin")
    )
    
    # Add title with barangay information
    ws.merge_cells('A1:J1')
    title_cell = ws['A1']
    title_cell.value = "Nutrition Report - {user_barangay.name} - {month_name}"
    title_cell.font = Font(bold=True, size=16)
    title_cell.alignment = center_alignment
    
    # Add generation info with user details
    ws.merge_cells('A2:J2')
    info_cell = ws['A2']
    info_cell.value = "Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')} by {current_user_info['name']} ({current_user_info['role']})"
    info_cell.font = Font(italic=True)
    info_cell.alignment = center_alignment
    
    # Add barangay info
    ws.merge_cells('A3:J3')
    barangay_cell = ws['A3']
    barangay_cell.value = "Barangay: {user_barangay.name}"
    barangay_cell.font = Font(bold=True)
    barangay_cell.alignment = center_alignment
    
    # Add headers (row 5, shifted down due to barangay info)
    headers = [
        "Child Seq.",
        "Address or Location of Child's Residence\nPurok, Block#, Area or Location in the Barangay",
        "Name of Mother or Caregiver\n(Surname, First Name)",
        "Full Name of Child\n(Surname, First Name)",
        "Belongs to IP Group?\nYES/NO",
        "Sex\nM/F",
        "Date of Birth",
        "Date Measured",
        "Weight\n(kg)",
        "Height\n(cm)"
    ]
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=5, column=col)
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_alignment
        cell.border = border
    
    # Add data
    row_num = 6
    processed_count = 0
    
    for preschooler in preschoolers:
        # Double-check barangay (security measure)
        if preschooler.barangay != user_barangay:
            print("DEBUG: Skipping preschooler {preschooler.first_name} {preschooler.last_name} - wrong barangay")
            continue
            
        bmi_query = preschooler.bmi_set.all()
        
        if month and selected_month and selected_year:
            bmi_query = bmi_query.filter(
                date_recorded__year=selected_year,
                date_recorded__month=selected_month
            )
        
        latest_bmi = bmi_query.order_by('-date_recorded').first()
        
        if not latest_bmi:
            continue
            
        if not all([latest_bmi.weight, latest_bmi.height, latest_bmi.date_recorded]):
            continue
        
        try:
            # Handle parent relationship using ForeignKey
            if preschooler.parent_id:
                parent = preschooler.parent_id
                # Verify parent is also in same barangay
                if parent.barangay != user_barangay:
                    print("DEBUG: Skipping preschooler {preschooler.first_name} {preschooler.last_name} - parent in different barangay")
                    continue
                    
                if hasattr(parent, 'mother_name') and parent.mother_name:
                    mother_name = parent.mother_name
                elif hasattr(parent, 'full_name') and parent.full_name:
                    mother_name = parent.full_name
                else:
                    mother_name = 'N/A'
            else:
                mother_name = 'N/A'
            
            data = [
                processed_count + 1,  # Child sequence number
                preschooler.address or "{user_barangay.name}",  # Include barangay in address
                mother_name,
                "{preschooler.last_name}, {preschooler.first_name}",
                'NO',  # IP Group
                preschooler.sex,
                preschooler.birth_date.strftime('%b-%d-%Y') if preschooler.birth_date else 'N/A',
                latest_bmi.date_recorded.strftime('%b-%d-%Y'),
                latest_bmi.weight,
                latest_bmi.height
            ]
            
            for col, value in enumerate(data, 1):
                cell = ws.cell(row=row_num, column=col)
                cell.value = value
                cell.alignment = center_alignment
                cell.border = border
                
                # Alternate row coloring
                if row_num % 2 == 0:
                    cell.fill = PatternFill(start_color="f9f9f9", end_color="f9f9f9", fill_type="solid")
            
            row_num += 1
            processed_count += 1
            
        except Exception as e:
            print("Error processing preschooler {preschooler.preschooler_id} for Excel: {e}")
            continue
    
    print("DEBUG: Processed {processed_count} preschoolers for Excel export")
    
    # Add empty rows to match template (up to row 482)
    for empty_row in range(row_num, 487):  # Adjusted for shifted rows
        for col in range(1, 11):
            cell = ws.cell(row=empty_row, column=col)
            cell.value = processed_count + (empty_row - row_num) + 1 if col == 1 else ""  # Only sequence number
            cell.alignment = center_alignment
            cell.border = border
            if empty_row % 2 == 0:
                cell.fill = PatternFill(start_color="f9f9f9", end_color="f9f9f9", fill_type="solid")
    
    # Auto-adjust column widths
    column_widths = [10, 25, 25, 25, 15, 8, 15, 15, 10, 10]
    for col, width in enumerate(column_widths, 1):
        col_letter = get_column_letter(col)
        ws.column_dimensions[col_letter].width = width
    
    # Set row heights (adjusted for shifted rows)
    for row in range(5, 487):
        ws.row_dimensions[row].height = 20
    
    # Save workbook to buffer
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    # Create HTTP response with barangay in filename
    filename = "Nutrition-Report-{user_barangay.name}-{month_name.replace(' ', '-')}.xlsx"
    response = HttpResponse(
        output,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    
    print("DEBUG: Generated Excel file: {filename} with {processed_count} preschoolers")
    return response



from .models import FCMToken

@csrf_exempt
def save_fcm_token(request):
    """Enhanced FCM token saving with nutrition service support"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        # Get data from POST or JSON
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            email = data.get('email')
            fcm_token = data.get('token')
            source = data.get('source', 'unknown')
            supports_nutrition = data.get('supports_nutrition_notifications', True)
        else:
            email = request.POST.get('email')
            fcm_token = request.POST.get('token')
            source = request.POST.get('source', 'form')
            supports_nutrition = True

        logger.info("🔥 Attempting to save FCM token for nutrition services")
        logger.info("📧 Email: {email}")
        logger.info("🔑 FCM Token: {fcm_token[:20] if fcm_token else 'None'}...")
        logger.info("🍎 Source: {source}, Supports Nutrition: {supports_nutrition}")

        if not email or not fcm_token:
            logger.warning("❌ Missing email or FCM token")
            return JsonResponse({'success': False, 'error': 'Email and token required'})

        # Find and update account
        try:
            from .models import Account, FCMToken  # Adjust import path as needed
            
            account = Account.objects.get(email=email)
            logger.info("✅ Found account: {account.email}")
            
            # Update account FCM token
            old_token = account.fcm_token
            account.fcm_token = fcm_token
            account.save(update_fields=['fcm_token'])
            logger.info("🔄 Updated token from {old_token[:20] if old_token else 'None'}... to {fcm_token[:20]}...")

            # Also create/update FCMToken record if you have this model
            try:
                fcm_token_obj, created = FCMToken.objects.update_or_create(
                    account=account,
                    defaults={
                        'token': fcm_token,
                        'device_type': 'android',
                        'is_active': True,
                        'updated_at': timezone.now(),
                        'supports_nutrition_notifications': supports_nutrition,
                        'registration_source': source
                    }
                )
                logger.info("✅ FCMToken record {'created' if created else 'updated'}")
            except Exception as fcm_model_error:
                logger.warning("⚠️ FCMToken model update failed (this may be OK): {fcm_model_error}")

            logger.info("✅ FCM token saved successfully for {email}")
            
            # Send test notification specifically for nutrition services
            test_result = PushNotificationService.send_push_notification(
                token=fcm_token,
                title="🍎 Nutrition Services Notifications Enabled",
                body="Your device is now registered for nutrition service notifications!",
                data={
                    "type": "registration_success",
                    "email": email,
                    "supports_nutrition": str(supports_nutrition),
                    "timestamp": str(timezone.now())
                }
            )
            
            return JsonResponse({
                'success': True, 
                'message': f'FCM token saved for {email} - Nutrition notifications enabled',
                'email': email,
                'token_preview': "{fcm_token[:20]}...",
                'supports_nutrition': supports_nutrition,
                'test_notification': test_result
            })

        except Account.DoesNotExist:
            logger.error("❌ Account not found: {email}")
            return JsonResponse({'success': False, 'error': f'Account not found for {email}'})

    except json.JSONDecodeError as e:
        logger.error("❌ JSON decode error: {e}")
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception as e:
        logger.error("❌ FCM save error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@require_POST
def register_fcm_token(request):
    """Enhanced FCM token registration with nutrition service support"""
    try:
        data = json.loads(request.body)
        token = data.get('token')
        device_type = data.get('device_type', 'android')
        supports_nutrition = data.get('supports_nutrition_notifications', True)
        source = data.get('source', 'app_startup')

        logger.info("🔥 Enhanced FCM token registration attempt")
        logger.info("🔑 Token: {token[:20] if token else 'None'}...")
        logger.info("📱 Device: {device_type}")
        logger.info("🍎 Supports Nutrition: {supports_nutrition}")
        logger.info("📍 Source: {source}")

        if not token:
            return JsonResponse({'success': False, 'message': 'FCM token required'})

        # Store token temporarily for later association
        # This is useful when the token arrives before login
        try:
            from .models import FCMToken
            
            # Check if token already exists
            existing_token = FCMToken.objects.filter(token=token).first()
            if existing_token:
                existing_token.device_type = device_type
                existing_token.supports_nutrition_notifications = supports_nutrition
                existing_token.registration_source = source
                existing_token.updated_at = timezone.now()
                existing_token.is_active = True
                existing_token.save()
                logger.info("✅ Updated existing FCM token record")
            else:
                # Create temporary token record without account association
                FCMToken.objects.create(
                    token=token,
                    device_type=device_type,
                    supports_nutrition_notifications=supports_nutrition,
                    registration_source=source,
                    is_active=True,
                    created_at=timezone.now(),
                    updated_at=timezone.now()
                    # account will be null until login
                )
                logger.info("✅ Created temporary FCM token record")
                
        except Exception as model_error:
            logger.warning("⚠️ Could not create FCMToken model (this may be OK): {model_error}")
        
        logger.info("✅ FCM token received and processed: {token[:20]}...")
        
        return JsonResponse({
            'success': True, 
            'message': 'FCM token registered successfully for nutrition services',
            'token_preview': "{token[:20]}...",
            'supports_nutrition': supports_nutrition,
            'device_type': device_type
        })
        
    except Exception as e:
        logger.error("❌ FCM token registration error: {e}")
        return JsonResponse({'success': False, 'message': str(e)})
    
import requests

@login_required
def check_notification_status(request):
    """Debug endpoint to check notification configuration and status"""
    try:
        from .models import Preschooler, Account, Parent
        from django.conf import settings
        import os
        
        # Check FCM configuration
        fcm_configured = False
        try:
            firebase_key_path = getattr(settings, 'FIREBASE_KEY_PATH', None)
            if firebase_key_path and os.path.exists(firebase_key_path):
                fcm_configured = True
        except:
            pass
        
        # Check email configuration
        email_configured = bool(
            getattr(settings, 'EMAIL_HOST', None) and 
            getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        )
        
        # Count parents and tokens
        total_parents = Parent.objects.count()
        parents_with_tokens = Account.objects.filter(
            fcm_token__isnull=False
        ).exclude(fcm_token='').count()
        
        # Sample FCM tokens (first 20 chars for security)
        sample_tokens = list(Account.objects.filter(
            fcm_token__isnull=False
        ).exclude(fcm_token='').values_list('email', 'fcm_token')[:5])
        
        sample_tokens_safe = [
            {
                'email': token[0], 
                'token_preview': token[1][:20] + '...' if token[1] else 'None'
            } 
            for token in sample_tokens
        ]
        
        return JsonResponse({
            'success': True,
            'fcm_configured': fcm_configured,
            'email_configured': email_configured,
            'total_parents': total_parents,
            'parents_with_tokens': parents_with_tokens,
            'sample_tokens': sample_tokens_safe,
            'firebase_key_exists': os.path.exists(getattr(settings, 'FIREBASE_KEY_PATH', '')) if getattr(settings, 'FIREBASE_KEY_PATH', None) else False
        })
        
    except Exception as e:
        logger.error("Error checking notification status: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })



@login_required
@require_POST
def test_push_notification(request):
    """Test endpoint to send a push notification to verify setup"""
    try:
        from .models import Account
        from .services import PushNotificationService  # Adjust import path
        
        # Get email from request
        email = request.POST.get('email') or request.user.email
        
        if not email:
            return JsonResponse({
                'success': False, 
                'error': 'Email required'
            })
        
        # Find account with FCM token
        account = Account.objects.filter(email=email, fcm_token__isnull=False).exclude(fcm_token='').first()
        
        if not account:
            return JsonResponse({
                'success': False, 
                'error': f'No FCM token found for {email}'
            })
        
        logger.info("🧪 Testing push notification for {email}")
        logger.info("🔑 Using FCM token: {account.fcm_token[:20]}...")
        
        # Send test notification
        result = PushNotificationService.send_push_notification(
            token=account.fcm_token,
            title="🧪 Test Notification",
            body="This is a test push notification from PPMS system. If you receive this, notifications are working!",
            data={
                "type": "test_notification",
                "timestamp": str(timezone.now()),
                "test": "true"
            }
        )
        
        logger.info("🧪 Test notification result: {result}")
        
        return JsonResponse({
            'success': result.get('success', False),
            'message': 'Test notification sent!' if result.get('success') else 'Test notification failed',
            'result': result,
            'email': email,
            'token_preview': account.fcm_token[:20] + '...'
        })
        
    except Exception as e:
        logger.error("❌ Test notification error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

def get_pending_validation_count(request):
    count = Account.objects.filter(
        is_validated=False
    ).exclude(user_role="Parent").count()
    return JsonResponse({'pending_count': count})


@csrf_protect
@login_required
@require_http_methods(["POST"])
def save_temperature(request):
    try:
        preschooler_id = request.POST.get('preschooler_id')
        temperature_value = request.POST.get('temperature_value')
        
        if not preschooler_id or not temperature_value:
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required fields'
            })
        
        # Convert and validate temperature
        try:
            temp_float = float(temperature_value)
            if temp_float < 30 or temp_float > 45:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Temperature must be between 30°C and 45°C'
                })
        except (ValueError, TypeError):
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid temperature value'
            })
        
        # Get the preschooler
        try:
            preschooler = Preschooler.objects.get(preschooler_id=preschooler_id, is_archived=False)
        except Preschooler.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Preschooler not found'
            })
        
        # Get BHW record - adjust this based on your actual model relationships
        bhw = None
        try:
            # Option 1: If BHW model has a direct user field
            if hasattr(BHW, 'user'):
                bhw = BHW.objects.get(user=request.user)
            
            # Option 2: If you need to find BHW by username or other field
            # elif hasattr(BHW, 'username'):
            #     bhw = BHW.objects.get(username=request.user.username)
            
            # Option 3: If BHW has an email field
            # elif hasattr(BHW, 'email'):
            #     bhw = BHW.objects.get(email=request.user.email)
            
            # Option 4: If you need to find by a custom field
            # else:
            #     bhw = BHW.objects.filter(/* your custom condition */).first()
                
        except BHW.DoesNotExist:
            # Create temperature record without BHW if not found
            pass
        except Exception as e:
            print("Error finding BHW: {e}")
        
        # Create temperature record
        temperature_record = Temperature.objects.create(
            preschooler_id=preschooler,
            temperature_value=temp_float,
            recorded_by=bhw  # This can be None if BHW not found
        )
        
        return JsonResponse({
            'status': 'success',
            'message': f'Temperature {temp_float}°C recorded successfully',
            'temperature_id': temperature_record.temperature_id,
            'date_recorded': temperature_record.date_recorded.strftime('%Y-%m-%d')
        })
        
    except Exception as e:
        print("Temperature save error: {e}")  # For debugging
        return JsonResponse({
            'status': 'error',
            'message': 'An unexpected error occurred while saving temperature'
        })




