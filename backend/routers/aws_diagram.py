"""Generate AWS-style architecture SVG diagrams from Stackport architecture JSON.

Produces a dark-theme SVG that matches AWS architecture diagram conventions:
- Orange dashed AWS Cloud boundary
- Zone columns (Edge/Network, Compute/API, Data/Storage)
- Platform services band at the bottom
- Colored service boxes (category-specific AWS brand colors)
- Numbered data-flow arrows
"""
from __future__ import annotations

from typing import Any

# ── AWS service color palette (by category) ───────────────────────────────────
_CAT_COLORS: dict[str, str] = {
    "networking":    "#9B59B6",   # purple  (Route53, CloudFront, ALB)
    "compute":       "#FF9900",   # AWS orange (Lambda, ECS, EKS)
    "data":          "#3DAA5C",   # green   (RDS, DynamoDB, Aurora)
    "storage":       "#3DAA5C",   # green   (S3)
    "security":      "#E74C3C",   # red     (IAM, WAF, Secrets Mgr)
    "cicd":          "#0073BB",   # blue    (CodePipeline, ECR, GitHub)
    "monitoring":    "#E91E93",   # magenta (CloudWatch, X-Ray)
    "observability": "#E91E93",   # alias
    "default":       "#527FFF",   # blue
}

# ── Short labels for well-known service modules ────────────────────────────────
_LABELS: dict[str, str] = {
    "cloudfront":      "CloudFront",
    "route53":         "Route 53",
    "alb":             "App LB",
    "nlb":             "Net LB",
    "waf":             "WAF",
    "vpc":             "VPC",
    "lambda":          "Lambda",
    "ecs":             "ECS Fargate",
    "eks":             "EKS",
    "ec2":             "EC2",
    "fargate":         "ECS Fargate",
    "api-gateway":     "API Gateway",
    "appsync":         "AppSync",
    "cognito":         "Cognito",
    "step-functions":  "Step Func",
    "rds":             "RDS",
    "aurora":          "Aurora",
    "dynamodb":        "DynamoDB",
    "elasticache":     "ElastiCache",
    "s3":              "S3",
    "sqs":             "SQS",
    "sns":             "SNS",
    "kinesis":         "Kinesis",
    "iam":             "IAM",
    "secrets-manager": "Secrets Mgr",
    "secrets":         "Secrets Mgr",
    "kms":             "KMS",
    "cloudwatch":      "CloudWatch",
    "xray":            "X-Ray",
    "codepipeline":    "CodePipeline",
    "ecr":             "ECR",
    "github-actions":  "GitHub CI",
}


def _svc_key(module: str) -> str:
    """Return the terminal segment of 'category/name', lowercased."""
    return (module.split("/")[-1] if "/" in module else module).lower()


def _svc_label(module: str) -> str:
    key = _svc_key(module)
    return _LABELS.get(key, key.replace("-", " ").title())


def _svc_color(module: str) -> str:
    cat = (module.split("/")[0] if "/" in module else "default").lower()
    return _CAT_COLORS.get(cat, _CAT_COLORS["default"])


def _zone_for(module: str) -> str:
    """Assign a module to one of four layout zones."""
    cat = (module.split("/")[0] if "/" in module else "").lower()
    key = _svc_key(module)

    _edge_keys = {"cloudfront", "route53", "waf", "alb", "nlb", "vpc", "api-gateway"}
    _compute_keys = {"lambda", "ecs", "eks", "ec2", "fargate", "appsync",
                     "cognito", "step-functions"}
    _data_keys = {"rds", "aurora", "dynamodb", "elasticache", "s3",
                  "sqs", "sns", "kinesis"}

    if key in _edge_keys or cat == "networking":
        return "edge"
    if key in _compute_keys or cat == "compute":
        return "compute"
    if key in _data_keys or cat in ("data", "storage"):
        return "data"
    return "platform"   # security, cicd, monitoring, observability


# ── SVG primitives ─────────────────────────────────────────────────────────────

def _service_box(
    x: int, y: int, w: int, h: int,
    label: str, color: str, order: int | None = None,
) -> str:
    r = 8
    bar_h = 30

    # Truncate long labels
    display = label if len(label) <= 13 else label[:12] + "…"

    parts = [
        # Card body
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
        f'fill="#1a2744" stroke="{color}" stroke-width="1.5"/>',
        # Colour bar (top)
        f'<rect x="{x}" y="{y}" width="{w}" height="{bar_h}" rx="{r}" fill="{color}" opacity="0.92"/>',
        # Square the bottom two corners of the bar
        f'<rect x="{x}" y="{y + bar_h - r}" width="{w}" height="{r}" fill="{color}" opacity="0.92"/>',
        # Label in bar
        f'<text x="{x + w // 2}" y="{y + bar_h // 2 + 5}" text-anchor="middle" '
        f'font-size="11" font-weight="700" fill="white">{display}</text>',
        # "AWS" sub-label below bar
        f'<text x="{x + w // 2}" y="{y + bar_h + 16}" text-anchor="middle" '
        f'font-size="9" fill="#94a3b8">AWS</text>',
    ]

    # Deploy-order badge (top-right corner)
    if order is not None:
        bx = x + w - 12
        by = y + 12
        parts += [
            f'<circle cx="{bx}" cy="{by}" r="9" fill="#0d1525" stroke="{color}" stroke-width="1.5"/>',
            f'<text x="{bx}" y="{by + 4}" text-anchor="middle" '
            f'font-size="9" font-weight="700" fill="{color}">{order}</text>',
        ]

    return "\n".join(parts)


def _dashed_arrow(x1: int, y1: int, x2: int, y2: int, color: str = "#64748b", num: int | None = None) -> str:
    mid_x = (x1 + x2) // 2
    mid_y = (y1 + y2) // 2
    parts = [
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{color}" stroke-width="1.5" stroke-dasharray="5,3" '
        f'marker-end="url(#ah)"/>',
    ]
    if num is not None:
        parts += [
            f'<circle cx="{mid_x}" cy="{mid_y}" r="9" fill="#0d1525" stroke="{color}" stroke-width="1"/>',
            f'<text x="{mid_x}" y="{mid_y + 4}" text-anchor="middle" '
            f'font-size="9" font-weight="700" fill="{color}">{num}</text>',
        ]
    return "\n".join(parts)


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_aws_svg(architecture: dict[str, Any]) -> str:
    """Return an SVG string representing the architecture as an AWS-style diagram."""

    modules = sorted(
        architecture.get("modules", []),
        key=lambda m: m.get("deploy_order", 99),
    )
    arch_name = architecture.get("architecture_name", "AWS Architecture")

    # ── Assign to zones ───────────────────────────────────────────────────────
    zones: dict[str, list[dict]] = {
        "edge": [], "compute": [], "data": [], "platform": [],
    }
    for mod in modules:
        zones[_zone_for(mod.get("module", ""))].append(mod)

    # ── Canvas geometry ───────────────────────────────────────────────────────
    W, H = 1100, 600
    PAD = 24

    # Three main columns
    COL_COUNT = 3
    COL_GAP = 16
    col_w = (W - PAD * 2 - COL_GAP * (COL_COUNT - 1)) // COL_COUNT

    col_x = [
        PAD,
        PAD + col_w + COL_GAP,
        PAD + (col_w + COL_GAP) * 2,
    ]

    MAIN_TOP = 88
    MAIN_H = 340
    BOX_W = col_w - 16
    BOX_H = 60
    BOX_GAP = 10

    PLAT_TOP = MAIN_TOP + MAIN_H + 18
    PLAT_H = H - PLAT_TOP - PAD

    # ── SVG header + defs ─────────────────────────────────────────────────────
    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'style="background:#0d1525;font-family:Inter,\'SF Pro Display\',system-ui,sans-serif;">',

        # Arrowhead marker
        '<defs>'
        '<marker id="ah" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">'
        '<polygon points="0 0, 8 3, 0 6" fill="#64748b"/>'
        '</marker>'
        '<marker id="ah-accent" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">'
        '<polygon points="0 0, 8 3, 0 6" fill="#FF9900"/>'
        '</marker>'
        '</defs>',

        # Background
        f'<rect x="0" y="0" width="{W}" height="{H}" fill="#0d1525"/>',

        # ── AWS Cloud border ──────────────────────────────────────────────────
        f'<rect x="{PAD // 2}" y="50" width="{W - PAD}" height="{H - 58}" rx="10" '
        f'fill="#FF990008" stroke="#FF9900" stroke-width="1.5" stroke-dasharray="10,5"/>',
        # "AWS Cloud" label chip (on border, top-left)
        f'<rect x="{PAD // 2 + 2}" y="43" width="96" height="20" rx="4" fill="#FF990020" stroke="#FF9900" stroke-width="1"/>',
        f'<text x="{PAD // 2 + 50}" y="57" text-anchor="middle" font-size="10.5" '
        f'font-weight="700" fill="#FF9900" letter-spacing="0.3">AWS Cloud</text>',

        # ── Title bar ─────────────────────────────────────────────────────────
        f'<text x="{W // 2}" y="34" text-anchor="middle" font-size="16" '
        f'font-weight="700" fill="#f1f5f9" letter-spacing="-0.3">{arch_name}</text>',
    ]

    # ── Zone column headers & backgrounds ─────────────────────────────────────
    zone_labels = ["Edge / Network", "Compute / API", "Data / Storage"]
    zone_keys_ordered = ["edge", "compute", "data"]

    for i, (zone_key, cx, zlabel) in enumerate(zip(zone_keys_ordered, col_x, zone_labels)):
        # Column background
        svg.append(
            f'<rect x="{cx}" y="{MAIN_TOP}" width="{col_w}" height="{MAIN_H}" rx="8" '
            f'fill="#ffffff05" stroke="#ffffff12" stroke-width="1"/>'
        )
        # Column label
        svg.append(
            f'<text x="{cx + col_w // 2}" y="{MAIN_TOP + 18}" text-anchor="middle" '
            f'font-size="9" font-weight="600" fill="#64748b" letter-spacing="1.5">'
            f'{zlabel.upper()}</text>'
        )

        # Service boxes
        mods = zones[zone_key][:5]  # max 5 per column
        for j, mod in enumerate(mods):
            bx = cx + 8
            by = MAIN_TOP + 30 + j * (BOX_H + BOX_GAP)
            label = _svc_label(mod.get("module", ""))
            color = _svc_color(mod.get("module", ""))
            order = mod.get("deploy_order")
            svg.append(_service_box(bx, by, BOX_W, BOX_H, label, color, order))

    # ── Platform services band ─────────────────────────────────────────────────
    plat_mods = zones["platform"]
    if plat_mods:
        svg.append(
            f'<rect x="{PAD}" y="{PLAT_TOP}" width="{W - PAD * 2}" height="{PLAT_H}" rx="8" '
            f'fill="#ffffff05" stroke="#ffffff12" stroke-width="1"/>'
        )
        svg.append(
            f'<text x="{PAD + 14}" y="{PLAT_TOP + 16}" '
            f'font-size="9" font-weight="600" fill="#64748b" letter-spacing="1.5">'
            f'PLATFORM SERVICES</text>'
        )

        max_plat = min(len(plat_mods), 8)
        total_gap = 10 * (max_plat - 1)
        plat_bw = max(72, (W - PAD * 2 - 20 - total_gap) // max_plat)
        for k, mod in enumerate(plat_mods[:8]):
            px = PAD + 10 + k * (plat_bw + 10)
            py = PLAT_TOP + 24
            ph = PLAT_H - 30
            label = _svc_label(mod.get("module", ""))
            color = _svc_color(mod.get("module", ""))
            order = mod.get("deploy_order")
            svg.append(_service_box(px, py, plat_bw, ph, label, color, order))

    # ── Data flow arrows between columns ──────────────────────────────────────
    # User → edge arrow
    user_cx = 14
    user_cy = MAIN_TOP + MAIN_H // 2
    svg += [
        # User icon
        f'<circle cx="{user_cx}" cy="{user_cy - 6}" r="8" fill="#1e293b" stroke="#94a3b8" stroke-width="1.5"/>',
        f'<circle cx="{user_cx}" cy="{user_cy - 6}" r="3.5" fill="#94a3b8"/>',
        f'<path d="M {user_cx - 7} {user_cy + 4} Q {user_cx} {user_cy - 1} {user_cx + 7} {user_cy + 4}" '
        f'fill="none" stroke="#94a3b8" stroke-width="1.5"/>',
        f'<text x="{user_cx}" y="{user_cy + 18}" text-anchor="middle" '
        f'font-size="8" fill="#64748b">Users</text>',
        # Arrow from user to edge column
        f'<line x1="{user_cx + 8}" y1="{user_cy - 6}" x2="{col_x[0] - 2}" y2="{user_cy - 6}" '
        f'stroke="#FF9900" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#ah-accent)"/>',
    ]

    # Edge → Compute
    if zones["edge"] and zones["compute"]:
        arrow_count = 0
        for row_idx in range(min(2, len(zones["edge"]), len(zones["compute"]))):
            ay = MAIN_TOP + 30 + row_idx * (BOX_H + BOX_GAP) + BOX_H // 2
            ax1 = col_x[0] + col_w - 2
            ax2 = col_x[1] + 2
            color = "#FF9900" if row_idx == 0 else "#64748b"
            num = arrow_count + 1
            svg.append(_dashed_arrow(ax1, ay, ax2, ay, color, num))
            arrow_count += 1

    # Compute → Data
    if zones["compute"] and zones["data"]:
        arrow_count = 0
        for row_idx in range(min(2, len(zones["compute"]), len(zones["data"]))):
            ay = MAIN_TOP + 30 + row_idx * (BOX_H + BOX_GAP) + BOX_H // 2
            ax1 = col_x[1] + col_w - 2
            ax2 = col_x[2] + 2
            color = "#FF9900" if row_idx == 0 else "#64748b"
            num = arrow_count + 1
            svg.append(_dashed_arrow(ax1, ay, ax2, ay, color, num))
            arrow_count += 1

    # Data → Platform (vertical, downward)
    if zones["data"] and zones["platform"]:
        ax = col_x[2] + col_w // 2
        ay1 = MAIN_TOP + MAIN_H - 2
        ay2 = PLAT_TOP + 2
        svg.append(
            f'<line x1="{ax}" y1="{ay1}" x2="{ax}" y2="{ay2}" '
            f'stroke="#64748b" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#ah)"/>'
        )

    # ── Legend ────────────────────────────────────────────────────────────────
    legend_y = H - 14
    legend_items = [
        ("#FF9900", "Compute"),
        ("#9B59B6", "Networking"),
        ("#3DAA5C", "Data/Storage"),
        ("#E74C3C", "Security"),
        ("#0073BB", "CI/CD"),
        ("#E91E93", "Monitoring"),
    ]
    lx = PAD + 10
    for color, lbl in legend_items:
        svg += [
            f'<rect x="{lx}" y="{legend_y - 7}" width="10" height="10" rx="2" fill="{color}" opacity="0.85"/>',
            f'<text x="{lx + 14}" y="{legend_y + 2}" font-size="9" fill="#64748b">{lbl}</text>',
        ]
        lx += 90

    # Stackport branding
    svg.append(
        f'<text x="{W - PAD}" y="{legend_y + 2}" text-anchor="end" '
        f'font-size="9" fill="#334155" font-style="italic">Generated by Stackport AI</text>'
    )

    svg.append("</svg>")
    return "\n".join(svg)
