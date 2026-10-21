import re
from .models import Product, Vendor, PurchaseInvoice

CATEGORY_PREFIXES = {
    "Memory": "RAM",
    "Storage": "STO",
    "Processor": "CPU",
    "Motherboard": "MB",
    "Graphics Card": "GPU",
    "Keyboard": "KEY",
    "Mouse": "MOU",
}

def generate_item_code(category):
    prefix = CATEGORY_PREFIXES.get(
        category,
        "".join(word[0] for word in category.split()).upper()[:4]
    )

    last_product = Product.objects.filter(
        item_code__startswith=f"{prefix}-"
    ).order_by("-id").first()

    if last_product:
        try:
            last_number = int(last_product.item_code.split("-")[-1])
        except ValueError:
            last_number = 0
    else:
        last_number = 0

    return f"{prefix}-{last_number + 1:04d}"

def generate_vendor_code():
    last_vendor = Vendor.objects.order_by('-id').first()
    if not last_vendor or not last_vendor.vendor_code:
        return "MI001"

    match = re.search(r'(\d+)$', last_vendor.vendor_code.lower())
    if match:
        number = int(match.group(1)) + 1
        return f"MI{number:03d}"
    return "MI001"

def generate_invoice_number(invoice_date):
    prefix = invoice_date.strftime("PI%Y%m%d")
    today_invoices = PurchaseInvoice.objects.filter(invoice_number__startswith=prefix).count()
    return f"{prefix}{today_invoices + 1:03d}"