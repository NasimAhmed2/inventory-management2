from django import forms
from .models import Product
from .models import Product_Categories

CATEGORY_HSN = {}

for entry in Product_Categories.objects.all():
    CATEGORY_HSN.setdefault(entry.category_name, []).append(
        (entry.hsn_code, entry.description)
    )


class ProductForm(forms.ModelForm):
    category = forms.ChoiceField(
        choices=[("", "Select Category")] + [(k, k) for k in CATEGORY_HSN.keys()],
        widget=forms.Select(attrs={"class": "form-select"})
    )

    hs_code = forms.ChoiceField(
        choices=[("", "Select HSN")],
        widget=forms.Select(attrs={"class": "form-select"})
    )

    opening_qty = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "min": 0,
        })
    )

    purchase_price = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        max_digits=15,
        initial=0,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "min": 0,
            "step": "0.01",
        })
    )

    class Meta:
        model = Product
        fields = [
            "item_code",
            "item_name",
            "category",
            "hs_code",
            "brand",
            "model_number",
            "specification",
            "unit_of_measure",
            "reorder_level",
            "opening_qty",
            "purchase_price",
            "stock_tracking",
        ]

        widgets = {
            "item_code": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Item Code"
            }),
            "item_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Item Name"
            }),
            "specification": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Specification"
            }),
            "unit_of_measure": forms.Select(
                choices=[
                    ("pcs", "Pieces"),
                    ("nos", "Numbers"),
                    ("box", "Box"),
                    ("set", "Set"),
                    ("kg", "Kg"),
                    ("ltr", "Litre"),
                    ("mtr", "Meter"),
                ],
                attrs={"class": "form-select"}
            ),
            "reorder_level": forms.NumberInput(attrs={
                "class": "form-control",
                "min": 0
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Populate HSN dropdown when editing an existing product
        if self.instance and self.instance.pk:
            category = self.instance.category

            if category in CATEGORY_HSN:
                self.fields["hs_code"].choices = [
                    ("", "Select HSN")
                ] + [
                    (code, f"{code} - {name}")
                    for code, name in CATEGORY_HSN[category]
                ]

        # Populate HSN dropdown after form validation failure
        elif "category" in self.data:
            category = self.data.get("category")

            if category in CATEGORY_HSN:
                self.fields["hs_code"].choices = [
                    ("", "Select HSN")
                ] + [
                    (code, f"{code} - {name}")
                    for code, name in CATEGORY_HSN[category]
                ]

    def clean_item_code(self):
        return self.cleaned_data["item_code"].strip().upper()

    def clean_item_name(self):
        return self.cleaned_data["item_name"].strip()

    def clean_specification(self):
        return self.cleaned_data.get("specification", "").strip()