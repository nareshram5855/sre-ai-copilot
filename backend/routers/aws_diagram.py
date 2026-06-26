"""AWS-style SVG diagram renderer for Stackport AI.

Two entry points:
  generate_aws_svg(architecture)  — primary: uses architecture["diagram"] (structured JSON
                                    that Gemini fills in) to produce a proper AWS-level diagram
                                    with VPC boundary boxes, service icons, numbered arrows.
  generate_styled_mermaid(arch)   — fallback string kept for compatibility.
"""
from __future__ import annotations
from typing import Any

# ── AWS brand colors ──────────────────────────────────────────────────────────
_SERVICE_COLORS: dict[str, str] = {
    # networking
    "cloudfront": "#8C4FFF", "route53": "#8C4FFF", "alb": "#8C4FFF",
    "nlb": "#8C4FFF", "waf": "#DD344C", "api-gateway": "#8C4FFF",
    # compute
    "lambda": "#FF9900", "ecs": "#FF9900", "eks": "#FF9900",
    "ec2": "#FF9900", "fargate": "#FF9900", "appsync": "#E7157B",
    "cognito": "#DD344C", "step-functions": "#FF4F8B",
    # data
    "rds": "#3F8624", "aurora": "#3F8624", "dynamodb": "#3F8624",
    "elasticache": "#3F8624", "s3": "#3F8624", "sqs": "#FF9900",
    "sns": "#FF9900", "kinesis": "#8C4FFF",
    # security/platform
    "iam": "#DD344C", "kms": "#DD344C", "secrets-manager": "#DD344C",
    "secrets": "#DD344C", "cloudwatch": "#E7157B", "xray": "#E7157B",
    "ecr": "#C7131F", "codepipeline": "#C7131F",
    "github-actions": "#333333",
}

_CAT_COLORS: dict[str, str] = {
    "networking": "#8C4FFF", "compute": "#FF9900", "data": "#3F8624",
    "storage": "#3F8624", "security": "#DD344C", "cicd": "#C7131F",
    "monitoring": "#E7157B", "observability": "#E7157B",
}

_LABELS: dict[str, str] = {
    "cloudfront": "CloudFront", "route53": "Route 53", "alb": "App LB",
    "nlb": "Net LB", "waf": "WAF", "vpc": "VPC", "api-gateway": "API Gateway",
    "lambda": "Lambda", "ecs": "ECS", "eks": "EKS", "ec2": "EC2",
    "fargate": "Fargate", "appsync": "AppSync", "cognito": "Cognito",
    "step-functions": "Step Func", "rds": "RDS", "aurora": "Aurora",
    "dynamodb": "DynamoDB", "elasticache": "ElastiCache", "s3": "S3",
    "sqs": "SQS", "sns": "SNS", "kinesis": "Kinesis",
    "iam": "IAM", "secrets-manager": "Secrets Mgr", "secrets": "Secrets Mgr",
    "kms": "KMS", "cloudwatch": "CloudWatch", "xray": "X-Ray",
    "codepipeline": "CodePipeline", "ecr": "ECR",
    "github-actions": "GitHub CI",
}

# ── SVG icon paths (centered at 0,0, ±20 viewport) ───────────────────────────
_ICONS: dict[str, str] = {
    "lambda": '<text x="0" y="12" text-anchor="middle" font-size="28" font-weight="900" fill="white" font-family="Georgia,serif">λ</text>',
    "rds": (
        '<ellipse cx="0" cy="-13" rx="14" ry="5" fill="white" opacity="0.9"/>'
        '<rect x="-14" y="-13" width="28" height="24" fill="white" opacity="0.2"/>'
        '<ellipse cx="0" cy="11" rx="14" ry="5" fill="white" opacity="0.5"/>'
        '<line x1="-14" y1="-13" x2="-14" y2="11" stroke="white" stroke-width="1.5"/>'
        '<line x1="14" y1="-13" x2="14" y2="11" stroke="white" stroke-width="1.5"/>'
    ),
    "aurora": (
        '<ellipse cx="0" cy="-13" rx="14" ry="5" fill="white" opacity="0.9"/>'
        '<rect x="-14" y="-13" width="28" height="24" fill="white" opacity="0.2"/>'
        '<ellipse cx="0" cy="11" rx="14" ry="5" fill="white" opacity="0.5"/>'
        '<line x1="-14" y1="-13" x2="-14" y2="11" stroke="white" stroke-width="1.5"/>'
        '<line x1="14" y1="-13" x2="14" y2="11" stroke="white" stroke-width="1.5"/>'
    ),
    "dynamodb": (
        '<ellipse cx="0" cy="-14" rx="13" ry="5" fill="white" opacity="0.9"/>'
        '<ellipse cx="0" cy="-3"  rx="13" ry="5" fill="white" opacity="0.7"/>'
        '<ellipse cx="0" cy="8"   rx="13" ry="5" fill="white" opacity="0.5"/>'
        '<line x1="-13" y1="-14" x2="-13" y2="8" stroke="white" stroke-width="1.5"/>'
        '<line x1="13"  y1="-14" x2="13"  y2="8" stroke="white" stroke-width="1.5"/>'
    ),
    "elasticache": (
        '<ellipse cx="0" cy="-11" rx="13" ry="5" fill="white" opacity="0.9"/>'
        '<ellipse cx="0" cy="5"   rx="13" ry="5" fill="white" opacity="0.6"/>'
        '<line x1="-13" y1="-11" x2="-13" y2="5" stroke="white" stroke-width="1.5"/>'
        '<line x1="13"  y1="-11" x2="13"  y2="5" stroke="white" stroke-width="1.5"/>'
        '<text x="0" y="-7" text-anchor="middle" font-size="8" fill="white">Redis</text>'
    ),
    "s3": (
        '<path d="M0,-19 L13,-8 L13,11 Q13,19 0,19 Q-13,19 -13,11 L-13,-8 Z" fill="white" opacity="0.25" stroke="white" stroke-width="1.5"/>'
        '<ellipse cx="0" cy="-19" rx="13" ry="5" fill="white" opacity="0.85"/>'
        '<line x1="-13" y1="-8" x2="13" y2="-8" stroke="white" stroke-width="1.5" opacity="0.7"/>'
    ),
    "cloudfront": (
        '<circle cx="0" cy="0" r="17" fill="none" stroke="white" stroke-width="1.8"/>'
        '<ellipse cx="0" cy="0" rx="7" ry="17" fill="none" stroke="white" stroke-width="1.5"/>'
        '<line x1="-17" y1="0" x2="17" y2="0" stroke="white" stroke-width="1.5"/>'
        '<line x1="-14" y1="-10" x2="14" y2="-10" stroke="white" stroke-width="1" opacity="0.6"/>'
        '<line x1="-14" y1="10" x2="14" y2="10" stroke="white" stroke-width="1" opacity="0.6"/>'
    ),
    "route53": (
        '<circle cx="0" cy="0" r="17" fill="none" stroke="white" stroke-width="1.8"/>'
        '<ellipse cx="0" cy="0" rx="7" ry="17" fill="none" stroke="white" stroke-width="1.5"/>'
        '<line x1="-17" y1="0" x2="17" y2="0" stroke="white" stroke-width="1.5"/>'
    ),
    "alb": (
        '<circle cx="-14" cy="-11" r="3" fill="white" opacity="0.85"/>'
        '<circle cx="0"   cy="-11" r="3" fill="white" opacity="0.85"/>'
        '<circle cx="14"  cy="-11" r="3" fill="white" opacity="0.85"/>'
        '<line x1="-17" y1="-11" x2="17" y2="-11" stroke="white" stroke-width="2"/>'
        '<line x1="-14" y1="-8" x2="-14" y2="11" stroke="white" stroke-width="1.5"/>'
        '<line x1="0"   y1="-8" x2="0"   y2="11" stroke="white" stroke-width="1.5"/>'
        '<line x1="14"  y1="-8" x2="14"  y2="11" stroke="white" stroke-width="1.5"/>'
        '<circle cx="-14" cy="13" r="3" fill="white" opacity="0.6"/>'
        '<circle cx="0"   cy="13" r="3" fill="white" opacity="0.6"/>'
        '<circle cx="14"  cy="13" r="3" fill="white" opacity="0.6"/>'
    ),
    "nlb": (
        '<circle cx="-14" cy="-11" r="3" fill="white" opacity="0.85"/>'
        '<circle cx="0"   cy="-11" r="3" fill="white" opacity="0.85"/>'
        '<circle cx="14"  cy="-11" r="3" fill="white" opacity="0.85"/>'
        '<line x1="-17" y1="-11" x2="17" y2="-11" stroke="white" stroke-width="2"/>'
        '<line x1="-14" y1="-8" x2="-14" y2="11" stroke="white" stroke-width="1.5"/>'
        '<line x1="0"   y1="-8" x2="0"   y2="11" stroke="white" stroke-width="1.5"/>'
        '<line x1="14"  y1="-8" x2="14"  y2="11" stroke="white" stroke-width="1.5"/>'
    ),
    "ecs": (
        '<rect x="-17" y="-13" width="13" height="10" rx="2" fill="white" opacity="0.85"/>'
        '<rect x="4"   y="-13" width="13" height="10" rx="2" fill="white" opacity="0.85"/>'
        '<rect x="-17" y="3"   width="13" height="10" rx="2" fill="white" opacity="0.65"/>'
        '<rect x="4"   y="3"   width="13" height="10" rx="2" fill="white" opacity="0.65"/>'
    ),
    "fargate": (
        '<rect x="-17" y="-13" width="13" height="10" rx="2" fill="white" opacity="0.85"/>'
        '<rect x="4"   y="-13" width="13" height="10" rx="2" fill="white" opacity="0.85"/>'
        '<rect x="-17" y="3"   width="13" height="10" rx="2" fill="white" opacity="0.65"/>'
        '<rect x="4"   y="3"   width="13" height="10" rx="2" fill="white" opacity="0.65"/>'
    ),
    "eks": (
        '<circle cx="0" cy="0" r="16" fill="none" stroke="white" stroke-width="2"/>'
        '<line x1="0" y1="-16" x2="0" y2="-8" stroke="white" stroke-width="2"/>'
        '<line x1="13.8" y1="8" x2="6.9" y2="4" stroke="white" stroke-width="2"/>'
        '<line x1="-13.8" y1="8" x2="-6.9" y2="4" stroke="white" stroke-width="2"/>'
        '<circle cx="0" cy="0" r="5" fill="white" opacity="0.85"/>'
    ),
    "ec2": (
        '<rect x="-16" y="-16" width="32" height="32" rx="3" fill="none" stroke="white" stroke-width="2"/>'
        '<rect x="-8"  y="-8"  width="16" height="16" rx="2" fill="white" opacity="0.7"/>'
    ),
    "cognito": (
        '<circle cx="0" cy="-10" r="8" fill="white" opacity="0.85"/>'
        '<path d="M-14,18 Q-14,2 0,2 Q14,2 14,18" fill="white" opacity="0.6"/>'
    ),
    "iam": (
        '<rect x="-13" y="2" width="26" height="17" rx="3" fill="none" stroke="white" stroke-width="2"/>'
        '<path d="M-8,2 L-8,-7 Q-8,-18 0,-18 Q8,-18 8,-7 L8,2" fill="none" stroke="white" stroke-width="2"/>'
        '<circle cx="0" cy="11" r="3.5" fill="white" opacity="0.9"/>'
    ),
    "kms": (
        '<circle cx="0" cy="-8" r="9" fill="none" stroke="white" stroke-width="2"/>'
        '<rect x="-4" y="-2" width="8" height="14" rx="2" fill="none" stroke="white" stroke-width="2"/>'
        '<rect x="-9" y="8" width="5" height="4" rx="1" fill="white" opacity="0.8"/>'
        '<rect x="4"  y="8" width="5" height="4" rx="1" fill="white" opacity="0.8"/>'
    ),
    "secrets-manager": (
        '<rect x="-13" y="2" width="26" height="17" rx="3" fill="none" stroke="white" stroke-width="2"/>'
        '<path d="M-8,2 L-8,-7 Q-8,-18 0,-18 Q8,-18 8,-7 L8,2" fill="none" stroke="white" stroke-width="2"/>'
        '<line x1="-6" y1="10" x2="6" y2="10" stroke="white" stroke-width="1.5"/>'
        '<line x1="-6" y1="14" x2="6" y2="14" stroke="white" stroke-width="1.5"/>'
    ),
    "waf": (
        '<path d="M0,-20 L17,-10 L17,7 Q17,20 0,20 Q-17,20 -17,7 L-17,-10 Z" fill="none" stroke="white" stroke-width="2"/>'
        '<line x1="-8" y1="0" x2="8" y2="0" stroke="white" stroke-width="2.5"/>'
        '<line x1="0" y1="-8" x2="0" y2="8" stroke="white" stroke-width="2.5"/>'
    ),
    "cloudwatch": (
        '<circle cx="0" cy="0" r="17" fill="none" stroke="white" stroke-width="1.8"/>'
        '<polyline points="-11,8 -5,-8 1,3 7,-10 12,5" fill="none" stroke="white" stroke-width="2.5" stroke-linejoin="round"/>'
    ),
    "appsync": (
        '<polygon points="0,-18 16,9 -16,9" fill="none" stroke="white" stroke-width="2.5"/>'
        '<circle cx="0"   cy="-18" r="4" fill="white" opacity="0.85"/>'
        '<circle cx="16"  cy="9"   r="4" fill="white" opacity="0.85"/>'
        '<circle cx="-16" cy="9"   r="4" fill="white" opacity="0.85"/>'
    ),
    "api-gateway": (
        '<rect x="-17" y="-17" width="34" height="34" rx="4" fill="none" stroke="white" stroke-width="1.8"/>'
        '<line x1="-9" y1="-8" x2="9" y2="-8" stroke="white" stroke-width="1.8"/>'
        '<line x1="-9" y1="0"  x2="9" y2="0"  stroke="white" stroke-width="1.8"/>'
        '<line x1="-9" y1="8"  x2="9" y2="8"  stroke="white" stroke-width="1.8"/>'
        '<circle cx="-13" cy="-8" r="2.5" fill="white" opacity="0.9"/>'
        '<circle cx="-13" cy="0"  r="2.5" fill="white" opacity="0.9"/>'
        '<circle cx="-13" cy="8"  r="2.5" fill="white" opacity="0.9"/>'
    ),
    "step-functions": (
        '<rect x="-13" y="-18" width="26" height="10" rx="2" fill="white" opacity="0.85"/>'
        '<rect x="-13" y="-4"  width="26" height="10" rx="2" fill="white" opacity="0.65"/>'
        '<rect x="-13" y="10"  width="26" height="10" rx="2" fill="white" opacity="0.45"/>'
        '<line x1="0" y1="-8" x2="0" y2="-4" stroke="white" stroke-width="1.5"/>'
        '<line x1="0" y1="6"  x2="0" y2="10" stroke="white" stroke-width="1.5"/>'
    ),
    "ecr": (
        '<rect x="-16" y="-16" width="32" height="32" rx="3" fill="none" stroke="white" stroke-width="2"/>'
        '<rect x="-10" y="-11" width="20" height="7" rx="2" fill="white" opacity="0.85"/>'
        '<rect x="-10" y="-1"  width="20" height="7" rx="2" fill="white" opacity="0.6"/>'
        '<rect x="-10" y="9"   width="20" height="7" rx="2" fill="white" opacity="0.4"/>'
    ),
    "sqs": (
        '<rect x="-18" y="-8" width="36" height="16" rx="8" fill="none" stroke="white" stroke-width="2"/>'
        '<circle cx="-9" cy="0" r="3" fill="white" opacity="0.9"/>'
        '<circle cx="0"  cy="0" r="3" fill="white" opacity="0.9"/>'
        '<circle cx="9"  cy="0" r="3" fill="white" opacity="0.9"/>'
    ),
    "sns": (
        '<path d="M-12,-17 L12,-17 L17,-8 L12,3 L4,3 L0,17 L-4,3 L-12,3 L-17,-8 Z" fill="white" opacity="0.7" stroke="white" stroke-width="1.5"/>'
    ),
    "kinesis": (
        '<path d="M-17,-10 Q-7,-4 0,-10 Q7,-16 17,-10" fill="none" stroke="white" stroke-width="2"/>'
        '<path d="M-17,0  Q-7,6  0,0  Q7,-6  17,0"  fill="none" stroke="white" stroke-width="2"/>'
        '<path d="M-17,10 Q-7,16 0,10 Q7,4  17,10"  fill="none" stroke="white" stroke-width="2"/>'
    ),
    "codepipeline": (
        '<rect x="-16" y="-14" width="12" height="9" rx="2" fill="white" opacity="0.85"/>'
        '<rect x="4"   y="-14" width="12" height="9" rx="2" fill="white" opacity="0.65"/>'
        '<rect x="-16" y="5"   width="12" height="9" rx="2" fill="white" opacity="0.45"/>'
        '<rect x="4"   y="5"   width="12" height="9" rx="2" fill="white" opacity="0.35"/>'
        '<line x1="-4" y1="-10" x2="3" y2="-10" stroke="white" stroke-width="1.5"/>'
        '<line x1="0"  y1="-5"  x2="-12" y2="5" stroke="white" stroke-width="1.5"/>'
        '<line x1="0"  y1="-5"  x2="12"  y2="5" stroke="white" stroke-width="1.5"/>'
    ),
    "github-actions": (
        '<circle cx="0" cy="0" r="17" fill="none" stroke="white" stroke-width="2"/>'
        '<circle cx="0" cy="-4" r="6" fill="none" stroke="white" stroke-width="2"/>'
        '<circle cx="-10" cy="12" r="3" fill="white" opacity="0.8"/>'
        '<circle cx="10"  cy="12" r="3" fill="white" opacity="0.8"/>'
    ),
}
_ICONS["secrets"] = _ICONS["secrets-manager"]
_ICONS["vpc"] = _ICONS.get("vpc", "")


def _svc_key(service: str) -> str:
    return (service.split("/")[-1] if "/" in service else service).lower()


def _icon_svg(service: str) -> str:
    key = _svc_key(service)
    if key in _ICONS:
        return _ICONS[key]
    abbr = _LABELS.get(key, key.upper())[:3]
    return f'<text x="0" y="8" text-anchor="middle" font-size="15" font-weight="800" fill="white">{abbr}</text>'


def _node_color(service: str) -> str:
    if service == "user":
        return "#475569"
    key = _svc_key(service)
    if key in _SERVICE_COLORS:
        return _SERVICE_COLORS[key]
    cat = (service.split("/")[0] if "/" in service else "default").lower()
    return _CAT_COLORS.get(cat, "#527FFF")


def _node_label(node: dict) -> str:
    return node.get("label") or _LABELS.get(_svc_key(node.get("service", "")), _svc_key(node.get("service", "")).title())


# ── Zone visual config ────────────────────────────────────────────────────────
_ZONE_STYLE: dict[str, dict] = {
    "internet":    {"fill": "#f1f5f9", "stroke": "#94a3b8", "dash": "6,4",  "label_color": "#64748b"},
    "aws_edge":    {"fill": "#faf5ff", "stroke": "#8C4FFF", "dash": "none", "label_color": "#6d28d9"},
    "vpc_public":  {"fill": "#f0fdf4", "stroke": "#3DAA5C", "dash": "5,3",  "label_color": "#15803d"},
    "vpc_private": {"fill": "#eff6ff", "stroke": "#3B82F6", "dash": "5,3",  "label_color": "#1d4ed8"},
    "aws_managed": {"fill": "#fff7ed", "stroke": "#FF9900", "dash": "none", "label_color": "#c2410c"},
}


# ── Icon box renderer ─────────────────────────────────────────────────────────
_BOX = 56   # icon box size

def _icon_box(cx: int, cy: int, node: dict, order: int | None = None) -> str:
    service = node.get("service", "")
    label = _node_label(node)
    color = _node_color(service)
    icon = _icon_svg(service)
    half = _BOX // 2
    r = 9

    # Two-line label split
    words = label.split()
    if len(label) <= 11 or len(words) == 1:
        lbl_svg = (
            f'<text x="{cx}" y="{cy + half + 15}" text-anchor="middle" '
            f'font-size="10.5" font-weight="600" fill="#1e293b">{label}</text>'
        )
    else:
        mid = (len(words) + 1) // 2
        l1, l2 = " ".join(words[:mid]), " ".join(words[mid:])
        lbl_svg = (
            f'<text x="{cx}" y="{cy + half + 13}" text-anchor="middle" '
            f'font-size="10" font-weight="600" fill="#1e293b">{l1}</text>'
            f'<text x="{cx}" y="{cy + half + 24}" text-anchor="middle" '
            f'font-size="10" font-weight="600" fill="#1e293b">{l2}</text>'
        )

    parts = [
        f'<rect x="{cx-half+2}" y="{cy-half+2}" width="{_BOX}" height="{_BOX}" rx="{r}" fill="#00000015"/>',
        f'<rect x="{cx-half}" y="{cy-half}" width="{_BOX}" height="{_BOX}" rx="{r}" fill="{color}"/>',
        f'<g transform="translate({cx},{cy})">{icon}</g>',
        lbl_svg,
    ]

    if order is not None:
        bx, by = cx + half - 1, cy - half + 1
        parts += [
            f'<circle cx="{bx}" cy="{by}" r="10" fill="white" stroke="{color}" stroke-width="2"/>',
            f'<text x="{bx}" y="{by+4}" text-anchor="middle" font-size="9" font-weight="700" fill="{color}">{order}</text>',
        ]

    if service == "user":
        parts = [
            f'<circle cx="{cx}" cy="{cy-8}" r="11" fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.5"/>',
            f'<circle cx="{cx}" cy="{cy-8}" r="5" fill="#94a3b8"/>',
            f'<path d="M{cx-12},{cy+7} Q{cx-12},{cy-1} {cx},{cy-1} Q{cx+12},{cy-1} {cx+12},{cy+7}" fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.5"/>',
            f'<text x="{cx}" y="{cy+22}" text-anchor="middle" font-size="10.5" font-weight="600" fill="#475569">Users</text>',
        ]

    return "\n".join(parts)


# ── Arrow renderer ────────────────────────────────────────────────────────────

def _arrow(x1: int, y1: int, x2: int, y2: int,
           label: str = "", seq: int | None = None, dashed: bool = False) -> str:
    stroke = "#475569" if dashed else "#1e293b"
    dash_attr = 'stroke-dasharray="6,4"' if dashed else ""
    mid_x, mid_y = (x1 + x2) // 2, (y1 + y2) // 2

    parts = [
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{stroke}" stroke-width="1.8" {dash_attr} marker-end="url(#ah)"/>'
    ]

    if seq is not None:
        parts += [
            f'<circle cx="{mid_x}" cy="{mid_y}" r="11" fill="{stroke}"/>',
            f'<text x="{mid_x}" y="{mid_y+4}" text-anchor="middle" font-size="10" font-weight="700" fill="white">{seq}</text>',
        ]
    elif label:
        parts += [
            f'<rect x="{mid_x-20}" y="{mid_y-9}" width="40" height="16" rx="4" fill="white" stroke="#e2e8f0" stroke-width="1"/>',
            f'<text x="{mid_x}" y="{mid_y+4}" text-anchor="middle" font-size="9" fill="{stroke}">{label}</text>',
        ]

    return "\n".join(parts)


# ── Primary renderer: uses diagram JSON from Gemini ───────────────────────────

def _render_from_diagram(diagram: dict, arch_name: str) -> str:
    zones_raw: list[dict] = diagram.get("zones", [])
    nodes_raw: list[dict] = diagram.get("nodes", [])
    edges_raw: list[dict] = diagram.get("edges", [])

    # Index nodes by id
    node_map: dict[str, dict] = {n["id"]: n for n in nodes_raw}

    # ── Layout ───────────────────────────────────────────────────────────────
    PAD = 28
    ZONE_PAD = 18       # padding inside zone box
    BOX_GAP_H = 20      # horizontal gap between icon boxes in a zone
    BOX_GAP_V = 26      # vertical gap between rows
    ZONE_GAP = 16       # gap between zone columns
    TOP = 72            # y start of zone boxes
    LABEL_H = 22        # zone header height
    MAX_PER_COL = 3     # max nodes per column within a zone

    # Compute per-zone node sets
    zone_nodes: dict[str, list[str]] = {z["id"]: z.get("nodes", []) for z in zones_raw}

    # Compute zone widths based on node count
    def _zone_width(node_ids: list[str]) -> int:
        cols = (len(node_ids) + MAX_PER_COL - 1) // MAX_PER_COL if node_ids else 1
        return ZONE_PAD * 2 + cols * _BOX + (cols - 1) * BOX_GAP_H

    # Determine if VPC box needed
    vpc_zone_types = {"vpc_public", "vpc_private"}
    vpc_zones = [z for z in zones_raw if z.get("type") in vpc_zone_types]
    has_vpc = bool(vpc_zones)

    # Zone heights
    def _zone_height(node_ids: list[str]) -> int:
        rows = min(len(node_ids), MAX_PER_COL) if node_ids else 1
        return LABEL_H + ZONE_PAD * 2 + rows * _BOX + (rows - 1) * BOX_GAP_V

    max_zone_h = max((_zone_height(zone_nodes.get(z["id"], [])) for z in zones_raw), default=200)
    max_zone_h = max(max_zone_h, 200)

    # Assign x positions to zones
    x = PAD
    zone_x: dict[str, int] = {}
    zone_w: dict[str, int] = {}
    for z in zones_raw:
        nids = zone_nodes.get(z["id"], [])
        w = _zone_width(nids)
        zone_x[z["id"]] = x
        zone_w[z["id"]] = w
        x += w + ZONE_GAP

    W = x - ZONE_GAP + PAD
    VPC_PAD = 12

    # VPC bounding box
    vpc_x1 = min((zone_x[z["id"]] for z in vpc_zones), default=0) - VPC_PAD
    vpc_x2 = max((zone_x[z["id"]] + zone_w[z["id"]] for z in vpc_zones), default=W) + VPC_PAD

    # Total canvas height
    legend_h = 30
    H = TOP + max_zone_h + (32 if has_vpc else 0) + legend_h + PAD

    # ── Compute node center positions ─────────────────────────────────────────
    node_cx: dict[str, int] = {}
    node_cy: dict[str, int] = {}

    for z in zones_raw:
        zid = z["id"]
        nids = zone_nodes.get(zid, [])
        zx = zone_x[zid]
        zw = zone_w[zid]
        cols = (len(nids) + MAX_PER_COL - 1) // MAX_PER_COL if nids else 1

        for i, nid in enumerate(nids):
            col = i // MAX_PER_COL
            row = i % MAX_PER_COL
            cx = zx + ZONE_PAD + col * (_BOX + BOX_GAP_H) + _BOX // 2
            cy = TOP + (32 if has_vpc else 0) + LABEL_H + ZONE_PAD + row * (_BOX + BOX_GAP_V) + _BOX // 2
            node_cx[nid] = cx
            node_cy[nid] = cy

    # ── SVG ──────────────────────────────────────────────────────────────────
    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'style="background:#f8fafc;font-family:Inter,\'Segoe UI\',system-ui,sans-serif;">',
        '<defs>'
        '<marker id="ah" markerWidth="9" markerHeight="7" refX="9" refY="3.5" orient="auto">'
        '<polygon points="0 0, 9 3.5, 0 7" fill="#1e293b"/>'
        '</marker>'
        '</defs>',
        f'<rect x="0" y="0" width="{W}" height="{H}" fill="#f8fafc"/>',
        # Title
        f'<rect x="0" y="0" width="{W}" height="50" fill="#1e293b"/>',
        f'<text x="{W//2}" y="31" text-anchor="middle" font-size="16" font-weight="700" fill="white">{arch_name}</text>',
        f'<text x="{W-PAD}" y="31" text-anchor="end" font-size="10" fill="#FF9900" font-weight="600">Stackport AI</text>',
        # AWS Cloud outer border
        f'<rect x="{PAD//2}" y="58" width="{W-PAD}" height="{H-66}" rx="8" '
        f'fill="none" stroke="#FF9900" stroke-width="1.8" stroke-dasharray="10,5"/>',
        f'<rect x="{PAD//2+2}" y="51" width="110" height="20" rx="4" fill="white" stroke="#FF9900" stroke-width="1.5"/>',
        f'<rect x="{PAD//2+6}" y="55" width="16" height="12" rx="3" fill="#FF9900"/>',
        f'<text x="{PAD//2+14}" y="64" text-anchor="middle" font-size="7.5" font-weight="900" fill="white">aws</text>',
        f'<text x="{PAD//2+72}" y="65" text-anchor="middle" font-size="11" font-weight="700" fill="#232F3E">AWS Cloud</text>',
    ]

    # VPC bounding box
    if has_vpc:
        vpc_top = TOP + 28
        vpc_bot = TOP + max_zone_h + 12
        svg += [
            f'<rect x="{vpc_x1}" y="{vpc_top}" width="{vpc_x2-vpc_x1}" height="{vpc_bot-vpc_top}" rx="8" '
            f'fill="#f0fdf4" stroke="#3DAA5C" stroke-width="1.8" stroke-dasharray="6,3"/>',
            f'<text x="{vpc_x1+10}" y="{vpc_top+16}" font-size="10" font-weight="700" fill="#15803d">VPC</text>',
        ]

    # Zone boxes
    for z in zones_raw:
        zid = z["id"]
        zstyle = _ZONE_STYLE.get(z.get("type", "aws_managed"), _ZONE_STYLE["aws_managed"])
        zx = zone_x[zid]
        zw = zone_w[zid]
        zy = TOP + (32 if has_vpc else 0)
        zh = max_zone_h

        dash = f'stroke-dasharray="{zstyle["dash"]}"' if zstyle["dash"] != "none" else ""
        svg += [
            f'<rect x="{zx}" y="{zy}" width="{zw}" height="{zh}" rx="8" '
            f'fill="{zstyle["fill"]}" stroke="{zstyle["stroke"]}" stroke-width="1.5" {dash}/>',
            f'<text x="{zx+zw//2}" y="{zy+15}" text-anchor="middle" font-size="9" '
            f'font-weight="700" fill="{zstyle["label_color"]}" letter-spacing="0.8">'
            f'{z.get("label","").upper()}</text>',
        ]

    # Node icon boxes
    for z in zones_raw:
        for nid in zone_nodes.get(z["id"], []):
            node = node_map.get(nid, {"id": nid, "label": nid, "service": nid})
            cx = node_cx.get(nid)
            cy = node_cy.get(nid)
            if cx is None or cy is None:
                continue
            svg.append(_icon_box(cx, cy, node))

    # Edges — draw solid first, then dashed on top
    def _edge_endpoints(e: dict):
        fid, tid = e["from"], e["to"]
        x1, y1 = node_cx.get(fid), node_cy.get(fid)
        x2, y2 = node_cx.get(tid), node_cy.get(tid)
        if None in (x1, y1, x2, y2):
            return None
        # Shorten to icon box edge
        half = _BOX // 2 + 4
        dx, dy = x2 - x1, y2 - y1
        dist = max((dx*dx + dy*dy)**0.5, 1)
        sx, sy = dx/dist * half, dy/dist * half
        return int(x1+sx), int(y1+sy), int(x2-sx), int(y2-sy)

    for dashed_pass in (False, True):
        for e in edges_raw:
            if bool(e.get("dashed")) != dashed_pass:
                continue
            pts = _edge_endpoints(e)
            if not pts:
                continue
            ax1, ay1, ax2, ay2 = pts
            seq = e.get("seq") if not e.get("dashed") else None
            svg.append(_arrow(ax1, ay1, ax2, ay2,
                              label=e.get("label", ""),
                              seq=seq,
                              dashed=bool(e.get("dashed"))))

    # Legend
    legend_items = [
        ("#FF9900", "Compute"), ("#8C4FFF", "Networking"), ("#3F8624", "Data"),
        ("#DD344C", "Security"), ("#E7157B", "Monitoring"), ("#C7131F", "CI/CD"),
    ]
    lx = PAD
    ly = H - 14
    for color, lbl in legend_items:
        svg += [
            f'<rect x="{lx}" y="{ly-8}" width="12" height="12" rx="3" fill="{color}"/>',
            f'<text x="{lx+16}" y="{ly+2}" font-size="9.5" fill="#64748b">{lbl}</text>',
        ]
        lx += 96

    svg.append("</svg>")
    return "\n".join(svg)


# ── Fallback: modules-based layout (when diagram JSON absent) ─────────────────

def _render_from_modules(architecture: dict[str, Any]) -> str:
    """Simple zone-based fallback when Gemini doesn't return diagram JSON."""
    modules = sorted(architecture.get("modules", []), key=lambda m: m.get("deploy_order", 99))
    arch_name = architecture.get("architecture_name", "AWS Architecture")

    _ZONE_ORDER = ["edge", "compute", "data", "platform"]
    _ZONE_LABELS = {"edge": "Edge / Network", "compute": "Compute / API",
                    "data": "Data / Storage", "platform": "Platform Services"}

    def _zone(mod: dict) -> str:
        key = _svc_key(mod.get("module", ""))
        cat = (mod.get("module", "").split("/")[0] if "/" in mod.get("module", "") else "").lower()
        if key in {"cloudfront","route53","waf","alb","nlb","api-gateway","vpc"} or cat=="networking":
            return "edge"
        if key in {"lambda","ecs","eks","ec2","fargate","appsync","cognito","step-functions"} or cat=="compute":
            return "compute"
        if key in {"rds","aurora","dynamodb","elasticache","s3","sqs","sns","kinesis"} or cat in ("data","storage"):
            return "data"
        return "platform"

    zones: dict[str, list] = {z: [] for z in _ZONE_ORDER}
    for mod in modules:
        zones[_zone(mod)].append(mod)

    # Build a fake diagram structure from modules
    zone_list, node_list, edge_list = [], [], []
    zone_type_map = {"edge":"aws_edge","compute":"vpc_private","data":"vpc_private","platform":"aws_managed"}
    for z in _ZONE_ORDER:
        mods = zones[z]
        if not mods:
            continue
        nids = [f"m{i}" for i, _ in enumerate(mods)]
        zone_list.append({"id": z, "label": _ZONE_LABELS[z], "type": zone_type_map[z], "nodes": nids})
        for i, mod in enumerate(mods):
            node_list.append({"id": f"m{i}", "label": mod.get("label", _svc_key(mod.get("module",""))),
                               "service": mod.get("module","")})

    # Simple edges: edge→compute, compute→data
    for i, em in enumerate(zones["edge"][:2]):
        for j, cm in enumerate(zones["compute"][:2]):
            edge_list.append({"from": f"m{i}", "to": f"m{len(zones['edge'])+j}",
                               "seq": i+j+1, "label": "", "dashed": False})
    base = len(zones["edge"])
    for i, cm in enumerate(zones["compute"][:2]):
        for j, dm in enumerate(zones["data"][:2]):
            edge_list.append({"from": f"m{base+i}",
                               "to": f"m{base+len(zones['compute'])+j}",
                               "seq": None, "label": "", "dashed": False})

    diagram = {"zones": zone_list, "nodes": node_list, "edges": edge_list}
    return _render_from_diagram(diagram, arch_name)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_aws_svg(architecture: dict[str, Any]) -> str:
    arch_name = architecture.get("architecture_name", "AWS Architecture")
    diagram = architecture.get("diagram")
    if diagram and diagram.get("nodes") and diagram.get("zones"):
        return _render_from_diagram(diagram, arch_name)
    return _render_from_modules(architecture)


def generate_styled_mermaid(architecture: dict[str, Any]) -> str:
    """Kept for import compatibility — not used when Gemini generates diagram JSON."""
    return architecture.get("mermaid", "graph LR\n  A[Architecture]")
