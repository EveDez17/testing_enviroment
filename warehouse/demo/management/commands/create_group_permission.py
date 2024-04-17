from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Create groups for user roles"

    def handle(self, *args, **options):
        roles = [
            'Security', 
            'Receptionist',
            'Warehouse Operative',
            'Warehouse Admin',
            'Warehouse Team Leader',
            'Warehouse Manager',
            'Inventory Admin',
            'Inventory Team Leader',
            'Inventory Manager',
            'Operational Manager',
        ]

        for role_name in roles:
            group, created = Group.objects.get_or_create(name=role_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Group "{role_name}" created successfully'))
            else:
                self.stdout.write(self.style.WARNING(f'Group "{role_name}" already exists'))