#USER SETUP TO LOGIN

from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from warehouse.app_auth_user.managers import UserManager
from warehouse.app_auth_user.utils import send_admin_approval_request
from django.db import models
from django.utils.translation import gettext_lazy as _


#Role Model
class Role(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name=_('Role Name'))
    permissions = models.ManyToManyField('auth.Permission', blank=True, verbose_name=_('Permissions'))

    class Meta:
        verbose_name = _('Role')
        verbose_name_plural = _('Roles')

    def __str__(self):
        return self.name

# Employee Model
class Employee(models.Model):
    first_name = models.CharField(max_length=255, verbose_name=_('First Name'))
    last_name = models.CharField(max_length=255, verbose_name=_('Last Name'))
    dob = models.DateField(verbose_name=_('Date of Birth'))
    personal_email = models.EmailField(unique=True, verbose_name=_('Personal Email'))
    contact_number = models.CharField(max_length=35, verbose_name=_('Contact Number'))
    address = models.OneToOneField('inventory.Address', on_delete=models.CASCADE, verbose_name=_('Address'))
    start_date = models.DateField(verbose_name=_('Start Date'))
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('Role'))

    class Meta:
        db_table = 'employee'
        verbose_name = _('Employee')
        verbose_name_plural = _('Employees')

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def employee_number(self):
        initials = self.first_name[:2].upper() + self.last_name[:2].upper()
        unique_id = uuid.uuid4().hex[:6]
        return f"{initials}-{unique_id}"


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(_('email address'), unique=True)
    is_staff = models.BooleanField(_('staff status'), default=False,
        help_text=_('Designates whether the user can log into this admin site.'))
    is_active = models.BooleanField(_('active'), default=True,
        help_text=_('Designates whether this user should be treated as active. '
                    'Unselect this instead of deleting accounts.'))
    date_joined = models.DateTimeField(_('date joined'), auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # email and password are required by default

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def __str__(self):
        return self.email


