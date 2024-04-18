from django.db.models.signals import post_save
from django.dispatch import receiver

from warehouse.app_auth_user.models import User
from warehouse.app_auth_user.utils import send_admin_approval_request

# Signal for User approval
@receiver(post_save, sender=User)
def handle_user_save(sender, instance, created, **kwargs):
    if created and instance.role in [User.Role.WAREHOUSE_ADMIN, User.Role.OPERATIONAL_MANAGER]:
        send_admin_approval_request(instance)
