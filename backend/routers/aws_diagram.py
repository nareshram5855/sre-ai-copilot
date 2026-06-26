"""AWS-architecture-style SVG diagram generator for Stackport AI.

Produces diagrams matching the official AWS architecture diagram visual language:
- White background with orange dashed "AWS Cloud" boundary
- Colored icon boxes with white service-specific SVG icons inside
- Account/VPC boundary dashed groups
- Dark numbered circles on flow arrows
- Labels below each service box
"""
from __future__ import annotations
from typing import Any

# ── AWS brand colors per service category ─────────────────────────────────────
_CAT_COLORS: dict[str, str] = {
    "networking":    "#8C4FFF",   # purple  (CloudFront, Route53, ALB)
    "compute":       "#FF9900",   # AWS orange (Lambda, ECS, EKS)
    "data":          "#3F8624",   # green   (RDS, DynamoDB, Aurora)
    "storage":       "#3F8624",   # green   (S3)
    "security":      "#DD344C",   # red     (IAM, WAF, Secrets Mgr, Cognito)
    "cicd":          "#C7131F",   # dark red (ECR, CodePipeline)
    "monitoring":    "#E7157B",   # magenta (CloudWatch)
    "observability": "#E7157B",
    "default":       "#527FFF",
}

# Specific service key → color overrides
_SVC_COLORS: dict[str, str] = {
    "appsync":        "#E7157B",
    "cognito":        "#DD344C",
    "api-gateway":    "#8C4FFF",
    "step-functions": "#FF4F8B",
    "kinesis":        "#8C4FFF",
    "sns":            "#FF9900",
    "sqs":            "#FF9900",
    "elasticache":    "#3F8624",
    "waf":            "#DD344C",
    "kms":            "#DD344C",
    "secrets-manager":"#DD344C",
    "secrets":        "#DD344C",
    "cloudwatch":     "#E7157B",
    "github-actions": "#333333",
    "codepipeline":   "#232F3E",
    "ecr":            "#FF9900",
}

# Short display labels
_LABELS: dict[str, str] = {
    "cloudfront": "CloudFront", "route53": "Route 53", "alb": "App LB",
    "nlb": "Net LB", "waf": "WAF", "vpc": "VPC",
    "lambda": "Lambda", "ecs": "ECS", "eks": "EKS", "ec2": "EC2",
    "fargate": "Fargate", "api-gateway": "API Gateway", "appsync": "AppSync",
    "cognito": "Cognito", "step-functions": "Step Func",
    "rds": "RDS", "aurora": "Aurora", "dynamodb": "DynamoDB",
    "elasticache": "ElastiCache", "s3": "S3", "sqs": "SQS", "sns": "SNS",
    "kinesis": "Kinesis", "iam": "IAM", "secrets-manager": "Secrets Mgr",
    "secrets": "Secrets Mgr", "kms": "KMS", "cloudwatch": "CloudWatch",
    "xray": "X-Ray", "codepipeline": "CodePipeline", "ecr": "ECR",
    "github-actions": "GitHub CI",
}

# SVG icon path definitions — each centered at (0,0), fit inside ±20 viewport
_ICONS: dict[str, str] = {
    "lambda": '<text x="0" y="12" text-anchor="middle" font-size="30" font-weight="900" fill="white" font-family="Georgia,serif">λ</text>',

    "rds": (
        '<ellipse cx="0" cy="-14" rx="15" ry="6" fill="white" opacity="0.9"/>'
        '<rect x="-15" y="-14" width="30" height="26" fill="white" opacity="0.25"/>'
        '<ellipse cx="0" cy="12" rx="15" ry="6" fill="white" opacity="0.5"/>'
        '<line x1="-15" y1="-14" x2="-15" y2="12" stroke="white" stroke-width="1.5"/>'
        '<line x1="15" y1="-14" x2="15" y2="12" stroke="white" stroke-width="1.5"/>'
    ),

    "aurora": (
        '<ellipse cx="0" cy="-14" rx="15" ry="6" fill="white" opacity="0.9"/>'
        '<rect x="-15" y="-14" width="30" height="26" fill="white" opacity="0.25"/>'
        '<ellipse cx="0" cy="12" rx="15" ry="6" fill="white" opacity="0.5"/>'
        '<line x1="-15" y1="-14" x2="-15" y2="12" stroke="white" stroke-width="1.5"/>'
        '<line x1="15" y1="-14" x2="15" y2="12" stroke="white" stroke-width="1.5"/>'
    ),

    "dynamodb": (
        '<ellipse cx="0" cy="-15" rx="13" ry="5" fill="white" opacity="0.9"/>'
        '<ellipse cx="0" cy="-3"  rx="13" ry="5" fill="white" opacity="0.7"/>'
        '<ellipse cx="0" cy="9"   rx="13" ry="5" fill="white" opacity="0.5"/>'
        '<line x1="-13" y1="-15" x2="-13" y2="9" stroke="white" stroke-width="1.5"/>'
        '<line x1="13"  y1="-15" x2="13"  y2="9" stroke="white" stroke-width="1.5"/>'
    ),

    "elasticache": (
        '<ellipse cx="0" cy="-12" rx="14" ry="5" fill="white" opacity="0.9"/>'
        '<ellipse cx="0" cy="6"   rx="14" ry="5" fill="white" opacity="0.6"/>'
        '<line x1="-14" y1="-12" x2="-14" y2="6" stroke="white" stroke-width="1.5"/>'
        '<line x1="14"  y1="-12" x2="14"  y2="6" stroke="white" stroke-width="1.5"/>'
        '<text x="0" y="-8" text-anchor="middle" font-size="8" fill="white" opacity="0.95">Redis</text>'
    ),

    "s3": (
        '<path d="M0,-20 L13,-9 L13,11 Q13,20 0,20 Q-13,20 -13,11 L-13,-9 Z" '
        'fill="white" opacity="0.3" stroke="white" stroke-width="1.5"/>'
        '<ellipse cx="0" cy="-20" rx="13" ry="5" fill="white" opacity="0.85"/>'
        '<line x1="-13" y1="-9" x2="13" y2="-9" stroke="white" stroke-width="1.5" opacity="0.7"/>'
    ),

    "cloudfront": (
        '<circle cx="0" cy="0" r="17" fill="none" stroke="white" stroke-width="1.8"/>'
        '<ellipse cx="0" cy="0" rx="7" ry="17" fill="none" stroke="white" stroke-width="1.5"/>'
        '<line x1="-17" y1="0" x2="17" y2="0" stroke="white" stroke-width="1.5"/>'
        '<line x1="-14" y1="-10" x2="14" y2="-10" stroke="white" stroke-width="1" opacity="0.7"/>'
        '<line x1="-14" y1="10" x2="14" y2="10" stroke="white" stroke-width="1" opacity="0.7"/>'
    ),

    "route53": (
        '<circle cx="0" cy="0" r="17" fill="none" stroke="white" stroke-width="1.8"/>'
        '<ellipse cx="0" cy="0" rx="7" ry="17" fill="none" stroke="white" stroke-width="1.5"/>'
        '<line x1="-17" y1="0" x2="17" y2="0" stroke="white" stroke-width="1.5"/>'
    ),

    "alb": (
        '<circle cx="-14" cy="-12" r="3" fill="white" opacity="0.85"/>'
        '<circle cx="0"   cy="-12" r="3" fill="white" opacity="0.85"/>'
        '<circle cx="14"  cy="-12" r="3" fill="white" opacity="0.85"/>'
        '<line x1="-14" y1="-9" x2="-14" y2="10" stroke="white" stroke-width="1.5"/>'
        '<line x1="0"   y1="-9" x2="0"   y2="10" stroke="white" stroke-width="1.5"/>'
        '<line x1="14"  y1="-9" x2="14"  y2="10" stroke="white" stroke-width="1.5"/>'
        '<line x1="-17" y1="-12" x2="17" y2="-12" stroke="white" stroke-width="2"/>'
        '<circle cx="-14" cy="13" r="3" fill="white" opacity="0.6"/>'
        '<circle cx="0"   cy="13" r="3" fill="white" opacity="0.6"/>'
        '<circle cx="14"  cy="13" r="3" fill="white" opacity="0.6"/>'
    ),

    "ecs": (
        '<rect x="-18" y="-14" width="14" height="11" rx="2" fill="white" opacity="0.85"/>'
        '<rect x="4"   y="-14" width="14" height="11" rx="2" fill="white" opacity="0.85"/>'
        '<rect x="-18" y="3"   width="14" height="11" rx="2" fill="white" opacity="0.65"/>'
        '<rect x="4"   y="3"   width="14" height="11" rx="2" fill="white" opacity="0.65"/>'
    ),

    "fargate": (
        '<rect x="-18" y="-14" width="14" height="11" rx="2" fill="white" opacity="0.85"/>'
        '<rect x="4"   y="-14" width="14" height="11" rx="2" fill="white" opacity="0.85"/>'
        '<rect x="-18" y="3"   width="14" height="11" rx="2" fill="white" opacity="0.65"/>'
        '<rect x="4"   y="3"   width="14" height="11" rx="2" fill="white" opacity="0.65"/>'
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
        '<path d="M-15,18 Q-15,2 0,2 Q15,2 15,18" fill="white" opacity="0.6"/>'
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
        '<path d="M0,-20 L17,-10 L17,7 Q17,20 0,20 Q-17,20 -17,7 L-17,-10 Z" '
        'fill="none" stroke="white" stroke-width="2"/>'
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
        '<line x1="-9" y1="-8" x2="9"  y2="-8" stroke="white" stroke-width="1.8"/>'
        '<line x1="-9" y1="0"  x2="9"  y2="0"  stroke="white" stroke-width="1.8"/>'
        '<line x1="-9" y1="8"  x2="9"  y2="8"  stroke="white" stroke-width="1.8"/>'
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

    "codepipeline": (
        '<rect x="-16" y="-14" width="12" height="9" rx="2" fill="white" opacity="0.85"/>'
        '<rect x="4"   y="-14" width="12" height="9" rx="2" fill="white" opacity="0.65"/>'
        '<rect x="-16" y="5"   width="12" height="9" rx="2" fill="white" opacity="0.45"/>'
        '<rect x="4"   y="5"   width="12" height="9" rx="2" fill="white" opacity="0.35"/>'
        '<line x1="-4" y1="-10" x2="3" y2="-10" stroke="white" stroke-width="1.5"/>'
        '<line x1="0"  y1="-5"  x2="-12" y2="5" stroke="white" stroke-width="1.5"/>'
        '<line x1="0"  y1="-5"  x2="12"  y2="5" stroke="white" stroke-width="1.5"/>'
    ),

    "sqs": (
        '<rect x="-18" y="-8" width="36" height="16" rx="8" fill="none" stroke="white" stroke-width="2"/>'
        '<circle cx="-9" cy="0" r="3" fill="white" opacity="0.9"/>'
        '<circle cx="0"  cy="0" r="3" fill="white" opacity="0.9"/>'
        '<circle cx="9"  cy="0" r="3" fill="white" opacity="0.9"/>'
    ),

    "sns": (
        '<path d="M-12,-18 L12,-18 L18,-8 L12,2 L4,2 L0,18 L-4,2 L-12,2 L-18,-8 Z" '
        'fill="white" opacity="0.7" stroke="white" stroke-width="1.5"/>'
    ),

    "kinesis": (
        '<path d="M-17,-10 Q-7,-4 0,-10 Q7,-16 17,-10" fill="none" stroke="white" stroke-width="2"/>'
        '<path d="M-17,0  Q-7,6  0,0  Q7,-6  17,0"  fill="none" stroke="white" stroke-width="2"/>'
        '<path d="M-17,10 Q-7,16 0,10 Q7,4  17,10"  fill="none" stroke="white" stroke-width="2"/>'
    ),

    "vpc": (
        '<path d="M-17,6 Q-19,-10 -7,-13 Q-4,-21 5,-21 Q15,-21 18,-13 Q24,-10 17,6 Z" '
        'fill="none" stroke="white" stroke-width="2"/>'
        '<line x1="-7" y1="17" x2="-17" y2="6" stroke="white" stroke-width="1.5"/>'
        '<line x1="7"  y1="17" x2="17"  y2="6" stroke="white" stroke-width="1.5"/>'
        '<line x1="-7" y1="17" x2="7"   y2="17" stroke="white" stroke-width="1.5"/>'
    ),

    "github-actions": (
        '<circle cx="0" cy="0" r="17" fill="none" stroke="white" stroke-width="2"/>'
        '<circle cx="0" cy="-4" r="6"  fill="none" stroke="white" stroke-width="2"/>'
        '<circle cx="-10" cy="12" r="3" fill="white" opacity="0.8"/>'
        '<circle cx="10"  cy="12" r="3" fill="white" opacity="0.8"/>'
    ),

    "xray": (
        '<line x1="-16" y1="0" x2="16" y2="0" stroke="white" stroke-width="2.5"/>'
        '<line x1="-16" y1="0" x2="-6" y2="-14" stroke="white" stroke-width="1.5"/>'
        '<line x1="-16" y1="0" x2="-6" y2="14"  stroke="white" stroke-width="1.5"/>'
        '<line x1="16"  y1="0" x2="6"  y2="-14" stroke="white" stroke-width="1.5"/>'
        '<line x1="16"  y1="0" x2="6"  y2="14"  stroke="white" stroke-width="1.5"/>'
    ),
}

# Aliases
_ICONS["secrets"] = _ICONS["secrets-manager"] = _ICONS.get("secrets-manager", _ICONS["iam"])
_ICONS["nlb"] = _ICONS["alb"]


def _svc_key(module: str) -> str:
    return (module.split("/")[-1] if "/" in module else module).lower()


def _svc_label(module: str) -> str:
    key = _svc_key(module)
    return _LABELS.get(key, key.replace("-", " ").title())


def _svc_color(module: str) -> str:
    key = _svc_key(module)
    if key in _SVC_COLORS:
        return _SVC_COLORS[key]
    cat = (module.split("/")[0] if "/" in module else "default").lower()
    return _CAT_COLORS.get(cat, _CAT_COLORS["default"])


def _svc_icon(module: str) -> str:
    key = _svc_key(module)
    if key in _ICONS:
        return _ICONS[key]
    # Generic: show 2-char abbreviation
    abbr = _LABELS.get(key, key.upper())[:3]
    return (
        f'<text x="0" y="8" text-anchor="middle" font-size="16" '
        f'font-weight="800" fill="white" font-family="Inter,system-ui,sans-serif">{abbr}</text>'
    )


def _zone_for(module: str) -> str:
    cat = (module.split("/")[0] if "/" in module else "").lower()
    key = _svc_key(module)
    _edge = {"cloudfront", "route53", "waf", "alb", "nlb", "vpc", "api-gateway"}
    _compute = {"lambda", "ecs", "eks", "ec2", "fargate", "appsync",
                "cognito", "step-functions"}
    _data = {"rds", "aurora", "dynamodb", "elasticache", "s3",
             "sqs", "sns", "kinesis"}
    if key in _edge or cat == "networking":
        return "edge"
    if key in _compute or cat == "compute":
        return "compute"
    if key in _data or cat in ("data", "storage"):
        return "data"
    return "platform"


# ── SVG builders ──────────────────────────────────────────────────────────────

def _icon_box(cx: int, cy: int, size: int, module: str, order: int | None = None) -> str:
    """Render one service icon box centered at (cx, cy)."""
    r = 10
    half = size // 2
    color = _svc_color(module)
    icon_svg = _svc_icon(module)
    label = _svc_label(module)

    # Split long labels to two lines
    words = label.split()
    if len(words) == 1 or len(label) <= 11:
        lbl_lines = [f'<text x="{cx}" y="{cy + half + 16}" text-anchor="middle" '
                     f'font-size="11" font-weight="600" fill="#1a2744">{label}</text>']
    else:
        mid = len(words) // 2
        l1 = " ".join(words[:mid])
        l2 = " ".join(words[mid:])
        lbl_lines = [
            f'<text x="{cx}" y="{cy + half + 13}" text-anchor="middle" '
            f'font-size="10.5" font-weight="600" fill="#1a2744">{l1}</text>',
            f'<text x="{cx}" y="{cy + half + 25}" text-anchor="middle" '
            f'font-size="10.5" font-weight="600" fill="#1a2744">{l2}</text>',
        ]

    parts = [
        # Drop shadow
        f'<rect x="{cx - half + 2}" y="{cy - half + 2}" width="{size}" height="{size}" '
        f'rx="{r}" fill="#00000018"/>',
        # Icon square
        f'<rect x="{cx - half}" y="{cy - half}" width="{size}" height="{size}" '
        f'rx="{r}" fill="{color}"/>',
        # White inner icon (transformed to icon box center)
        f'<g transform="translate({cx},{cy})">{icon_svg}</g>',
    ] + lbl_lines

    # Deploy-order badge
    if order is not None:
        bx = cx + half - 1
        by = cy - half + 1
        parts += [
            f'<circle cx="{bx}" cy="{by}" r="10" fill="#1a2744" stroke="{color}" stroke-width="1.5"/>',
            f'<text x="{bx}" y="{by + 4}" text-anchor="middle" '
            f'font-size="9" font-weight="700" fill="{color}">{order}</text>',
        ]

    return "\n".join(parts)


def _flow_arrow(x1: int, y1: int, x2: int, y2: int, num: int, color: str = "#1a2744") -> str:
    """Arrow with a numbered dark circle at midpoint."""
    mx = (x1 + x2) // 2
    my = (y1 + y2) // 2
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{color}" stroke-width="1.5" marker-end="url(#ah)"/>\n'
        f'<circle cx="{mx}" cy="{my}" r="10" fill="{color}"/>\n'
        f'<text x="{mx}" y="{my + 4}" text-anchor="middle" '
        f'font-size="10" font-weight="700" fill="white">{num}</text>'
    )


def _user_icon(cx: int, cy: int) -> str:
    return (
        f'<circle cx="{cx}" cy="{cy - 9}" r="10" fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.5"/>'
        f'<circle cx="{cx}" cy="{cy - 9}" r="4" fill="#64748b"/>'
        f'<path d="M{cx-10},{cy+5} Q{cx-10},{cy-2} {cx},{cy-2} Q{cx+10},{cy-2} {cx+10},{cy+5}" '
        f'fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.5"/>'
        f'<text x="{cx}" y="{cy + 20}" text-anchor="middle" font-size="10" '
        f'font-weight="600" fill="#475569">Users</text>'
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_aws_svg(architecture: dict[str, Any]) -> str:
    """Return a professional AWS-architecture-style SVG string."""

    modules = sorted(
        architecture.get("modules", []),
        key=lambda m: m.get("deploy_order", 99),
    )
    arch_name = architecture.get("architecture_name", "AWS Architecture")

    # ── Zone assignment ───────────────────────────────────────────────────────
    zones: dict[str, list[dict]] = {
        "edge": [], "compute": [], "data": [], "platform": []
    }
    for mod in modules:
        zones[_zone_for(mod.get("module", ""))].append(mod)

    # ── Canvas ────────────────────────────────────────────────────────────────
    W, H = 1200, 680
    PAD = 28
    BOX = 60           # icon box size
    BOX_GAP_V = 32     # vertical gap between boxes in a column
    COL_INNER = 24     # padding inside zone columns

    # Three main columns
    COL_COUNT = 3
    COL_GAP = 18
    col_w = (W - PAD * 2 - 60 - COL_GAP * (COL_COUNT - 1)) // COL_COUNT  # 60 = user space on left
    LEFT_OFFSET = 60  # space for user icon

    col_x = [
        PAD + LEFT_OFFSET,
        PAD + LEFT_OFFSET + col_w + COL_GAP,
        PAD + LEFT_OFFSET + (col_w + COL_GAP) * 2,
    ]

    # Max items per column → column height
    max_items = max(
        max(len(zones[z]) for z in ("edge", "compute", "data")), 1
    )
    MAIN_TOP = 90
    col_h = max_items * (BOX + BOX_GAP_V) + COL_INNER * 2
    MAIN_H = col_h

    PLAT_TOP = MAIN_TOP + MAIN_H + 22
    PLAT_H = 100

    TOTAL_H = PLAT_TOP + PLAT_H + PAD
    # Adjust SVG height dynamically
    H = TOTAL_H

    # ── Header ────────────────────────────────────────────────────────────────
    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'style="background:#f0f4f8;font-family:Inter,\'Segoe UI\',system-ui,sans-serif;">',

        '<defs>'
        '<marker id="ah" markerWidth="9" markerHeight="7" refX="9" refY="3.5" orient="auto">'
        '<polygon points="0 0, 9 3.5, 0 7" fill="#1a2744"/>'
        '</marker>'
        '<filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">'
        '<feDropShadow dx="1" dy="2" stdDeviation="3" flood-color="#00000018"/>'
        '</filter>'
        '</defs>',

        # Background
        f'<rect x="0" y="0" width="{W}" height="{H}" fill="#f0f4f8"/>',

        # Title bar
        f'<rect x="0" y="0" width="{W}" height="52" fill="#1a2744"/>',
        f'<text x="{W // 2}" y="33" text-anchor="middle" font-size="17" '
        f'font-weight="700" fill="white" letter-spacing="-0.3">{arch_name}</text>',
        f'<text x="{W - PAD}" y="33" text-anchor="end" font-size="11" '
        f'fill="#FF9900" font-weight="600">Generated by Stackport AI</text>',
    ]

    # ── AWS Cloud boundary ────────────────────────────────────────────────────
    cloud_y = 62
    cloud_h = H - cloud_y - 10
    svg += [
        # Main AWS Cloud box
        f'<rect x="{PAD // 2}" y="{cloud_y}" width="{W - PAD}" height="{cloud_h}" rx="8" '
        f'fill="white" stroke="#FF9900" stroke-width="2" stroke-dasharray="10,5"/>',

        # AWS Cloud label chip
        f'<rect x="{PAD // 2 + 2}" y="{cloud_y - 10}" width="108" height="22" rx="4" '
        f'fill="white" stroke="#FF9900" stroke-width="1.5"/>',
        # Mini AWS logo (orange square with "aws")
        f'<rect x="{PAD // 2 + 6}" y="{cloud_y - 6}" width="16" height="14" rx="3" fill="#FF9900"/>',
        f'<text x="{PAD // 2 + 14}" y="{cloud_y + 4}" text-anchor="middle" '
        f'font-size="8" font-weight="900" fill="white">aws</text>',
        f'<text x="{PAD // 2 + 70}" y="{cloud_y + 4}" text-anchor="middle" '
        f'font-size="11" font-weight="700" fill="#232F3E">AWS Cloud</text>',
    ]

    # ── Zone column backgrounds & labels ──────────────────────────────────────
    zone_defs = [
        ("edge",    col_x[0], "Edge / Network"),
        ("compute", col_x[1], "Compute / API"),
        ("data",    col_x[2], "Data / Storage"),
    ]

    for zone_key, cx, zlabel in zone_defs:
        svg += [
            f'<rect x="{cx}" y="{MAIN_TOP}" width="{col_w}" height="{MAIN_H}" rx="8" '
            f'fill="#f8fafc" stroke="#e2e8f0" stroke-width="1.5"/>',
            f'<text x="{cx + col_w // 2}" y="{MAIN_TOP + 18}" text-anchor="middle" '
            f'font-size="10" font-weight="700" fill="#64748b" letter-spacing="1">'
            f'{zlabel.upper()}</text>',
        ]

        mods = zones[zone_key][:6]  # max 6 per column
        for j, mod in enumerate(mods):
            item_cx = cx + col_w // 2
            item_cy = MAIN_TOP + COL_INNER + 28 + j * (BOX + BOX_GAP_V)
            svg.append(_icon_box(item_cx, item_cy, BOX, mod.get("module", ""), mod.get("deploy_order")))

    # ── Platform services band ────────────────────────────────────────────────
    plat_mods = zones["platform"]
    if plat_mods:
        svg += [
            f'<rect x="{PAD + LEFT_OFFSET}" y="{PLAT_TOP}" '
            f'width="{W - PAD * 2 - LEFT_OFFSET}" height="{PLAT_H}" rx="8" '
            f'fill="#f8fafc" stroke="#e2e8f0" stroke-width="1.5"/>',
            f'<text x="{PAD + LEFT_OFFSET + 14}" y="{PLAT_TOP + 18}" '
            f'font-size="10" font-weight="700" fill="#64748b" letter-spacing="1">'
            f'PLATFORM SERVICES</text>',
        ]
        n = min(len(plat_mods), 7)
        avail_w = W - PAD * 2 - LEFT_OFFSET - 20
        step = avail_w // n
        for k, mod in enumerate(plat_mods[:7]):
            px = PAD + LEFT_OFFSET + 10 + k * step + step // 2
            py = PLAT_TOP + PLAT_H // 2 + 4
            svg.append(_icon_box(px, py, BOX - 4, mod.get("module", ""), mod.get("deploy_order")))

    # ── User icon on left ─────────────────────────────────────────────────────
    user_cx = PAD + LEFT_OFFSET // 2 - 4
    user_cy = MAIN_TOP + MAIN_H // 2 - 10
    svg.append(_user_icon(user_cx, user_cy))

    # ── Flow arrows ───────────────────────────────────────────────────────────
    arrow_num = 1

    def _first_cy(zone_key: str, default_y: int) -> int:
        mods = zones[zone_key]
        if not mods:
            return default_y
        return MAIN_TOP + COL_INNER + 28  # y-center of first item

    # User → Edge
    if zones["edge"]:
        ey = _first_cy("edge", MAIN_TOP + MAIN_H // 2)
        svg.append(_flow_arrow(user_cx + 10, user_cy - 8, col_x[0] - 4, ey, arrow_num))
        arrow_num += 1

    # Edge → Compute
    if zones["edge"] and zones["compute"]:
        rows = min(2, len(zones["edge"]), len(zones["compute"]))
        for row in range(rows):
            ay = MAIN_TOP + COL_INNER + 28 + row * (BOX + BOX_GAP_V)
            ax1 = col_x[0] + col_w
            ax2 = col_x[1]
            svg.append(_flow_arrow(ax1, ay, ax2, ay, arrow_num))
            arrow_num += 1

    # Compute → Data
    if zones["compute"] and zones["data"]:
        rows = min(2, len(zones["compute"]), len(zones["data"]))
        for row in range(rows):
            ay = MAIN_TOP + COL_INNER + 28 + row * (BOX + BOX_GAP_V)
            ax1 = col_x[1] + col_w
            ax2 = col_x[2]
            svg.append(_flow_arrow(ax1, ay, ax2, ay, arrow_num))
            arrow_num += 1

    # Data → Platform (vertical)
    if zones["data"] and zones["platform"]:
        ax = col_x[2] + col_w // 2
        ay1 = MAIN_TOP + MAIN_H
        ay2 = PLAT_TOP
        svg.append(
            f'<line x1="{ax}" y1="{ay1}" x2="{ax}" y2="{ay2}" '
            f'stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="5,3" marker-end="url(#ah)"/>'
        )

    # Compute → Platform (vertical, center)
    if zones["compute"] and zones["platform"]:
        ax = col_x[1] + col_w // 2
        ay1 = MAIN_TOP + MAIN_H
        ay2 = PLAT_TOP
        svg.append(
            f'<line x1="{ax}" y1="{ay1}" x2="{ax}" y2="{ay2}" '
            f'stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="5,3" marker-end="url(#ah)"/>'
        )

    # ── Legend ────────────────────────────────────────────────────────────────
    legend_items = [
        ("#FF9900", "Compute"), ("#8C4FFF", "Networking"), ("#3F8624", "Data/Storage"),
        ("#DD344C", "Security"), ("#E7157B", "Monitoring"), ("#C7131F", "CI/CD"),
    ]
    lx = PAD + LEFT_OFFSET + 10
    ly = H - 14
    for color, lbl in legend_items:
        svg += [
            f'<rect x="{lx}" y="{ly - 8}" width="12" height="12" rx="3" fill="{color}"/>',
            f'<text x="{lx + 16}" y="{ly + 2}" font-size="10" fill="#64748b">{lbl}</text>',
        ]
        lx += 100

    svg.append("</svg>")
    return "\n".join(svg)


# ── Styled Mermaid fallback (works with current frontend without SVG support) ──

def generate_styled_mermaid(architecture: dict[str, Any]) -> str:
    """Generate a color-coded Mermaid LR diagram from architecture JSON.

    Overrides Gemini's raw mermaid output with a deterministic, well-labelled
    diagram using AWS brand colors via classDef — works with the existing dark
    Mermaid theme in the Stackport frontend without any frontend changes.
    """
    modules = sorted(
        architecture.get("modules", []),
        key=lambda m: m.get("deploy_order", 99),
    )

    lines = [
        "graph LR",
        "  classDef networking fill:#8C4FFF,stroke:#7040CC,color:#fff",
        "  classDef compute    fill:#FF9900,stroke:#CC7A00,color:#fff",
        "  classDef data       fill:#3F8624,stroke:#2E6418,color:#fff",
        "  classDef storage    fill:#3F8624,stroke:#2E6418,color:#fff",
        "  classDef security   fill:#DD344C,stroke:#AA2238,color:#fff",
        "  classDef monitoring fill:#E7157B,stroke:#B50F60,color:#fff",
        "  classDef observability fill:#E7157B,stroke:#B50F60,color:#fff",
        "  classDef cicd       fill:#C7131F,stroke:#960F18,color:#fff",
        "  classDef platform   fill:#232F3E,stroke:#1A2533,color:#fff",
    ]

    _cls_map = {
        "networking": "networking", "compute": "compute",
        "data": "data", "storage": "storage",
        "security": "security", "monitoring": "monitoring",
        "observability": "observability", "cicd": "cicd",
    }

    # Build node list
    node_ids: dict[str, str] = {}
    for i, mod in enumerate(modules):
        nid = f"N{i}"
        node_ids[mod.get("module", "")] = nid
        label = _svc_label(mod.get("module", ""))
        cat = (mod.get("module", "").split("/")[0] if "/" in mod.get("module", "") else "platform").lower()
        cls = _cls_map.get(cat, "platform")
        lines.append(f"  {nid}[{label}]:::{cls}")

    # Draw edges by zone flow: edge → compute → data; platform dotted to compute
    zones: dict[str, list[dict]] = {"edge": [], "compute": [], "data": [], "platform": []}
    for mod in modules:
        zones[_zone_for(mod.get("module", ""))].append(mod)

    def _nid(mod: dict) -> str | None:
        return node_ids.get(mod.get("module", ""))

    # Sequential within edge
    edge = zones["edge"]
    for i in range(len(edge) - 1):
        a, b = _nid(edge[i]), _nid(edge[i + 1])
        if a and b:
            lines.append(f"  {a} --> {b}")

    # Edge → Compute (last edge → first compute)
    if edge and zones["compute"]:
        a = _nid(edge[-1])
        for cm in zones["compute"][:2]:
            b = _nid(cm)
            if a and b:
                lines.append(f"  {a} --> {b}")

    # Compute → Data
    for cm in zones["compute"][:2]:
        for dm in zones["data"][:3]:
            a, b = _nid(cm), _nid(dm)
            if a and b:
                lines.append(f"  {a} --> {b}")

    # Platform → Compute (dotted — observability/security watching compute)
    for pm in zones["platform"][:3]:
        for cm in zones["compute"][:1]:
            a, b = _nid(pm), _nid(cm)
            if a and b:
                lines.append(f"  {a} -.-> {b}")

    return "\n".join(lines)
