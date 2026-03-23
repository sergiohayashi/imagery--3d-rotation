import uuid

import fitz

from app.language_models.file_utils import download_to_temp
from app.services.file_utils import FileUtils
from app.services.s3_services import S3UploadServices
from app.services.services_for_rag.rag_llm_service import RagLLMService
from app.utils.file_utils import to_url_valid_filename

MAX_PAGE_PER_FILE = 173  # 100 pages..


def rand_filename():
    guid = uuid.uuid4().hex
    return guid[:8] + "-" + guid[-8:]


class PdfSpliter:
    @classmethod
    async def split(cls, file_name, file_url, file_content_id: str, file_id: str):
        tmp_file = download_to_temp(file_url)
        try:
            import re

            image_count = 0
            image_parts = []
            text_parts = []
            full_text_parts = []
            print("file_name", file_name)
            file_name_only = re.split(r"[./]", file_name)[-2]  # before extension

            seq = 1
            with fitz.open(tmp_file) as doc:
                for page_num, page in enumerate(doc):

                    if page_num >= MAX_PAGE_PER_FILE:
                        print(
                            f"\n****PILOTO**** Excedido numero máximo de páginas {MAX_PAGE_PER_FILE}. Ignora paginas restantes."
                        )
                        break

                    # extract images
                    images = page.get_images(full=True)
                    for img_index, img_info in enumerate(images):
                        xref = img_info[0]

                        base_image = doc.extract_image(xref)

                        width = base_image["width"]
                        height = base_image["height"]
                        if width < 100 or height < 100:
                            print("Image is too small. skip..", width, height)
                            continue

                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        image_count += 1
                        image_file_name = to_url_valid_filename(
                            f"{file_name_only}-{image_count}.{image_ext}"
                        )
                        image_url = (
                            await S3UploadServices.upload_file_context_extracted_image(
                                image_file_name,
                                image_bytes,
                                file_content_id,
                                file_id,
                                None,
                            )
                        )

                        image_parts.append(
                            dict(
                                image_url=image_url,
                                caption=None,
                                ext=image_ext,
                                content_type=f"image/{image_ext}",
                                source=f"image {image_count} from page {page_num+1} of file {file_name}",
                                seq=seq,
                            )
                        )
                        seq += 1

                        if img_index >= 3:
                            print(f"\n****PILOTO**** Pega máximo 3 imagens por página")
                            break

                    # extract page. 1 page = 1 chunk, no overlap. Discard too short text
                    text = page.get_text().strip()
                    if len(text) >= 100:
                        text_parts.append(
                            dict(
                                content=page.get_text(),
                                source=f"page {page_num+1} of file {file_name}",
                                seq=seq,
                            )
                        )
                        seq += 1
                        full_text_parts.append(text)
                    else:
                        print(
                            f"pagina {page_num+1} com texto com menos de 100 characters. Skip.."
                        )

            # generate the captions after, because it takes time to the image be ready on s3
            for image in image_parts:
                caption, _ = await RagLLMService.generate_image_caption(
                    image["image_url"]
                )
                image["caption"] = caption

            return (
                text_parts,
                image_parts,
                FileUtils.getsize(tmp_file),
                "\n".join(full_text_parts),
            )

        finally:
            FileUtils.safe_delete(tmp_file)
