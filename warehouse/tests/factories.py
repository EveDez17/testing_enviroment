import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from warehouse.inventory.models import Address
from warehouse.app_auth_user.models import Employee, Role

class RoleFactory(DjangoModelFactory):
    class Meta:
        model = Role

    name = factory.Iterator(['DEFAULT_USER', 'SECURITY', 'RECEPTIONIST'])
    
    
#Address test model for Employee  
class AddressFactory(DjangoModelFactory):
    class Meta:
        model = Address

    street_number = factory.Faker('building_number')
    street_name = factory.Faker('street_name')
    city = factory.Faker('city')
    county = factory.Faker('state')
    country = factory.Faker('country')
    post_code = factory.Faker('postcode')
    


# Employee Factory
class EmployeeFactory(DjangoModelFactory):
    class Meta:
        model = Employee

    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    dob = factory.Faker('date_of_birth')
    personal_email = factory.LazyAttribute(lambda a: f'{a.first_name.lower()}.{a.last_name.lower()}@example.com')
    contact_number = factory.Faker('phone_number')
    address = factory.SubFactory(AddressFactory)
    start_date = factory.Faker('past_date')
    role = factory.SubFactory(RoleFactory)

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    email = factory.Faker('email')
    password = factory.PostGenerationMethodCall('set_unusable_password')
    is_approved = True

class SuperUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    email = factory.Sequence(lambda n: f"superuser{n}@example.com")
    password = factory.PostGenerationMethodCall('set_password', 'superpassword')
    is_approved = True
    is_staff = True
    is_superuser = True





    
 #Address test model for data insertation   
class AddressFactory(DjangoModelFactory):
    class Meta:
        model = Address

    street_number = factory.Faker('building_number')
    street_name = factory.Faker('street_name')
    city = factory.Faker('city')
    county = factory.Faker('state')
    country = factory.Faker('country')
    post_code = factory.Faker('postcode')






