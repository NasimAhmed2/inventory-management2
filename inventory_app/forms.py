from django import forms
from .models import Product
from .constants import CATEGORY_HSN


class ProductForm(forms.ModelForm):
    category = forms.ChoiceField(
        choices=[("", "Select Category")] + [(k, k) for k in CATEGORY_HSN.keys()],
        widget=forms.Select(attrs={"class": "form-select"})
    )

    hs_code = forms.ChoiceField(
        choices=[("", "Select HSN")],
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = Product
        fields = [
            "item_code",
            "item_name",
            "category",
            "hs_code",
            "specification",
            "unit_of_measure",
            "reorder_level",
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