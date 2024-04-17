from django.conf import settings
from django.db import models
from django.utils import timezone
import joblib
from simple_history.models import HistoricalRecords
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from mptt.models import MPTTModel, TreeForeignKey
from django.core.validators import RegexValidator, MinValueValidator
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
import logging
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import transaction
from django.db import models
from django.db.models import Count, Sum, Max, Avg

from warehouse.inventory.utils import send_admin_approval_request

class HistoricalCategoryModel(models.Model):
    lft = models.IntegerField(null=True, blank=True)
    rght = models.IntegerField(null=True, blank=True)
    tree_id = models.IntegerField(null=True, blank=True)
    level = models.IntegerField(null=True, blank=True)

    class Meta:
        abstract = True       
class Category(MPTTModel):
    name = models.CharField(
        max_length=100,
        null=False,
        blank=False,
        verbose_name=_("category name"),
        help_text=_("format: required, max-100"),
    )
    slug = models.SlugField(
        max_length=150,
        null=False,
        blank=False,
        unique=True,  # Ensure URL uniqueness within the system
        verbose_name=_("category safe URL"),
        help_text=_("format: required, letters, numbers, underscore, or hyphens"),
    )
    is_active = models.BooleanField(default=True)
    parent = TreeForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
        verbose_name=_("parent category"),
        help_text=_("format: not required"),
    )
    pnd_location = models.ForeignKey(
        'PNDLocation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("PND Location"),
        help_text=_("Preferred PND location for this category")
    )
    weight_limit = models.DecimalField(
        max_digits=5,  
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("weight limit"),
        help_text=_("Maximum weight limit for this category in kilograms.")
    )
    history = HistoricalRecords(excluded_fields=['lft', 'rght', 'tree_id', 'level'])

    class MPTTMeta:
        order_insertion_by = ["name"]

    class Meta:
        verbose_name = _("product category")
        verbose_name_plural = _("product categories")

    def __str__(self):
        return self.name




class Address(models.Model):
    street_number = models.CharField(max_length=128)
    street_name = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    county = models.CharField(max_length=255)
    country = models.CharField(max_length=255)
    post_code = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        unique_together = (('street_number', 'post_code'),)

    def __str__(self):
        # Corrected the return statement
        return f"{self.street_number} {self.street_name}, {self.city}, {self.county}, {self.country}, {self.post_code}"
    
class Supplier(models.Model):
    name = models.CharField(max_length=255, verbose_name=_("supplier name"))
    contact = models.CharField(max_length=255, verbose_name=_("supplier contact"))
    email = models.EmailField(verbose_name=_("supplier email"))
    contact_number = models.CharField(max_length=50, verbose_name=_("supplier contact number"))
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    address = models.OneToOneField(
        Address,
        on_delete=models.CASCADE,
        related_name='supplier',
        verbose_name=_("address")
    )
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.name} - {self.email}"
    
class FoodProduct(models.Model):
    sku = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    suppliers = models.ManyToManyField(Supplier, related_name='products')
    is_high_demand = models.BooleanField(default=False, help_text=_("Indicates if the product is in high demand"))
    batch_number = models.CharField(max_length=100)
    storage_temperature = models.CharField(max_length=50)
    date_received = models.DateField()
    expiration_date = models.DateField()
    supplier = models.CharField(max_length=255)
    last_updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='product_updates')
    updated_at = models.DateTimeField(auto_now=True, null=True)
    stock = models.IntegerField(default=0)
    history = HistoricalRecords()

    def clean(self):
        # Custom validation to disallow negative quantities
        if self.quantity < 0:
            raise ValidationError({"quantity": ["Quantity must be non-negative."]})

    def save(self, *args, **kwargs):
        self.full_clean()  # This calls the clean method and validates the model
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sku}: {self.name} - Batch {self.batch_number}"

    def is_expired(self):
        """Check if the product is expired based on the current date."""
        return self.expiration_date < timezone.now().date()

    class Meta:
        ordering = ['expiration_date']
        
class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('Start', _('Task Started')),
        ('Complete', _('Task Completed')),
        ('Interrupt', _('Task Interrupted')),
        ('Update', _('Status Updated')),
        ('Manual', _('Manual Change')),
    ]

    # Generic Foreign Key setup
    content_type = models.ForeignKey(
        ContentType, 
        on_delete=models.CASCADE, 
        verbose_name=_("Content Type")
    )
    object_id = models.PositiveIntegerField(verbose_name=_("Object ID"))
    content_object = GenericForeignKey('content_type', 'object_id')

    action = models.CharField(
        max_length=50, 
        choices=ACTION_CHOICES, 
        verbose_name=_("Action")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name=_("User")
    )
    timestamp = models.DateTimeField(
        auto_now_add=True, 
        verbose_name=_("Timestamp")
    )
    description = models.TextField(
        verbose_name=_("Description"), 
        blank=True, 
        null=True
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = _("Audit Log")
        verbose_name_plural = _("Audit Logs")

    def __str__(self):
        return f"{self.content_type.model.capitalize()} ({self.object_id}) - {self.get_action_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

#STOCK LEVEL
    
class StockLevel(models.Model):
    location = models.ForeignKey(
        'Location', 
        on_delete=models.CASCADE, 
        related_name='stock_levels', 
        verbose_name=_("Warehouse Location")
    )
    pick_face = models.ForeignKey(
        'PickFace', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='pick_face_stock_levels',  # Changed related_name to be unique
        verbose_name=_("Pick Face Location")
    )
    product = models.ForeignKey(
        'FoodProduct', 
        on_delete=models.CASCADE, 
        related_name='product_stock_levels',  # Ensuring this related_name is uniquely identifying the relation
        verbose_name=_("Product")
    )
    quantity = models.PositiveIntegerField(
        default=0, 
        validators=[MinValueValidator(0)],
        help_text=_("Current quantity of the product at the location.")
    )
    batch_number = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text=_("Batch number for tracking specific batches of the product")
    )
    expiration_date = models.DateField(
        blank=True, 
        null=True, 
        help_text=_("Expiration date of the product batch")
    )
    last_updated = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = _("Stock Level")
        verbose_name_plural = _("Stock Levels")
        unique_together = (('location', 'product', 'batch_number'),)
        ordering = ['location', 'product', '-expiration_date']

    def __str__(self):
        return f"{self.product.name} - {self.quantity} units at {self.location}"

    def save(self, *args, **kwargs):
        """Custom save method to handle stock updates."""
        if self.quantity < 0:
            raise ValidationError(_("Quantity cannot be negative."))
        super().save(*args, **kwargs)

    def update_quantity(self, change):
        """Method to update the quantity of stock."""
        if not self.pk:
            raise ValidationError(_("StockLevel instance must be saved before updating quantity."))
        if self.quantity + change < 0:
            raise ValidationError(_("Resulting quantity cannot be negative."))

        with transaction.atomic():
            StockLevel.objects.filter(pk=self.pk).update(quantity=models.F('quantity') + change)
            self.refresh_from_db()

    @classmethod
    def adjust_stock(cls, product_id, location_id, quantity_change):
        """Class method to adjust stock levels."""
        with transaction.atomic():
            stock, created = cls.objects.get_or_create(
                product_id=product_id, 
                location_id=location_id,
                defaults={'quantity': max(quantity_change, 0)}  # Ensure non-negative initial quantity
            )
            if not created:
                stock.update_quantity(quantity_change)

    @classmethod
    def check_for_expired_stock(cls):
        """Class method to find expired stock."""
        today = timezone.now().date()
        return cls.objects.filter(expiration_date__lt=today).order_by('expiration_date')

    @classmethod
    def products_at_location(cls, location_id):
        """Class method to get products at a specific location."""
        return cls.objects.filter(location_id=location_id).select_related('product')

    def is_product_expired(self):
        """Check if the product batch is expired."""
        if not self.expiration_date:
            return False
        today = timezone.now().date()  # Ensures correct handling of time zone
        return today > self.expiration_date
        
    
class Receiving(models.Model):
    product = models.ForeignKey(
        FoodProduct,
        on_delete=models.CASCADE,
        related_name='receivings',  # This establishes the one-to-many relationship
        verbose_name=_("received product"),
        help_text=_("Select product being received")
    )
    quantity = models.PositiveIntegerField(
        verbose_name=_("quantity received"),
        help_text=_("Enter quantity of product received")
    )
    receiving_date = models.DateField(
        default=timezone.now,
        verbose_name=_("receiving date"),
        help_text=_("Date when product was received")
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name='receivings',  # Each supplier can have multiple receivings, but this line primarily impacts the product-receiving relationship
        verbose_name=_("supplier"),
        help_text=_("Select supplier of the received product")
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='received_by',  # Similar to 'product', establishes a one-to-many relationship: one user can receive many products
        verbose_name=_("received by"),
        help_text=_("User who received the product")
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("additional notes"),
        help_text=_("Any additional notes about the receiving")
    )
    history = HistoricalRecords()  # Tracks changes to each receiving record, implicitly a one-to-many relationship (each receiving record can have multiple history entries)

    class Meta:
        verbose_name = _("Receiving")
        verbose_name_plural = _("Receivings")
        ordering = ['-receiving_date']

    def __str__(self):
        return f"{self.product.name} received from {self.supplier.name} on {self.receiving_date}"
    
class GatehouseBooking(models.Model):
    driver_name = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    vehicle_registration = models.CharField(max_length=50)
    trailer_number = models.CharField(max_length=50, verbose_name=_("Trailer Number"))
    arrival_time = models.DateTimeField(default=timezone.now)
    paperwork = models.FileField(upload_to='gatehouse_paperwork/')
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.driver_name} from {self.company} with trailer {self.trailer_number} arrived at {self.arrival_time.strftime('%Y-%m-%d %H:%M')}"
    
class ProvisionalBayAssignment(models.Model):
    gatehouse_booking = models.OneToOneField(GatehouseBooking, on_delete=models.CASCADE)
    provisional_bay = models.CharField(max_length=50)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    assigned_at = models.DateTimeField(default=timezone.now)
    history = HistoricalRecords()

    def __str__(self):
        return f"Provisional bay {self.provisional_bay} assigned to {self.gatehouse_booking}"

class FinalBayAssignment(models.Model):
    provisional_bay_assignment = models.OneToOneField(ProvisionalBayAssignment, on_delete=models.CASCADE)
    final_bay = models.CharField(max_length=50)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    confirmed_at = models.DateTimeField(default=timezone.now)
    is_loaded = models.BooleanField(default=False, verbose_name=_("Loading Confirmed"))
    loaded_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Loaded At"))
    loader = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='loaded_bays', on_delete=models.SET_NULL, null=True, verbose_name=_("Loader"))
    history = HistoricalRecords()

    def confirm_loading(self, loader_user):
        """ Method to confirm the loading of goods into the vehicle. """
        if not self.is_loaded:
            self.is_loaded = True
            self.loaded_at = timezone.now()
            self.loader = loader_user
            self.save()
            return "Loading confirmed, vehicle ready for departure."
        else:
            return "Loading already confirmed."

    def __str__(self):
        return f"Final bay {self.final_bay} confirmed for {self.provisional_bay_assignment}, Loaded: {self.is_loaded}"

class Inbound(models.Model):
    final_bay_assignment = models.OneToOneField(FinalBayAssignment, on_delete=models.CASCADE, related_name='inbounds')
    product = models.ForeignKey(FoodProduct, on_delete=models.CASCADE, related_name='inbounds')
    quantity = models.PositiveIntegerField(verbose_name=_("quantity received"))
    receiving_date = models.DateTimeField(default=timezone.now, verbose_name=_("receiving date"))
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name=_("received by"), related_name='inbound_receivings')
    notes = models.TextField(blank=True, null=True, verbose_name=_("additional notes"))
    STATUS_CHOICES = [
        ('Pending', _('Pending Release')),  # Load is awaiting admin release
        ('Received', _('Received')),  # Admin has released the load, and it's acknowledged
        ('Released', _('Released for Putaway')),  # The load is acknowledged and ready for putaway
        ('Stored', _('Stored')),  # The putaway process is complete, and the load is stored
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending', verbose_name=_("Status"))
    floor_location = models.CharField(max_length=100, verbose_name=_("Floor Location"), help_text=_("Location on the warehouse floor where the stock is placed"))
    history = HistoricalRecords()

    def __str__(self):
        return f"Received {self.product.name} in bay {self.final_bay_assignment.final_bay} on {self.receiving_date.strftime('%Y-%m-%d %H:%M')}, Status: {self.get_status_display()}"

    def update_status(self, new_status):
        """Update the status of the inbound record with checks."""
        if new_status not in [choice[0] for choice in self.STATUS_CHOICES]:
            raise ValueError("Invalid status")
        if new_status == 'Released' and self.status != 'Pending':
            raise ValueError("Can only release loads that are pending.")
        self.status = new_status
        self.save()

        # Placeholder for additional actions based on the new status
        if new_status == 'Released':
            # Placeholder for actions to take when load is released for putaway
            # Implement actions here (e.g., create PutawayTask or send notification)
            pass

    class Meta:
        verbose_name = _("Inbound Record")
        verbose_name_plural = _("Inbound Records")
        ordering = ['-receiving_date']
    
        
# LLOP TASK MODEL

class LLOPTask(models.Model):
    TASK_CHOICES = [
        ('Picking', _('Picking')),
        ('Replenishing', _('Replenishing')),
    ]

    task_type = models.CharField(
        max_length=20, 
        choices=TASK_CHOICES, 
        default='Picking', 
        help_text=_("Type of LLOP task.")
    )
    product = models.ForeignKey(
        'FoodProduct', 
        on_delete=models.CASCADE, 
        related_name='llop_tasks', 
        verbose_name=_("Product")
    )
    source_location = models.ForeignKey(
        'PickFace', 
        on_delete=models.CASCADE, 
        related_name='llop_source_tasks', 
        verbose_name=_("Source Location")
    )
    destination_location = models.ForeignKey(
        'Outbound',  # Directly using Outbound which is a specialized Location
        on_delete=models.CASCADE, 
        related_name='llop_destination_tasks', 
        verbose_name=_("Destination Location")
    )
    quantity = models.PositiveIntegerField(verbose_name=_("Quantity"))
    unit_price = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        help_text=_("Unit price at the time of task creation")
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_llop_tasks', 
        verbose_name=_("Assigned To")
    )
    status = models.CharField(
        max_length=20, 
        choices=[('Assigned', _('Assigned')), ('In Progress', _('In Progress')), ('Completed', _('Completed'))], 
        default='Assigned', 
        verbose_name=_("Status")
    )
    start_time = models.DateTimeField(
        auto_now_add=True, 
        verbose_name=_("Start Time")
    )
    completion_time = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name=_("Completion Time")
    )
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.get_task_type_display()} Task for {self.product.name} - {self.quantity} units from {self.source_location} to {self.destination_location}"

    def perform_task(self):
        if self.status != 'Assigned':
            return "Task is already started or completed."
        self.status = 'In Progress'
        self.save()

        if self.source_location.current_stock < self.quantity:
            raise ValueError("Insufficient stock at source.")

        self.source_location.current_stock -= self.quantity
        self.source_location.save()

        destination_stock, _ = StockLevel.objects.get_or_create(
        location=self.destination_location, product=self.product, defaults={'quantity': 0})
        destination_stock.quantity += self.quantity
        destination_stock.save()

        self.status = 'Completed'
        self.completion_time = timezone.now()
        self.save()
        return "Task completed."

    def __str__(self):
        return f"{self.get_task_type_display()} - {self.product.name} from {self.source_location} to {self.destination_location}"

    def update_stock_levels(self):
        """Adjust stock levels at source and destination based on the task."""
        if self.source_location.current_stock < self.quantity:
            raise ValueError("Insufficient stock at source location to perform the task.")

        self.source_location.current_stock -= self.quantity
        self.source_location.save()

        destination_stock, created = StockLevel.objects.get_or_create(
            location=self.destination_location,
            product=self.product,
            defaults={'quantity': 0}
        )
        destination_stock.quantity += self.quantity
        destination_stock.save()
        
        
    # STORAGE 

class Zone(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, blank=True)
    history = HistoricalRecords()
    

    def __str__(self):
        return self.name

class Aisle(models.Model):
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='aisles', verbose_name=_("Zone"))
    aisle_letter = models.CharField(
        max_length=5,
        validators=[RegexValidator(r'^[A-Za-z]+$', 'Only letters are allowed for aisle letters.')],
        verbose_name=_("Aisle Letter"),
        help_text=_("Aisle identifier (letters only).")
    )
    history = HistoricalRecords()

    class Meta:
        unique_together = ('zone', 'aisle_letter')
        verbose_name = _("Aisle")
        verbose_name_plural = _("Aisles")

    def __str__(self):
        return f"Aisle {self.aisle_letter} in Zone {self.zone.name}"
    
class Rack(models.Model):
    aisle = models.ForeignKey(Aisle, on_delete=models.CASCADE, related_name='racks', verbose_name=_("Aisle"))
    rack_number = models.CharField(max_length=50, verbose_name=_("Rack Number"))
    history = HistoricalRecords()

    def __str__(self):
        return f"Rack {self.rack_number} in {self.aisle}"

class Level(models.Model):
    rack = models.ForeignKey('Rack', on_delete=models.CASCADE, related_name='levels')
    LEVEL_CHOICES = [
        ('G', 'Ground Floor'),
        ('1', 'Level 1'),
        ('2', 'Level 2'),
        ('3', 'Level 3'),
        ('4', 'Level 4'),
    ]
    level = models.CharField(
        max_length=1,
        choices=LEVEL_CHOICES,
        default='G',
        help_text="Specifies the level within the rack."
    )

    def __str__(self):
        return f"{self.get_level_display()} in Rack {self.rack.rack_number}, Aisle {self.rack.aisle.aisle_letter}"

    
class Location(models.Model):
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_("Location Code"),
        help_text=_("Unique code for identifying the location.")
    )
    description = models.TextField(
        verbose_name=_("Description"),
        blank=True,
        help_text=_("Description of the location.")
    )
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name='locations')
    side = models.CharField(
        max_length=1, 
        choices=(
            ('E', 'East'),
            ('W', 'West'),
            ('N', 'North'),
            ('S', 'South'),
        ),
        help_text="Side of the location"
    )
    location_number = models.IntegerField()
    weight = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00, 
        validators=[MinValueValidator(0.00)]
    )
    TYPE_CHOICES = [
        ('PND', 'PND'), 
        ('Storage', 'Storage'), 
        ('Pick Face', 'Pick Face'), 
        ('Inbound Floor', 'Inbound Floor'), 
        ('Outbound Floor', 'Outbound Floor')
    ]
    type = models.CharField(
        max_length=15, 
        choices=TYPE_CHOICES, 
        default='Storage'
    )
    STATUS_CHOICES = [
        ('empty', 'Empty'), 
        ('full', 'Full'), 
        ('vor', 'Verification Required'), 
        ('urgent_pick', 'Urgent Picking Required'), 
        ('urgent_replenish', 'Urgent Replenishment Required'), 
        ('low_stock', 'Low Stock')
    ]
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='empty'
    )
    name = models.CharField(max_length=255, blank=True)
    history = HistoricalRecords()

    class Meta:
        unique_together = ('level', 'side', 'location_number')
        ordering = ['level', 'side', 'location_number']

    def __str__(self):
        return f"Location {self.location_number} ({self.get_side_display()}) on {self.level}"

    def clean(self):
        """Validate conditions that could affect the location status."""
        if self.weight > 0 and self.status == 'empty':
            raise ValidationError('Location status and weight are inconsistent.')

    def save(self, *args, **kwargs):
        """Save method that includes a pre-save validation."""
        self.full_clean()  # Ensures the model is clean before saving
        super().save(*args, **kwargs)

    def update_status_based_on_sensor_data(self, weight, low_stock_threshold=50, urgent_replenish_threshold=20):
        """Update location status dynamically based on sensor data and type-specific thresholds."""
        self.weight = weight
        if self.type == 'PND':
            self.status = 'empty' if weight == 0 else 'full'
        elif self.type == 'Pick Face':
            if weight == 0:
                self.status = 'empty'
            elif weight <= urgent_replenish_threshold:
                self.status = 'urgent_replenish'
            elif weight <= low_stock_threshold:
                self.status = 'low_stock'
            else:
                self.status = 'full'
        else:
            if weight == 0:
                self.status = 'empty'
            elif weight <= urgent_replenish_threshold:
                self.status = 'urgent_replenish'
            elif weight <= low_stock_threshold:
                self.status = 'low_stock'
            else:
                self.status = 'full'
        self.save()

    @classmethod
    def get_for_full_pallets(cls, product):
        """Retrieve the location for full pallets of a specific product."""
        location = cls.objects.filter(
            stock_levels__product=product, 
            stock_levels__quantity__gte=product.pallet_size
        ).first()
        if not location:
            raise ValueError(f"No full pallets found for product {product.name}.")


class PNDLocation(Location):
    temperature_range = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        default='default-range',  # Providing a default value
        verbose_name=_("Temperature Range"),
        help_text=_("Suitable temperature range for this location, e.g., '0-4°C' for chilled.")
    )
    capacity = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        verbose_name=_("Capacity"),
        help_text=_("Maximum capacity of the location. Useful for space management.")
    )
    restrictions = models.TextField(
        blank=True, 
        null=True, 
        verbose_name=_("Restrictions"),
        help_text=_("Any specific restrictions for this location, such as 'No flammable products'.")
    )
    history = HistoricalRecords()

    def __str__(self):
        return super().__str__() + " - PND"
    
class Outbound(Location):  # Assuming 'Location' is the correct base class
    address = models.CharField(max_length=255, null=True)
    floor_number = models.PositiveIntegerField()
    bay_number = models.PositiveIntegerField()
    additional_info = models.TextField()
    location_identifier = models.CharField(max_length=100)
    max_capacity = models.IntegerField()
    operational_restrictions = models.CharField(max_length=255)
    special_handling_required = models.BooleanField(default=False)
    history = HistoricalRecords()
    outbound_code = models.CharField(max_length=50, unique=True, verbose_name=_("Outbound Code"))
    related_outbounds = models.ManyToManyField('self', symmetrical=False, blank=True, verbose_name=_("Related Outbounds"))
    managing_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='managed_outbounds', verbose_name=_("Managing User"))
    utilized_capacity = models.PositiveIntegerField(default=0, verbose_name=_("Utilized Capacity"))

    def __str__(self):
        return f"{self.outbound_code} - Floor {self.floor_number} - Bay {self.bay_number}"

    @staticmethod
    def get_default_location():
        unique_criteria = {
            'outbound_code': 'DEFAULT_OUTBOUND',  # Ensuring unique code for default location
            'location_identifier': 'DEFAULT_OUTBOUND'  # Assuming 'location_identifier' needs to be unique as well
        }
        default_location, _ = Outbound.objects.get_or_create(
            defaults={
                'address': 'Default Address',
                'floor_number': 1,
                'bay_number': 1,
                'additional_info': 'Default outbound location',
                'max_capacity': 1000,
                'operational_restrictions': 'None',
                'special_handling_required': False,
                'utilized_capacity': 0
            },
            **unique_criteria
        )
        return default_location
    
class PickFace(Location):
    pick_face_code = models.CharField(max_length=50, unique=True, verbose_name=_("Pick Face Code"))
    pick_faces = models.ManyToManyField('self', symmetrical=False, blank=True, verbose_name=_("Related Pick Faces"))
    parent_location = models.ForeignKey('self', on_delete=models.CASCADE, related_name='child_pick_faces', null=True, blank=True, verbose_name=_("Parent Location"))
    product = models.ForeignKey('FoodProduct', on_delete=models.CASCADE, related_name='pick_faces', verbose_name=_("Product"))
    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name='pick_faces', verbose_name=_("Category"))
    current_stock = models.PositiveIntegerField(default=0, verbose_name=_("Current Stock"))
    low_stock_threshold = models.PositiveIntegerField(default=10, verbose_name=_("Low Stock Threshold"))
    target_stock_level = models.PositiveIntegerField(default=100, verbose_name=_("Target Stock Level"))
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.pick_face_code} - {super().__str__()} - {self.category.name}"

    def trigger_replenishment(self):
        """Trigger a replenishment task based on stock availability and the required task type."""
        stock_location = self.find_available_stock_location()
        if not stock_location:
            print(f"No stock available for replenishment of {self.pick_face_code}.")
            return

        task_class, task_type = self.determine_task_type(stock_location)
        task_class.objects.create(
            task_type=task_type,
            product=self.product,
            quantity=self.calculate_replenishment_quantity(),
            source_location=stock_location,
            destination_location=self,
            vna_equipment='Default VNA' if task_class == VNATask else '',
            status='Assigned'
        )
        print(f"Replenishment task created for {self.pick_face_code} from {stock_location}.")

    def find_available_stock_location(self):
        """Find a stock location with sufficient inventory to fulfill a replenishment."""
        return Location.objects.exclude(stock_levels__quantity=0).filter(type__in=['Storage', 'Inbound Floor']).order_by('-stock_levels__quantity').first()

    def determine_task_type(self, stock_location):
        """Determine the appropriate task type based on the location type."""
        if stock_location.type in ['Inbound Floor', 'Outbound Floor']:
            return FLTTask, 'Replenishment'
        else:
            return VNATask, 'Replenishment Picking'

    def calculate_replenishment_quantity(self):
        """Calculate the quantity needed to replenish the pick face to the target level."""
        return max(self.target_stock_level - self.current_stock, 0)

@receiver(post_save, sender=PickFace)
def handle_low_stock_pick_face(sender, instance, **kwargs):
    if instance.current_stock < instance.low_stock_threshold:
        location = instance.find_available_stock_location()
        if location:
            task_class, task_type = instance.determine_task_type(location)
            task_class.objects.create(
                task_type=task_type,
                product=instance.product,
                quantity=instance.calculate_replenishment_quantity(),  # Update method name
                source_location=location,
                destination_location=instance.location,
                status='Assigned'
            )
# Inbound class

class PutawayTask(models.Model):
    inbound = models.ForeignKey(Inbound, on_delete=models.CASCADE, related_name='putaway_tasks')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='putaway_tasks', verbose_name=_("Assigned FLT Driver"))
    pnd_location = models.ForeignKey(PNDLocation, on_delete=models.SET_NULL, null=True, verbose_name=_("PND Location"), help_text=_("Final destination in the PND location"))
    pick_face = models.ForeignKey(PickFace, on_delete=models.SET_NULL, null=True, verbose_name=_("Pick Face"), help_text=_("Designated pick face for replenishment"))
    status = models.CharField(max_length=20, choices=[('Assigned', _('Assigned')), ('In Progress', _('In Progress')), ('Completed', _('Completed'))], default='Assigned', verbose_name=_("Status"))
    start_time = models.DateTimeField(auto_now_add=True, verbose_name=_("Start Time"))
    completion_time = models.DateTimeField(null=True, blank=True, verbose_name=_("Completion Time"))
    history = HistoricalRecords()

    def __str__(self):
        return f"Putaway Task for {self.inbound.product.name}, PND: {self.pnd_location}, assigned to {self.assigned_to}, status: {self.status}"

  # VNA TASKS
        
class VNATask(models.Model):
    TASK_TYPES = [
        ('Putaway', 'Putaway from PND to Storage'),
        ('Order Picking', 'Order Picking from Storage to PND'),
        ('Replenishment Picking', 'Replenishment Picking from Storage to PND')
    ]

    task_type = models.CharField(
        max_length=30,
        choices=TASK_TYPES, 
        default='Putaway',
        help_text=_("Type of VNA task.")
    )
    product = models.ForeignKey('FoodProduct', on_delete=models.CASCADE, related_name='vna_tasks', verbose_name=_("Product"))
    quantity = models.PositiveIntegerField(verbose_name=_("Quantity"))
    source_location = models.ForeignKey('Location', on_delete=models.CASCADE, related_name='vna_source_tasks', verbose_name=_("Source Location"))
    destination_location = models.ForeignKey('Location', on_delete=models.CASCADE, related_name='vna_destination_tasks', verbose_name=_("Destination Location"))
    vna_equipment = models.CharField(max_length=255, verbose_name=_("VNA Equipment"), help_text=_("The VNA equipment used for this task."))
    status = models.CharField(
        max_length=20, 
        choices=[
            ('Assigned', 'Assigned'), 
            ('In Progress', 'In Progress'), 
            ('Completed', 'Completed')
        ], 
        default='Assigned', 
        verbose_name=_("Status")
    )
    start_time = models.DateTimeField(auto_now_add=True, verbose_name=_("Start Time"))
    completion_time = models.DateTimeField(null=True, blank=True, verbose_name=_("Completion Time"))
    notes = models.TextField(blank=True, null=True, verbose_name=_("Notes"))
    history = HistoricalRecords()

    class Meta:
        verbose_name = _("VNATask")
        verbose_name_plural = _("VNATasks")

    def __str__(self):
        task_type_display = dict(self.TASK_TYPES).get(self.task_type, "Unknown Task Type")
        return f"{task_type_display} for {self.product.name} from {self.source_location} to {self.destination_location} - {self.status}"

    def save(self, *args, **kwargs):
        creating = not self.pk  # Check if the object is being created
        if self.task_type == 'Putaway' and self.source_location.type != 'PND':
            raise ValidationError("Source location must be a PND type for Putaway tasks.")
        elif self.task_type in ['Order Picking', 'Replenishment Picking'] and self.destination_location.type != 'PND':
            raise ValidationError("Destination location must be a PND type for Picking tasks.")
        
        super().save(*args, **kwargs)  # Call the "real" save method.
        
        if creating and self.status == 'Completed' and self.task_type == 'Order Picking':
            # Assuming FLTTask and Outbound models are defined with a get_default_location method
            FLTTask.objects.create(
                task_type='Order Completion',
                product=self.product,
                quantity=self.quantity,
                source_location=self.destination_location,
                destination_location=Outbound.get_default_location(),
                status='Pending'
            )
    
logger = logging.getLogger(__name__)
    
class ReplenishmentTask(models.Model):
    source_location = models.ForeignKey('Location', on_delete=models.CASCADE, related_name='replenishment_sources')
    destination_location = models.ForeignKey(Location, null=True, on_delete=models.CASCADE, related_name='replenishment_destinations')
    product = models.ForeignKey('FoodProduct', on_delete=models.CASCADE, related_name='replenishment_tasks')
    quantity = models.PositiveIntegerField(help_text=_("Quantity to be replenished."))
    status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('In Progress', 'In Progress'), ('Completed', 'Completed')], default='Pending')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='replenishment_tasks')
    priority = models.IntegerField(default=0, help_text=_("Priority of the task, with higher numbers indicating higher priority."))
    history = HistoricalRecords()

    def clean(self):
        """Perform validations before saving the model."""
        if not self.product_id:
            raise ValidationError("Product must be set before saving a ReplenishmentTask.")
        if self.quantity is None:
            raise ValidationError("Quantity must be provided for a ReplenishmentTask.")

    def save(self, *args, **kwargs):
        """Custom save method that includes set_priority call."""
        self.set_priority()  # Adjust priority before saving
        self.clean()  # Validate before saving to ensure data integrity
        super().save(*args, **kwargs)

    def set_priority(self):
        """Set priority based on quantity and product demand."""
        if self.quantity > 100 or (self.product and self.product.is_high_demand):
            self.priority = 100
        else:
            self.priority = 10

    def create_movement_task(self, FLTTask, VNATask, logger, request=None):
        """Create movement task based on the type of source location."""
        try:
            task_class = FLTTask if self.source_location.type == 'Inbound' else VNATask
            task_class.objects.create(
                replenishment_task=self,
                source_location=self.source_location,
                destination_location=self.destination_location,
                product=self.product,
                quantity=self.quantity,
            )
        except Exception as e:
            error_message = f"Error creating movement task: {str(e)}"
            logger.error(error_message)
            if request:
                from django.contrib import messages
                messages.error(request, error_message)
            
# FLT TASKS MODEL

class FLTTask(models.Model):
    TASK_TYPES = [
        ('Putaway', 'Putaway from Inbound to PND'),
        ('Order Completion', 'Full Pallets Order Completion to Outbound'),
        ('Replenishment', 'Replenishment to Pick Faces'),
    ]
    task_type = models.CharField(max_length=30, choices=TASK_TYPES, default='Putaway', help_text=_("Type of FLT task."))
    source_location = models.ForeignKey('Location', on_delete=models.CASCADE, related_name='flt_source_tasks')
    destination_location = models.ForeignKey('Location', on_delete=models.CASCADE, related_name='flt_destination_tasks')
    product = models.ForeignKey('FoodProduct', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='flt_tasks', verbose_name=_("Assigned FLT Driver"))
    status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('In Progress', 'In Progress'), ('Completed', 'Completed')], default='Pending')
    start_time = models.DateTimeField(default=timezone.now)
    completion_time = models.DateTimeField(null=True, blank=True)
    history = HistoricalRecords()

    vna_task = models.ForeignKey(
        'VNATask', 
        on_delete=models.SET_NULL,  # Consider SET_NULL for non-mandatory relationships
        related_name='flt_tasks_vna',
        verbose_name=_("Related VNATask"),
        null=True, 
        blank=True
    )

    replenishment_task = models.ForeignKey(
        'ReplenishmentTask', 
        on_delete=models.SET_NULL,  # Similarly consider SET_NULL here
        related_name='flt_tasks_replenishment',
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.get_task_type_display()} Task for {self.product.name}, From {self.source_location} to {self.destination_location} [{self.status}]"

    def perform_task(self):
        if self.status == 'Pending':
            self.status = 'In Progress'
            self.save()

            self.status = 'Completed'
            self.completion_time = timezone.now()
            self.save()

            self.update_stock_levels()
            return f"Task {self.id} completed."
        return f"Task {self.id} is already in progress or completed."

    def update_stock_levels(self):
        if self.source_location.stock_levels.filter(product=self.product).exists():
            source_stock = self.source_location.stock_levels.get(product=self.product)
            source_stock.quantity -= self.quantity
            source_stock.save()

        if self.destination_location.stock_levels.filter(product=self.product).exists():
            dest_stock = self.destination_location.stock_levels.get(product=self.product)
            dest_stock.quantity += self.quantity
            dest_stock.save()
        else:
            StockLevel.objects.create(product=self.product, location=self.destination_location, quantity=self.quantity)
    

    
    
class ProductLocation(models.Model):
    product = models.ForeignKey(FoodProduct, on_delete=models.CASCADE, related_name='locations')
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='products')
    quantity = models.PositiveIntegerField(default=0, help_text=_("Quantity of the product at the location."))
    history = HistoricalRecords()

    class Meta:
        unique_together = ('product', 'location')
        verbose_name = _("Product Location")
        verbose_name_plural = _("Product Locations")

    def __str__(self):
        return f"{self.product.name} at {self.location}"
    
class PickingTaskBase(models.Model):
    """
    Abstract base class for picking tasks, providing common attributes.
    """
    product = models.ForeignKey(FoodProduct, on_delete=models.CASCADE, related_name='%(class)s_products')
    source_location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='%(class)s_source')
    destination_location = models.ForeignKey(PNDLocation, on_delete=models.CASCADE, related_name='%(class)s_destination')
    quantity = models.PositiveIntegerField()
    vna_equipment = models.CharField(max_length=255, verbose_name=_("VNA Equipment"), help_text=_("VNA equipment used for the task."))
    status = models.CharField(max_length=20, choices=[('Pending', _('Pending')), ('In Progress', _('In Progress')), ('Completed', _('Completed'))], default='Pending')
    start_time = models.DateTimeField(default=timezone.now)
    completion_time = models.DateTimeField(null=True, blank=True)
    history = HistoricalRecords(inherit=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.product.name} from {self.source_location} to {self.destination_location} [{self.status}]"



class ReplenishmentPickingTask(PickingTaskBase):
    """
    Task for replenishing stock from storage to PND locations.
    """
    replenishment_request = models.ForeignKey('ReplenishmentRequest', on_delete=models.CASCADE, related_name='picking_tasks', verbose_name=_("Replenishment Request"))
    
    
    class Meta:
        verbose_name = _("Replenishment Picking Task")
        verbose_name_plural = _("Replenishment Picking Tasks")
        
class ReplenishmentRequest(models.Model):
    product = models.ForeignKey(FoodProduct, on_delete=models.CASCADE)
    required_quantity = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,  # Adjusted for realistic option length
        choices=[
            ('Requested', 'Requested'),
            ('Fulfilling', 'Fulfilling'),
            ('Completed', 'Completed')
        ],
        default='Requested'  # Set default status directly in the field definition
    )
    created_at = models.DateTimeField(default=timezone.now)
    history = HistoricalRecords()

    def __str__(self):
        return f"Replenishment request for {self.product.name}, Quantity: {self.required_quantity}"
    
class Customer(models.Model):
    name = models.CharField(max_length=255, verbose_name=_("Customer Name"))
    email = models.EmailField(verbose_name=_("Customer Email"), unique=True)
    phone = models.CharField(max_length=20, verbose_name=_("Contact Phone"), blank=True)
    address = models.OneToOneField(
        'Address', 
        on_delete=models.CASCADE, 
        related_name='customer',  # Changed to singular since it's one-to-one
        verbose_name=_("Address")
    )
    history = HistoricalRecords()
    
    def __str__(self):
        return f"{self.name} - {self.email}"

class Order(models.Model):
    customer = models.ForeignKey(
        'Customer', 
        on_delete=models.CASCADE, 
        related_name='orders', 
        verbose_name=_("Customer")
    )
    order_date = models.DateTimeField(default=timezone.now, verbose_name=_("Order Date"))
    status = models.CharField(
        max_length=20,
        choices=[
            ('Pending', _('Pending')),
            ('Processing', _('Processing')),
            ('Shipped', _('Shipped')),
            ('Cancelled', _('Cancelled'))
        ],
        default='Pending',
        verbose_name=_("Status")
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_("Total Amount"))
    is_paid = models.BooleanField(default=False, verbose_name=_("Is Paid"))
    payment_date = models.DateTimeField(blank=True, null=True, verbose_name=_("Payment Date"))
    notes = models.TextField(blank=True, null=True, verbose_name=_("Additional Notes"))
    history = HistoricalRecords()

    class Meta:
        ordering = ['-order_date']
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")

    def __str__(self):
        return f"Order {self.id} - {self.customer.name}"

    def complete_order(self):
        if self.status not in ['Pending', 'Processing']:
            return f"Order {self.id} cannot be completed from its current state ({self.status})."

        try:
            tasks = []
            for item in self.items.all():
                source = Location.get_for_full_pallets(item.product)
                destination = Outbound.get_default_location()
                task = self.create_flt_task('Order Completion', item.product, item.quantity, source, destination, None)
                tasks.append(task)
            self.status = 'Shipped'
            self.save()

            # Dispatch creation assumes that transport details are provided somehow
            dispatch = Dispatch.objects.create(
                order=self,
                dispatched_by=None,  # Typically set by context or user session
                driver_name="John Doe",
                vehicle_registration="XYZ 1234",
                trailer_number="TR 5678"
            )

            # Create loader tasks for each FLT task
            for task in tasks:
                LoaderTask.objects.create(
                    dispatch=dispatch,
                    product=task.product,
                    quantity=task.quantity,
                    source_location=task.destination_location,
                    status='Pending'
                )

            return f"Order {self.id} completed and marked as shipped. Dispatch ID: {dispatch.id}"
        except ValueError as e:
            return str(e)

    def create_flt_task(self, task_type, product, quantity, source, destination, assigned_to):
        if quantity <= 0:
            raise ValueError("Quantity must be positive and sufficient for transfer.")
        return FLTTask.objects.create(
            task_type=task_type,
            product=product,
            quantity=quantity,
            source_location=source,
            destination_location=destination,
            assigned_to=assigned_to,
            status='Pending'
        )

    def generate_invoice(self):
        items = self.items.all()
        invoice_lines = [f"Invoice for Order {self.id} - {self.customer.name}\n"]
        invoice_lines.append(f"Order Date: {self.order_date.strftime('%Y-%m-%d %H:%M')}\n")
        invoice_lines.append(f"Status: {self.get_status_display()}\n")
        invoice_lines.append("Items:\n")
        
        for item in items:
            invoice_lines.append(f" - {item.product.name}, Quantity: {item.quantity}, Unit Price: ${item.unit_price}, Total: ${item.total_price}\n")
        
        invoice_lines.append(f"Total Amount: ${self.total_amount}\n")
        invoice_lines.append(f"Paid: {'Yes' if self.is_paid else 'No'}\n")
        
        if self.is_paid:
            invoice_lines.append(f"Payment Date: {self.payment_date.strftime('%Y-%m-%d %H:%M')}\n")
        
        return "".join(invoice_lines)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name=_("Order"))
    product = models.ForeignKey('FoodProduct', on_delete=models.SET_NULL, null=True, related_name='order_items', verbose_name=_("Product"))
    quantity = models.PositiveIntegerField(verbose_name=_("Quantity"))
    unit_price = models.DecimalField(max_digits=8, decimal_places=2, verbose_name=_("Unit Price"))
    history = HistoricalRecords()
    
    @property
    def total_price(self):
        return self.quantity * self.unit_price

    class Meta:
        verbose_name = _("Order Item")
        verbose_name_plural = _("Order Items")

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
    
class OrderPickingTask(models.Model):
    order = models.ForeignKey('Order', on_delete=models.CASCADE)
    source_location = models.ForeignKey(
        'Location', 
        on_delete=models.CASCADE,
        related_name='tasks_as_source',
        verbose_name="Source Location"
    )
    destination_location = models.ForeignKey(
        'Outbound', 
        on_delete=models.CASCADE,
        related_name='tasks_as_destination',
        verbose_name="Destination Location"
    )
    product = models.ForeignKey('FoodProduct', on_delete=models.CASCADE)
    quantity = models.IntegerField()
    vna_equipment = models.CharField(max_length=100)
    start_time = models.DateTimeField()
    completion_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10)
    history = HistoricalRecords()

    def __str__(self):
        return f"Task for Order {self.order.id} - {self.quantity} units from {self.source_location} to {self.destination_location}"
    
class Dispatch(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='dispatch')
    dispatch_time = models.DateTimeField(default=timezone.now, verbose_name=_("Dispatch Time"))
    dispatched_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name=_("Dispatched By"))
    driver_name = models.CharField(max_length=255, verbose_name=_("Driver Name"))
    vehicle_registration = models.CharField(max_length=255, verbose_name=_("Vehicle Registration"))
    trailer_number = models.CharField(max_length=255, verbose_name=_("Trailer Number"))
    final_bay_assignment = models.ForeignKey(FinalBayAssignment, on_delete=models.SET_NULL, null=True, verbose_name=_("Final Bay Assignment"))
    history = HistoricalRecords()

    def finalize_dispatch(self):
        if not self.final_bay_assignment.is_loaded:
            return "Cannot dispatch. Vehicle loading not confirmed."
        self.dispatch_time = timezone.now()
        self.save()
        return f"Dispatch finalized for {self.driver_name}. Departure at {self.dispatch_time.strftime('%Y-%m-%d %H:%M')}."

    def __str__(self):
        return f"Dispatch for Order {self.order.id} - Vehicle {self.vehicle_registration} - Trailer {self.trailer_number} at {self.dispatch_time.strftime('%Y-%m-%d %H:%M')}"

class LoaderTask(models.Model):
    dispatch = models.ForeignKey('Dispatch', on_delete=models.CASCADE, related_name='loader_tasks')
    product = models.ForeignKey('FoodProduct', on_delete=models.CASCADE, verbose_name=_("Product"))
    quantity = models.PositiveIntegerField(verbose_name=_("Quantity"))
    source_location = models.ForeignKey('Location', on_delete=models.CASCADE, verbose_name=_("Source Location"))
    status = models.CharField(
        max_length=20,
        choices=[('Pending', 'Pending'), ('In Progress', 'In Progress'), ('Completed', 'Completed')],
        default='Pending',
        verbose_name=_("Status")
    )
    completion_time = models.DateTimeField(null=True, blank=True, verbose_name=_("Completion Time"))
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name=_("Confirmed By"))
    history = HistoricalRecords()

    def __str__(self):
        return f"Loader Task for {self.product.name}, Quantity: {self.quantity} - Status: {self.get_status_display()}"

class CMR(models.Model):
    dispatch = models.OneToOneField('Dispatch', on_delete=models.CASCADE, related_name='cmr')
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name=_("Confirmed By"))
    document = models.FileField(upload_to='cmr_documents/', verbose_name=_("CMR Document"))
    history = HistoricalRecords()

    def __str__(self):
        return f"CMR Document for Dispatch {self.dispatch.id} created at {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class Shipment(models.Model):
    dispatch = models.OneToOneField(Dispatch, on_delete=models.CASCADE, related_name='shipment')
    shipment_time = models.DateTimeField(default=timezone.now, verbose_name=_("Shipment Time"))
    shipped_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name=_("Shipped By"))
    tracking_number = models.CharField(max_length=255, verbose_name=_("Tracking Number"), null=True, blank=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"Shipment for Dispatch {self.dispatch.order.id} - Shipped at {self.shipment_time.strftime('%Y-%m-%d %H:%M')}"
    
from django.db import models
from django.utils import timezone
from django.db.models import Count, Sum, Avg

class Report(models.Model):
    REPORT_CHOICES = [
        ('inventory', 'Inventory Report'),
        ('order', 'Order Report'),
        ('supplier', 'Supplier Report'),
        ('shipment', 'Shipment Report'),
        ('activity', 'User Activity Report'),
        ('maximums', 'Max Values Report'),  # New type for maximum values report
    ]

    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=100, choices=REPORT_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def generate_report(self):
        """ Dispatch to the specific report generator based on the report type. """
        report_generators = {
            'inventory': self.inventory_report,
            'order': self.order_report,
            'supplier': self.supplier_report,
            'shipment': self.shipment_report,
            'activity': self.activity_report,
            'maximums': self.maximums_report,  # Handle maximums report
        }
        report_func = report_generators.get(self.report_type, lambda: "Unsupported report type")
        return report_func()

    def inventory_report(self):
        """ Generate a report summarizing inventory levels across products. """
        data = StockLevel.objects.values('product__name') \
                .annotate(total_stock=Sum('quantity'), max_stock=Max('quantity'), average_price=Avg('product__unit_price')) \
                .order_by('-total_stock')
        return data

    def order_report(self):
        """ Generate a report on orders, categorized by status and aggregated for the past month. """
        data = Order.objects.filter(order_date__gte=timezone.now() - timezone.timedelta(days=30)) \
                .values('status') \
                .annotate(total_orders=Count('id'), max_order_amount=Max('total_amount'), total_amount=Sum('total_amount')) \
                .order_by('-total_orders')
        return data

    def maximums_report(self):
        """ Generate a report to find the maximum values across various entities. """
        report_data = {
            'max_inventory': StockLevel.objects.aggregate(Max('quantity')),
            'max_order_amount': Order.objects.aggregate(Max('total_amount')),
            'max_product_price': FoodProduct.objects.aggregate(Max('unit_price')),
            'max_quantity_received': Receiving.objects.aggregate(Max('quantity')),
            # You can add more fields as required
        }
        return report_data

    def __str__(self):
        return f"{self.name} - {self.get_report_type_display()} ({self.created_at.strftime('%Y-%m-%d')})"

    class Meta:
        verbose_name = _("Report")
        verbose_name_plural = _("Reports")
        ordering = ['-created_at']


class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        PAYMENT = 'PAY', _('Payment')
        REFUND = 'REF', _('Refund')
        ADJUSTMENT = 'ADJ', _('Adjustment')

    class TransactionStatus(models.TextChoices):
        PENDING = 'PEN', _('Pending')
        COMPLETED = 'COM', _('Completed')
        FAILED = 'FAI', _('Failed')

    # Basic transaction details
    transaction_type = models.CharField(
        max_length=3,
        choices=TransactionType.choices,
        default=TransactionType.PAYMENT,
        verbose_name=_("Transaction Type")
    )
    status = models.CharField(
        max_length=3,
        choices=TransactionStatus.choices,
        default=TransactionStatus.PENDING,
        verbose_name=_("Status")
    )
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        verbose_name=_("Amount")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )

    # References to related entities
    order = models.ForeignKey(
        'Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name=_("Related Order")
    )
    customer = models.ForeignKey(
        'Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name=_("Related Customer")
    )
    supplier = models.ForeignKey(
        'Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name=_("Related Supplier")
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At")
    )

    def __str__(self):
        return f"{self.get_transaction_type_display()} - ${self.amount} - {self.get_status_display()} on {self.created_at.strftime('%Y-%m-%d')}"

    class Meta:
        verbose_name = _("Transaction")
        verbose_name_plural = _("Transactions")
        ordering = ['-created_at']

# IoT Integretion

class Sensor(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='sensors')
    sensor_type = models.CharField(max_length=50, verbose_name=_("Sensor Type"))
    status = models.CharField(max_length=20, choices=[('Active', 'Active'), ('Inactive', 'Inactive')], default='Active')
    last_checked = models.DateTimeField(auto_now=True, verbose_name=_("Last Checked"))

    def __str__(self):
        return f"{self.sensor_type} Sensor at {self.location.code} - {self.get_status_display()}"

class SensorData(models.Model):
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name='data')
    data = models.JSONField(verbose_name=_("Data"))
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name=_("Timestamp"))

    def __str__(self):
        return f"Data from {self.sensor} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


# AI Integresion

class PredictionModel(models.Model):
    name = models.CharField(max_length=255)
    model_file = models.FileField(upload_to='models/')

    def predict(self, X):
        # Load the model from the file each time before making a prediction
        model = joblib.load(self.model_file.path)
        return model.predict(X)

    def __str__(self):
        return self.name





#USER SETUP TO LOGIN

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from warehouse.inventory.managers import UserManager

class User(AbstractUser):
    username = None  # We're using email instead of username
    email = models.EmailField(_('email address'), unique=True)
    is_approved = models.BooleanField(default=False, verbose_name=_('Is Approved'))  # Field to track approval status
    
    class Role(models.TextChoices):
        DEFAULT_USER = "DEFAULT_USER", _('Default User')
        SECURITY = "SECURITY", _('Security')
        RECEPTIONIST = "RECEPTIONIST", _('Receptionist')
        WAREHOUSE_OPERATIVE = "WAREHOUSE_OPERATIVE", _('Warehouse Operative')
        WAREHOUSE_ADMIN = "WAREHOUSE_ADMIN", _('Warehouse Admin')
        WAREHOUSE_TEAM_LEADER = "WAREHOUSE_TEAM_LEADER", _('Warehouse Team Leader')
        WAREHOUSE_MANAGER = "WAREHOUSE_MANAGER", _('Warehouse Manager')
        INVENTORY_ADMIN = "INVENTORY_ADMIN", _('Inventory Admin')
        INVENTORY_TEAM_LEADER = "INVENTORY_TEAM_LEADER", _('Inventory Team Leader')
        INVENTORY_MANAGER = "INVENTORY_MANAGER", _('Inventory Manager')
        OPERATIONAL_MANAGER = "OPERATIONAL_MANAGER", _('Operational Manager')

    role = models.CharField(max_length=50, choices=Role.choices, default=Role.DEFAULT_USER, verbose_name=_('Role'))

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')

    def __str__(self):
        return self.email

    def has_role(self, role):
        return self.role == role

    def save(self, *args, **kwargs):
        creating = not self.pk
        super().save(*args, **kwargs)
        if creating and not self.is_approved and self.role in [
            self.Role.WAREHOUSE_ADMIN, self.Role.OPERATIONAL_MANAGER]:
            self.is_active = False
            send_admin_approval_request(self)  # Call to send an admin approval request
        super().save(*args, **kwargs)

class Employee(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    first_name = models.CharField(max_length=255, verbose_name=_('First Name'))
    last_name = models.CharField(max_length=255, verbose_name=_('Last Name'))
    dob = models.DateField(verbose_name=_('Date of Birth'))
    personal_email = models.EmailField(unique=True, verbose_name=_('Personal Email'))
    contact_number = models.CharField(max_length=20, verbose_name=_('Contact Number'))
    address = models.TextField(verbose_name=_('Address'))  # Assuming you have Address as a model or change to appropriate field type
    position = models.CharField(max_length=100, verbose_name=_('Position'))
    start_date = models.DateField(verbose_name=_('Start Date'))

    class Meta:
        db_table = 'employee'
        verbose_name = _('Employee')
        verbose_name_plural = _('Employees')

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

        
