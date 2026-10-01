from django import template

register = template.Library()

# Bootstrap colour for each status badge.
STATUS_COLOURS = {
    "booked": "secondary",
    "pickup_assigned": "info",
    "picked_up": "info",
    "at_store": "primary",
    "tagged": "primary",
    "in_cleaning": "primary",
    "ready": "warning",
    "out_for_delivery": "warning",
    "delivered": "success",
    "cancelled": "danger",
}


@register.filter
def status_colour(status):
    return STATUS_COLOURS.get(str(status), "secondary")
