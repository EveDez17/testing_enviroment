#USER SETUP TO LOGIN

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from warehouse.app_auth_user.managers  import UserManager
from warehouse.app_auth_user.utils import send_admin_approval_request
from warehouse.inventory.models import Address

class User(AbstractUser):
    username = None  # We're using email instead of username
    email = models.EmailField(_('email address'), unique=True)
    is_approved = models.BooleanField(default=False, verbose_name=_('Is Approved'))  # Field to track approval status
    
    class Role(models.TextChoices):
        DEFAULT_USER = "DEFAULT_USER", _('Default User')
        SECURITY = "SECURITY", _('Security')
        RECEPTIONIST = "RECEPTIONIST", _('Receptionist')
        WAREHOUSE_OPERATIVE = "WAREHOUSE_OPERATIVE", _('Warehouse Operative')
        WAREHOUSE_ADMIN = "WAREHOUSE_ADMIN", _('Warehouse Admin')
        WAREHOUSE_TEAM_LEADER = "WAREHOUSE_TEAM_LEADER", _('Warehouse Team Leader')
        WAREHOUSE_MANAGER = "WAREHOUSE_MANAGER", _('Warehouse Manager')
        INVENTORY_ADMIN = "INVENTORY_ADMIN", _('Inventory Admin')
        INVENTORY_TEAM_LEADER = "INVENTORY_TEAM_LEADER", _('Inventory Team Leader')
        INVENTORY_MANAGER = "INVENTORY_MANAGER", _('Inventory Manager')
        OPERATIONAL_MANAGER = "OPERATIONAL_MANAGER", _('Operational Manager')

    role = models.CharField(max_length=50, choices=Role.choices, default=Role.DEFAULT_USER, verbose_name=_('Role'))

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')

    def __str__(self):
        return self.email

    def has_role(self, role):
        return self.role == role

    def save(self, *args, **kwargs):
        creating = not self.pk
        super().save(*args, **kwargs)
        if creating and not self.is_approved and self.role in [
            self.Role.WAREHOUSE_ADMIN, self.Role.OPERATIONAL_MANAGER]:
            self.is_active = False
            send_admin_approval_request(self)  # Call to send an admin approval request
        super().save(*args, **kwargs)

class Employee(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    first_name = models.CharField(max_length=255, verbose_name=_('First Name'))
    last_name = models.CharField(max_length=255, verbose_name=_('Last Name'))
    dob = models.DateField(verbose_name=_('Date of Birth'))
    personal_email = models.EmailField(unique=True, verbose_name=_('Personal Email'))
    contact_number = models.CharField(max_length=20, verbose_name=_('Contact Number'))
    address = models.OneToOneField(Address, on_delete=models.CASCADE, verbose_name=_('Address'))  
    position = models.CharField(max_length=100, verbose_name=_('Position'))
    start_date = models.DateField(verbose_name=_('Start Date'))

    class Meta:
        db_table = 'employee'
        verbose_name = _('Employee')
        verbose_name_plural = _('Employees')

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

        
