import {
  ChevronDown,
  ExternalLink,
  FileText,
  MessageCircle,
  RefreshCw,
  Upload,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  getDocumentContent,
  getDocumentFileUrl,
  getSubjectDocuments,
  retryDocumentProcessing,
  uploadSubjectMaterial,
  type DocumentContent,
  type SubjectDocumentsData,
} from "../api";

type Material = SubjectDocumentsData["documents"][number];
const uploadSteps = [
  "Subiendo…",
  "Extrayendo contenido…",
  "Preparando búsqueda…",
  "Organizando temario…",
  "Listo",
];

export default function MaterialLibrary({
  subjectId,
  onAsk,
}: {
  subjectId: number;
  onAsk: (document: Material) => void;
}) {
  const [data, setData] = useState<SubjectDocumentsData | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<DocumentContent | null>(null);
  const [openingId, setOpeningId] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStep, setUploadStep] = useState(0);
  const [uploadResult, setUploadResult] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setData(await getSubjectDocuments(subjectId));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudieron cargar los materiales.",
      );
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, [subjectId]);

  async function openMaterial(document: Material) {
    setOpeningId(document.id);
    setError(null);
    try {
      setActive(await getDocumentContent(document.id));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : `No se pudo abrir ${document.title}.`,
      );
    } finally {
      setOpeningId(null);
    }
  }

  async function upload(file: File) {
    setUploading(true);
    setUploadStep(0);
    setUploadResult(null);
    setError(null);
    try {
      const result = await uploadSubjectMaterial(subjectId, file);
      if (result.duplicate) {
        setUploadResult(result.message);
        await load();
        return;
      }
      let latest = result.document;
      for (let attempt = 0; attempt < 180; attempt += 1) {
        const refreshed = await getSubjectDocuments(subjectId);
        setData(refreshed);
        latest =
          refreshed.documents.find((item) => item.id === result.document.id) ??
          latest;
        const stageIndex = uploadSteps.indexOf(latest.processing_stage ?? "");
        if (stageIndex >= 0) setUploadStep(stageIndex);
        if (latest.processing_status === "ready") {
          setUploadStep(4);
          setUploadResult(`Listo · ${latest.title}`);
          return;
        }
        if (latest.processing_status === "error")
          throw new Error(
            latest.processing_error || "No se pudo preparar el material.",
          );
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
      }
      setUploadResult(
        "El archivo se sigue preparando. Puedes continuar; actualizaremos su estado al recargar.",
      );
    } catch (caught) {
      setError(
        `${file.name}: ${caught instanceof Error ? caught.message : "no se pudo preparar el material."}`,
      );
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function retryProcessing(document: Material) {
    setError(null);
    setUploadResult(null);
    try {
      await retryDocumentProcessing(document.id);
      setUploadResult(
        "Reintentando el procesamiento sin volver a subir el archivo.",
      );
      await load();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "No se pudo reintentar el procesamiento.",
      );
    }
  }

  const documents = data?.documents ?? [];
  return (
    <section className={`uc-material-library ${expanded ? "is-expanded" : ""}`}>
      <header className="uc-material-header">
        <div>
          <p className="uc-eyebrow">Biblioteca de asignatura</p>
          <h2>
            Materiales{" "}
            <small>
              {loading
                ? ""
                : `${documents.length} archivo${documents.length === 1 ? "" : "s"}`}
            </small>
          </h2>
          <p>
            Apuntes y lecturas persistentes, preparados para consultar con
            UniCore.
          </p>
        </div>
        <button
          className="uc-material-toggle"
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "Contraer" : "Ver materiales"}
          <ChevronDown size={16} />
        </button>
      </header>
      {expanded && (
        <div className="uc-material-body">
          <div className="uc-material-upload">
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.docx,.pptx,.txt,.md"
              disabled={uploading}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void upload(file);
              }}
            />
            <button
              className="uc-primary-action"
              disabled={uploading}
              onClick={() => inputRef.current?.click()}
            >
              <Upload size={16} />{" "}
              {uploading ? uploadSteps[uploadStep] : "Subir material"}
            </button>
            <small>PDF · DOCX · PPTX · TXT · MD · máx. 50 MB</small>
          </div>
          {uploading && (
            <div className="uc-upload-progress">
              <span style={{ width: `${(uploadStep + 1) * 20}%` }} />
              <strong>{uploadSteps[uploadStep]}</strong>
            </div>
          )}
          {uploadResult && !uploading && (
            <p className="uc-upload-success">{uploadResult}</p>
          )}
          {error && (
            <div className="uc-inline-error">
              <span>{error}</span>
              <button onClick={() => void load()} aria-label="Reintentar">
                <RefreshCw size={14} />
              </button>
            </div>
          )}
          {loading ? (
            <div className="uc-material-state">Cargando materiales…</div>
          ) : documents.length === 0 ? (
            <div className="uc-material-state">
              <FileText size={20} />
              <strong>Aún no hay materiales.</strong>
              <span>
                Sube el primer archivo para leerlo y consultarlo con el Agent.
              </span>
            </div>
          ) : (
            <div className="uc-material-ledger">
              {documents.map((document) => (
                <article
                  key={document.id}
                  className={
                    active?.document.id === document.id ? "is-active" : ""
                  }
                >
                  <button
                    className="uc-material-open"
                    onClick={() => void openMaterial(document)}
                    disabled={
                      openingId === document.id ||
                      document.processing_status === "processing"
                    }
                  >
                    <FileText size={17} />
                    <span>
                      <strong>{document.title}</strong>
                      <small>
                        {document.processing_status === "processing"
                          ? (document.processing_stage ?? "Preparando…")
                          : document.processing_status === "error"
                            ? `El archivo se subió, pero no pudo terminar de procesarse. ${document.processing_error ?? ""}`
                            : `${document.file_type?.toUpperCase() ?? "Archivo"} · ${document.chunk_count} fragmento(s) preparado(s)`}
                      </small>
                    </span>
                    <span>
                      {openingId === document.id
                        ? "Abriendo…"
                        : document.processing_status === "processing"
                          ? "Preparando"
                          : "Abrir"}
                    </span>
                  </button>
                  {document.processing_status === "error" ? (
                    <button
                      className="uc-material-ask"
                      onClick={() => void retryProcessing(document)}
                    >
                      <RefreshCw size={15} /> Reintentar procesamiento
                    </button>
                  ) : (
                    <button
                      className="uc-material-ask"
                      disabled={document.processing_status !== "ready"}
                      onClick={() => onAsk(document)}
                    >
                      <MessageCircle size={15} /> Preguntar a UniCore
                    </button>
                  )}
                </article>
              ))}
            </div>
          )}
          {active && (
            <div className="uc-material-viewer">
              <header>
                <div>
                  <p className="uc-eyebrow">Documento activo</p>
                  <h3>{active.document.title}</h3>
                </div>
                <div>
                  <a
                    href={getDocumentFileUrl(active.document.id)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <ExternalLink size={15} /> Abrir original
                  </a>
                  <button onClick={() => onAsk(active.document)}>
                    <MessageCircle size={15} /> Preguntar sobre este material
                  </button>
                  <button
                    onClick={() => setActive(null)}
                    aria-label="Cerrar material"
                  >
                    <X size={17} />
                  </button>
                </div>
              </header>
              <pre>
                {active.content ||
                  "Este archivo no tiene contenido extraído disponible."}
              </pre>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
