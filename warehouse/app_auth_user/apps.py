from django.apps import AppConfig

class AppAuthUserConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'warehouse.app_auth_user'
    label = 'app_auth_user' 
    
    def ready(self):
        from . import signals 
        
    