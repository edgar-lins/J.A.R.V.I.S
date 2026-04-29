import anthropic
import base64
import tempfile
import os
from pypdf import PdfReader
from config import get_settings
from core import memory as mem

settings = get_settings()
client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _extract_pdf_text(file_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(file_bytes)
        tmp_path = f.name

    try:
        reader = PdfReader(tmp_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    finally:
        os.unlink(tmp_path)


def _analyze_with_claude(raw_text: str, filename: str) -> str:
    """Pede ao Claude para interpretar o exame e gerar um resumo claro."""
    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": (
                f"Analise este exame médico/documento de saúde chamado '{filename}' "
                f"e forneça:\n"
                f"1. Tipo do exame\n"
                f"2. Resultados principais\n"
                f"3. Valores fora da referência (se houver)\n"
                f"4. Observações clínicas relevantes\n\n"
                f"Seja direto e objetivo. Use português.\n\n"
                f"--- CONTEÚDO DO DOCUMENTO ---\n{raw_text[:8000]}"
            ),
        }],
    )
    return response.content[0].text


async def process_document(user_id: str, filename: str, file_bytes: bytes) -> dict:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "pdf":
        raw_text = _extract_pdf_text(file_bytes)
    elif ext in ("jpg", "jpeg", "png", "webp"):
        # Para imagens, envia direto ao Claude Vision
        b64 = base64.standard_b64encode(file_bytes).decode()
        media_type = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Analise esta imagem de exame médico e forneça: "
                            "1. Tipo do exame 2. Resultados principais "
                            "3. Valores fora da referência 4. Observações clínicas. "
                            "Use português e seja objetivo."
                        ),
                    },
                ],
            }],
        )
        raw_text = f"[imagem: {filename}]"
        summary = response.content[0].text
    else:
        raw_text = file_bytes.decode("utf-8", errors="replace")

    if ext != "pdf" or "summary" not in dir():
        summary = _analyze_with_claude(raw_text, filename)

    # Upload do arquivo para o Supabase Storage
    from core.memory import get_db
    db = get_db()
    storage_path = f"{user_id}/exams/{filename}"
    db.storage.from_("health-documents").upload(storage_path, file_bytes, {"upsert": "true"})

    doc = mem.save_health_document(
        user_id=user_id,
        filename=filename,
        file_path=storage_path,
        document_type="medical_exam",
        summary=summary,
        raw_text=raw_text[:5000],
    )

    # Salva um resumo na memória de longo prazo
    mem.add_memory(
        user_id=user_id,
        category="health",
        content=f"Exame '{filename}' analisado. Resumo: {summary[:300]}",
        importance=4,
    )

    return {"filename": filename, "summary": summary, "document": doc}
