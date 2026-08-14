import { FormEvent, useEffect, useState } from "react";
import { assignProfessor, getProfessors, setAcademicLanguage, type ProfessorData, type ProfessorOverview } from "../api";

export default function ProfessorAssignmentPanel({ subjectId, current, onChanged }: { subjectId: number; current: ProfessorData | null; onChanged: () => Promise<void> }) {
  const [professors, setProfessors] = useState<ProfessorOverview[]>([]);
  const [professorId, setProfessorId] = useState("");
  const [newName, setNewName] = useState("");
  const [language, setLanguage] = useState<"English" | "Spanish">(current?.subject.academic_language ?? "Spanish");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => { getProfessors().then((data) => setProfessors(data.professors)).catch(() => setProfessors([])); }, []);
  useEffect(() => { setLanguage(current?.subject.academic_language ?? "Spanish"); }, [current]);
  async function submit(event: FormEvent) { event.preventDefault(); if (!professorId && !newName.trim()) return; setSaving(true); try { await assignProfessor(subjectId, professorId ? { professor_id: Number(professorId) } : { name: newName.trim() }); setProfessorId(""); setNewName(""); setNotice("Profesor asignado."); await onChanged(); } finally { setSaving(false); } }
  async function updateLanguage(value: "English" | "Spanish") { setLanguage(value); setSaving(true); try { await setAcademicLanguage(subjectId, value); setNotice("Idioma académico actualizado."); await onChanged(); } finally { setSaving(false); } }
  return <section className="uc-professor-assignment"><header><div><p className="uc-eyebrow">Configuración académica</p><h3>Profesor e idioma</h3></div>{notice && <small>{notice}</small>}</header><div><label><span>Idioma académico</span><select value={language} disabled={saving} onChange={(event) => void updateLanguage(event.target.value as "English" | "Spanish")}><option>Spanish</option><option>English</option></select></label><form onSubmit={submit}><label><span>Profesor existente</span><select value={professorId} onChange={(event) => { setProfessorId(event.target.value); if (event.target.value) setNewName(""); }}><option value="">Seleccionar</option>{professors.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><span>o</span><label><span>Crear profesor</span><input value={newName} onChange={(event) => { setNewName(event.target.value); if (event.target.value) setProfessorId(""); }} placeholder="Nombre" /></label><button disabled={saving || (!professorId && !newName.trim())}>Asignar</button></form></div></section>;
}
