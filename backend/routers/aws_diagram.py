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
    # AI / ML — teal to distinguish from compute/data
    "bedrock": "#01A88D", "opensearch": "#01A88D", "sagemaker": "#01A88D",
    "knowledge-base": "#01A88D", "vector-store": "#01A88D",
}

_CAT_COLORS: dict[str, str] = {
    "networking": "#8C4FFF", "compute": "#FF9900", "data": "#3F8624",
    "storage": "#3F8624", "security": "#DD344C", "cicd": "#C7131F",
    "monitoring": "#E7157B", "observability": "#E7157B",
    "ai": "#01A88D", "ml": "#01A88D",
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
    # AI / ML
    "bedrock": "Bedrock", "opensearch": "OpenSearch", "sagemaker": "SageMaker",
    "knowledge-base": "Knowledge Base", "vector-store": "Vector Store",
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
    # ── AI / ML icons ─────────────────────────────────────────────────────────
    # Bedrock: neural network / foundation model — triangle of nodes connected
    "bedrock": (
        '<circle cx="0"   cy="-16" r="4.5" fill="white" opacity="0.95"/>'
        '<circle cx="-14" cy="8"   r="4.5" fill="white" opacity="0.95"/>'
        '<circle cx="14"  cy="8"   r="4.5" fill="white" opacity="0.95"/>'
        '<line x1="0" y1="-11" x2="-10" y2="4" stroke="white" stroke-width="1.8" opacity="0.85"/>'
        '<line x1="0" y1="-11" x2="10"  y2="4" stroke="white" stroke-width="1.8" opacity="0.85"/>'
        '<line x1="-10" y1="4" x2="10"  y2="4" stroke="white" stroke-width="1.8" opacity="0.85"/>'
        '<circle cx="0" cy="-3" r="3" fill="white" opacity="0.7"/>'
    ),
    # OpenSearch: magnifying glass — vector/semantic search
    "opensearch": (
        '<circle cx="-3" cy="-3" r="12" fill="none" stroke="white" stroke-width="2.5"/>'
        '<line x1="6" y1="6" x2="17" y2="17" stroke="white" stroke-width="3" stroke-linecap="round"/>'
        '<line x1="-9" y1="-3" x2="3" y2="-3" stroke="white" stroke-width="1.5" opacity="0.7"/>'
        '<line x1="-3" y1="-9" x2="-3" y2="3" stroke="white" stroke-width="1.5" opacity="0.7"/>'
    ),
    # SageMaker: ML pipeline layers with connector
    "sagemaker": (
        '<rect x="-16" y="-17" width="32" height="10" rx="3" fill="white" opacity="0.85"/>'
        '<rect x="-16" y="-3"  width="32" height="10" rx="3" fill="white" opacity="0.6"/>'
        '<rect x="-16" y="11"  width="32" height="10" rx="3" fill="white" opacity="0.4"/>'
        '<line x1="0" y1="-7"  x2="0" y2="-3"  stroke="white" stroke-width="1.8"/>'
        '<line x1="0" y1="7"   x2="0" y2="11"  stroke="white" stroke-width="1.8"/>'
    ),
}
_ICONS["secrets"] = _ICONS["secrets-manager"]
_ICONS["knowledge-base"] = _ICONS["opensearch"]
_ICONS["vector-store"]   = _ICONS["opensearch"]
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
           label: str = "", seq: int | None = None, dashed: bool = False,
           mid_offset: int = 0) -> str:
    stroke   = "#64748b" if dashed else "#1e293b"
    marker   = "ah-dashed" if dashed else "ah"
    dash_attr = 'stroke-dasharray="6,4"' if dashed else ""
    w        = 2.0 if not dashed else 1.5
    mid_x, mid_y = (x1 + x2) // 2, (y1 + y2) // 2

    # Perpendicular offset for label (avoids stacking over numbered circles)
    if mid_offset and (x2 != x1 or y2 != y1):
        dx, dy = x2 - x1, y2 - y1
        dist = max((dx*dx + dy*dy) ** 0.5, 1)
        lx = mid_x + int(-dy / dist * mid_offset)
        ly = mid_y + int(dx / dist * mid_offset)
    else:
        lx, ly = mid_x, mid_y

    parts = [
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{stroke}" stroke-width="{w}" {dash_attr} marker-end="url(#{marker})"/>'
    ]

    if seq is not None:
        parts += [
            f'<circle cx="{mid_x}" cy="{mid_y}" r="11" fill="#1e293b"/>',
            f'<text x="{mid_x}" y="{mid_y+4}" text-anchor="middle" '
            f'font-size="10" font-weight="700" fill="white">{seq}</text>',
        ]
    elif label:
        tw = len(label) * 6 + 14
        parts += [
            f'<rect x="{lx-tw//2}" y="{ly-9}" width="{tw}" height="16" rx="4" '
            f'fill="white" stroke="#e2e8f0" stroke-width="1" opacity="0.95"/>',
            f'<text x="{lx}" y="{ly+4}" text-anchor="middle" font-size="9" fill="{stroke}">{label}</text>',
        ]

    return "\n".join(parts)


# ── Primary renderer: uses diagram JSON from Gemini ───────────────────────────

def _render_from_diagram(diagram: dict, arch_name: str) -> str:
    zones_raw: list[dict] = diagram.get("zones", [])
    nodes_raw: list[dict] = diagram.get("nodes", [])
    edges_raw: list[dict] = diagram.get("edges", [])

    node_map: dict[str, dict] = {n["id"]: n for n in nodes_raw}

    # ── Strip common app-name prefix that Gemini often adds to every label ────
    # e.g. "Payments ALB" "Payments EKS" "Payments RDS" → "ALB" "EKS" "RDS"
    _KNOWN_AWS = {
        "alb","nlb","waf","cloudfront","route53","apigw","apigateway","cognito",
        "eks","ecs","ec2","lambda","fargate","rds","aurora","dynamodb","elasticache",
        "s3","sqs","sns","kinesis","kms","iam","ecr","cloudwatch","xray","msk",
        "users","user","internet","client","browser","on-prem","vpn",
    }
    all_labels = [n.get("label","") for n in nodes_raw if n.get("label","")]
    first_words = [lbl.split()[0].lower() for lbl in all_labels if " " in lbl]
    if first_words:
        from collections import Counter
        common_word, cnt = Counter(first_words).most_common(1)[0]
        # Strip if it's a repeated non-AWS word (app/team name prefix)
        if cnt >= max(2, len(nodes_raw) // 2) and common_word not in _KNOWN_AWS:
            for nid, n in list(node_map.items()):
                lbl = n.get("label", "")
                if lbl.lower().startswith(common_word + " "):
                    node_map[nid] = {**n, "label": lbl[len(common_word)+1:]}

    # ── Layout constants ──────────────────────────────────────────────────────
    PAD       = 30
    ZONE_PAD  = 22   # inner padding of zone box
    BOX_GAP_H = 22   # horizontal gap between icon boxes in a column
    BOX_GAP_V = 52   # vertical gap — extra room for labels below icons (was 42)
    ZONE_GAP  = 22   # gap between zone columns
    CHIP_H    = 22   # zone label chip height (sits on border)
    NODE_TOP  = 18   # offset below zone top before first icon center
    MAX_ROWS  = 4    # max nodes stacked vertically in a zone column

    zone_nodes: dict[str, list[str]] = {z["id"]: z.get("nodes", []) for z in zones_raw}

    vpc_zone_types = {"vpc_public", "vpc_private"}
    vpc_zones = [z for z in zones_raw if z.get("type") in vpc_zone_types]
    has_vpc = bool(vpc_zones)
    VPC_WRAP = 14   # extra padding around vpc zone cluster

    # Each zone box starts this far down (leaves room for VPC label)
    ZONE_TOP = PAD + 62 + (CHIP_H + VPC_WRAP if has_vpc else 0)

    def _zone_cols(nids: list[str]) -> int:
        return max(1, (len(nids) + MAX_ROWS - 1) // MAX_ROWS)

    def _zone_width(nids: list[str]) -> int:
        cols = _zone_cols(nids)
        return ZONE_PAD * 2 + cols * _BOX + (cols - 1) * BOX_GAP_H

    def _zone_height(nids: list[str]) -> int:
        rows = min(len(nids), MAX_ROWS) if nids else 1
        # icon + label space + top/bottom padding
        return CHIP_H + NODE_TOP + rows * (_BOX + 26) + (rows - 1) * (BOX_GAP_V - _BOX - 26) + ZONE_PAD

    # Recalculate: zone_height = chip + top_pad + rows*(box + label_gap) + bottom_pad
    def _zone_h(nids: list[str]) -> int:
        rows = min(len(nids), MAX_ROWS) if nids else 1
        return CHIP_H + ZONE_PAD + rows * _BOX + (rows - 1) * BOX_GAP_V + 36 + ZONE_PAD

    max_zone_h = max((_zone_h(zone_nodes.get(z["id"], [])) for z in zones_raw), default=260)
    max_zone_h = max(max_zone_h, 220)

    # X positions
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

    # VPC wrapper box
    if has_vpc:
        vpc_x1 = min(zone_x[z["id"]] for z in vpc_zones) - VPC_WRAP
        vpc_x2 = max(zone_x[z["id"]] + zone_w[z["id"]] for z in vpc_zones) + VPC_WRAP
    else:
        vpc_x1 = vpc_x2 = 0

    # Canvas height: extra 48px for node label text below bottom icon row
    LEGEND_H = 32
    NODE_LABEL_OVERHANG = 48   # label text sits below icon bottom edge
    H = ZONE_TOP + max_zone_h + NODE_LABEL_OVERHANG + LEGEND_H + PAD

    # ── Node center positions ─────────────────────────────────────────────────
    node_cx: dict[str, int] = {}
    node_cy: dict[str, int] = {}

    for z in zones_raw:
        zid  = z["id"]
        nids = zone_nodes.get(zid, [])
        zx   = zone_x[zid]

        for i, nid in enumerate(nids):
            col = i // MAX_ROWS
            row = i % MAX_ROWS
            cx = zx + ZONE_PAD + col * (_BOX + BOX_GAP_H) + _BOX // 2
            # First node starts below chip + padding; subsequent spaced by BOX+BOX_GAP_V
            cy = ZONE_TOP + CHIP_H + ZONE_PAD + row * (_BOX + BOX_GAP_V) + _BOX // 2
            node_cx[nid] = cx
            node_cy[nid] = cy

    # ── SVG header ────────────────────────────────────────────────────────────
    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'style="background:#f8fafc;font-family:Inter,\'Segoe UI\',system-ui,sans-serif;">',
        '<defs>'
        '<marker id="ah" markerWidth="9" markerHeight="7" refX="9" refY="3.5" orient="auto">'
        '<polygon points="0 0, 9 3.5, 0 7" fill="#1e293b"/>'
        '</marker>'
        '<marker id="ah-dashed" markerWidth="9" markerHeight="7" refX="9" refY="3.5" orient="auto">'
        '<polygon points="0 0, 9 3.5, 0 7" fill="#64748b"/>'
        '</marker>'
        '</defs>',
        f'<rect x="0" y="0" width="{W}" height="{H}" fill="#f8fafc"/>',
        # Title bar — watermark moved to bottom-right to avoid title overlap
        f'<rect x="0" y="0" width="{W}" height="52" fill="#1e293b"/>',
        f'<text x="{W//2}" y="33" text-anchor="middle" font-size="17" font-weight="700" fill="white">{arch_name}</text>',
        # AWS Cloud dashed border
        f'<rect x="{PAD//2}" y="60" width="{W-PAD}" height="{H-68}" rx="10" '
        f'fill="#FFFBF5" stroke="#FF9900" stroke-width="2" stroke-dasharray="10,5"/>',
        # AWS chip on border
        f'<rect x="{PAD//2+6}" y="53" width="116" height="24" rx="6" fill="white" stroke="#FF9900" stroke-width="1.5"/>',
        f'<rect x="{PAD//2+10}" y="57" width="18" height="14" rx="3" fill="#FF9900"/>',
        f'<text x="{PAD//2+19}" y="67" text-anchor="middle" font-size="8" font-weight="900" fill="white">aws</text>',
        f'<text x="{PAD//2+76}" y="70" text-anchor="middle" font-size="11.5" font-weight="700" fill="#232F3E">AWS Cloud</text>',
    ]

    # ── VPC wrapper ───────────────────────────────────────────────────────────
    if has_vpc:
        vpc_top = ZONE_TOP - VPC_WRAP - CHIP_H
        vpc_bot = ZONE_TOP + max_zone_h + VPC_WRAP
        svg += [
            f'<rect x="{vpc_x1}" y="{vpc_top}" width="{vpc_x2-vpc_x1}" height="{vpc_bot-vpc_top}" rx="10" '
            f'fill="#f0fdf4" stroke="#3DAA5C" stroke-width="2" stroke-dasharray="6,3"/>',
            f'<rect x="{vpc_x1+8}" y="{vpc_top-10}" width="44" height="20" rx="5" '
            f'fill="white" stroke="#3DAA5C" stroke-width="1.5"/>',
            f'<text x="{vpc_x1+30}" y="{vpc_top+4}" text-anchor="middle" '
            f'font-size="10" font-weight="700" fill="#15803d">VPC</text>',
        ]

    # ── Zone boxes with label chip on top border ───────────────────────────────
    for z in zones_raw:
        zid    = z["id"]
        zstyle = _ZONE_STYLE.get(z.get("type", "aws_managed"), _ZONE_STYLE["aws_managed"])
        zx     = zone_x[zid]
        zw     = zone_w[zid]
        zy     = ZONE_TOP
        zh     = max_zone_h

        dash_attr = f'stroke-dasharray="{zstyle["dash"]}"' if zstyle["dash"] != "none" else ""

        # Zone background box
        svg.append(
            f'<rect x="{zx}" y="{zy}" width="{zw}" height="{zh}" rx="8" '
            f'fill="{zstyle["fill"]}" stroke="{zstyle["stroke"]}" stroke-width="1.5" {dash_attr}/>'
        )

        # Label chip sits ON the top border line
        raw_label = z.get("label", "")
        # Use 2-word max to keep chips short
        label_words = raw_label.split()
        if len(label_words) > 2:
            short = " ".join(label_words[:2])
        else:
            short = raw_label

        # Cap chip width to zone width minus margin so adjacent chips never overlap
        chip_w = min(max(len(short) * 7 + 16, 54), zw - 8)
        chip_x = max(zx + 4, zx + zw // 2 - chip_w // 2)
        font_sz = "8.5" if len(short) > 10 else "9.5"
        svg += [
            f'<rect x="{chip_x}" y="{zy - CHIP_H // 2}" width="{chip_w}" height="{CHIP_H}" '
            f'rx="6" fill="{zstyle["fill"]}" stroke="{zstyle["stroke"]}" stroke-width="1.5"/>',
            f'<text x="{chip_x + chip_w // 2}" y="{zy + 5}" text-anchor="middle" '
            f'font-size="{font_sz}" font-weight="700" fill="{zstyle["label_color"]}" letter-spacing="0.4">'
            f'{short.upper()}</text>',
        ]

    # ── Icon boxes ────────────────────────────────────────────────────────────
    for z in zones_raw:
        for nid in zone_nodes.get(z["id"], []):
            node = node_map.get(nid, {"id": nid, "label": nid, "service": nid})
            cx, cy = node_cx.get(nid), node_cy.get(nid)
            if cx is None or cy is None:
                continue
            svg.append(_icon_box(cx, cy, node))

    # ── Edges ─────────────────────────────────────────────────────────────────
    def _edge_pts(e: dict):
        x1, y1 = node_cx.get(e["from"]), node_cy.get(e["from"])
        x2, y2 = node_cx.get(e["to"]),   node_cy.get(e["to"])
        if None in (x1, y1, x2, y2):
            return None
        half = _BOX // 2 + 5
        dx, dy = x2 - x1, y2 - y1
        dist = max((dx*dx + dy*dy)**0.5, 1)
        sx, sy = dx / dist * half, dy / dist * half
        return int(x1+sx), int(y1+sy), int(x2-sx), int(y2-sy)

    # Only show label on the FIRST dashed edge from each source node
    shown_dashed_labels: set[str] = set()

    for dashed_pass in (False, True):
        for e in edges_raw:
            if bool(e.get("dashed")) != dashed_pass:
                continue
            pts = _edge_pts(e)
            if not pts:
                continue
            ax1, ay1, ax2, ay2 = pts
            seq   = e.get("seq") if not e.get("dashed") else None
            label = e.get("label", "")

            # Suppress duplicate labels from the same dashed source
            if e.get("dashed") and label:
                src = e["from"]
                if src in shown_dashed_labels:
                    label = ""
                else:
                    shown_dashed_labels.add(src)

            # Offset label slightly off midpoint to avoid overlapping circle badges
            mid_offset = 18 if seq is not None else 0

            svg.append(_arrow(ax1, ay1, ax2, ay2,
                              label=label, seq=seq,
                              dashed=bool(e.get("dashed")),
                              mid_offset=mid_offset))

    # ── Legend ────────────────────────────────────────────────────────────────
    items = [
        ("#FF9900","Compute"),("#8C4FFF","Networking"),("#3F8624","Data/Storage"),
        ("#DD344C","Security"),("#E7157B","Monitoring"),("#C7131F","CI/CD"),
    ]
    lx, ly = PAD, H - 12
    for color, lbl in items:
        svg += [
            f'<rect x="{lx}" y="{ly-8}" width="12" height="12" rx="3" fill="{color}"/>',
            f'<text x="{lx+16}" y="{ly+2}" font-size="9.5" fill="#64748b">{lbl}</text>',
        ]
        lx += 100

    # Stackport AI watermark — bottom-right corner, never overlaps title
    svg.append(
        f'<text x="{W-PAD}" y="{H-4}" text-anchor="end" font-size="9" '
        f'fill="#FF9900" font-weight="700" opacity="0.8">Stackport AI</text>'
    )
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
