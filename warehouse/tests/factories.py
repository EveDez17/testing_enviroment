# factories.py
import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from warehouse.inventory.models import Employee

class UserFactory(DjangoModelFactory):
    class Meta:
        model = get_user_model()
        django_get_or_create = ('email',)

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password = factory.PostGenerationMethodCall('set_password', 'defaultpassword')
    is_staff = False
    is_superuser = False
    is_active = True

    @factory.post_generation
    def roles(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for role in extracted:
                self.groups.add(role)


class EmployeeFactory(DjangoModelFactory):
    class Meta:
        model = Employee  # Ensure Employee is imported correctly

    user = factory.SubFactory(UserFactory)
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    personal_email = factory.LazyAttribute(lambda obj: f"{obj.user.email}")
    contact_number = factory.Faker('phone_number')
    address = factory.Faker('address')
    position = "Warehouse Operative"
    start_date = factory.Faker('past_date')

