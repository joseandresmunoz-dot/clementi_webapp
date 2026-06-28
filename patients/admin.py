from django.contrib import admin

from patients.models import Category, ClinicalTimelineEntry, Lead, Order, PatientProfile, Product, ProductImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ("name", "order", "is_active", "created_at")
    list_editable = ("order", "is_active")


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "is_cover", "order")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ("name", "category", "price", "discount_price", "is_on_sale", "is_featured", "is_curso", "is_active", "order")
    list_editable = ("price", "discount_price", "is_on_sale", "is_featured", "is_curso", "is_active", "order")
    list_filter = ("category", "is_curso", "is_on_sale", "is_featured", "is_active")
    inlines = [ProductImageInline]


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("product", "is_cover", "order", "created_at")
    list_filter = ("is_cover",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("product", "quantity", "unit_price", "total_price", "customer_name", "status", "created_at")
    list_filter = ("status", "created_at")
    readonly_fields = ("created_at",)


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "is_approved",
        "approved_at",
        "approved_by",
        "phone",
        "locality",
        "date_of_birth",
        "created_at",
    )
    search_fields = ("user__first_name", "user__last_name", "user__email", "phone")
    list_filter = ("is_approved", "created_at", "approved_at")
    readonly_fields = ("id", "created_at", "updated_at", "approved_at", "approved_by")


@admin.register(ClinicalTimelineEntry)
class ClinicalTimelineEntryAdmin(admin.ModelAdmin):
    list_display = ("patient", "subject", "appointment", "created_by", "created_at")
    search_fields = ("patient__email", "patient__first_name", "patient__last_name", "subject")
    list_filter = ("created_at",)
    readonly_fields = ("id", "created_at")


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "source", "is_subscribed", "created_at")
    search_fields = ("name", "email", "phone")
    list_filter = ("source", "is_subscribed", "created_at")
    readonly_fields = ("created_at",)
