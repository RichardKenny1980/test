from django.contrib import admin

from .models import Customer, CustomerEmailAlias


class CustomerEmailAliasInline(admin.TabularInline):
    model = CustomerEmailAlias
    extra = 0


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "company_domain", "primary_email", "updated_at")
    search_fields = ("name", "company_domain", "primary_email")
    inlines = [CustomerEmailAliasInline]


@admin.register(CustomerEmailAlias)
class CustomerEmailAliasAdmin(admin.ModelAdmin):
    list_display = ("email", "customer")
    search_fields = ("email",)
