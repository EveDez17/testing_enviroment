from django.core.mail import send_mail
from django.conf import settings

def send_admin_approval_request(user):
    subject = 'Approval Needed for New User'
    message = f'Please review and approve the new user: {user.email}'
    email_from = settings.DEFAULT_FROM_EMAIL
    recipient_list = ['admin@example.com']
    send_mail(subject, message, email_from, recipient_list)
