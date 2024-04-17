
import pytest
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from warehouse.tests.factories import UserFactory, EmployeeFactory
from warehouse.inventory.models import User

#Test case for actual user created
@pytest.mark.django_db
class AdminAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            email='a@a.com',
            password='testpassword'
        )
        self.client.login(email='a@a.com', password='testpassword')

    def test_admin_site_access(self):
        url = reverse('admin:index')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
#Verify Register new User

class TestUserCreation(TestCase):
    def setUp(self):
        Group.objects.create(name="Warehouse Operative")

    def test_user_creation(self):
        self.assertEqual(User.objects.count(), 0)
        try:
            user = UserFactory()
            group = Group.objects.get(name="Warehouse Operative")
            user.groups.add(group)
            user.save()
        except IntegrityError:
            self.fail("IntegrityError raised unexpectedly!")

        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(user.groups.filter(name="Warehouse Operative").exists())

@pytest.mark.django_db
def test_admin_approval_process():
    try:
        admin = UserFactory()
        admin_group = Group.objects.get(name="Warehouse Admin")
        admin.groups.add(admin_group)
        admin.is_active = False  # Assuming this field must be manually set for the test
        admin.save()
    except IntegrityError:
        pytest.fail("IntegrityError raised unexpectedly!")

    assert not admin.is_active
    assert admin_group in admin.groups.all()

@pytest.mark.django_db
def test_employee_creation():
    try:
        employee = EmployeeFactory()
        operative_group = Group.objects.get(name="Warehouse Operative")
        employee.user.groups.add(operative_group)
        employee.user.save()
    except IntegrityError:
        pytest.fail("IntegrityError raised unexpectedly!")

    assert operative_group in employee.user.groups.all()