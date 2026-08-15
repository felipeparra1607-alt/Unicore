import { ChevronDown, ExternalLink, FileText, Pencil, RefreshCw, Trash2, Upload, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { deleteSubjectMaterial, getCurriculum, getDocumentContent, getDocumentFileUrl, getSubjectDocuments, rebuildSubjectCurriculum, retryDocumentProcessing, updateDocumentClassification, uploadSubjectMaterial, type CurriculumData, type DocumentContent, type MaterialType, type SubjectDocumentsData } from "../api";

type Material = SubjectDocumentsData["documents"][number];
const materialTypes: Array<[MaterialType, string]> = [["official_unit", "Temario oficial"], ["class_notes", "Apuntes de clase"], ["required_reading", "Lectura obligatoria"], ["assignment", "Enunciado de tarea"], ["rubric", "Rúbrica"], ["other", "Otro material"]];
const typeLabel = (value?: string) => materialTypes.find(([type]) => type === value)?.[1] ?? "Otro material";
const uploadSteps = ["Subiendo…", "Extrayendo contenido…", "Preparando búsqueda…", "Organizando temario…", "Listo"];

export default function MaterialLibrary({ subjectId }: { subjectId: number }) {
  const [data, setData] = useState<SubjectDocumentsData | null>(null);
  const [curriculum, setCurriculum] = useState<CurriculumData | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<DocumentContent | null>(null);
  const [openingId, setOpeningId] = useState<number | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [materialType, setMaterialType] = useState<MaterialType | "">("");
  const [unitId, setUnitId] = useState("");
  const [editing, setEditing] = useState<Material | null>(null);
  const [editType, setEditType] = useState<MaterialType>("other");
  const [editUnitId, setEditUnitId] = useState("");
  const [deleting, setDeleting] = useState<Material | null>(null);
  const [busy, setBusy] = useState(false);
  const [uploadStep, setUploadStep] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function load() {
    setLoading(true); setError(null);
    try {
      const [documents, curriculumData] = await Promise.all([getSubjectDocuments(subjectId), getCurriculum(subjectId)]);
      setData(documents); setCurriculum(curriculumData);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudieron cargar los materiales."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, [subjectId]);

  async function openMaterial(document: Material) {
    setOpeningId(document.id);
    try { setActive(await getDocumentContent(document.id)); }
    catch (caught) { setError(caught instanceof Error ? caught.message : `No se pudo abrir ${document.title}.`); }
    finally { setOpeningId(null); }
  }

  async function upload() {
    if (!selectedFile || !materialType) return;
    setBusy(true); setUploadStep(0); setNotice(null); setError(null);
    try {
      const result = await uploadSubjectMaterial(subjectId, selectedFile, { material_type: materialType, curriculum_unit_id: unitId ? Number(unitId) : null });
      if (result.duplicate) { setNotice(result.message); await load(); return; }
      let latest = result.document;
      for (let attempt = 0; attempt < 180; attempt += 1) {
        const refreshed = await getSubjectDocuments(subjectId); setData(refreshed);
        latest = refreshed.documents.find((item) => item.id === result.document.id) ?? latest;
        const stageIndex = uploadSteps.indexOf(latest.processing_stage ?? "");
        if (stageIndex >= 0) setUploadStep(stageIndex);
        if (latest.processing_status === "ready") { setUploadStep(4); setNotice(`Listo · ${latest.title}`); setSelectedFile(null); setMaterialType(""); setUnitId(""); await load(); return; }
        if (latest.processing_status === "error") throw new Error(latest.processing_error || "No se pudo preparar el material.");
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
      }
      setNotice("El archivo sigue preparándose. Puedes continuar y volver más tarde.");
    } catch (caught) { setError(`${selectedFile.name}: ${caught instanceof Error ? caught.message : "no se pudo preparar el material."}`); }
    finally { setBusy(false); if (inputRef.current) inputRef.current.value = ""; }
  }

  function beginEdit(document: Material) { setEditing(document); setEditType((document.material_type as MaterialType) || "other"); setEditUnitId(document.curriculum_unit_id ? String(document.curriculum_unit_id) : ""); }
  async function saveClassification() {
    if (!editing) return;
    setBusy(true); setError(null);
    try { await updateDocumentClassification(editing.id, { material_type: editType, curriculum_unit_id: editUnitId ? Number(editUnitId) : null }); setEditing(null); setNotice("Clasificación actualizada. Se reutilizaron el texto y los embeddings existentes."); await load(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo actualizar la clasificación."); }
    finally { setBusy(false); }
  }
  async function confirmDelete() {
    if (!deleting) return;
    setBusy(true); setError(null);
    try { await deleteSubjectMaterial(deleting.id); if (active?.document.id === deleting.id) setActive(null); setNotice("Material eliminado."); setDeleting(null); await load(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo eliminar el material."); }
    finally { setBusy(false); }
  }

  const documents = data?.documents ?? []; const units = curriculum?.units ?? [];
  return <section className={`uc-material-library ${expanded ? "is-expanded" : ""}`}>
    <header className="uc-material-header"><div><p className="uc-eyebrow">Biblioteca de asignatura</p><h2>Materiales <small>{loading ? "" : `${documents.length} archivo${documents.length === 1 ? "" : "s"}`}</small></h2><p>Fuentes clasificadas que alimentan el temario y la búsqueda académica.</p></div><button className="uc-material-toggle" onClick={() => setExpanded((value) => !value)}>{expanded ? "Contraer" : "Ver materiales"}<ChevronDown size={16} /></button></header>
    {expanded && <div className="uc-material-body">
      <div className="uc-material-upload-panel"><div className="uc-material-upload"><input ref={inputRef} type="file" accept=".pdf,.docx,.pptx,.txt,.md" disabled={busy} onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} /><button onClick={() => inputRef.current?.click()} disabled={busy}><Upload size={16} /> {selectedFile ? selectedFile.name : "Elegir archivo"}</button><select aria-label="Tipo de material" value={materialType} disabled={busy} onChange={(event) => setMaterialType(event.target.value as MaterialType | "")}><option value="">Tipo de material · obligatorio</option>{materialTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><select aria-label="Unidad relacionada" value={unitId} disabled={busy} onChange={(event) => setUnitId(event.target.value)}><option value="">Unidad relacionada · opcional</option>{units.map((unit) => <option key={unit.id} value={unit.id}>{unit.name}</option>)}</select><button className="uc-primary-action" disabled={busy || !selectedFile || !materialType} onClick={() => void upload()}>{busy && selectedFile ? uploadSteps[uploadStep] : "Subir material"}</button></div><small>PDF · DOCX · PPTX · TXT · MD · máx. 50 MB. La unidad seleccionada prevalece sobre la inferencia automática.</small></div>
      {busy && selectedFile && <div className="uc-upload-progress"><span style={{ width: `${(uploadStep + 1) * 20}%` }} /><strong>{uploadSteps[uploadStep]}</strong></div>}
      {notice && <p className="uc-upload-success">{notice}</p>}{error && <div className="uc-inline-error"><span>{error}</span><button onClick={() => void load()} aria-label="Reintentar"><RefreshCw size={14} /></button></div>}
      {loading ? <div className="uc-material-state">Cargando materiales…</div> : documents.length === 0 ? <div className="uc-material-state"><FileText size={20} /><strong>Aún no hay materiales.</strong><span>Clasifica y sube el primer archivo de esta asignatura.</span></div> : <div className="uc-material-ledger">{documents.map((document) => <article key={document.id} className={active?.document.id === document.id ? "is-active" : ""}><button className="uc-material-open" onClick={() => void openMaterial(document)} disabled={openingId === document.id || document.processing_status === "processing"}><FileText size={17} /><span><strong>{document.title}</strong><small>{typeLabel(document.material_type)}{document.curriculum_unit_name ? ` · ${document.curriculum_unit_name}` : ""} · {document.processing_status === "processing" ? document.processing_stage ?? "Preparando…" : document.processing_status === "error" ? "Error de procesamiento" : `${document.chunk_count} fragmentos`}</small></span><span>{openingId === document.id ? "Abriendo…" : "Abrir"}</span></button><div className="uc-material-row-actions">{document.processing_status === "error" && <button onClick={() => void retryDocumentProcessing(document.id).then(load)}><RefreshCw size={14} /> Reintentar</button>}<button onClick={() => beginEdit(document)}><Pencil size={14} /> Editar</button><button className="is-danger" onClick={() => setDeleting(document)}><Trash2 size={14} /> Eliminar</button></div></article>)}</div>}
      {documents.length > 0 && <button className="uc-secondary-action uc-curriculum-rebuild" disabled={busy} onClick={async () => { setBusy(true); setError(null); try { await rebuildSubjectCurriculum(subjectId); setNotice("Temario reconstruido desde los materiales actuales."); await load(); } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo reconstruir el temario."); } finally { setBusy(false); } }}><RefreshCw size={14} /> Reconstruir temario</button>}
      {active && <div className="uc-material-viewer"><header><div><p className="uc-eyebrow">Documento activo</p><h3>{active.document.title}</h3></div><div><a href={getDocumentFileUrl(active.document.id)} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Abrir original</a><button onClick={() => setActive(null)} aria-label="Cerrar material"><X size={17} /></button></div></header><pre>{active.content || "Este archivo no tiene contenido extraído disponible."}</pre></div>}
    </div>}
    {editing && <div className="uc-form-backdrop" onMouseDown={() => !busy && setEditing(null)}><section className="uc-form-modal uc-material-edit" onMouseDown={(event) => event.stopPropagation()}><header><div><p className="uc-eyebrow">Clasificación persistente</p><h2>{editing.title}</h2></div><button onClick={() => setEditing(null)} aria-label="Cerrar"><X size={18} /></button></header><label>Tipo de material<select value={editType} onChange={(event) => setEditType(event.target.value as MaterialType)}>{materialTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>Unidad relacionada<span>Opcional</span><select value={editUnitId} onChange={(event) => setEditUnitId(event.target.value)}><option value="">Sin relación manual</option>{units.map((unit) => <option key={unit.id} value={unit.id}>{unit.name}</option>)}</select></label><p>Este cambio reorganiza las referencias curriculares sin volver a extraer el archivo ni recalcular embeddings.</p><footer><button onClick={() => setEditing(null)} disabled={busy}>Cancelar</button><button className="uc-primary-action" onClick={() => void saveClassification()} disabled={busy}>Guardar cambios</button></footer></section></div>}
    {deleting && <div className="uc-form-backdrop" onMouseDown={() => !busy && setDeleting(null)}><section className="uc-form-modal uc-confirm-delete" onMouseDown={(event) => event.stopPropagation()}><header><div><p className="uc-eyebrow">Eliminar material</p><h2>¿Eliminar “{deleting.title}”?</h2></div></header><p>Se eliminarán el archivo, sus fragmentos y sus referencias. El temario compartido con otros materiales se conservará.</p><footer><button onClick={() => setDeleting(null)} disabled={busy}>Cancelar</button><button className="uc-danger-action" onClick={() => void confirmDelete()} disabled={busy}><Trash2 size={15} /> Eliminar definitivamente</button></footer></section></div>}
  </section>;
}
