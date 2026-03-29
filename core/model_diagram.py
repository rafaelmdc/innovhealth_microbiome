import html
import subprocess

from django.apps import apps


PROJECT_APP_LABELS = ('database',)
MODEL_DIAGRAM_CONTENT_TYPES = {
    'png': 'image/png',
    'svg': 'image/svg+xml',
}


def _model_label(model):
    field_lines = []
    for field in model._meta.fields:
        if field.is_relation and field.remote_field:
            field_type = f'FK -> {field.remote_field.model.__name__}'
        else:
            field_type = field.get_internal_type()
        field_lines.append(f'{field.name}: {field_type}')

    rows = ''.join(
        f'<TR><TD ALIGN="LEFT" BALIGN="LEFT"><FONT POINT-SIZE="10">{html.escape(line)}</FONT></TD></TR>'
        for line in field_lines
    )
    return (
        '<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="8">'
        f'<TR><TD BGCOLOR="#0f766e"><FONT COLOR="white"><B>{html.escape(model.__name__)}</B></FONT></TD></TR>'
        f'{rows}'
        '</TABLE>>'
    )


def build_model_diagram_dot():
    models = []
    for app_label in PROJECT_APP_LABELS:
        models.extend(apps.get_app_config(app_label).get_models())

    lines = [
        'digraph django_models {',
        '  graph [rankdir=LR, bgcolor="transparent", pad="0.4", nodesep="0.6", ranksep="1.0"];',
        '  node [shape=plain, fontname="Helvetica"];',
        '  edge [color="#5d6b6e", penwidth=1.3, arrowsize=0.8];',
    ]

    for model in models:
        lines.append(f'  {model.__name__} [label={_model_label(model)}];')

    for model in models:
        for field in model._meta.fields:
            if field.is_relation and field.remote_field:
                related_model = field.remote_field.model
                if related_model._meta.app_label in PROJECT_APP_LABELS:
                    lines.append(
                        f'  {model.__name__} -> {related_model.__name__} '
                        f'[label="{field.name}", fontname="Helvetica", fontsize=10];'
                    )

    lines.append('}')
    return '\n'.join(lines)


def render_model_diagram(output_format='svg'):
    dot_source = build_model_diagram_dot()
    if output_format not in MODEL_DIAGRAM_CONTENT_TYPES:
        raise ValueError(f'Unsupported diagram format: {output_format}')

    completed = subprocess.run(
        ['dot', f'-T{output_format}'],
        input=dot_source.encode('utf-8'),
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode('utf-8', errors='replace').strip()
        raise RuntimeError(stderr or 'Graphviz failed to render the model diagram.')
    return completed.stdout


def render_model_diagram_svg():
    return render_model_diagram('svg').decode('utf-8')
