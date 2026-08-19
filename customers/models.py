from django.db import models


class Customer(models.Model):
    """A customer/account that Gmail, Chat, and Tasks activity is grouped under."""

    name = models.CharField(max_length=255, blank=True)
    company_domain = models.CharField(max_length=255, blank=True, db_index=True)
    primary_email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "company_domain"]

    def __str__(self):
        return self.name or self.company_domain or self.primary_email or f"Customer #{self.pk}"


class CustomerEmailAlias(models.Model):
    """One known email address belonging to a Customer.

    A customer accumulates aliases as new contacts from the same company (or
    the same personal address) are seen across Gmail/Chat/Tasks.
    """

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="email_aliases")
    email = models.EmailField(unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email
