"""Timeline bar rendering helpers."""


def render_timeline(position: int, total: int, width: int = 30) -> str:
    if total <= 0:
        return "[" + "." * width + "]"
    position = min(max(position, 0), total - 1)
    filled = round(position / max(total - 1, 1) * width)
    return "[" + "=" * filled + ">" + "." * (width - filled) + "]"