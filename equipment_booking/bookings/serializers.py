from rest_framework import serializers
from .models import User, Equipment, EquipmentType, Booking, Notification
from django.utils import timezone
from datetime import timedelta
import calendar

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'department', 'phone']
        read_only_fields = ['id', 'role']

class EquipmentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentType
        fields = '__all__'

class EquipmentSerializer(serializers.ModelSerializer):
    type = EquipmentTypeSerializer(read_only=True)
    type_id = serializers.PrimaryKeyRelatedField(
        queryset=EquipmentType.objects.all(), 
        source='type', 
        write_only=True
    )
    
    class Meta:
        model = Equipment
        fields = '__all__'
    
    def get_availability(self, obj):
        request = self.context.get('request')
        if request and request.query_params.get('availability'):
            start_date_str = request.query_params.get('start_date')
            end_date_str = request.query_params.get('end_date')
            
            if start_date_str and end_date_str:
                try:
                    start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
                    return obj.get_availability(start_date, end_date)
                except ValueError:
                    pass
        return None

class BookingSerializer(serializers.ModelSerializer):
    employee = UserSerializer(read_only=True)
    manager = UserSerializer(read_only=True)
    equipment = EquipmentSerializer(read_only=True)
    
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='EMPLOYEE'),
        source='employee',
        write_only=True,
        required=False
    )
    equipment_id = serializers.PrimaryKeyRelatedField(
        queryset=Equipment.objects.filter(is_active=True),
        source='equipment',
        write_only=True
    )
    manager_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='MANAGER'),
        source='manager',
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields = ['status', 'created_at', 'updated_at', 'recurrence_id']
    
    def validate(self, data):
        
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("End time must be after start time")
        
        if data['start_time'] < timezone.now():
            raise serializers.ValidationError("Cannot book equipment in the past")
        
        
        recurrence = data.get('recurrence', 'NONE')
        recurrence_end = data.get('recurrence_end')
        
        if recurrence != 'NONE' and not recurrence_end:
            raise serializers.ValidationError("Recurrence end date is required for recurring bookings")
        
        if recurrence_end and recurrence_end < data['start_time']:
            raise serializers.ValidationError("Recurrence end date must be after the booking start time")
        
       
        equipment = data['equipment']
        start_time = data['start_time']
        end_time = data['end_time']
        
        
        current_booking = self.instance.id if self.instance else None
        
        
        if recurrence != 'NONE':
            return self._validate_recurring_availability(equipment, start_time, end_time, recurrence, recurrence_end, current_booking)
        else:
            return self._validate_single_booking_availability(equipment, start_time, end_time, current_booking)
    
    def _validate_single_booking_availability(self, equipment, start_time, end_time, current_booking=None):
        overlapping_bookings = Booking.objects.filter(
            equipment=equipment,
            start_time__lt=end_time,
            end_time__gt=start_time,
            status__in=['PENDING', 'APPROVED']
        ).exclude(id=current_booking).count()
        
        if overlapping_bookings >= equipment.quantity:
            raise serializers.ValidationError("Equipment not available for the selected time slot")
        
        return {'equipment': equipment, 'start_time': start_time, 'end_time': end_time}
    
    def _validate_recurring_availability(self, equipment, start_time, end_time, recurrence, recurrence_end, current_booking=None):
        current_time = start_time
        delta = None
        conflict_dates = []
        
        if recurrence == 'DAILY':
            delta = timedelta(days=1)
        elif recurrence == 'WEEKLY':
            delta = timedelta(weeks=1)
        
        while current_time < recurrence_end:
            if recurrence == 'MONTHLY':
               
                try:
                    current_time = current_time.replace(month=current_time.month + 1)
                except ValueError:
                    
                    next_month = current_time.month + 1
                    if next_month > 12:
                        next_month = 1
                        year = current_time.year + 1
                    else:
                        year = current_time.year
                    last_day = (timezone.datetime(year, next_month + 1, 1) - timedelta(days=1)).day
                    current_time = current_time.replace(day=last_day, month=next_month, year=year)
            else:
                current_time += delta
            
            if current_time >= recurrence_end:
                break
                
            occurrence_end = current_time + (end_time - start_time)
            
            overlapping_bookings = Booking.objects.filter(
                equipment=equipment,
                start_time__lt=occurrence_end,
                end_time__gt=current_time,
                status__in=['PENDING', 'APPROVED']
            ).exclude(id=current_booking).count()
            
            if overlapping_bookings >= equipment.quantity:
                conflict_dates.append(current_time.date())
        
        if conflict_dates:
            raise serializers.ValidationError(
                f"Equipment not available on these dates: {', '.join(str(d) for d in conflict_dates)}"
            )
        
        return {
            'equipment': equipment,
            'start_time': start_time,
            'end_time': end_time,
            'recurrence': recurrence,
            'recurrence_end': recurrence_end
        }
    
    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user:
           
            if request.user.is_employee():
                validated_data['employee'] = request.user
            elif request.user.is_manager() and 'employee' not in validated_data:
                raise serializers.ValidationError("Managers must specify an employee for the booking")
            
            
            if request.user.is_manager():
                validated_data['manager'] = request.user
        
        
        return super().create(validated_data)

class NotificationSerializer(serializers.ModelSerializer):
    related_booking = BookingSerializer(read_only=True)
    
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ['user', 'is_read', 'created_at']