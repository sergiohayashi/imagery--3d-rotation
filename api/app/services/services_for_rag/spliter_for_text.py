from app.language_models.file_utils import download_file_as_byte

CHARS_PER_CHUNK = 5000  # 5000 ~= 1 page ~= 1000 tokens
OVERLAP_RATIO = 0.2

MAX_CHUNK_PER_FILE = 100  # 100 pages..


class TextSpliter:

    @staticmethod
    def split(filename, file_url):
        # download and convert to text
        content_as_bytes = download_file_as_byte(file_url)
        text = content_as_bytes.decode("utf-8")

        return TextSpliter.split_text(text, filename)

    @classmethod
    def split_text(cls, text, filename):
        # split in paragraphs
        lines = text.split("\n")

        # split in chunks. Add overlap for each chunk
        start, j = 0, 0
        parts = []
        while j < len(lines):
            if len(parts) >= MAX_CHUNK_PER_FILE:
                print(
                    f"\n*****PILOTO***** Excedido numero máximo de chunks {MAX_CHUNK_PER_FILE}. Ignora conteúdo restantes."
                )
                break

            size = 0
            while j < len(lines) and size < CHARS_PER_CHUNK:
                size += len(lines[j])
                j += 1

            # end of list
            if size <= 0:
                break

            # process chunk
            parts.append(
                {
                    "source": f"lines {start+1}–{j} of {len(lines)} from {filename}",
                    "content": "\n".join(lines[start:j]),
                }
            )

            # adjust the start to include overlap
            start, overlap_remain = j, CHARS_PER_CHUNK * OVERLAP_RATIO
            while overlap_remain > 0 and start > 0:
                start -= 1
                overlap_remain -= len(lines[start])

        return parts, text, len(text)
