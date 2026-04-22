"""Vector-Graph-RAG semantic search backend for pgk-laboral-desk.

Provides semantic search over convenio colectivo categories using
vector-graph-rag with Z.ai infrastructure (ZAI_API_KEY, glm-4.5,
local embeddings).

Supplements the existing keyword/regex matching in ChatParser with
real semantic search when LABORAL_VECTOR_GRAPH_RAG=true.

Requiere: pip install vector-graph-rag
Requiere: ZAI_API_KEY en el entorno
Feature flag: LABORAL_VECTOR_GRAPH_RAG=true (default: false)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("laboral.vgrag_search")

FEATURE_FLAG = "LABORAL_VECTOR_GRAPH_RAG"
_PROJECT_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class VGRAGResult:
    """Resultado de busqueda semantica sobre convenio colectivo."""

    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


def is_enabled() -> bool:
    """Check if vector-graph-rag feature flag is enabled."""
    return os.getenv(FEATURE_FLAG, "false").lower() in ("true", "1", "yes")


class ConvenioVGRAGBackend:
    """Backend de busqueda semantica sobre convenio colectivo.

    Permite buscar categorias profesionales, condiciones laborales,
    y relaciones entre articulos del convenio usando multi-hop retrieval
    con Z.ai LLM.
    """

    def __init__(self) -> None:
        self._rag: Any = None
        self._available = False
        self._vgrag_cls: Any = None

        try:
            from vector_graph_rag import VectorGraphRAG

            self._vgrag_cls = VectorGraphRAG
            self._available = True
            logger.info("ConvenioVGRAGBackend: vector-graph-rag disponible")
        except ImportError:
            logger.info(
                "ConvenioVGRAGBackend: vector-graph-rag no instalado. "
                "Instala con: pip install vector-graph-rag"
            )

    @property
    def available(self) -> bool:
        return self._available

    def _get_rag(self) -> Any:
        """Obtiene o crea la instancia VectorGraphRAG."""
        if self._rag is not None:
            return self._rag

        if not self._available:
            return None

        try:
            from vector_graph_rag.config import Settings as VGRAGSettings

            zai_key = os.getenv("ZAI_API_KEY", "")
            zai_base = os.getenv("ZAI_BASE_URL_OPENAI", "https://api.z.ai/api/paas/v4/")
            llm_model = os.getenv("VGRAG_LLM_MODEL", "glm-4.5")
            embedding_model = os.getenv(
                "VGRAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
            )
            embedding_dim = int(os.getenv("VGRAG_EMBEDDING_DIMENSION", "384"))

            milvus_dir = _PROJECT_ROOT / "data"
            milvus_dir.mkdir(parents=True, exist_ok=True)
            milvus_uri = str(milvus_dir / "vgrag_convenio.db")

            settings = VGRAGSettings(
                openai_api_key=zai_key,
                openai_base_url=zai_base,
                llm_model=llm_model,
                embedding_model=embedding_model,
                embedding_dimension=embedding_dim,
                milvus_uri=milvus_uri,
                collection_prefix="laboral_convenio",
            )

            self._rag = self._vgrag_cls(settings=settings)
            logger.info(
                "ConvenioVGRAGBackend: instancia creada (Z.ai endpoint=%s)",
                zai_base,
            )
            return self._rag
        except Exception as exc:
            logger.warning("ConvenioVGRAGBackend: error creando instancia: %s", exc)
            self._available = False
            return None

    def index_articulo_convenio(
        self,
        numero_articulo: str,
        titulo: str,
        contenido: str,
        seccion: str = "",
    ) -> bool:
        """Indexa un articulo del convenio colectivo en el knowledge graph.

        Extrae tripletas semanticas del texto del convenio (ej:
        'Socorrista Nivel A' → 'tiene salario' → '1.800€/mes').
        """
        if not is_enabled():
            return False

        rag = self._get_rag()
        if rag is None:
            return False

        try:
            doc_text = f"Art. {numero_articulo}: {titulo}\n\n{contenido}"
            metadata = {
                "articulo": numero_articulo,
                "titulo": titulo,
                "seccion": seccion,
                "source": "convenio_colectivo",
            }
            rag.add_texts(texts=[doc_text], metadatas=[metadata])
            return True
        except Exception as exc:
            logger.warning("Error indexando articulo convenio: %s", exc)
            return False

    def search_categoria(self, query: str, limit: int = 5) -> list[VGRAGResult]:
        """Busqueda semantica de categorias profesionales.

        Usa multi-hop retrieval para encontrar categorias relevantes
        basandose en la descripcion del puesto en lenguaje natural.
        """
        if not is_enabled():
            return []

        rag = self._get_rag()
        if rag is None:
            return []

        try:
            result = rag.retrieve(query, top_k=limit)

            vgrag_results: list[VGRAGResult] = []
            passages = result.passages or result.retrieved_passages or []
            for i, passage in enumerate(passages[:limit]):
                # Score by position: first result is best
                score = 1.0 - (i / max(len(passages), 1))
                vgrag_results.append(
                    VGRAGResult(
                        content=passage,
                        score=score,
                        metadata={"source": "vgrag", "rank": i},
                    )
                )

            return vgrag_results
        except Exception as exc:
            logger.warning("Error en busqueda semantica convenio: %s", exc)
            return []


_backend: ConvenioVGRAGBackend | None = None


def get_convenio_vgrag_backend() -> ConvenioVGRAGBackend:
    """Obtiene el singleton del backend de busqueda semantica."""
    global _backend
    if _backend is None:
        _backend = ConvenioVGRAGBackend()
    return _backend
