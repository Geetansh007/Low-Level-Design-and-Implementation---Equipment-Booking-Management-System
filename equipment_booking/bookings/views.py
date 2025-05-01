from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from .models import User, Equipment, EquipmentType, Booking, Notification
from .serializers import (
    UserSerializer, EquipmentSerializer, EquipmentTypeSerializer, 
    BookingSerializer, NotificationSerializer
)
from .permissions import (
    IsAdmin, IsManager, IsEmployee, 
    IsManagerOrAdmin, IsOwnerOrManagerOrAdmin
)
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta, datetime
import calendar

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]

class EquipmentTypeViewSet(viewsets.ModelViewSet):
    queryset = EquipmentType.objects.all()
    serializer_class = EquipmentTypeSerializer
    permission_classes = [IsAdmin]

class EquipmentViewSet(viewsets.ModelViewSet):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['type', 'location', 'is_active']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = []
        return [permission() for permission in permission_classes]
    
    @action(detail=True, methods=['post'])
    def set_unavailable(self, request, pk=None):
        equipment = self.get_object()
        equipment.is_active = False
        equipment.save()
        return Response({'status': 'equipment set as unavailable'})
    
    @action(detail=True, methods=['post'])
    def set_available(self, request, pk=None):
        equipment = self.get_object()
        equipment.is_active = True
        equipment.save()
        return Response({'status': 'equipment set as available'})
    
    @action(detail=False, methods=['get'])
    def availability(self, request):
        equipment_id = request.query_params.get('equipment_id')
        period = request.query_params.get('period', 'day')  # day/week/month
        date_str = request.query_params.get('date')
        
        if not equipment_id or not date_str:
            return Response(
                {'error': 'equipment_id and date parameters are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            equipment = Equipment.objects.get(pk=equipment_id)
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except Equipment.DoesNotExist:
            return Response(
                {'error': 'Equipment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        availability_data = []
        
        if period == 'day':
            start_time = timezone.make_aware(datetime.combine(date, datetime.min.time()))
            end_time = start_time + timedelta(days=1)
            
            # Check availability for each hour
            for hour in range(0, 24):
                slot_start = start_time + timedelta(hours=hour)
                slot_end = slot_start + timedelta(hours=1)
                available = equipment.available_quantity(slot_start, slot_end) > 0
                availability_data.append({
                    'time': slot_start.time().strftime('%H:%M'),
                    'available': available
                })
                
        elif period == 'week':
            start_date = date - timedelta(days=date.weekday())
            for day in range(0, 7):
                current_date = start_date + timedelta(days=day)
                start_time = timezone.make_aware(datetime.combine(current_date, datetime.min.time()))
                end_time = start_time + timedelta(days=1)
                
                # Get all bookings for this day
                bookings = Booking.objects.filter(
                    equipment=equipment,
                    start_time__lt=end_time,
                    end_time__gt=start_time,
                    status__in=['PENDING', 'APPROVED']
                )
                
                availability_data.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'day': current_date.strftime('%A'),
                    'booked_hours': bookings.count(),
                    'available': equipment.quantity > bookings.count()
                })
                
        elif period == 'month':
            year = date.year
            month = date.month
            days_in_month = calendar.monthrange(year, month)[1]
            
            for day in range(1, days_in_month + 1):
                current_date = datetime(year, month, day).date()
                start_time = timezone.make_aware(datetime.combine(current_date, datetime.min.time()))
                end_time = start_time + timedelta(days=1)
                
                bookings = Booking.objects.filter(
                    equipment=equipment,
                    start_time__lt=end_time,
                    end_time__gt=start_time,
                    status__in=['PENDING', 'APPROVED']
                )
                
                availability_data.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'booked': bookings.exists(),
                    'available': equipment.quantity > bookings.count()
                })
        
        return Response({
            'equipment': EquipmentSerializer(equipment).data,
            'period': period,
            'date': date_str,
            'availability': availability_data
        })

class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'equipment', 'status', 'start_time', 'end_time', 'recurrence']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'cancel_series']:
            permission_classes = [IsOwnerOrManagerOrAdmin]
        else:
            permission_classes = []
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_admin():
            return Booking.objects.all()
        elif user.is_manager():
            return Booking.objects.filter(Q(manager=user) | Q(employee__department=user.department))
        else:
            return Booking.objects.filter(employee=user)
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        recurrence = serializer.validated_data.get('recurrence', 'NONE')
        recurrence_end = serializer.validated_data.get('recurrence_end')
        
        if recurrence != 'NONE' and not recurrence_end:
            return Response(
                {'error': 'recurrence_end is required for recurring bookings'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create the first booking
        booking = serializer.save()
        
        if recurrence != 'NONE':
            # Generate a unique ID for this series of recurring bookings
            recurrence_id = f"rec_{booking.id}_{timezone.now().timestamp()}"
            booking.recurrence_id = recurrence_id
            booking.save()
            
            # Create the recurring bookings
            self._create_recurring_bookings(booking, recurrence, recurrence_end)
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def _create_recurring_bookings(self, original_booking, recurrence, recurrence_end):
        current_time = original_booking.start_time
        delta = None
        
        if recurrence == 'DAILY':
            delta = timedelta(days=1)
        elif recurrence == 'WEEKLY':
            delta = timedelta(weeks=1)
        elif recurrence == 'MONTHLY':
            # For monthly, we'll add 1 month to the date
            delta = None  # Handle specially
        
        while current_time < recurrence_end:
            if recurrence == 'MONTHLY':
                # Handle month increments (accounting for different month lengths)
                try:
                    current_time = current_time.replace(month=current_time.month + 1)
                except ValueError:
                    # If next month doesn't have enough days (e.g., Jan 31 -> Feb)
                    # Move to last day of next month
                    next_month = current_time.month + 1
                    if next_month > 12:
                        next_month = 1
                        year = current_time.year + 1
                    else:
                        year = current_time.year
                    last_day = (datetime(year, next_month + 1, 1) - timedelta(days=1)).day
                    current_time = current_time.replace(day=last_day, month=next_month, year=year)
            else:
                current_time += delta
            
            if current_time >= recurrence_end:
                break
                
            # Create a new booking for this occurrence
            booking_data = {
                'employee': original_booking.employee.id,
                'manager': original_booking.manager.id if original_booking.manager else None,
                'equipment': original_booking.equipment.id,
                'start_time': current_time,
                'end_time': current_time + (original_booking.end_time - original_booking.start_time),
                'status': original_booking.status,
                'purpose': original_booking.purpose,
                'recurrence': original_booking.recurrence,
                'recurrence_end': original_booking.recurrence_end,
                'recurrence_id': original_booking.recurrence_id
            }
            
            serializer = self.get_serializer(data=booking_data)
            if serializer.is_valid():
                serializer.save()
            else:
                # Log error but continue with other occurrences
                print(f"Failed to create recurring booking: {serializer.errors}")
    
    @action(detail=False, methods=['get'])
    def available_equipment(self, request):
        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')
        
        if not start_time or not end_time:
            return Response(
                {'error': 'Both start_time and end_time parameters are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            start_time = timezone.datetime.fromisoformat(start_time)
            end_time = timezone.datetime.fromisoformat(end_time)
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if start_time >= end_time:
            return Response(
                {'error': 'End time must be after start time'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get all equipment
        all_equipment = Equipment.objects.filter(is_active=True)
        available_equipment = []
        
        for equipment in all_equipment:
            if equipment.available_quantity(start_time, end_time) > 0:
                available_equipment.append(equipment)
        
        serializer = EquipmentSerializer(available_equipment, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if booking.employee != request.user and not (request.user.is_manager() or request.user.is_admin()):
            return Response(
                {'error': 'You do not have permission to cancel this booking'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        booking.status = 'CANCELLED'
        booking.save()
        return Response({'status': 'booking cancelled'})
    
    @action(detail=True, methods=['post'])
    def cancel_series(self, request, pk=None):
        booking = self.get_object()
        if not booking.recurrence_id:
            return Response(
                {'error': 'This booking is not part of a recurring series'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if booking.employee != request.user and not (request.user.is_manager() or request.user.is_admin()):
            return Response(
                {'error': 'You do not have permission to cancel this booking series'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Cancel all bookings in this series
        Booking.objects.filter(recurrence_id=booking.recurrence_id).update(status='CANCELLED')
        
        return Response({'status': 'recurring booking series cancelled'})

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    queryset = Notification.objects.all()
    
    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'status': 'notification marked as read'})
    
    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'status': 'all notifications marked as read'})

class ReportViewSet(viewsets.ViewSet):
    permission_classes = [IsAdmin]
    
    def list(self, request):
        # Most booked equipment
        most_booked = Equipment.objects.annotate(
            booking_count=Count('booking')
        ).order_by('-booking_count')[:5]
        
        # Usage stats by equipment type
        usage_stats = EquipmentType.objects.annotate(
            total_bookings=Count('equipment__booking'),
            unique_users=Count('equipment__booking__employee', distinct=True)
        )
        
        # Current month bookings
        current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month_start = (current_month_start + timedelta(days=32)).replace(day=1)
        
        current_month_bookings = Booking.objects.filter(
            start_time__gte=current_month_start,
            start_time__lt=next_month_start
        ).count()
        
        # Recurring bookings stats
        recurring_bookings = Booking.objects.filter(recurrence__ne='NONE').count()
        
        data = {
            'most_booked_equipment': EquipmentSerializer(most_booked, many=True).data,
            'usage_stats_by_type': [
                {
                    'type': stat.name,
                    'total_bookings': stat.total_bookings,
                    'unique_users': stat.unique_users
                } for stat in usage_stats
            ],
            'current_month_bookings': current_month_bookings,
            'recurring_bookings_count': recurring_bookings
        }
        
        return Response(data)
    
    #