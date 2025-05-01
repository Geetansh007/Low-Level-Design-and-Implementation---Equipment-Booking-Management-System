from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin()

class IsManager(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_manager()

class IsEmployee(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_employee()

class IsManagerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (request.user.is_manager() or request.user.is_admin())

class IsOwnerOrManagerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin() or request.user.is_manager():
            return True
        return obj.employee == request.user