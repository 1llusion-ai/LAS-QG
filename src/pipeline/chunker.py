import re
import uuid

from src.schemas.types import DocumentChunk, Document


class TextChunker:
    CHAPTER_PATTERN = r"^(第[一二三四五六七八九十百千零\d]+[章节篇集部])\s*[:：]?\s*(.+?)?$"

    ARTICLE_PATTERN = r"^(第[一二三四五六七八九十百千零\d]+条)\s*[:：.]?\s*(.+?)?$"

    ARTICLE_PREFIX_PATTERN = r'^第[一二三四五六七八九十百零]+条[　\s]*'

    def __init__(self, chunk_size: int = 800, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def _clean_article_prefix(self, text: str) -> str:
        return re.sub(self.ARTICLE_PREFIX_PATTERN, '', text, flags=re.MULTILINE)

    def chunk(self, document: Document) -> list[DocumentChunk]:
        content = document.content
        lines = content.split("\n")

        articles = self._split_by_articles(lines)

        chunks = []
        chunk_index = 0

        for article in articles:
            article_text = "\n".join(article["lines"])
            article_no = article["article_no"]
            article_title = article.get("title", "")
            chapter = article.get("chapter", "")

            cleaned_text = self._clean_article_prefix(article_text)

            if len(cleaned_text) <= self.chunk_size:
                chunk = DocumentChunk(
                    id=str(uuid.uuid4()),
                    document_id=document.id,
                    chunk_index=chunk_index,
                    content=cleaned_text.strip(),
                    metadata={
                        "chapter": chapter,
                        "article_no": article_no,
                        "article_title": article_title,
                        "chunk_id": f"chunk_{chunk_index}",
                        "source_text": cleaned_text.strip(),
                        "parent_article_id": article_no,
                    },
                )
                chunks.append(chunk)
                chunk_index += 1
            else:
                sub_chunks = self._split_long_article(
                    cleaned_text,
                    document.id,
                    chunk_index,
                    article_no,
                    chapter,
                    article_title,
                )
                chunks.extend(sub_chunks)
                chunk_index += len(sub_chunks)

        return chunks

    def _split_by_articles(self, lines: list[str]) -> list[dict]:
        articles = []
        current_chapter = ""
        current_article_lines = []
        current_article_no = ""
        current_article_title = ""

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                current_article_lines.append(line)
                continue

            chapter_match = re.match(self.CHAPTER_PATTERN, line_stripped)
            if chapter_match:
                current_chapter = chapter_match.group(1)
                continue

            article_match = re.match(self.ARTICLE_PATTERN, line_stripped)
            if article_match:
                if current_article_lines:
                    articles.append({
                        "chapter": current_chapter,
                        "article_no": current_article_no,
                        "title": current_article_title,
                        "lines": current_article_lines,
                    })

                current_article_no = article_match.group(1)
                current_article_title = article_match.group(2) or ""

                remaining = line_stripped[len(article_match.group(0)):].strip()
                current_article_lines = [line] if not remaining else [remaining if remaining else line]
            else:
                current_article_lines.append(line)

        if current_article_lines:
            articles.append({
                "chapter": current_chapter,
                "article_no": current_article_no,
                "title": current_article_title,
                "lines": current_article_lines,
            })

        if not articles:
            articles = [{"chapter": "", "article_no": "全文", "title": "", "lines": lines}]

        return articles

    def _split_long_article(
        self,
        article_text: str,
        document_id: str,
        start_index: int,
        article_no: str,
        chapter: str,
        article_title: str,
    ) -> list[DocumentChunk]:
        chunks = []
        chars = list(article_text)
        current_start = 0
        chunk_index = start_index

        while current_start < len(chars):
            current_end = min(current_start + self.chunk_size, len(chars))

            if current_end < len(chars):
                while current_end > current_start and chars[current_end - 1] not in "。！？；\n":
                    current_end -= 1

                if current_end == current_start:
                    current_end = min(current_start + self.chunk_size, len(chars))

            chunk_text = "".join(chars[current_start:current_end])

            chunk = DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=document_id,
                chunk_index=chunk_index,
                content=chunk_text.strip(),
                metadata={
                    "chapter": chapter,
                    "article_no": article_no,
                    "article_title": article_title,
                    "chunk_id": f"chunk_{chunk_index}",
                    "source_text": chunk_text.strip(),
                    "parent_article_id": article_no,
                    "is_subchunk": True,
                    "subchunk_index": chunk_index - start_index,
                },
            )
            chunks.append(chunk)
            chunk_index += 1

            if self.overlap > 0 and current_end < len(chars):
                overlap_start = max(0, current_end - self.overlap)
                overlap_text = "".join(chars[overlap_start:current_end])
                current_start = current_end - len(overlap_text)
            else:
                current_start = current_end

        return chunks


def chunk_document(
    document: Document, chunk_size: int = 800, overlap: int = 50
) -> list[DocumentChunk]:
    chunker = TextChunker(chunk_size=chunk_size, overlap=overlap)
    return chunker.chunk(document)
