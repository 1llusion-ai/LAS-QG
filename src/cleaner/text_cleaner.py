import re


class TextCleaner:
    def clean(self, text: str) -> str:
        text = self._remove_extra_whitespace(text)
        text = self._remove_special_chars(text)
        text = self._normalize_unicode(text)
        return text.strip()

    def _remove_extra_whitespace(self, text: str) -> str:
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text

    def _remove_special_chars(self, text: str) -> str:
        text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)
        return text

    def _normalize_unicode(self, text: str) -> str:
        text = text.replace("\u2018", "'").replace("\u2019", "'")
        text = text.replace("\u201c", '"').replace("\u201d", '"')
        text = text.replace("\u2013", "-").replace("\u2014", "-")
        return text


def clean_text(text: str) -> str:
    cleaner = TextCleaner()
    return cleaner.clean(text)
