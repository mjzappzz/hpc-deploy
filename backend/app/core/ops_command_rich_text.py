from html import escape
from html.parser import HTMLParser


class _OpsCommandHtmlSanitizer(HTMLParser):
    _allowed_tags = {"p", "div", "br", "strong", "b"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._blocked_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style"}:
            self._blocked_depth += 1
            return
        if self._blocked_depth or tag.lower() not in self._allowed_tags:
            return
        normalized = "strong" if tag.lower() == "b" else tag.lower()
        self.parts.append(f"<{normalized}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if not self._blocked_depth and tag.lower() == "br":
            self.parts.append("<br>")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"}:
            self._blocked_depth = max(0, self._blocked_depth - 1)
            return
        if self._blocked_depth or tag.lower() not in self._allowed_tags or tag.lower() == "br":
            return
        normalized = "strong" if tag.lower() == "b" else tag.lower()
        self.parts.append(f"</{normalized}>")

    def handle_data(self, data: str) -> None:
        if not self._blocked_depth:
            self.parts.append(escape(data))


def sanitize_ops_command_rich_text(value: str) -> str:
    """Keep only the presentation markup supported by the command editor."""
    parser = _OpsCommandHtmlSanitizer()
    parser.feed(value)
    parser.close()
    return "".join(parser.parts)
