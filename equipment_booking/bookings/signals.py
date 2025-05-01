from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from .models import Booking, Notification
from django.utils import timezone
from django.core.exceptions import ValidationError

@receiver(post_save, sender=Booking)
def handle_booking_notification(sender, instance, created, **kwargs):
    if created:
        Notification.objects.create(
            user=instance.employee,
            message=f"Your booking for {instance.equipment.name} has been created.",
            related_booking=instance,
            notification_type='BOOKING_CREATED'
        )
        
        
        if instance.manager:
            Notification.objects.create(
                user=instance.manager,
                message=f"You booked {instance.equipment.name} for {instance.employee.get_full_name()}.",
                related_booking=instance,
                notification_type='MANAGER_BOOKING'
            )
    else:
        
        old_status = Booking.objects.filter(pk=instance.pk).values_list('status', flat=True).first()
        if old_status and old_status != instance.status:
            Notification.objects.create(
                user=instance.employee,
                message=f"Booking status for {instance.equipment.name} changed to {instance.get_status_display()}.",
                related_booking=instance,
                notification_type='STATUS_CHANGED'
            )
            
@receiver(pre_save, sender=Booking)
def check_booking_conflicts(sender, instance, **kwargs):

    if instance.status in ['CANCELLED', 'COMPLETED']:
        return
        
    if instance.pk:  # Only for existing bookings
        original = Booking.objects.get(pk=instance.pk)
        
        # Check if relevant fields changed
        relevant_fields_changed = (
            original.equipment != instance.equipment or
            original.start_time != instance.start_time or
            original.end_time != instance.end_time
        )
        
        if not relevant_fields_changed:
            return
            

        available = instance.equipment.available_quantity(
            instance.start_time, 
            instance.end_time
        )
        
        if instance.pk:
            available += 1
                
        if available <= 0:
            raise ValidationError("Equipment not available for the selected time slot")
        
@receiver(post_delete, sender=Booking)
def handle_booking_deletion(sender, instance, **kwargs):
    # Notify when a booking is deleted
    Notification.objects.create(
        user=instance.employee,
        message=f"Your booking for {instance.equipment.name} has been deleted.",
        notification_type='BOOKING_DELETED'
    )
    

    if instance.recurrence != 'NONE' and instance.recurrence_id:
        Notification.objects.create(
            user=instance.employee,
            message=f"Your recurring booking series for {instance.equipment.name} has been cancelled.",
            notification_type='RECURRING_CANCELLED'
        )