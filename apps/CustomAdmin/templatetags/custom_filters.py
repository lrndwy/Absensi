from django import template

register = template.Library()

@register.filter
def jam(value):
    return value // 60

@register.filter
def menit(value):
    return value % 60 
