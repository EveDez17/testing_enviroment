
from psycopg2 import IntegrityError
import pytest
import logging
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.db import transaction
from warehouse.app_auth_user.models import Employee, User
from warehouse.inventory.models import Address
from warehouse.tests.factories import AddressFactory, EmployeeFactory, RoleFactory, SuperUserFactory, UserFactory


    
#Address test model insertion data 
@pytest.mark.django_db
def test_address_creation():
    # Create an address using the factory
    address = AddressFactory()

    # Retrieve the address from the database
    db_address = Address.objects.get(id=address.id)

    # Assert that the address exists in the database with correct attributes
    assert db_address.street_number == address.street_number
    assert db_address.street_name == address.street_name
    assert db_address.city == address.city
    assert db_address.county == address.county
    assert db_address.country == address.country
    assert db_address.post_code == address.post_code
    

    
    
@pytest.mark.django_db
class UserTestCase(TestCase):
    def test_user_creation(self):
        """Test the user creation using factory"""
        user = UserFactory()
        self.assertTrue(user.email.startswith("user"))
        self.assertTrue(user.check_password('defaultpassword'))
        self.assertTrue(user.is_approved)
        self.assertEqual(user.is_staff, True)  # Ensure is_staff is set as expected
        self.assertIsNotNone(user.role) 
        
@pytest.mark.django_db
class RoleTestCase(TestCase):

    def test_role_creation(self):
        """Test role creation and its properties"""
        role = RoleFactory()
        self.assertIn(role.name, ['DEFAULT_USER', 'SECURITY', 'RECEPTIONIST'])
        
@pytest.mark.django_db
class EmployeeTestCase(TestCase):

    def test_employee_creation(self):
        """Test the employee creation and linked objects like Role and Address"""
        employee = EmployeeFactory()
        self.assertIsNotNone(employee.role)
        self.assertIsNotNone(employee.address)
        self.assertTrue(employee.personal_email.startswith(employee.first_name.lower()))
        self.assertEqual(employee.address.city, employee.address.city)  # Check for consistent city name from Faker

    def test_employee_number_generation(self):
        """Test the logic to generate employee number"""
        employee = EmployeeFactory()
        emp_number = employee.employee_number  # Updated to use the property name
        self.assertTrue(emp_number.startswith(employee.first_name[:2].upper()))
        self.assertEqual(len(emp_number.split('-')[1]), 6) 

@pytest.mark.django_db
def test_user_role_integration():
    """Test user creation linked with a specific role via employee"""
    role = RoleFactory(name='WAREHOUSE_ADMIN')
    employee = EmployeeFactory(role=role)
    user = UserFactory(email=employee.personal_email)
    assert user.email == employee.personal_email
    assert employee.role.name == 'WAREHOUSE_ADMIN'
    
@pytest.mark.django_db
class TestUserManager:
    def test_create_user(self):
        user = User.objects.create_user(email='regular@example.com', password='regularpassword')
        assert user.email == 'regular@example.com'
        assert user.check_password('regularpassword')
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_superuser(self):
        superuser = User.objects.create_superuser(email='superuser@example.com', password='superpassword')
        assert superuser.email == 'superuser@example.com'
        assert superuser.check_password('superpassword')
        assert superuser.is_staff
        assert superuser.is_superuser

