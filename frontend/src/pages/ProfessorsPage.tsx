import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link2, Plus, RefreshCw, UserRound, X } from "lucide-react";
import {
  addProfessorCriterion,
  assignProfessor,
  createProfessor,
  getDashboard,
  getProfessors,
  getSubjectProfessor,
  type DashboardSubject,
  type ProfessorData,
  type ProfessorOverview,
} from "../api";

const avoidPattern = /penal|avoid|error|negative|rechaz/i;

export default function ProfessorsPage() {
  const [professors, setProfessors] = useState<ProfessorOverview[]>([]);
  const [subjects, setSubjects] = useState<DashboardSubject[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detailSubjectId, setDetailSubjectId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ProfessorData | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newProfessor, setNewProfessor] = useState({ name: "", notes: "", subjectId: "" });
  const [associationId, setAssociationId] = useState("");
  const [criterion, setCriterion] = useState("");
  const [importance, setImportance] = useState(3);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const selected = professors.find((item) => item.id === selectedId) ?? null;

  async function loadDetail(subjectId: number | null) {
    setDetailSubjectId(subjectId);
    setDetail(subjectId == null ? null : await getSubjectProfessor(subjectId));
  }

  async function load(preferredId?: number | null) {
    setLoading(true); setError(null);
    try {
      const [response, dashboard] = await Promise.all([getProfessors(), getDashboard()]);
      setProfessors(response.professors); setSubjects(dashboard.subjects);
      const next = response.professors.find((item) => item.id === (preferredId ?? selectedId)) ?? response.professors[0] ?? null;
      setSelectedId(next?.id ?? null);
      await loadDetail(next?.subjects[0]?.id ?? null);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudieron cargar los profesores."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  async function selectProfessor(item: ProfessorOverview) {
    setSelectedId(item.id); setError(null); setAssociationId("");
    try { await loadDetail(item.subjects[0]?.id ?? null); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo cargar el detalle."); }
  }

  async function submitProfessor(event: FormEvent) {
    event.preventDefault();
    if (!newProfessor.name.trim() || !newProfessor.subjectId) return;
    setSaving(true); setError(null);
    try {
      const result = await createProfessor({ subject_id: Number(newProfessor.subjectId), name: newProfessor.name.trim(), notes: newProfessor.notes.trim() || null });
      setShowCreate(false); setNewProfessor({ name: "", notes: "", subjectId: "" }); setNotice("Profesor creado y asociado.");
      await load(result.professor.id);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo crear el profesor."); }
    finally { setSaving(false); }
  }

  async function associateSubject() {
    if (!selected || !associationId) return;
    setSaving(true); setError(null);
    try { await assignProfessor(Number(associationId), { professor_id: selected.id }); setNotice("Asignatura asociada."); setAssociationId(""); await load(selected.id); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo asociar la asignatura."); }
    finally { setSaving(false); }
  }

  async function submitCriterion(event: FormEvent) {
    event.preventDefault(); if (!selected || !detailSubjectId || !criterion.trim()) return;
    setSaving(true); setError(null);
    try { await addProfessorCriterion(selected.id, detailSubjectId, criterion, importance); setCriterion(""); setNotice("Criterio guardado."); await load(selected.id); await loadDetail(detailSubjectId); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo guardar el criterio."); }
    finally { setSaving(false); }
  }

  const criteria = useMemo(() => detail ? [...detail.preferences.filter((item) => item.professor_id === selectedId), ...detail.rubric_criteria.filter((item) => item.professor_id === selectedId).map((item) => ({ id: item.id, preference: `${item.title}${item.description ? `: ${item.description}` : ""}`, importance: item.weight_percentage ?? item.maximum_points ?? 0, source_type: "rubric", source_reference: item.notes, category: "rubric", confidence: 5, professor_id: selectedId! }))].sort((a, b) => b.importance - a.importance) : [], [detail, selectedId]);
  const availableSubjects = subjects.filter((subject) => !selected?.subjects.some((item) => item.id === subject.id));

  if (loading && !professors.length) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Profesores</p><h1>Reuniendo criterios reales…</h1></section>;
  if (error && !professors.length) return <section className="uc-page-shell uc-state-page"><p className="uc-eyebrow">Profesores</p><h1>No se pudo cargar Professor Intelligence.</h1><p>{error}</p><button className="uc-primary-action" onClick={() => void load()}>Reintentar <RefreshCw size={15} /></button></section>;

  return <div className="uc-page-shell uc-professors-page"><header className="uc-page-intro"><div><p className="uc-eyebrow">Professor Intelligence</p><h1>Entiende cómo evalúa cada profesor.</h1><p className="uc-page-subtitle">Criterios trazables desde rúbricas, feedback, instrucciones y observaciones reales.</p></div><div className="uc-professor-header-actions"><button className="uc-primary-action" onClick={() => setShowCreate(true)}><Plus size={15} /> Añadir profesor</button><span className="uc-date-chip"><UserRound size={15} /> {professors.length} registrados</span></div></header>{notice && <div className="uc-inline-success">{notice}</div>}{error && <div className="uc-inline-error">{error}</div>}{professors.length ? <div className="uc-professor-workspace"><aside>{professors.map((item) => <button key={item.id} className={item.id === selectedId ? "is-active" : ""} onClick={() => void selectProfessor(item)}><strong>{item.name}</strong><span>{item.subjects.map((subject) => subject.name).join(" · ") || "Sin asignatura"}</span><small>{item.criteria_count} criterios · {item.transcript_count} transcripciones</small></button>)}</aside><main>{selected && <><header><p className="uc-eyebrow">Detalle</p><h2>{selected.name}</h2>{selected.notes && <p>{selected.notes}</p>}</header><section className="uc-professor-subjects"><div><h3>Asignaturas asociadas</h3><div>{selected.subjects.map((item) => <button className={item.id === detailSubjectId ? "is-active" : ""} key={item.id} onClick={() => void loadDetail(item.id)}>{item.name}</button>)}</div></div>{availableSubjects.length > 0 && <div className="uc-professor-associate"><select value={associationId} onChange={(event) => setAssociationId(event.target.value)}><option value="">Añadir asignatura</option>{availableSubjects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><button disabled={!associationId || saving} onClick={() => void associateSubject()}><Link2 size={13} /> Asociar</button></div>}</section><section><h3>Cómo evalúa</h3>{criteria.filter((item) => !avoidPattern.test(item.category)).length ? <ol>{criteria.filter((item) => !avoidPattern.test(item.category)).map((item) => <li key={`${item.source_type}-${item.id}`}><strong>{item.preference}</strong><span>Importancia {item.importance} · origen {item.source_type || "observación"}</span>{item.source_reference && <small>{item.source_reference}</small>}</li>)}</ol> : <p className="uc-empty-inline">No hay criterios reales registrados para esta asignatura.</p>}</section>{criteria.some((item) => avoidPattern.test(item.category)) && <section className="uc-professor-avoid"><h3>A evitar</h3><ul>{criteria.filter((item) => avoidPattern.test(item.category)).map((item) => <li key={item.id}>{item.preference}</li>)}</ul></section>}<form onSubmit={submitCriterion}><h3>Añadir criterio</h3><label><span>Criterio observado</span><textarea rows={3} value={criterion} onChange={(event) => setCriterion(event.target.value)} placeholder="Ej. Valora conclusiones derivadas explícitamente del análisis." /></label><label><span>Importancia</span><select value={importance} onChange={(event) => setImportance(Number(event.target.value))}>{[1, 2, 3, 4, 5].map((value) => <option key={value}>{value}</option>)}</select></label><button className="uc-primary-action" disabled={saving || !criterion.trim() || !detailSubjectId}><Plus size={14} /> Guardar criterio</button></form></>}</main></div> : <section className="uc-professor-empty"><h2>No hay profesores registrados.</h2><p>Crea el primero y asócialo inicialmente a una asignatura.</p><button className="uc-primary-action" onClick={() => setShowCreate(true)}><Plus size={15} /> Añadir profesor</button></section>}{showCreate && <div className="uc-form-backdrop" onMouseDown={() => !saving && setShowCreate(false)}><form className="uc-form-modal" onSubmit={submitProfessor} onMouseDown={(event) => event.stopPropagation()}><header><div><p className="uc-eyebrow">Professor Intelligence</p><h2>Añadir profesor</h2></div><button type="button" onClick={() => setShowCreate(false)} aria-label="Cerrar"><X size={18} /></button></header><label>Nombre<span>Obligatorio</span><input autoFocus value={newProfessor.name} onChange={(event) => setNewProfessor({ ...newProfessor, name: event.target.value })} /></label><label>Notas<span>Opcional</span><textarea rows={3} value={newProfessor.notes} onChange={(event) => setNewProfessor({ ...newProfessor, notes: event.target.value })} /></label><label>Asignatura inicial<span>Necesaria para la arquitectura actual</span><select value={newProfessor.subjectId} onChange={(event) => setNewProfessor({ ...newProfessor, subjectId: event.target.value })}><option value="">Seleccionar</option>{subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.name}</option>)}</select></label><footer><button type="button" onClick={() => setShowCreate(false)}>Cancelar</button><button className="uc-primary-action" disabled={saving || !newProfessor.name.trim() || !newProfessor.subjectId}>{saving ? "Guardando…" : "Crear profesor"}</button></footer></form></div>}</div>;
}
