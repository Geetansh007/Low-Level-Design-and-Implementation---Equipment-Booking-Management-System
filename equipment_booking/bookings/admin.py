from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from .models import User, EquipmentType, Equipment, Booking, Notification
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Q

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'department', 'is_staff')
    list_filter = ('role', 'department', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'department', 'phone')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('role', 'department', 'phone')}),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(id=request.user.id)
    
    def has_module_permission(self, request):
        return request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role in ['ADMIN', 'MANAGER'])

class EquipmentTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    
    def has_module_permission(self, request):
        return request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role in ['ADMIN', 'MANAGER'])
    
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role in ['ADMIN', 'MANAGER'])

class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'location', 'quantity', 'is_active', 'availability_actions')
    list_filter = ('type', 'is_active')
    search_fields = ('name', 'location')
    
    def get_queryset(self, request):
        self.request = request  # Store request for availability_actions
        qs = super().get_queryset(request)
        if request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role in ['ADMIN', 'MANAGER']):
            return qs
        return qs.filter(is_active=True)
    
    def availability_actions(self, obj):
        # Check if user is admin or manager
        if not (self.request.user.is_superuser or 
                (hasattr(self.request.user, 'role') and 
                 self.request.user.role in ['ADMIN', 'MANAGER'])):
            return "-"
            
        return format_html(
            '<a class="button" href="{}">Today</a>&nbsp;'
            '<a class="button" href="{}">This Week</a>&nbsp;'
            '<a class="button" href="{}">This Month</a>',
            reverse('admin:equipment_availability', args=[obj.pk, 'day']),
            reverse('admin:equipment_availability', args=[obj.pk, 'week']),
            reverse('admin:equipment_availability', args=[obj.pk, 'month']),
        )
    availability_actions.short_description = 'Check Availability'
    
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
        if not (request.user.is_superuser or 
                (hasattr(request.user, 'role') and 
                 request.user.role in ['ADMIN', 'MANAGER'])):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        
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
    
    def has_module_permission(self, request):
        return request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role in ['ADMIN', 'MANAGER'])
    
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role in ['ADMIN', 'MANAGER'])
    
    def has_add_permission(self, request):
        return request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role == 'ADMIN')
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role == 'ADMIN')
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role == 'ADMIN')

class BookingAdmin(admin.ModelAdmin):
    list_display = ('employee', 'equipment', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'equipment__type', 'start_time')
    search_fields = ('employee__username', 'equipment__name')
    
    def has_module_permission(self, request):
        return request.user.is_authenticated
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role == 'ADMIN'):
            return qs
        elif hasattr(request.user, 'role') and request.user.role == 'MANAGER':
            return qs.filter(Q(manager=request.user) | Q(employee__department=request.user.department))
        else:
            return qs.filter(employee=request.user)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "employee":
            if hasattr(request.user, 'role') and request.user.role == 'MANAGER':
                kwargs["queryset"] = User.objects.filter(role='EMPLOYEE', department=request.user.department)
            else:
                kwargs["queryset"] = User.objects.filter(id=request.user.id)
            return db_field.formfield(**kwargs)

        elif db_field.name == "manager":
            kwargs["queryset"] = User.objects.filter(role='MANAGER')
            return db_field.formfield(**kwargs)
            
        elif db_field.name == "equipment":
            if not (request.user.is_superuser or (hasattr(request.user, 'role')) and request.user.role == 'ADMIN'):
                kwargs["queryset"] = Equipment.objects.filter(is_active=True)
            return db_field.formfield(**kwargs)
            
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def has_add_permission(self, request):
        return request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role in ['ADMIN', 'MANAGER'])
    
    def has_change_permission(self, request, obj=None):
        if obj is None:
            return True
        if request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role == 'ADMIN'):
            return True
        if hasattr(request.user, 'role') and request.user.role == 'MANAGER' and obj.employee.department == request.user.department:
            return True
        if obj.employee == request.user:
            return True
        return False
    
    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)
    
    def has_view_permission(self, request, obj=None):
        return request.user.is_authenticated

class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'is_read', 'created_at')
    
    def has_module_permission(self, request):
        return request.user.is_authenticated
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role == 'ADMIN'):
            return qs
        return qs.filter(user=request.user)
    
    def has_change_permission(self, request, obj=None):
        return obj and obj.user == request.user
    
    def has_delete_permission(self, request, obj=None):
        return False

admin.site.register(User, CustomUserAdmin)
admin.site.register(EquipmentType, EquipmentTypeAdmin)
admin.site.register(Equipment, EquipmentAdmin)
admin.site.register(Booking, BookingAdmin)
admin.site.register(Notification, NotificationAdmin)

def setup_manager_permissions():
    """Create and configure permissions for Manager role"""
    manager_group, created = Group.objects.get_or_create(name='Manager')
    

    booking_perms = Permission.objects.filter(content_type__model='booking')
    manager_group.permissions.add(*booking_perms)
    

    view_perms = Permission.objects.filter(
        content_type__model__in=['equipment', 'equipmenttype'],
        codename__startswith='view_'
    )
    manager_group.permissions.add(*view_perms)
    
    print("Manager permissions setup complete")

def setup_employee_permissions():
    """Create and configure permissions for Employee role"""
    employee_group, created = Group.objects.get_or_create(name='Employee')
    

    booking_view_perm = Permission.objects.get(
        content_type__model='booking',
        codename='view_booking'
    )
    employee_group.permissions.add(booking_view_perm)
    
    print("Employee permissions setup complete")

def setup_all_permissions():
    """Run both permission setup functions"""
    setup_manager_permissions()
    setup_employee_permissions()
    print("All role permissions configured")