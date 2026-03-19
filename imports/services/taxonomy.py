"""Taxonomy persistence helpers used by preview and import flows."""

from database.models import Taxon, TaxonClosure, TaxonName

from .taxonbridge_client import TaxonbridgeUnavailable, get_lineage_for_taxid, resolve_taxon_name


def resolve_taxon(scientific_name, ncbi_taxonomy_id):
    """Resolve a taxon by taxonomy ID first, then by canonical or known names."""
    if ncbi_taxonomy_id is not None:
        taxon = Taxon.objects.filter(ncbi_taxonomy_id=ncbi_taxonomy_id).first()
        if taxon:
            return taxon
    if scientific_name:
        taxon = Taxon.objects.filter(scientific_name__iexact=scientific_name).first()
        if taxon:
            return taxon
        name_match = (
            TaxonName.objects.select_related('taxon')
            .filter(name__iexact=scientific_name)
            .order_by('-is_preferred', 'taxon__scientific_name')
            .first()
        )
        if name_match:
            return name_match.taxon
    return None


def sync_taxon_closure(taxon):
    """Ensure closure rows exist for the taxon and its direct ancestry."""
    TaxonClosure.objects.filter(descendant=taxon).exclude(ancestor=taxon, depth=0).delete()
    TaxonClosure.objects.update_or_create(
        ancestor=taxon,
        descendant=taxon,
        defaults={'depth': 0},
    )
    if not taxon.parent_id:
        return taxon

    parent_paths = TaxonClosure.objects.filter(descendant=taxon.parent).select_related('ancestor')
    for parent_path in parent_paths:
        TaxonClosure.objects.update_or_create(
            ancestor=parent_path.ancestor,
            descendant=taxon,
            defaults={'depth': parent_path.depth + 1},
        )
    return taxon


def upsert_taxon(*, scientific_name, ncbi_taxonomy_id=None, rank='', notes='', parent=None, aliases=None):
    """Create or update one canonical taxon row and maintain its closure rows."""
    taxon = resolve_taxon(scientific_name, ncbi_taxonomy_id)
    if taxon:
        taxon.scientific_name = scientific_name
        taxon.ncbi_taxonomy_id = ncbi_taxonomy_id
        taxon.rank = rank
        taxon.parent = parent
        if notes:
            taxon.notes = notes
        taxon.save(
            update_fields=[
                'scientific_name',
                'ncbi_taxonomy_id',
                'rank',
                'parent',
                'notes',
                'updated_at',
            ]
        )
    else:
        taxon = Taxon.objects.create(
            scientific_name=scientific_name,
            ncbi_taxonomy_id=ncbi_taxonomy_id,
            rank=rank,
            parent=parent,
            notes=notes,
        )

    TaxonName.objects.update_or_create(
        taxon=taxon,
        name=scientific_name,
        name_class=TaxonName.NameClass.SCIENTIFIC,
        defaults={'is_preferred': True},
    )
    for alias in aliases or ():
        if alias and alias.lower() != scientific_name.lower():
            TaxonName.objects.update_or_create(
                taxon=taxon,
                name=alias,
                name_class=TaxonName.NameClass.IMPORTED_AS_WRITTEN,
                defaults={'is_preferred': False},
            )

    return sync_taxon_closure(taxon)


def upsert_taxon_lineage(lineage, *, aliases=None, leaf_notes=''):
    """Upsert a lineage ordered from root to leaf and return the leaf taxon."""
    parent = None
    leaf = None
    for index, node in enumerate(lineage):
        leaf = upsert_taxon(
            scientific_name=node['scientific_name'],
            ncbi_taxonomy_id=node.get('ncbi_taxonomy_id'),
            rank=node.get('rank', ''),
            notes=leaf_notes if index == len(lineage) - 1 else '',
            parent=parent,
            aliases=aliases if index == len(lineage) - 1 else None,
        )
        parent = leaf
    return leaf


def _lineage_payload_from_taxonbridge(lineage):
    """Convert taxonbridge lineage entries into this app's upsert shape."""
    payload = []
    for entry in lineage:
        if isinstance(entry, dict):
            payload.append(
                {
                    'ncbi_taxonomy_id': entry['taxid'],
                    'scientific_name': entry['name'],
                    'rank': entry['rank'],
                }
            )
        else:
            payload.append(
                {
                    'ncbi_taxonomy_id': entry.taxid,
                    'scientific_name': entry.name,
                    'rank': entry.rank,
                }
            )
    return payload


def _lineage_payload_from_local_taxon(taxon):
    lineage = (
        TaxonClosure.objects.filter(descendant=taxon)
        .select_related('ancestor')
        .order_by('-depth')
    )
    return [
        {
            'ncbi_taxonomy_id': path.ancestor.ncbi_taxonomy_id,
            'scientific_name': path.ancestor.scientific_name,
            'rank': path.ancestor.rank,
        }
        for path in lineage
    ]


def _provided_name_matches_taxid(scientific_name, ncbi_taxonomy_id, rank=''):
    """Return whether the provided name cleanly resolves back to the same taxid."""
    if not scientific_name:
        return True

    try:
        result = resolve_taxon_name(scientific_name, level=rank or None, allow_fuzzy=True)
    except Exception:
        return False

    return (
        not result.review_required
        and result.matched_taxid is not None
        and int(result.matched_taxid) == int(ncbi_taxonomy_id)
    )


def build_taxon_preview_payload(*, scientific_name, ncbi_taxonomy_id=None, rank='', notes='', aliases=None):
    """Return the preview-time canonical taxon payload used by CSV and workbook imports."""
    alias_names = [alias for alias in (aliases or ()) if alias]
    if scientific_name:
        alias_names.append(scientific_name)
    alias_names = list(dict.fromkeys(alias_names))

    lineage = []
    resolution_status = 'preview_fallback_local'
    resolution_message = 'Preview fallback local'
    review_required = True
    resolver_source = 'local_fallback'

    try:
        if ncbi_taxonomy_id is not None and _provided_name_matches_taxid(scientific_name, ncbi_taxonomy_id, rank=rank):
            lineage = get_lineage_for_taxid(ncbi_taxonomy_id)
            resolution_status = 'resolved_from_taxid'
            resolution_message = 'Resolved from provided taxid'
            review_required = False
            resolver_source = 'taxonbridge_taxid'

        if not lineage and scientific_name:
            result = resolve_taxon_name(scientific_name, level=rank or None, allow_fuzzy=True)
            resolution_status = result.status.value
            resolution_message = result.status.value.replace('_', ' ')
            review_required = result.review_required
            resolver_source = 'taxonbridge_name'
            if not result.review_required and result.matched_taxid is not None:
                lineage = result.lineage or get_lineage_for_taxid(result.matched_taxid)
    except TaxonbridgeUnavailable as exc:
        resolution_status = 'taxonbridge_unavailable'
        resolution_message = str(exc)
        resolver_source = 'local_fallback'
        review_required = True
    except Exception as exc:
        resolution_status = 'taxonbridge_error'
        resolution_message = str(exc) or exc.__class__.__name__
        resolver_source = 'local_fallback'
        review_required = True

    if lineage:
        payload = _lineage_payload_from_taxonbridge(lineage)
        leaf = payload[-1]
        canonical_name = leaf['scientific_name']
        canonical_rank = leaf.get('rank', '') or rank
        canonical_taxid = leaf.get('ncbi_taxonomy_id')
    else:
        local_taxon = resolve_taxon(scientific_name, ncbi_taxonomy_id)
        if local_taxon:
            payload = _lineage_payload_from_local_taxon(local_taxon)
            canonical_name = local_taxon.scientific_name
            canonical_rank = rank or local_taxon.rank
            canonical_taxid = local_taxon.ncbi_taxonomy_id
            resolution_status = 'resolved_local_taxon'
            resolution_message = 'Resolved from existing local taxonomy'
            review_required = False
            resolver_source = 'local_fallback'
        else:
            payload = [
                {
                    'ncbi_taxonomy_id': ncbi_taxonomy_id,
                    'scientific_name': scientific_name,
                    'rank': rank,
                }
            ]
            canonical_name = scientific_name
            canonical_rank = rank
            canonical_taxid = ncbi_taxonomy_id

    effective_aliases = [name for name in alias_names if name and name.lower() != (canonical_name or '').lower()]
    lineage_summary = ' > '.join(node['scientific_name'] for node in payload if node.get('scientific_name'))

    return {
        'scientific_name': canonical_name,
        'ncbi_taxonomy_id': canonical_taxid,
        'rank': canonical_rank,
        'notes': notes,
        'aliases': effective_aliases,
        'lineage': payload,
        'lineage_summary': lineage_summary,
        'resolution_status': resolution_status,
        'resolution_message': resolution_message,
        'review_required': review_required,
        'resolver_source': resolver_source,
    }


def resolve_and_upsert_taxon(*, scientific_name, ncbi_taxonomy_id=None, rank='', notes='', aliases=None):
    """Resolve with taxonbridge when available, then persist full lineage locally.

    Falls back to a direct local upsert when taxonbridge is unavailable or when
    the resolver result still requires human review.
    """

    alias_names = [alias for alias in (aliases or ()) if alias]
    if scientific_name:
        alias_names.append(scientific_name)
    alias_names = list(dict.fromkeys(alias_names))

    try:
        lineage = []
        if ncbi_taxonomy_id is not None:
            if _provided_name_matches_taxid(scientific_name, ncbi_taxonomy_id, rank=rank):
                lineage = get_lineage_for_taxid(ncbi_taxonomy_id)

        if not lineage and scientific_name:
            result = resolve_taxon_name(scientific_name, level=rank or None, allow_fuzzy=True)
            if not result.review_required and result.matched_taxid is not None:
                lineage = result.lineage or get_lineage_for_taxid(result.matched_taxid)

        if lineage:
            return upsert_taxon_lineage(
                _lineage_payload_from_taxonbridge(lineage),
                aliases=alias_names,
                leaf_notes=notes,
            )
    except TaxonbridgeUnavailable:
        pass
    except Exception:
        pass

    return upsert_taxon(
        scientific_name=scientific_name,
        ncbi_taxonomy_id=ncbi_taxonomy_id,
        rank=rank,
        notes=notes,
        aliases=alias_names,
    )
