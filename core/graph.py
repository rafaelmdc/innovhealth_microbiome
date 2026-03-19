def _disease_label(comparison):
    condition = (comparison.group_a.condition or '').strip()
    if condition:
        return condition
    return comparison.group_a.name


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


def _build_disease_positions(disease_nodes, organism_positions, *, x_position, fallback_step=120, y_start=96):
    def disease_sort_key(node_id):
        neighbor_positions = sorted(
            organism_positions[neighbor_id]['y']
            for neighbor_id in disease_nodes[node_id]['neighbors']
            if neighbor_id in organism_positions
        )
        if neighbor_positions:
            midpoint = sum(neighbor_positions) / len(neighbor_positions)
        else:
            midpoint = 0
        return (midpoint, -len(disease_nodes[node_id]['neighbors']), disease_nodes[node_id]['label'].lower())

    positions = {}
    for index, node_id in enumerate(sorted(disease_nodes, key=disease_sort_key)):
        neighbor_positions = sorted(
            organism_positions[neighbor_id]['y']
            for neighbor_id in disease_nodes[node_id]['neighbors']
            if neighbor_id in organism_positions
        )
        preferred_y = sum(neighbor_positions) / len(neighbor_positions) if neighbor_positions else y_start + (index * fallback_step)
        minimum_y = y_start if index == 0 else positions[previous_node_id]['y'] + fallback_step
        y_position = max(preferred_y, minimum_y)
        positions[node_id] = {'x': x_position, 'y': y_position}
        previous_node_id = node_id
    return positions


def build_disease_graph(findings):
    disease_nodes = {}
    taxon_nodes = {}
    edge_map = {}
    unique_taxon_ids = set()

    for finding in findings:
        comparison = finding.comparison
        taxon = finding.taxon
        disease_label = _disease_label(comparison)
        disease_node_id = f'disease-{disease_label.lower()}'
        direction_column = 'enriched' if finding.direction in {'enriched', 'increased'} else 'depleted'
        taxon_node_id = f'{direction_column}-taxon-{taxon.pk}'

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
                'label': taxon.scientific_name,
                'node_type': 'taxon',
                'column': direction_column,
                'direction': direction_column,
                'rank': taxon.rank,
                'taxonomy_id': taxon.ncbi_taxonomy_id,
                'study_ids': set(),
                'neighbors': set(),
            },
        )
        taxon_node['study_ids'].add(comparison.study_id)
        taxon_node['neighbors'].add(disease_node_id)
        unique_taxon_ids.add(taxon.pk)

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
            },
        )
        edge['finding_count'] += 1
        edge['study_ids'].add(comparison.study_id)
        edge['sources'].add(finding.source)
        edge['comparison_labels'].add(comparison.label)

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
                    'column': attrs['column'],
                    'degree': len(attrs['neighbors']),
                    'study_count': len(attrs['study_ids']),
                    'group': f"{attrs['node_type']}-{attrs['column']}",
                    'rank': attrs['rank'],
                    'taxonomy_id': attrs['taxonomy_id'],
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
                    'source_label': source_node['label'],
                    'target_label': target_node['label'],
                    'column': edge['column'],
                    'direction_summary': edge['column'],
                    'finding_count': edge['finding_count'],
                    'study_count': len(edge['study_ids']),
                    'source_count': len(edge['sources']),
                    'comparison_labels': ', '.join(sorted(edge['comparison_labels'])),
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
            'taxon_count': len(unique_taxon_ids),
            'enriched_taxon_count': enriched_count,
            'depleted_taxon_count': depleted_count,
            'layout_width': 1240,
            'layout_height': layout_height,
        },
    }
