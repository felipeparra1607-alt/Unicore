import { FormEvent, useEffect, useState } from "react";
import { Plus, UserRound, X } from "lucide-react";
import { assignProfessor, getProfessors, setAcademicLanguage, type AcademicLanguage, type ProfessorData, type ProfessorOverview } from "../api";

export default function ProfessorAssignmentPanel({ subjectId, current, onChanged }: { subjectId: number; current: ProfessorData | null; onChanged: () => Promise<void> }) {
  const [professors, setProfessors] = useState<ProfessorOverview[]>([]);
  const [professorId, setProfessorId] = useState("");
  const [newName, setNewName] = useState("");
  const [newNotes, setNewNotes] = useState("");
  const [language, setLanguage] = useState<AcademicLanguage>(current?.subject.academic_language ?? "Spanish");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const assigned = current?.professors[0] ?? null;

  async function loadProfessors() { try { setProfessors((await getProfessors()).professors); } catch { setProfessors([]); } }
  useEffect(() => { void loadProfessors(); }, []);
  useEffect(() => { setLanguage(current?.subject.academic_language ?? "Spanish"); if (current && !current.subject.academic_language_configured) setNotice("Confirma el idioma académico antes de generar contenido."); }, [current]);

  async function submit(event: FormEvent) {
    event.preventDefault(); if (!professorId && !newName.trim()) return;
    setSaving(true);
    try {
      await assignProfessor(subjectId, professorId ? { professor_id: Number(professorId) } : { name: newName.trim(), notes: newNotes.trim() || null });
      setProfessorId(""); setNewName(""); setNewNotes(""); setEditing(false); setNotice("Profesor asignado.");
      await Promise.all([onChanged(), loadProfessors()]);
    } finally { setSaving(false); }
  }

  async function updateLanguage(value: AcademicLanguage) {
    setLanguage(value); setSaving(true);
    try { await setAcademicLanguage(subjectId, value); setNotice("Idioma académico actualizado."); await onChanged(); }
    finally { setSaving(false); }
  }

  return <section className="uc-professor-assignment"><header><div><p className="uc-eyebrow">Configuración académica</p><h3>Profesor e idioma</h3></div>{notice && <small>{notice}</small>}</header><div className="uc-professor-assignment-summary"><label><span>Idioma académico</span><select value={language} disabled={saving} onChange={(event) => void updateLanguage(event.target.value as AcademicLanguage)}><option value="Spanish">Spanish</option><option value="English">English</option></select></label><div className="uc-assigned-professor">{assigned ? <><UserRound size={17} /><span><small>Profesor asignado</small><strong>{assigned.name}</strong></span></> : <span><small>Profesor</small><strong>No hay profesor asignado</strong></span>}<button onClick={() => setEditing((value) => !value)}>{editing ? <X size={13} /> : <Plus size={13} />} {editing ? "Cancelar" : assigned ? "Cambiar profesor" : "Asignar profesor"}</button></div></div>{editing && <form className="uc-professor-assignment-editor" onSubmit={submit}><label><span>Elegir existente</span><select value={professorId} onChange={(event) => { setProfessorId(event.target.value); if (event.target.value) { setNewName(""); setNewNotes(""); } }}><option value="">Seleccionar profesor</option>{professors.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><span>o crear nuevo</span><label><span>Nombre</span><input value={newName} onChange={(event) => { setNewName(event.target.value); if (event.target.value) setProfessorId(""); }} placeholder="Nombre del profesor" /></label><label><span>Notas · opcional</span><input value={newNotes} onChange={(event) => setNewNotes(event.target.value)} placeholder="Contexto útil" /></label><button disabled={saving || (!professorId && !newName.trim())}>Asignar</button></form>}</section>;
}
