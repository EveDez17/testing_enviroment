import argparse
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Creates or updates a user'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True, help='Email address of the user')
        parser.add_argument('--password', required=True, help='Password for the user')

    def handle(self, *args, **options):
        User = get_user_model()
        email = options['email']
        password = options['password']

        user, created = User.objects.get_or_create(email=email)
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created a new user: {email}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'User already exists. Updating password for {email}.'))
            user.set_password(password)
            user.save()

        self.stdout.write(self.style.SUCCESS('Operation completed successfully.'))
