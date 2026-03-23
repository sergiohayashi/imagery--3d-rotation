from app.language_models import openai_embedding
from app.services.services_for_rag.rag_llm_service import RagLLMService
from app.services.services_for_rag.spliter_for_pdf import PdfSpliter
from app.services.services_for_rag.spliter_for_text import TextSpliter


def likely_text(content_type: str) -> bool:
    """
    Best-effort classifier for determining whether a MIME content type
    should be considered textual.

    Parameters
    ----------
    content_type : str
        A MIME type such as "text/plain" or "application/json". It may include
        parameters like "; charset=utf-8".

    Returns
    -------
    bool
        True if the content type is most likely textual, False otherwise.
    """
    if not content_type:
        return False

    ctype = content_type.strip().lower()
    if not ctype:
        return False

    # Strip optional parameters (e.g., "; charset=utf-8")
    if ";" in ctype:
        ctype = ctype.split(";", 1)[0].strip()

    if "/" not in ctype:
        return False

    main_type, subtype = ctype.split("/", 1)
    main_type = main_type.strip()
    subtype = subtype.strip()

    if not main_type or not subtype:
        return False

    # Anything explicitly declared as text/* is considered text
    if main_type == "text":
        return True

    # Some message/ types (e.g., message/rfc822) are textual
    if main_type == "message":
        return True

    # Known textual application/* types
    known_textual = {
        "application/json",
        "application/ld+json",
        "application/x-ndjson",
        "application/xml",
        "application/xhtml+xml",
        "application/atom+xml",
        "application/rss+xml",
        "application/mathml+xml",
        "application/svg+xml",
        "application/javascript",
        "application/ecmascript",
        "application/sql",
        "application/graphql",
        "application/x-www-form-urlencoded",
        "application/rtf",
        "application/yaml",
        "application/x-yaml",
        "application/toml",
        "application/x-toml",
        "application/csv",
        "application/prs.cww",  # WML script
        "application/problem+json",
        "application/problem+xml",
        "application/vnd.api+json",
    }

    if ctype in known_textual:
        return True

    # Heuristics based on subtype suffixes that imply textual content
    text_like_suffixes = (
        "json",
        "xml",
        "yaml",
        "toml",
        "csv",
        "rtf",
        "html",
        "sgml",
        "javascript",
        "ecmascript",
        "rdf",
        "sparql",
        "webmanifest",
        "urlencoded",
    )

    if any(subtype == suffix for suffix in text_like_suffixes):
        return True

    if subtype.endswith(tuple(f"+{suffix}" for suffix in text_like_suffixes)):
        return True

    # image/svg+xml and similar "+xml" types should be considered text-like
    if subtype.endswith("+xml") or subtype.endswith("+json"):
        return True

    # Some audio/video types with textual subtypes (rare but possible)
    if subtype in {"sdp", "ttml+xml"}:
        return True

    # Otherwise assume binary
    return False


class FileSpliter:
    def __init__(
        self,
        file_url,
        file_name,
        file_content,
        file_content_id: str,
        content_file_id: str,
    ):
        self.file_url = file_url
        self.file_name = file_name
        self.file_content = file_content
        self.file_context_id = file_content_id
        self.content_file_id = content_file_id

    async def _split_text(self):
        # split text
        parts, full_content, file_size = TextSpliter.split(
            self.file_name, self.file_url
        )

        # generate embedding
        chunks = []
        seq = 1
        for p in parts:
            if len(p["content"]) > 100:
                intro, _ = await RagLLMService.generate_one_paragraph_introduction(
                    p["content"]
                )
                chunks.append(
                    dict(
                        type="text",
                        content=p["content"],
                        introduction=intro,
                        embedding=await openai_embedding.get_embedding(p["content"]),
                        source=p["source"],
                        seq=seq,
                    )
                )
                seq += 1
        return chunks, file_size, openai_embedding.EMBEDDING_MODEL, full_content

    async def _split_pdf(self):
        # split pdf
        text_parts, image_parts, file_size, full_text = await PdfSpliter.split(
            self.file_name, self.file_url, self.file_context_id, self.content_file_id
        )

        chunks = []

        # text
        for p in text_parts:
            intro, _ = await RagLLMService.generate_one_paragraph_introduction(
                p["content"]
            )
            chunks.append(
                dict(
                    type="text",
                    content=p["content"],
                    introduction=intro,
                    embedding=await openai_embedding.get_embedding(p["content"]),
                    source=p["source"],
                    seq=p["seq"],
                )
            )

        # images
        for img in image_parts:
            intro, _ = await RagLLMService.generate_one_paragraph_introduction(
                img["caption"]
            )
            chunks.append(
                dict(
                    type="image",
                    image_url=img["image_url"],
                    ext=img["ext"],
                    caption=img["caption"],
                    introduction=intro,
                    embedding=await openai_embedding.get_embedding(img["caption"]),
                    source=img["source"],
                    seq=img["seq"],
                )
            )

        return chunks, file_size, openai_embedding.EMBEDDING_MODEL, full_text

    async def split_in_chunks(self):

        if "pdf" in self.file_content:
            return await self._split_pdf()

        elif likely_text(self.file_content):
            return await self._split_text()

        else:
            return [], None, None, None
