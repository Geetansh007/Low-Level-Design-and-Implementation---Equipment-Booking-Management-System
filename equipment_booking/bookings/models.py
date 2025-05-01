from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField
from datetime import timedelta
from dirtyfields import DirtyFieldsMixin
class User(AbstractUser):
    ROLES = (
        ('ADMIN', 'Admin'),
        ('MANAGER', 'Manager'),
        ('EMPLOYEE', 'Employee'),
    )
    
    role = models.CharField(max_length=10, choices=ROLES, default='EMPLOYEE')
    department = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

class EquipmentType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

class Equipment(models.Model):
    name = models.CharField(max_length=100)
    type = models.ForeignKey(EquipmentType, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    location = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    tags = models.TextField(blank=True, null=True, help_text="Comma-separated tags")
    specifications = models.TextField(blank=True, null=True, help_text="JSON-formatted specifications")
    
    def available_quantity(self, start_time, end_time):
        booked_quantity = Booking.objects.filter(
            equipment=self,
            start_time__lt=end_time,
            end_time__gt=start_time,
            status__in=['PENDING', 'APPROVED']
        ).count()
        return self.quantity - booked_quantity
    
    def get_availability(self, start_date, end_date):
        """
        Returns availability data between start_date and end_date
        """
        availability = []
        current_date = start_date
        
        while current_date <= end_date:
            day_start = timezone.make_aware(timezone.datetime.combine(current_date, timezone.datetime.min.time()))
            day_end = day_start + timedelta(days=1)
            
            bookings = Booking.objects.filter(
                equipment=self,
                start_time__lt=day_end,
                end_time__gt=day_start,
                status__in=['PENDING', 'APPROVED']
            )
            
            availability.append({
                'date': current_date,
                'available': self.quantity - bookings.count(),
                'total_slots': self.quantity
            })
            
            current_date += timedelta(days=1)
        
        return availability
    
    def clean(self):
        if self.quantity < 0:
            raise ValidationError("Quantity cannot be negative")
    
    def __str__(self):
        return f"{self.name} ({self.type})"

class Booking(DirtyFieldsMixin,models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    )
    
    RECURRENCE_CHOICES = (
        ('NONE', 'None'),
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
    )
    
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_bookings')
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    purpose = models.TextField()
    attachments = models.FileField(upload_to='booking_attachments/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    

    recurrence = models.CharField(
        max_length=10,
        choices=RECURRENCE_CHOICES,
        default='NONE',
        help_text="Recurrence pattern for the booking"
    )
    recurrence_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End date for recurring bookings"
    )
    recurrence_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Unique identifier for a series of recurring bookings"
    )
    
    class Meta:
        indexes = [
            models.Index(fields=['start_time', 'end_time']),
            models.Index(fields=['status']),
            models.Index(fields=['recurrence_id']),  # New index for recurring bookings
        ]
        ordering = ['start_time']
    
    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time")
        
        if self.start_time < timezone.now():
            raise ValidationError("Cannot book equipment in the past")
        
        if self.recurrence != 'NONE' and not self.recurrence_end:
            raise ValidationError("Recurrence end date is required for recurring bookings")
            
        if self.recurrence_end and self.recurrence_end < self.start_time:
            raise ValidationError("Recurrence end date must be after the booking start time")
        
        # For new bookings or when changing time/equipment
        if not self.pk or (self.pk and (
            'start_time' in self.get_dirty_fields() or 
            'end_time' in self.get_dirty_fields() or
            'equipment_id' in self.get_dirty_fields()
        )):
            if self.equipment.available_quantity(self.start_time, self.end_time) <= 0:
                raise ValidationError("Equipment not available for the selected time slot")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        
        if self.pk is None and self.recurrence != 'NONE' and not self.recurrence_id:
            self.recurrence_id = f"rec_{timezone.now().timestamp()}"
        
        super().save(*args, **kwargs)
        
    
    def get_recurring_instances(self):
        """
        Returns all bookings in this recurring series
        """
        if not self.recurrence_id:
            return Booking.objects.filter(pk=self.pk)
        return Booking.objects.filter(recurrence_id=self.recurrence_id).order_by('start_time')
    
    def __str__(self):
        recurrence_str = f" ({self.get_recurrence_display()})" if self.recurrence != 'NONE' else ""
        return f"{self.employee.username}'s booking for {self.equipment.name}{recurrence_str}"

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    related_booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True)
    notification_type = models.CharField(max_length=20, default='INFO')
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Notification for {self.user.username}"