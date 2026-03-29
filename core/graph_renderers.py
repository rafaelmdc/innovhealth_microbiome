GRAPH_ENGINE_CHOICES = (
    ('cytoscape', 'Cytoscape'),
    ('echarts', 'ECharts'),
)
GRAPH_ENGINES = {value for value, _label in GRAPH_ENGINE_CHOICES}

DIRECTIONAL_LAYOUT_CONTROL_SPECS = {
    'cytoscape': (
        {
            'name': 'cytoscape_repulsion_scale',
            'label': 'Repulsion scale',
            'default': 1.0,
            'minimum': 0.4,
            'maximum': 2.4,
            'step': 0.1,
        },
        {
            'name': 'cytoscape_edge_length_scale',
            'label': 'Edge length scale',
            'default': 1.0,
            'minimum': 0.6,
            'maximum': 2.0,
            'step': 0.1,
        },
        {
            'name': 'cytoscape_gravity',
            'label': 'Gravity',
            'default': 0.1,
            'minimum': 0.02,
            'maximum': 0.3,
            'step': 0.01,
        },
    ),
    'echarts': (
        {
            'name': 'echarts_repulsion',
            'label': 'Repulsion',
            'default': 1050.0,
            'minimum': 200.0,
            'maximum': 2200.0,
            'step': 50.0,
        },
        {
            'name': 'echarts_edge_length',
            'label': 'Edge length',
            'default': 240.0,
            'minimum': 80.0,
            'maximum': 420.0,
            'step': 10.0,
        },
        {
            'name': 'echarts_gravity',
            'label': 'Gravity',
            'default': 0.025,
            'minimum': 0.005,
            'maximum': 0.12,
            'step': 0.005,
        },
    ),
}


def normalize_graph_engine(value):
    return value if value in GRAPH_ENGINES else 'cytoscape'


def _coerce_float(raw_value, *, default, minimum, maximum):
    try:
        parsed = float(raw_value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)


def build_directional_layout_settings(params):
    settings = {}
    for specs in DIRECTIONAL_LAYOUT_CONTROL_SPECS.values():
        for spec in specs:
            settings[spec['name']] = _coerce_float(
                params.get(spec['name']),
                default=spec['default'],
                minimum=spec['minimum'],
                maximum=spec['maximum'],
            )
    return settings
