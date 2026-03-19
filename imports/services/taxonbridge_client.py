"""Thin Django-facing adapter for the external taxonbridge package."""

from functools import lru_cache
from pathlib import Path

from django.conf import settings


class TaxonbridgeUnavailable(RuntimeError):
    """Raised when the external resolver package or its database is unavailable."""


@lru_cache(maxsize=1)
def get_taxonomy_resolver():
    """Return one cached resolver service instance configured from Django settings."""
    try:
        from taxonomy_resolver import TaxonomyResolverService
    except ImportError as exc:
        raise TaxonbridgeUnavailable('taxonbridge is not installed in the active environment.') from exc

    taxonomy_db_path = Path(getattr(settings, 'TAXONOMY_DB_PATH', '')).expanduser()
    if not taxonomy_db_path.exists():
        raise TaxonbridgeUnavailable(f'Taxonomy DB not found: {taxonomy_db_path}')

    cache_db_setting = getattr(settings, 'TAXONOMY_CACHE_DB_PATH', '')
    cache_db_path = Path(cache_db_setting).expanduser() if cache_db_setting else None
    return TaxonomyResolverService(
        taxonomy_db_path=taxonomy_db_path,
        cache_db_path=cache_db_path,
    )


def resolve_taxon_name(name, level=None, *, allow_fuzzy=True):
    """Resolve one taxon name using taxonbridge."""
    from taxonomy_resolver import ResolveRequest

    resolver = get_taxonomy_resolver()
    return resolver.resolve_name(
        ResolveRequest(
            original_name=name,
            provided_level=level or None,
            allow_fuzzy=allow_fuzzy,
        )
    )


def get_lineage_for_taxid(taxid):
    """Return one lineage from root to leaf for a resolved taxid."""
    resolver = get_taxonomy_resolver()
    return resolver.get_lineage(int(taxid))
