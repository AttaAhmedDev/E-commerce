from django.contrib import admin
from .models import Category, Brand, Product, ProductVariant, Inventory


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "is_active", "created_at"]
    list_filter = ["is_active", "parent"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "brand", "is_active", "created_at"]
    list_filter = ["is_active", "category", "brand"]
    search_fields = ["name", "description"]
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ["category", "brand"]


class InventoryInline(admin.StackedInline):
    model = Inventory
    extra = 0


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ["sku", "product", "size", "color", "price", "is_active"]
    list_filter = ["is_active", "product__category"]
    search_fields = ["sku", "product__name"]
    autocomplete_fields = ["product"]
    inlines = [InventoryInline]
