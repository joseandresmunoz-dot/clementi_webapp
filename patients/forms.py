from django import forms

from patients.models import Category, LeadReply, Product


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug", "description", "order", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "category", "name", "slug",
            "price", "discount_price", "promo_label", "is_on_sale",
            "image", "is_active", "is_curso", "is_featured", "order",
            "description", "details",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "details": forms.Textarea(attrs={"rows": 4}),
        }


class LeadReplyForm(forms.ModelForm):
    class Meta:
        model = LeadReply
        fields = ["message"]
        widgets = {
            "message": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Escribí tu respuesta...",
                    "class": "form-control",
                }
            ),
        }
        labels = {
            "message": "Respuesta",
        }
