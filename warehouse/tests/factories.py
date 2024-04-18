# factories.py
import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from warehouse.app_auth_user.models import Employee
from warehouse.inventory.models import Address



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
                



