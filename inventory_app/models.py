from django.conf import settings
from django.db import models
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    full_name = models.CharField(max_length=150)
    business_name = models.CharField(max_length=150)
    mobile_number = models.CharField(max_length=15)

    def __str__(self):
        return self.full_name or self.user.email
    



class Vendor(models.Model):
    vendor_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    pan = models.CharField(max_length=20, blank=True, null=True)
    vat_number = models.CharField(max_length=50, blank=True, null=True)
    mobile = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['vendor_code']
        db_table = 'purchases_vendor'

    def __str__(self):
        return f"{self.vendor_code} - {self.name}"


class PurchaseInvoice(models.Model):
    invoice_number = models.CharField(max_length=100, unique=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name='invoices')
    invoice_date = models.DateField()
    entry_date = models.DateField(auto_now_add=True)
    credit_period = models.IntegerField(default=0, help_text='Credit period in days')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    pdf_path = models.CharField(max_length=255, blank=True)
    narration = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-invoice_date']
        db_table = 'purchases_purchaseinvoice'

    def __str__(self):
        return f"{self.invoice_number} - {self.vendor.name}"


class PurchaseLineItem(models.Model):
    invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.CASCADE, related_name='items')
    item_name = models.CharField(max_length=255)
    item_code = models.CharField(max_length=100)
    specification = models.CharField(max_length=255, blank=True)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    rate = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=13)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    serial_number = models.CharField(max_length=255, blank=True)
    hs_code = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['-invoice__invoice_date']
        db_table = 'purchases_purchaselineitem'

    def __str__(self):
        return f"{self.item_code} - {self.item_name}"




class VendorLedger(models.Model):
    PAYMENT_MODE_CHOICES = [
        ("cash", "Cash"),
        ("bank", "Bank"),
        ("upi", "UPI"),
        ("credit_card", "Credit Card"),
    ]

    TRANSACTION_TYPE_CHOICES = [
        ("opening", "Opening Balance"),
        ("purchase", "Purchase"),
        ("payment", "Payment"),
        ("return", "Purchase Return"),
    ]
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name="ledger_entries",
    )

    transaction_date = models.DateField()

    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES,
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    mode = models.CharField(
        max_length=20,
        choices=PAYMENT_MODE_CHOICES,
        null=True,
        blank=True,
    )

    against_invoice = models.ForeignKey(
        PurchaseInvoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
    )

    remark = models.TextField(blank=True)

    attachment = models.FileField(
        upload_to="vendor_ledger/",
        blank=True,
        null=True,
    )

    dr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    cr = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    closing_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "vendor_ledgers"
        ordering = ["-transaction_date", "-id"]

    def __str__(self):
        return f"{self.vendor.name} - {self.transaction_type} - {self.amount}"


class Product(models.Model):
    item_code = models.CharField(max_length=100, unique=True)
    item_name = models.CharField(max_length=255)
    specification = models.CharField(max_length=255, blank=True)
    hs_code = models.CharField(max_length=50, blank=True)
    unit_of_measure = models.CharField(max_length=20, default='pcs')
    selling_price = models.DecimalField(max_digits=12, decimal_places=2,default=0)
    reorder_level = models.IntegerField(default=10)
    category = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['item_code']
        db_table = 'inventory_product'

    def __str__(self):
        return f"{self.item_code} - {self.item_name}"



class InventoryStock(models.Model):

    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="stock"
    )

    quantity_on_hand = models.PositiveIntegerField(default=0)

    quantity_reserved = models.PositiveIntegerField(default=0)

    last_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00")
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inventory_inventorystock"
        verbose_name_plural = "Inventory Stock"

    @property
    def quantity_available(self):
        return self.quantity_on_hand - self.quantity_reserved

    @property
    def total_value(self):
        return self.quantity_on_hand * self.last_cost

    @property
    def stock_status(self):
        if self.quantity_on_hand < 2:
            return "Critical"

        elif self.quantity_on_hand <= self.product.reorder_level:
            return "Low"

        return "Healthy"

    def __str__(self):
        return f"{self.product.item_code} ({self.quantity_on_hand})"



class InventoryMovement(models.Model):
    """
    Inventory transaction ledger.

    Every stock increase/decrease must create one movement.
    InventoryStock represents the current balance,
    InventoryMovement represents the complete history.
    """

    # ==========================================================
    # Movement Types
    # ==========================================================

    PURCHASE = "PURCHASE"
    PURCHASE_RETURN = "PURCHASE_RETURN"

    SALE = "SALE"
    SALE_RETURN = "SALE_RETURN"

    REPAIR_ISSUE = "REPAIR_ISSUE"
    REPAIR_RETURN = "REPAIR_RETURN"

    TRANSFER = "TRANSFER"

    ADJUSTMENT = "ADJUSTMENT"

    OPENING = "OPENING"

    MOVEMENT_TYPES = [

        (PURCHASE, "Purchase"),
        (PURCHASE_RETURN, "Purchase Return"),

        (SALE, "Sale"),
        (SALE_RETURN, "Sale Return"),

        (REPAIR_ISSUE, "Issue to Repair Desk"),
        (REPAIR_RETURN, "Return from Repair Desk"),

        (TRANSFER, "Warehouse Transfer"),

        (ADJUSTMENT, "Stock Adjustment"),

        (OPENING, "Opening Stock"),

    ]

    # ==========================================================
    # Location Types
    # ==========================================================

    VENDOR = "VENDOR"
    WAREHOUSE = "WAREHOUSE"
    REPAIR = "REPAIR"
    CUSTOMER = "CUSTOMER"
    DAMAGED = "DAMAGED"
    ADJUSTMENT_LOCATION = "ADJUSTMENT"

    LOCATION_TYPES = [

        (VENDOR, "Vendor"),

        (WAREHOUSE, "Warehouse"),

        (REPAIR, "Repair Desk"),

        (CUSTOMER, "Customer"),

        (DAMAGED, "Damaged Stock"),

        (ADJUSTMENT_LOCATION, "Adjustment"),

    ]

    # ==========================================================
    # Helper Groups
    # ==========================================================

    INCOMING_TYPES = (

        PURCHASE,

        SALE_RETURN,

        REPAIR_RETURN,

        OPENING,

    )

    OUTGOING_TYPES = (

        SALE,

        PURCHASE_RETURN,

        REPAIR_ISSUE,

    )

    # ==========================================================
    # Fields
    # ==========================================================

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="movements",
    )

    movement_type = models.CharField(
        max_length=30,
        choices=MOVEMENT_TYPES,
    )

    movement_date = models.DateTimeField(
        default=timezone.now,
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    from_location = models.CharField(
        max_length=30,
        choices=LOCATION_TYPES,
    )

    to_location = models.CharField(
        max_length=30,
        choices=LOCATION_TYPES,
    )

    unit_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    remarks = models.CharField(
        max_length=255,
        blank=True,
    )

    # Future document linkage

    reference_type = models.CharField(
        max_length=30,
        blank=True,
    )

    reference_id = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    document_number = models.CharField(
        max_length=50,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    # ==========================================================
    # Meta
    # ==========================================================

    class Meta:

        db_table = "inventory_inventorymovement"

        ordering = ["-movement_date", "-id"]

        indexes = [

            models.Index(fields=["movement_date"]),

            models.Index(fields=["movement_type"]),

            models.Index(fields=["product"]),

            models.Index(fields=["document_number"]),

        ]

    # ==========================================================
    # Properties
    # ==========================================================

    @property
    def is_incoming(self):
        return self.movement_type in self.INCOMING_TYPES

    @property
    def is_outgoing(self):
        return self.movement_type in self.OUTGOING_TYPES

    @property
    def signed_quantity(self):

        if self.is_incoming:
            return self.quantity

        if self.is_outgoing:
            return -self.quantity

        return 0
    
    @property
    def badge_class(self):
        return {
            self.PURCHASE: "success",
            self.SALE: "danger",
            self.REPAIR_ISSUE: "primary",
            self.REPAIR_RETURN: "info",
            self.TRANSFER: "secondary",
            self.PURCHASE_RETURN: "warning",
            self.SALE_RETURN: "success",
            self.ADJUSTMENT: "dark",
            self.OPENING: "dark",
        }.get(self.movement_type, "secondary")
    
    @property
    def quantity_class(self):
        if self.is_incoming:
            return "success"

        if self.is_outgoing:
            return "danger"

        return "secondary"

    # ==========================================================
    # String Representation
    # ==========================================================

    def __str__(self):

        return (

            f"{self.product.item_code} | "

            f"{self.get_movement_type_display()} | "

            f"{self.quantity}"

        )
class BatchTracking(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='batches')
    batch_number = models.CharField(max_length=100)
    serial_numbers = models.TextField(help_text='Comma separated serial numbers')
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    received_date = models.DateField()
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)
    cost_per_unit = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        unique_together = ['product', 'batch_number']
        ordering = ['-received_date']
        db_table = 'inventory_batchtracking'

    def __str__(self):
        return f"{self.product.item_code} - Batch {self.batch_number}"


class Customer(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('cash', 'Cash'),
        ('credit', 'Credit'),
    ]

    customer_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    mobile = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    vat_number = models.CharField(max_length=50, blank=True)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='cash')
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['customer_code']
        db_table = 'sales_customer'

    def __str__(self):
        return f"{self.customer_code} - {self.name}"

from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models
from django.utils import timezone


class Ticket(models.Model):
    # ---------------------------------------------------------
    # Status
    # ---------------------------------------------------------

    OPEN = "OPEN"
    INSPECTION = "INSPECTION"
    ESTIMATE_PENDING = "ESTIMATE_PENDING"
    ESTIMATE_APPROVED = "ESTIMATE_APPROVED"
    ESTIMATE_REJECTED = "ESTIMATE_REJECTED"
    REPAIR_IN_PROGRESS = "REPAIR_IN_PROGRESS"
    READY_FOR_DELIVERY = "READY_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CLOSED = "CLOSED"

    STATUS_CHOICES = [
        (OPEN, "Open"),
        (INSPECTION, "Inspection"),
        (ESTIMATE_PENDING, "Estimate Pending"),
        (ESTIMATE_APPROVED, "Estimate Approved"),
        (ESTIMATE_REJECTED, "Estimate Rejected"),
        (REPAIR_IN_PROGRESS, "Repair In Progress"),
        (READY_FOR_DELIVERY, "Ready For Delivery"),
        (DELIVERED, "Delivered"),
        (CLOSED, "Closed"),
    ]

    # ---------------------------------------------------------
    # Priority
    # ---------------------------------------------------------

    NORMAL = "NORMAL"
    URGENT = "URGENT"

    PRIORITY_CHOICES = [
        (NORMAL, "Normal"),
        (URGENT, "Urgent"),
    ]

    # ---------------------------------------------------------
    # Device Type
    # ---------------------------------------------------------

    LAPTOP = "Laptop"
    DESKTOP = "Desktop"
    PRINTER = "Printer"
    MONITOR = "Monitor"
    UPS = "UPS"
    ROUTER = "Router"
    CCTV = "CCTV"
    OTHER = "Other"

    DEVICE_TYPES = [
        (LAPTOP, "Laptop"),
        (DESKTOP, "Desktop"),
        (PRINTER, "Printer"),
        (MONITOR, "Monitor"),
        (UPS, "UPS"),
        (ROUTER, "Router"),
        (CCTV, "CCTV"),
        (OTHER, "Other"),
    ]

    # ---------------------------------------------------------
    # Fields
    # ---------------------------------------------------------

    ticket_number = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
    )

    customer = models.ForeignKey(
        "Customer",
        on_delete=models.PROTECT,
        related_name="tickets",
    )

    device_type = models.CharField(
        max_length=30,
        choices=DEVICE_TYPES,
    )

    brand = models.CharField(
        max_length=100,
        blank=True,
    )

    model = models.CharField(
        max_length=150,
        blank=True,
    )

    serial_number = models.CharField(
        max_length=150,
        blank=True,
    )

    accessories = models.TextField(
        blank=True,
        help_text="Adapter, Battery, Mouse, Bag, etc.",
    )

    issue_description = models.TextField(
        validators=[MinLengthValidator(5)],
    )

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=NORMAL,
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=OPEN,
    )

    estimated_delivery = models.DateField(
        null=True,
        blank=True,
    )

    remarks = models.TextField(
        blank=True,
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tickets",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "service_ticket"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ticket_number} - {self.customer.name}"

    @property
    def is_closed(self):
        return self.status == self.CLOSED

    @property
    def can_generate_service_report(self):
        return self.status in [
            self.OPEN,
            self.INSPECTION,
            self.ESTIMATE_PENDING,
            self.ESTIMATE_APPROVED,
        ]

    @property
    def can_generate_invoice(self):
        return self.status in [
            self.READY_FOR_DELIVERY,
            self.DELIVERED,
        ]

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            today = timezone.localdate()

            prefix = today.strftime("TKT%y%m%d")

            last_ticket = (
                Ticket.objects.filter(ticket_number__startswith=prefix)
                .order_by("-ticket_number")
                .first()
            )

            if last_ticket:
                last_number = int(last_ticket.ticket_number[-4:])
                number = last_number + 1
            else:
                number = 1

            self.ticket_number = f"{prefix}{number:04d}"

        super().save(*args, **kwargs)


class ServiceReport(models.Model):

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"

    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (SUBMITTED, "Submitted"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (COMPLETED, "Completed"),
    ]

    report_number = models.CharField(
        max_length=30,
        unique=True,
    )

    ticket = models.OneToOneField(
        "Ticket",
        on_delete=models.CASCADE,
        related_name="service_report",
    )

    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="service_reports",
    )

    inspection_notes = models.TextField(
        blank=True,
    )

    problem_found = models.TextField(
        blank=True,
    )

    repair_solution = models.TextField(
        blank=True,
    )

    labor_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    other_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    remarks = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT,
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_service_reports",
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_service_reports",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "service_report"
        ordering = ["-created_at"]

    def __str__(self):
        return self.report_number

    @property
    def parts_total(self):

        total = Decimal("0.00")

        for item in self.items.all():
            total += item.line_total

        return total

    @property
    def estimated_total(self):

        return (
            self.parts_total
            + self.labor_charge
            + self.other_charge
        )

class ServiceReportItem(models.Model):

    service_report = models.ForeignKey(
        ServiceReport,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
    )

    item_code = models.CharField(max_length=100)

    item_name = models.CharField(max_length=255)

    specification = models.CharField(max_length=255, blank=True)

    quantity = models.PositiveIntegerField(default=1)

    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=13)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    estimated_rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    remarks = models.CharField(
        max_length=255,
        blank=True,
    )

    class Meta:
        db_table = "service_report_item"

    def save(self, *args, **kwargs):

        base_amount = self.quantity * self.estimated_rate

        self.tax_amount = (
            base_amount * self.tax_percentage / Decimal("100")
        )

        self.line_total = base_amount + self.tax_amount

        if self.product:
            self.item_code = self.product.item_code
            self.item_name = self.product.item_name
            self.specification = self.product.specification

        super().save(*args, **kwargs)


class SalesInvoice(models.Model):

    SALE_TYPE_CHOICES = [
        ("DIRECT", "Direct Sale"),
        ("REPAIR", "Repair Work"),
        ("RETURN", "Sale Return"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("confirmed", "Confirmed"),
        ("delivered", "Delivered"),
        ("invoiced", "Invoiced"),
    ]

    PAYMENT_MODE_CHOICES = [
        ("cash", "Cash"),
        ("upi", "UPI"),
        ("card", "Card"),
        ("credit", "Credit"),
    ]

    payment_mode = models.CharField(
        max_length=20,
        choices=PAYMENT_MODE_CHOICES,
        default="cash",
    )

    invoice_number = models.CharField(
        max_length=100,
        unique=True,
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="invoices",
    )

    invoice_date = models.DateField()

    delivery_date = models.DateField(
        null=True,
        blank=True,
    )

    sale_type = models.CharField(
        max_length=20,
        choices=SALE_TYPE_CHOICES,
        default="DIRECT",
    )

    # Only used when sale_type == REPAIR
    service_report = models.OneToOneField(
        "ServiceReport",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales_invoice",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    discount_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    grand_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    notes = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-invoice_date"]
        db_table = "sales_salesinvoice"

    def __str__(self):
        return f"{self.invoice_number} - {self.customer.name}"


class SalesLineItem(models.Model):
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name='items')
    item_code = models.CharField(max_length=100)
    item_name = models.CharField(max_length=255)
    specification = models.CharField(max_length=255, blank=True)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    rate = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=13)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    serial_number = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-invoice__invoice_date']
        db_table = 'sales_saleslineitem'

    def __str__(self):
        return f"{self.item_code} - {self.item_name}"


class Warehouse(models.Model):
    WAREHOUSE_TYPE_CHOICES = [
        ('main', 'Main Warehouse'),
        ('repair', 'Repair Warehouse'),
    ]

    warehouse_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    warehouse_type = models.CharField(max_length=20, choices=WAREHOUSE_TYPE_CHOICES)
    location = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    manager_name = models.CharField(max_length=255, blank=True)
    manager_contact = models.CharField(max_length=20, blank=True)
    capacity = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['warehouse_code']
        db_table = 'warehouse_warehouse'

    def __str__(self):
        return f"{self.warehouse_code} - {self.name}"


class WarehouseStock(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stocks')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='warehouse_stocks')
    quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['warehouse', 'product']
        verbose_name_plural = 'Warehouse Stock'
        db_table = 'warehouse_warehousestock'

    def __str__(self):
        return f"{self.warehouse.name} - {self.product.item_code}: {self.quantity} units"


class DeliveryChallan(models.Model):
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('sent', 'Sent'),
        ('received', 'Received'),
    ]

    challan_number = models.CharField(max_length=100, unique=True)
    from_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='sent_challans')
    to_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='received_challans')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')
    created_date = models.DateField(auto_now_add=True)
    sent_date = models.DateField(null=True, blank=True)
    received_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_date']
        db_table = 'warehouse_deliverychallan'

    def __str__(self):
        return f"{self.challan_number}"


class ChallanLineItem(models.Model):
    challan = models.ForeignKey(DeliveryChallan, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    serial_number = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['challan']
        db_table = 'warehouse_challanlineitem'

    def __str__(self):
        return f"{self.product.item_code} - {self.quantity} units"


class FinanceEntry(models.Model):
    ENTRY_TYPE_CHOICES = [
        ('purchase', 'Purchase Cost'),
        ('sale', 'Sale Revenue'),
        ('expense', 'Expense'),
        ('adjustment', 'Adjustment'),
    ]

    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES)
    reference_id = models.CharField(max_length=100)
    reference_type = models.CharField(max_length=50)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name_plural = 'Finance Entries'
        db_table = 'finance_financeentry'

    def __str__(self):
        return f"{self.get_entry_type_display()} - {self.reference_id}"


class CostTracking(models.Model):
    product_code = models.CharField(max_length=100)
    product_name = models.CharField(max_length=255)
    purchase_invoice_number = models.CharField(max_length=100)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    unit_cost = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    date = models.DateField()
    narration = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']
        verbose_name_plural = 'Cost Tracking'
        db_table = 'finance_costtracking'

    def __str__(self):
        return f"{self.product_code} - {self.purchase_invoice_number}"


class InventoryValuation(models.Model):
    VALUATION_METHOD_CHOICES = [
        ('fifo', 'FIFO'),
        ('lifo', 'LIFO'),
        ('weighted_avg', 'Weighted Average'),
    ]

    product_code = models.CharField(max_length=100, unique=True)
    product_name = models.CharField(max_length=255)
    quantity_on_hand = models.IntegerField()
    unit_value = models.DecimalField(max_digits=15, decimal_places=2)
    total_value = models.DecimalField(max_digits=15, decimal_places=2)
    valuation_method = models.CharField(max_length=20, choices=VALUATION_METHOD_CHOICES, default='fifo')
    valuation_date = models.DateField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Inventory Valuations'
        db_table = 'finance_inventoryvaluation'

    def __str__(self):
        return f"{self.product_code} - {self.total_value}"


class Report(models.Model):
    REPORT_TYPE_CHOICES = [
        ('purchase_summary', 'Purchase Summary'),
        ('sale_summary', 'Sale Summary'),
        ('inventory', 'Inventory Report'),
        ('financial', 'Financial Report'),
        ('warehouse', 'Warehouse Report'),
    ]

    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPE_CHOICES)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='management_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField()
    end_date = models.DateField()
    file_path = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'reports_report'

    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()})"


class ReportData(models.Model):
    report = models.OneToOneField(Report, on_delete=models.CASCADE, related_name='data')
    data_json = models.JSONField()
    summary = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Report Data'
        db_table = 'reports_reportdata'

    def __str__(self):
        return f"Data for {self.report.name}"


class UserRole(models.Model):
    ROLE_CHOICES = [
        ('superadmin', 'Super Admin'),
        ('seller', 'Seller'),
        ('repairman', 'Repairman'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='management_role')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'User Roles'
        db_table = 'users_userrole'

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

    def is_superadmin(self):
        return self.role == 'superadmin'

    def is_seller(self):
        return self.role == 'seller'

    def is_repairman(self):
        return self.role == 'repairman'

