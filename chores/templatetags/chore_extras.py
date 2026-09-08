from django import template

register = template.Library()


@register.filter
def percent(value):
    """Render a 0..1 share as a whole-number percentage for display and bar widths."""
    try:
        return round(float(value) * 100)
    except (TypeError, ValueError):
        return 0
