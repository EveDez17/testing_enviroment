from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Permission
from warehouse.app_auth_user.models import User
from warehouse.app_auth_user.utils import send_admin_approval_request
from .models import User



# Signal for User approval
@receiver(post_save, sender=User)
def handle_user_save(sender, instance, created, **kwargs):
    if created:
        send_admin_approval_request(instance)
        
        
#Permission Users    
@receiver(post_save, sender=User)
def assign_role_permissions(sender, instance, created, **kwargs):
    if created or 'employee' in (kwargs.get('update_fields') or []):
        employee = instance.employee
        if employee and employee.role:
            instance.user_permissions.clear()
            # Assuming you have a method in Employee model to get permissions based on role
            if hasattr(employee.role, 'permissions'):
                permissions = Permission.objects.filter(codename__in=employee.role.permissions.values_list('codename', flat=True))
                instance.user_permissions.add(*permissions)
            instance.save()