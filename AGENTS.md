# UniCore — Reglas obligatorias para Codex

## Objetivo actual

Completar únicamente el frontend de UniCore.

El backend ya está terminado, probado y cerrado.

---

## REGLA CRÍTICA — BACKEND READ-ONLY

NO modificar, borrar, refactorizar, mover ni reorganizar archivos existentes dentro de:

- src/
- data/
- tests/
- evals/
- prompts/
- docs/

Tampoco modificar:

- pyproject.toml
- SQLite
- modelos SQLAlchemy
- MCP Server
- MCP Client
- Tools
- Resources
- Decision Engine
- Knowledge Map backend
- UniCore Agent
- Jobs
- Handoff
- RuntimeContext
- permisos
- evaluaciones backend

Puedes LEER el backend completo para comprender cómo funciona.

No puedes CAMBIARLO.

### Excepción

Existe:

src/frontend_api.py

Este archivo es el puente HTTP entre React y el backend.

No modificarlo sin explicar primero por qué es necesario.

Si el frontend requiere un dato o endpoint que no existe:

1. no modifiques backend;
2. identifica exactamente qué falta;
3. explica el bloqueo;
4. espera aprobación humana.

---

## Directorio principal de trabajo

Puedes modificar:

frontend/

Puedes:

- crear componentes React;
- crear páginas;
- crear hooks;
- crear utilidades;
- crear tipos TypeScript;
- modificar CSS;
- modificar navegación;
- conectar APIs existentes;
- ejecutar npm;
- ejecutar TypeScript;
- ejecutar Vite;
- ejecutar tests frontend.

---

## Arquitectura

UniCore es una aplicación universitaria personal.

Backend:

Usuario
→ UniCore Agent
→ MCP Client
→ MCP Server
→ Tools / Resources
→ SQLite

También existen:

- Decision Engine
- Knowledge Map
- Gamification
- Study system
- Assessments
- Analytics
- Agent
- Jobs
- Handoff

El backend debe considerarse terminado.

---

## API frontend existente

Se ejecuta mediante:

python -m src.frontend_api

Puerto:

http://127.0.0.1:8766

Endpoints actuales:

GET /api/health

GET /api/dashboard

GET /api/decision-plan

Antes de asumir que falta información, inspecciona el backend.

No crear mocks si el backend ya contiene el dato.

---

## Frontend

Ruta:

frontend/

Stack:

- React
- TypeScript
- Vite
- Tailwind
- Recharts
- Lucide React

Comandos:

npm run build

npm run dev

---

## Diseño ya aprobado

NO reconstruir el diseño desde cero.

La dirección visual actual del Inicio está aprobada.

Mantener:

- modo claro;
- modo oscuro;
- sidebar;
- dashboard académico;
- gráficos;
- gamificación;
- jerarquía visual actual.

---

## Identidad

UniCore debe sentirse como un:

ACADEMIC PERFORMANCE OS

Combinación de:

- universidad;
- analytics;
- productividad académica;
- progresión tipo videojuego.

La home debe responder:

"¿Qué debería hacer ahora?"

El Decision Engine determina esa prioridad.

---

## Evitar estética típica generada por IA

Evitar:

- gradientes morado/azul innecesarios;
- blobs;
- glassmorphism generalizado;
- grids de cards idénticas;
- exceso de bordes redondeados;
- estética genérica shadcn/v0/Lovable;
- enormes espacios vacíos;
- hero SaaS centrada;
- chatbot como home;
- iconos puramente decorativos;
- hover scale generalizado;
- copy genérico de IA;
- donut charts decorativos.

Preferir:

- jerarquía visual;
- densidad informativa;
- layouts deliberados;
- tablas;
- barras;
- heatmaps;
- gráficos académicos;
- interfaz específica para UniCore.

---

## IA

UniCore NO es un wrapper de ChatGPT.

El Agent es una capacidad dentro del producto.

No mostrar al usuario normal:

- nombres internos de Tools;
- Resources MCP;
- JSON;
- IDs técnicos;
- routing interno.

---

## Gamificación

Es una parte central.

Debe usar actividad académica real:

- XP;
- niveles;
- rachas;
- objetivos;
- logros;
- progreso por asignatura;
- Boss Battles;
- preparación para exámenes.

Nunca inventar XP si existe en backend.

---

## Gráficas

Deben ayudar a tomar decisiones.

Ejemplos:

- minutos estudiados;
- preparación;
- quizzes;
- progreso por asignatura;
- heatmap de actividad;
- tiempo por asignatura;
- notas.

Nunca inventar una serie histórica si backend no dispone de ella.

---

## Correcciones pendientes del Inicio

Resolver antes del cierre final:

1. El bloque de gamificación tiene un problema de layout:
   parte del texto cae demasiado hacia abajo.

2. Los días sin actividad deben mostrarse en rojo.

No es necesario resolverlo antes de construir las demás pantallas.

---

## Navegación objetivo

- Inicio
- Asignaturas
- Tareas
- Estudio
- Conocimiento
- Agent
- Jobs
- Ajustes

---

## Asignaturas

Vista global:

- nombre;
- nota;
- objetivo;
- preparación;
- próximo examen;
- tareas;
- tiempo estudiado;
- quiz medio;
- XP;
- estado.

Vista individual:

- resumen;
- notas;
- evaluaciones;
- tareas;
- Knowledge Map;
- estudio;
- quizzes;
- materiales;
- progreso;
- riesgo académico.

---

## Tareas

Mostrar:

- pendientes;
- vencidas;
- en progreso;
- completadas;
- prioridad;
- fecha;
- asignatura;
- progreso.

Usar Decision Engine para planificación.

Opciones de tiempo:

- 15 min
- 30 min
- 45 min
- 60 min
- 90 min

---

## Estudio

Modos existentes:

- explanation
- flashcards
- quick_review
- quiz
- summary

Mostrar:

- duración;
- foco;
- dificultad;
- satisfacción;
- historial;
- quizzes;
- repasos.

---

## Knowledge Map

Debe ser visual.

Estados:

- mastered
- developing
- weak
- unassessed

Debe permitir ver rápidamente:

- qué domina el usuario;
- qué necesita atención;
- qué debería estudiar.

---

## Agent

Tiene su propia vista.

No es la home.

Debe usar contexto académico real.

Puede ser conversacional pero debe sentirse integrado en UniCore.

---

## Jobs

Mostrar:

- processing;
- completed;
- failed.

Presentar resultados de forma humana.

No mostrar IDs técnicos salvo detalle avanzado.

---

## Estados obligatorios

Cada pantalla debe tener:

- loading;
- success;
- empty;
- error.

---

## Responsive

Desktop es prioritario.

También debe funcionar correctamente en móvil.

---

## Orden de trabajo

Trabajar pantalla por pantalla:

1. Asignaturas
2. Tareas
3. Estudio
4. Knowledge Map
5. Agent
6. Jobs
7. Ajustes
8. correcciones globales
9. responsive
10. E2E final

No hacer una reescritura masiva.

---

## Verificación

Después de cada módulo importante:

1. ejecutar TypeScript;
2. ejecutar npm run build;
3. corregir errores;
4. revisar git diff;
5. confirmar que backend no fue modificado.

---

## Git

Trabajar únicamente en:

frontend-codex

NO cambiar a master.

NO hacer:

git reset --hard

NO force push.

NO borrar tags.

NO modificar backend.

Crear commits descriptivos después de cada módulo funcional.

---

## Regla final

Si existe elección entre:

A) modificar backend;

B) adaptar frontend al backend actual;

elegir B.

Si B es imposible, detenerse y pedir aprobación antes de tocar backend.