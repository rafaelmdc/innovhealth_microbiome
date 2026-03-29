from database.models import TaxonClosure


GRAPH_GROUPING_CHOICES = (
    ('leaf', 'Leaf'),
    ('species', 'Species'),
    ('genus', 'Genus'),
    ('family', 'Family'),
    ('order', 'Order'),
    ('class', 'Class'),
    ('phylum', 'Phylum'),
)
GRAPH_GROUPING_RANKS = {value for value, _label in GRAPH_GROUPING_CHOICES}
POSITIVE_DIRECTIONS = {'enriched', 'increased'}
NEGATIVE_DIRECTIONS = {'depleted', 'decreased'}


def _disease_label(comparison):
    condition = (comparison.group_a.condition or '').strip()
    if condition:
        return condition
    return comparison.group_a.name


def _normalize_direction(direction):
    if direction in POSITIVE_DIRECTIONS:
        return 'positive'
    if direction in NEGATIVE_DIRECTIONS:
        return 'negative'
    return ''


def _node_sort_key(nodes_by_id, node_id):
    node = nodes_by_id[node_id]
    return (-len(node['neighbors']), node['label'].lower())


def _build_positions(nodes_by_id, *, x_position, y_step=108, y_start=96):
    positions = {}
    for index, node_id in enumerate(
        sorted(nodes_by_id, key=lambda current_id: _node_sort_key(nodes_by_id, current_id))
    ):
        positions[node_id] = {'x': x_position, 'y': y_start + (index * y_step)}
    return positions


def _build_disease_positions(disease_nodes, taxon_positions, *, x_position, fallback_step=120, y_start=96):
    def disease_sort_key(node_id):
        neighbor_positions = sorted(
            taxon_positions[neighbor_id]['y']
            for neighbor_id in disease_nodes[node_id]['neighbors']
            if neighbor_id in taxon_positions
        )
        if neighbor_positions:
            midpoint = sum(neighbor_positions) / len(neighbor_positions)
        else:
            midpoint = 0
        return (midpoint, -len(disease_nodes[node_id]['neighbors']), disease_nodes[node_id]['label'].lower())

    positions = {}
    previous_node_id = None
    for index, node_id in enumerate(sorted(disease_nodes, key=disease_sort_key)):
        neighbor_positions = sorted(
            taxon_positions[neighbor_id]['y']
            for neighbor_id in disease_nodes[node_id]['neighbors']
            if neighbor_id in taxon_positions
        )
        preferred_y = sum(neighbor_positions) / len(neighbor_positions) if neighbor_positions else y_start + (index * fallback_step)
        minimum_y = y_start if index == 0 else positions[previous_node_id]['y'] + fallback_step
        y_position = max(preferred_y, minimum_y)
        positions[node_id] = {'x': x_position, 'y': y_position}
        previous_node_id = node_id
    return positions


def _resolve_grouped_taxa(findings, grouping_rank):
    if grouping_rank not in GRAPH_GROUPING_RANKS or grouping_rank == 'leaf':
        return {finding.pk: finding.taxon for finding in findings}

    descendant_ids = {finding.taxon_id for finding in findings}
    ancestor_paths = (
        TaxonClosure.objects.filter(
            descendant_id__in=descendant_ids,
            ancestor__rank=grouping_rank,
        )
        .select_related('ancestor')
        .order_by('descendant_id', 'depth')
    )

    grouped_by_descendant = {}
    for path in ancestor_paths:
        grouped_by_descendant.setdefault(path.descendant_id, path.ancestor)

    return {
        finding.pk: grouped_by_descendant.get(finding.taxon_id)
        for finding in findings
    }


def build_directional_taxon_network(findings, *, grouping_rank='leaf', minimum_support=1, pattern_filter='all'):
    grouping_rank = grouping_rank if grouping_rank in GRAPH_GROUPING_RANKS else 'leaf'
    pattern_filter = pattern_filter if pattern_filter in {'all', 'same_direction', 'opposite_direction', 'mixed'} else 'all'
    try:
        minimum_support = max(int(minimum_support), 1)
    except (TypeError, ValueError):
        minimum_support = 1

    findings = list(findings)
    grouped_taxa = _resolve_grouped_taxa(findings, grouping_rank)
    skipped_rollup_count = 0
    per_comparison = {}

    for finding in findings:
        grouped_taxon = grouped_taxa.get(finding.pk)
        if grouped_taxon is None:
            skipped_rollup_count += 1
            continue

        normalized_direction = _normalize_direction(finding.direction)
        if not normalized_direction:
            continue

        comparison_bucket = per_comparison.setdefault(
            finding.comparison_id,
            {
                'comparison': finding.comparison,
                'items': {},
            },
        )
        item_key = (grouped_taxon.pk, normalized_direction)
        item = comparison_bucket['items'].setdefault(
            item_key,
            {
                'taxon': grouped_taxon,
                'direction': normalized_direction,
                'leaf_taxon_ids': set(),
                'sources': set(),
            },
        )
        item['leaf_taxon_ids'].add(finding.taxon_id)
        if finding.source:
            item['sources'].add(finding.source)

    node_map = {}
    edge_map = {}
    total_support_count = 0

    for comparison_data in per_comparison.values():
        comparison = comparison_data['comparison']
        unique_items = sorted(
            comparison_data['items'].values(),
            key=lambda item: (item['taxon'].scientific_name.lower(), item['direction']),
        )
        comparison_pair_map = {}
        for index, left_item in enumerate(unique_items):
            for right_item in unique_items[index + 1:]:
                if left_item['taxon'].pk == right_item['taxon'].pk:
                    continue

                pair_taxa = sorted(
                    [left_item['taxon'], right_item['taxon']],
                    key=lambda taxon: (taxon.pk, taxon.scientific_name.lower()),
                )
                source_taxon, target_taxon = pair_taxa
                edge_key = (source_taxon.pk, target_taxon.pk)
                pair_pattern = (
                    'same_direction'
                    if left_item['direction'] == right_item['direction']
                    else 'opposite_direction'
                )
                comparison_pair = comparison_pair_map.setdefault(
                    edge_key,
                    {
                        'same_direction': False,
                        'opposite_direction': False,
                        'source_labels': set(),
                        'leaf_taxon_ids': set(),
                    },
                )
                comparison_pair[pair_pattern] = True
                comparison_pair['source_labels'].update(left_item['sources'])
                comparison_pair['source_labels'].update(right_item['sources'])
                comparison_pair['leaf_taxon_ids'].update(left_item['leaf_taxon_ids'])
                comparison_pair['leaf_taxon_ids'].update(right_item['leaf_taxon_ids'])

        disease_label = _disease_label(comparison)
        for edge_key, comparison_pair in comparison_pair_map.items():
            source_taxon_id, target_taxon_id = edge_key
            source_taxon = next(
                item['taxon']
                for item in unique_items
                if item['taxon'].pk == source_taxon_id
            )
            target_taxon = next(
                item['taxon']
                for item in unique_items
                if item['taxon'].pk == target_taxon_id
            )
            edge = edge_map.setdefault(
                edge_key,
                {
                    'source_taxon': source_taxon,
                    'target_taxon': target_taxon,
                    'same_direction_count': 0,
                    'opposite_direction_count': 0,
                    'study_ids': set(),
                    'source_labels': set(),
                    'comparison_labels': set(),
                    'disease_labels': set(),
                    'comparison_ids': set(),
                    'leaf_taxon_ids': set(),
                },
            )

            if comparison_pair['same_direction']:
                edge['same_direction_count'] += 1
                total_support_count += 1
            if comparison_pair['opposite_direction']:
                edge['opposite_direction_count'] += 1
                total_support_count += 1
            edge['study_ids'].add(comparison.study_id)
            edge['comparison_ids'].add(comparison.pk)
            if comparison.label:
                edge['comparison_labels'].add(comparison.label)
            if disease_label:
                edge['disease_labels'].add(disease_label)
            edge['source_labels'].update(comparison_pair['source_labels'])
            edge['leaf_taxon_ids'].update(comparison_pair['leaf_taxon_ids'])

    filtered_edges = []
    for edge in edge_map.values():
        total_support = edge['same_direction_count'] + edge['opposite_direction_count']
        if total_support < minimum_support:
            continue

        if edge['same_direction_count'] and edge['opposite_direction_count']:
            dominant_pattern = (
                'mixed'
                if edge['same_direction_count'] == edge['opposite_direction_count']
                else (
                    'same_direction'
                    if edge['same_direction_count'] > edge['opposite_direction_count']
                    else 'opposite_direction'
                )
            )
        elif edge['same_direction_count']:
            dominant_pattern = 'same_direction'
        else:
            dominant_pattern = 'opposite_direction'

        if pattern_filter != 'all' and dominant_pattern != pattern_filter:
            continue

        source_id = f'taxon-{edge["source_taxon"].pk}'
        target_id = f'taxon-{edge["target_taxon"].pk}'

        for taxon in (edge['source_taxon'], edge['target_taxon']):
            node_id = f'taxon-{taxon.pk}'
            node = node_map.setdefault(
                node_id,
                {
                    'id': node_id,
                    'label': taxon.scientific_name,
                    'node_type': 'taxon',
                    'taxon_pk': taxon.pk,
                    'rank': taxon.rank,
                    'taxonomy_id': taxon.ncbi_taxonomy_id,
                    'grouping_rank': grouping_rank,
                    'neighbors': set(),
                    'study_ids': set(),
                    'leaf_taxon_ids': set(),
                },
            )
            node['study_ids'].update(edge['study_ids'])
            node['leaf_taxon_ids'].update(edge['leaf_taxon_ids'])

        node_map[source_id]['neighbors'].add(target_id)
        node_map[target_id]['neighbors'].add(source_id)

        filtered_edges.append(
            {
                'data': {
                    'id': f'{source_id}-{target_id}',
                    'source': source_id,
                    'target': target_id,
                    'source_label': edge['source_taxon'].scientific_name,
                    'target_label': edge['target_taxon'].scientific_name,
                    'dominant_pattern': dominant_pattern,
                    'same_direction_count': edge['same_direction_count'],
                    'opposite_direction_count': edge['opposite_direction_count'],
                    'total_support': total_support,
                    'comparison_count': len(edge['comparison_ids']),
                    'study_count': len(edge['study_ids']),
                    'source_count': len(edge['source_labels']),
                    'comparison_labels': ', '.join(sorted(edge['comparison_labels'])),
                    'disease_labels': ', '.join(sorted(edge['disease_labels'])),
                    'leaf_taxon_count': len(edge['leaf_taxon_ids']),
                }
            }
        )

    nodes = []
    for attrs in node_map.values():
        nodes.append(
            {
                'data': {
                    'id': attrs['id'],
                    'label': attrs['label'],
                    'node_type': attrs['node_type'],
                    'taxon_pk': attrs['taxon_pk'],
                    'rank': attrs['rank'],
                    'taxonomy_id': attrs['taxonomy_id'],
                    'grouping_rank': attrs['grouping_rank'],
                    'degree': len(attrs['neighbors']),
                    'study_count': len(attrs['study_ids']),
                    'leaf_taxon_count': len(attrs['leaf_taxon_ids']),
                    'group': 'taxon',
                }
            }
        )

    nodes.sort(key=lambda item: item['data']['label'].lower())
    filtered_edges.sort(key=lambda item: (item['data']['source_label'].lower(), item['data']['target_label'].lower()))

    same_direction_edge_count = sum(1 for edge in filtered_edges if edge['data']['dominant_pattern'] == 'same_direction')
    opposite_direction_edge_count = sum(1 for edge in filtered_edges if edge['data']['dominant_pattern'] == 'opposite_direction')
    mixed_edge_count = sum(1 for edge in filtered_edges if edge['data']['dominant_pattern'] == 'mixed')

    return {
        'nodes': nodes,
        'edges': filtered_edges,
        'summary': {
            'node_count': len(nodes),
            'edge_count': len(filtered_edges),
            'taxon_count': len(nodes),
            'study_count': len({study_id for node in node_map.values() for study_id in node['study_ids']}),
            'grouping_rank': grouping_rank,
            'skipped_rollup_count': skipped_rollup_count,
            'minimum_support': minimum_support,
            'pattern_filter': pattern_filter,
            'same_direction_edge_count': same_direction_edge_count,
            'opposite_direction_edge_count': opposite_direction_edge_count,
            'mixed_edge_count': mixed_edge_count,
            'total_support_count': sum(edge['data']['total_support'] for edge in filtered_edges),
            'comparison_support_count': total_support_count,
        },
    }


def build_disease_graph(findings, *, grouping_rank='leaf'):
    grouping_rank = grouping_rank if grouping_rank in GRAPH_GROUPING_RANKS else 'leaf'
    findings = list(findings)
    grouped_taxa = _resolve_grouped_taxa(findings, grouping_rank)
    skipped_rollup_count = 0

    disease_nodes = {}
    taxon_nodes = {}
    edge_map = {}
    unique_grouped_taxon_ids = set()

    for finding in findings:
        grouped_taxon = grouped_taxa.get(finding.pk)
        if grouped_taxon is None:
            skipped_rollup_count += 1
            continue

        comparison = finding.comparison
        disease_label = _disease_label(comparison)
        disease_node_id = f'disease-{disease_label.lower()}'
        direction_column = 'enriched' if finding.direction in {'enriched', 'increased'} else 'depleted'
        taxon_node_id = f'{direction_column}-taxon-{grouped_taxon.pk}'

        disease_node = disease_nodes.setdefault(
            disease_node_id,
            {
                'id': disease_node_id,
                'label': disease_label,
                'node_type': 'disease',
                'study_ids': set(),
                'neighbors': set(),
                'comparison_labels': set(),
                'group_names': set(),
            },
        )
        disease_node['study_ids'].add(comparison.study_id)
        disease_node['neighbors'].add(taxon_node_id)
        disease_node['comparison_labels'].add(comparison.label)
        disease_node['group_names'].add(comparison.group_a.name)

        taxon_node = taxon_nodes.setdefault(
            taxon_node_id,
            {
                'id': taxon_node_id,
                'label': grouped_taxon.scientific_name,
                'node_type': 'taxon',
                'taxon_pk': grouped_taxon.pk,
                'column': direction_column,
                'direction': direction_column,
                'rank': grouped_taxon.rank,
                'taxonomy_id': grouped_taxon.ncbi_taxonomy_id,
                'grouping_rank': grouping_rank,
                'study_ids': set(),
                'neighbors': set(),
                'leaf_taxon_ids': set(),
            },
        )
        taxon_node['study_ids'].add(comparison.study_id)
        taxon_node['neighbors'].add(disease_node_id)
        taxon_node['leaf_taxon_ids'].add(finding.taxon_id)
        unique_grouped_taxon_ids.add(grouped_taxon.pk)

        edge_key = (taxon_node_id, disease_node_id)
        edge = edge_map.setdefault(
            edge_key,
            {
                'source': taxon_node_id,
                'target': disease_node_id,
                'column': direction_column,
                'finding_count': 0,
                'study_ids': set(),
                'sources': set(),
                'comparison_labels': set(),
                'leaf_taxon_ids': set(),
            },
        )
        edge['finding_count'] += 1
        edge['study_ids'].add(comparison.study_id)
        edge['sources'].add(finding.source)
        edge['comparison_labels'].add(comparison.label)
        edge['leaf_taxon_ids'].add(finding.taxon_id)

    enriched_positions = _build_positions(
        {node_id: node for node_id, node in taxon_nodes.items() if node['column'] == 'enriched'},
        x_position=180,
    )
    depleted_positions = _build_positions(
        {node_id: node for node_id, node in taxon_nodes.items() if node['column'] == 'depleted'},
        x_position=1060,
    )
    disease_positions = _build_disease_positions(
        disease_nodes,
        {**enriched_positions, **depleted_positions},
        x_position=620,
    )
    node_positions = {**enriched_positions, **disease_positions, **depleted_positions}

    nodes = []
    for attrs in disease_nodes.values():
        nodes.append(
            {
                'data': {
                    'id': attrs['id'],
                    'label': attrs['label'],
                    'node_type': attrs['node_type'],
                    'degree': len(attrs['neighbors']),
                    'study_count': len(attrs['study_ids']),
                    'comparison_count': len(attrs['comparison_labels']),
                    'group': attrs['node_type'],
                    'comparison_labels': ', '.join(sorted(attrs['comparison_labels'])),
                    'group_names': ', '.join(sorted(attrs['group_names'])),
                },
                'position': node_positions[attrs['id']],
            }
        )

    for attrs in taxon_nodes.values():
        nodes.append(
            {
                'data': {
                    'id': attrs['id'],
                    'label': attrs['label'],
                    'node_type': attrs['node_type'],
                    'taxon_pk': attrs['taxon_pk'],
                    'column': attrs['column'],
                    'degree': len(attrs['neighbors']),
                    'study_count': len(attrs['study_ids']),
                    'group': f"{attrs['node_type']}-{attrs['column']}",
                    'rank': attrs['rank'],
                    'taxonomy_id': attrs['taxonomy_id'],
                    'grouping_rank': attrs['grouping_rank'],
                    'leaf_taxon_count': len(attrs['leaf_taxon_ids']),
                },
                'position': node_positions[attrs['id']],
            }
        )

    edges = []
    for edge in edge_map.values():
        source_node = taxon_nodes[edge['source']]
        target_node = disease_nodes[edge['target']]
        edges.append(
            {
                'data': {
                    'id': f"{edge['source']}-{edge['target']}",
                    'source': edge['source'],
                    'target': edge['target'],
                    'source_taxon_pk': source_node['taxon_pk'],
                    'source_label': source_node['label'],
                    'target_label': target_node['label'],
                    'column': edge['column'],
                    'direction_summary': edge['column'],
                    'finding_count': edge['finding_count'],
                    'study_count': len(edge['study_ids']),
                    'source_count': len(edge['sources']),
                    'comparison_labels': ', '.join(sorted(edge['comparison_labels'])),
                    'leaf_taxon_count': len(edge['leaf_taxon_ids']),
                }
            }
        )

    nodes.sort(key=lambda item: (item['data']['node_type'], item['data'].get('column', ''), item['data']['label']))
    edges.sort(key=lambda item: (item['data']['target_label'], item['data']['column'], item['data']['source_label']))

    enriched_count = sum(1 for node in taxon_nodes.values() if node['column'] == 'enriched')
    depleted_count = sum(1 for node in taxon_nodes.values() if node['column'] == 'depleted')
    max_column_count = max(
        enriched_count,
        depleted_count,
        len(disease_nodes),
        1,
    )
    layout_height = max(680, 160 + ((max_column_count - 1) * 108))

    return {
        'nodes': nodes,
        'edges': edges,
        'summary': {
            'node_count': len(nodes),
            'edge_count': len(edges),
            'finding_count': sum(edge['data']['finding_count'] for edge in edges),
            'disease_count': len(disease_nodes),
            'taxon_count': len(unique_grouped_taxon_ids),
            'enriched_taxon_count': enriched_count,
            'depleted_taxon_count': depleted_count,
            'grouping_rank': grouping_rank,
            'skipped_rollup_count': skipped_rollup_count,
            'layout_width': 1240,
            'layout_height': layout_height,
        },
    }
