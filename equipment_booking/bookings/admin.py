# bookings/admin.py
from django.contrib import admin
from .models import User, EquipmentType, Equipment, Booking, Notification
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta, datetime

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'department', 'is_staff')
    list_filter = ('role', 'department', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'department', 'phone')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('role', 'department', 'phone')}),
    )
    def get_role_display(self, obj):
        return obj.get_role_display()
    get_role_display.short_description = 'Role'

class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'location', 'quantity', 'is_active', 'availability_actions')
    list_filter = ('type', 'is_active')
    search_fields = ('name', 'location')
    filter_horizontal = ()
    
    def availability_actions(self, obj):
        return format_html(
            '<a class="button" href="{}">Today</a>&nbsp;'
            '<a class="button" href="{}">This Week</a>&nbsp;'
            '<a class="button" href="{}">This Month</a>',
            reverse('admin:equipment_availability', args=[obj.pk, 'day']),
            reverse('admin:equipment_availability', args=[obj.pk, 'week']),
            reverse('admin:equipment_availability', args=[obj.pk, 'month']),
        )
    availability_actions.short_description = 'Check Availability'
    availability_actions.allow_tags = True
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<int:equipment_id>/availability/<str:period>/', 
                 self.admin_site.admin_view(self.equipment_availability_view),
                 name='equipment_availability'),
        ]
        return custom_urls + urls
    
    def equipment_availability_view(self, request, equipment_id, period):
        from django.shortcuts import get_object_or_404, render
        equipment = get_object_or_404(Equipment, pk=equipment_id)
        
        now = timezone.now()
        start_date = now.date()
        end_date = start_date
        
        if period == 'week':
            start_date = start_date - timedelta(days=start_date.weekday())
            end_date = start_date + timedelta(days=6)
        elif period == 'month':
            start_date = start_date.replace(day=1)
            end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        availability_data = []
        current_date = start_date
        
        while current_date <= end_date:
            day_start = timezone.make_aware(datetime.combine(current_date, datetime.min.time()))
            day_end = day_start + timedelta(days=1)
            
            bookings = Booking.objects.filter(
                equipment=equipment,
                start_time__lt=day_end,
                end_time__gt=day_start,
                status__in=['PENDING', 'APPROVED']
            )
            
            availability_data.append({
                'date': current_date,
                'bookings': bookings.count(),
                'available': equipment.quantity - bookings.count(),
                'total': equipment.quantity
            })
            
            current_date += timedelta(days=1)
        
        context = {
            **self.admin_site.each_context(request),
            'title': f'Availability for {equipment.name}',
            'equipment': equipment,
            'period': period,
            'availability_data': availability_data,
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/equipment_availability.html', context)

class BookingAdmin(admin.ModelAdmin):
    list_display = ('employee', 'equipment', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'equipment__type', 'start_time')
    search_fields = ('employee__username', 'equipment__name')
    

    raw_id_fields = ()  
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):

        if db_field.name == "employee":
            kwargs["queryset"] = User.objects.filter(role='EMPLOYEE').order_by('username')
            return db_field.formfield(**kwargs)

        elif db_field.name == "manager":
            kwargs["queryset"] = User.objects.filter(role='MANAGER').order_by('username')
            return db_field.formfield(**kwargs)
            
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
   
    def employee(self, obj):
        return str(obj.employee)
    employee.admin_order_field = 'employee__username'
    
    def equipment(self, obj):
        return str(obj.equipment)
    equipment.admin_order_field = 'equipment__name'
    
admin.site.register(User, CustomUserAdmin)
admin.site.register(EquipmentType)
admin.site.register(Equipment, EquipmentAdmin)
admin.site.register(Booking, BookingAdmin)
admin.site.register(Notification)