from django import template


register = template.Library()


@register.filter
def get_item(mapping, key):
    if mapping is None:
        return ''
    return mapping.get(key, '')


def _resolver_bucket(mapping):
    if not mapping:
        return ''
    if not mapping.get('resolution_status'):
        return ''
    if mapping.get('review_required'):
        return 'review'
    if mapping.get('resolver_source') == 'local_fallback':
        return 'fallback'
    return 'auto'


@register.filter
def resolver_bucket(mapping):
    return _resolver_bucket(mapping)


@register.filter
def resolver_label(mapping):
    bucket = _resolver_bucket(mapping)
    if bucket == 'auto':
        return 'Auto-resolved'
    if bucket == 'review':
        return 'Review required'
    if bucket == 'fallback':
        return 'Fallback local'
    return ''


@register.filter
def resolver_detail(mapping):
    if not mapping:
        return ''
    return mapping.get('resolution_status', '').replace('_', ' ')
