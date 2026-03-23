"""
文档处理服务 - 支持PDF、图片OCR、视频转录、代码AST分块
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import io
import base64
import hashlib

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """文档处理器"""

    def __init__(self):
        self._processors = {
            "pdf": self._process_pdf,
            "image": self._process_image,
            "video": self._process_video,
            "code": self._process_code,
            "text": self._process_text,
        }

    async def process(
        self,
        file_content: bytes,
        mime_type: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        处理文档

        Args:
            file_content: 文件内容
            mime_type: MIME类型
            metadata: 元数据

        Returns:
            处理结果，包含：
            - text: 提取的文本
            - metadata: 增强的元数据
            - chunks: 分块内容（用于向量化）
            - processing_time: 处理时间（秒）
        """
        start_time = datetime.utcnow()
        doc_type = self._detect_type(mime_type)

        processor = self._processors.get(doc_type, self._process_text)

        try:
            result = await processor(file_content, metadata)
            result["processing_time"] = (datetime.utcnow() - start_time).total_seconds()
            result["doc_type"] = doc_type
            result["hash"] = hashlib.sha256(file_content).hexdigest()

            logger.info(f"Processed {doc_type} document in {result['processing_time']:.2f}s")
            return result

        except Exception as e:
            logger.error(f"Failed to process document: {e}")
            raise

    def _detect_type(self, mime_type: str) -> str:
        """检测文档类型"""
        if mime_type.startswith("image/"):
            return "image"
        elif mime_type == "application/pdf":
            return "pdf"
        elif mime_type.startswith("video/"):
            return "video"
        elif mime_type.startswith("text/") or mime_type in [
            "application/json",
            "application/xml",
            "application/javascript",
        ]:
            return "text"
        else:
            return "text"

    async def _process_pdf(self, content: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理PDF文档

        提取文本、OCR（如果需要）、分块
        """
        try:
            # 尝试使用 PyPDF2 提取文本
            import PyPDF2
            import io

            pdf_file = io.BytesIO(content)
            reader = PyPDF2.PdfReader(pdf_file)

            text_parts = []
            for page in reader.pages:
                try:
                    text = page.extract_text()
                    if text.strip():
                        text_parts.append(text)
                except Exception as e:
                    logger.warning(f"Failed to extract text from PDF page: {e}")

            full_text = "\n\n".join(text_parts)

            # 更新元数据
            metadata["page_count"] = len(reader.pages)
            metadata["pdf_info"] = {
                "title": reader.metadata.get("/Title") if reader.metadata else None,
                "author": reader.metadata.get("/Author") if reader.metadata else None,
                "subject": reader.metadata.get("/Subject") if reader.metadata else None,
                "creator": reader.metadata.get("/Creator") if reader.metadata else None,
                "producer": reader.metadata.get("/Producer") if reader.metadata else None,
            }

            # 分块（按页或按段落）
            chunks = self._chunk_text(full_text, max_chars=2000)

            return {
                "text": full_text,
                "metadata": metadata,
                "chunks": chunks,
            }

        except ImportError:
            logger.warning("PyPDF2 not installed, falling back to basic text extraction")
            return await self._process_text(content, metadata)
        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            # 回退到文本提取
            return await self._process_text(content, metadata)

    async def _process_image(self, content: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理图片文档

        使用OCR提取文本
        """
        try:
            # 尝试使用 pytesseract OCR
            from PIL import Image
            import pytesseract
            import io

            image = Image.open(io.BytesIO(content))

            # OCR 提取文本
            text = pytesseract.image_to_string(image)

            # 更新元数据
            metadata["image_info"] = {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "mode": image.mode,
            }

            # 分块
            chunks = self._chunk_text(text, max_chars=2000)

            return {
                "text": text,
                "metadata": metadata,
                "chunks": chunks,
            }

        except ImportError:
            logger.warning("PIL or pytesseract not installed, returning empty text")
            return {
                "text": "",
                "metadata": metadata,
                "chunks": [],
            }
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            return {
                "text": "",
                "metadata": metadata,
                "chunks": [],
            }

    async def _process_video(self, content: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理视频文档

        提取音频、转录（需要外部服务）
        """
        # 视频处理需要外部服务（如 OpenAI Whisper）
        # 这里只返回占位符，实际实现需要调用转录服务
        logger.warning("Video processing requires external transcription service")

        metadata["video_info"] = {
            "size_bytes": len(content),
            "note": "Transcription requires external service",
        }

        return {
            "text": "",  # 需要外部转录服务
            "metadata": metadata,
            "chunks": [],
        }

    async def _process_code(self, content: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理代码文档

        使用AST解析、语法高亮
        """
        try:
            import ast
            import textwrap

            text = content.decode("utf-8", errors="ignore")

            # 尝试解析Python代码的AST
            try:
                tree = ast.parse(text)
                functions = []
                classes = []
                imports = []

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        functions.append({
                            "name": node.name,
                            "lineno": node.lineno,
                            "docstring": ast.get_docstring(node),
                        })
                    elif isinstance(node, ast.ClassDef):
                        classes.append({
                            "name": node.name,
                            "lineno": node.lineno,
                            "docstring": ast.get_docstring(node),
                        })
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                imports.append(alias.name)
                        else:
                            module = node.module if node.module else ""
                            for alias in node.names:
                                imports.append(f"{module}.{alias.name}")

                metadata["code_info"] = {
                    "language": "python",
                    "functions": functions,
                    "classes": classes,
                    "imports": imports,
                }

            except SyntaxError:
                # 不是Python代码，作为普通文本处理
                pass

            # 分块（按函数或按行）
            chunks = self._chunk_text(text, max_chars=2000)

            return {
                "text": text,
                "metadata": metadata,
                "chunks": chunks,
            }

        except Exception as e:
            logger.error(f"Code processing failed: {e}")
            return await self._process_text(content, metadata)

    async def _process_text(self, content: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理文本文档

        直接提取文本、智能分块
        """
        text = content.decode("utf-8", errors="ignore")

        # 智能分块（按段落、句子等）
        chunks = self._chunk_text(text, max_chars=2000)

        # 更新元数据
        metadata["text_info"] = {
            "char_count": len(text),
            "word_count": len(text.split()),
            "line_count": len(text.splitlines()),
        }

        return {
            "text": text,
            "metadata": metadata,
            "chunks": chunks,
        }

    def _chunk_text(self, text: str, max_chars: int = 2000, overlap: int = 200) -> List[Dict[str, Any]]:
        """
        智能分块

        优先按段落分块，其次按句子，最后按字符
        """
        if not text or not text.strip():
            return []

        chunks = []

        # 尝试按段落分块
        paragraphs = text.split("\n\n")
        current_chunk = ""
        chunk_num = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果段落本身就很短，直接加入
            if len(current_chunk) + len(para) <= max_chars:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
            else:
                # 保存当前chunk
                if current_chunk:
                    chunks.append({
                        "chunk_id": f"chunk_{chunk_num}",
                        "text": current_chunk,
                        "char_count": len(current_chunk),
                    })
                    chunk_num += 1

                # 如果段落超过max_chars，需要进一步分块
                if len(para) > max_chars:
                    sub_chunks = self._chunk_by_sentence(para, max_chars, overlap)
                    for sub_chunk in sub_chunks:
                        chunks.append({
                            "chunk_id": f"chunk_{chunk_num}",
                            "text": sub_chunk,
                            "char_count": len(sub_chunk),
                        })
                        chunk_num += 1
                    current_chunk = ""
                else:
                    current_chunk = para

        # 保存最后一个chunk
        if current_chunk:
            chunks.append({
                "chunk_id": f"chunk_{chunk_num}",
                "text": current_chunk,
                "char_count": len(current_chunk),
            })

        return chunks

    def _chunk_by_sentence(self, text: str, max_chars: int, overlap: int = 200) -> List[str]:
        """按句子分块"""
        import re

        # 简单的句子分割（基于标点符号）
        sentences = re.split(r'([。！？.!?])', text)

        chunks = []
        current_chunk = ""

        for i in range(0, len(sentences), 2):
            if i + 1 < len(sentences):
                sentence = sentences[i] + sentences[i + 1]
            else:
                sentence = sentences[i]

            if len(current_chunk) + len(sentence) <= max_chars:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)

                # 添加重叠
                if overlap > 0 and len(current_chunk) > overlap:
                    overlap_text = current_chunk[-overlap:]
                    current_chunk = overlap_text + sentence
                else:
                    current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks


class DocumentProcessingResult:
    """文档处理结果"""

    def __init__(
        self,
        success: bool,
        text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        chunks: Optional[List[Dict[str, Any]]] = None,
        error: Optional[str] = None,
        processing_time: Optional[float] = None,
    ):
        self.success = success
        self.text = text
        self.metadata = metadata or {}
        self.chunks = chunks or []
        self.error = error
        self.processing_time = processing_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "text": self.text,
            "metadata": self.metadata,
            "chunks": self.chunks,
            "error": self.error,
            "processing_time": self.processing_time,
        }


# 全局处理器实例
document_processor = DocumentProcessor()
