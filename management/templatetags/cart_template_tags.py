from django import template
from management.models import Order

register = template.Library()
#this cart_item_count is for pagination
@register.filter
def cart_item_count(user):
    if user.is_authenticated:
        qs = Order.objects.filter(user=user,ordered=False)
        if qs.exists():
            return qs[0].items.count()
    return 0