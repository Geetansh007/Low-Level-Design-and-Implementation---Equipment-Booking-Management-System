from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, EquipmentViewSet, EquipmentTypeViewSet,
    BookingViewSet, NotificationViewSet, ReportViewSet
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'equipment-types', EquipmentTypeViewSet)
router.register(r'equipment', EquipmentViewSet)
router.register(r'bookings', BookingViewSet)
router.register(r'notifications', NotificationViewSet, basename='notification')  
router.register(r'reports', ReportViewSet, basename='report')

urlpatterns = [
    path('', include(router.urls)),
    # Additional custom endpoints
    path('equipment/<int:pk>/availability/', 
         EquipmentViewSet.as_view({'get': 'availability'}), 
         name='equipment-availability'),
    path('bookings/available-equipment/', 
         BookingViewSet.as_view({'get': 'available_equipment'}), 
         name='available-equipment'),
    path('bookings/<int:pk>/cancel-series/', 
         BookingViewSet.as_view({'post': 'cancel_series'}), 
         name='booking-cancel-series'),
]