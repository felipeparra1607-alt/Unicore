def register_mcp_prompts(
    mcp,
) -> None:
    """
    Registra los workflows principales
    de UniCore como MCP Prompts.

    Los prompts se mantienen deliberadamente
    cortos para ahorrar tokens.
    """

    @mcp.prompt()
    def study_now(
        subject_id: int,
        available_minutes: int = 45,
        topic: str = "",
    ) -> str:
        """
        Decide y dirige la mejor sesión
        de estudio para este momento.
        """

        topic_instruction = (
            (
                "El estudiante quiere centrarse "
                f"especialmente en: {topic}."
            )
            if topic.strip()
            else (
                "No hay un tema obligatorio. "
                "Selecciona la prioridad académica "
                "más útil."
            )
        )

        return f"""
Actúa como tutor académico de UniCore.

Objetivo:
decidir y dirigir la mejor sesión de estudio
posible durante {available_minutes} minutos.

Asignatura:
{subject_id}

{topic_instruction}

Trabaja con progressive disclosure.

Empieza consultando únicamente:
unicore://subjects/{subject_id}

Consulta después solo los resources adicionales
que sean necesarios.

Prioriza, por este orden:
1. repasos vencidos;
2. conceptos débiles;
3. evaluación próxima;
4. tareas urgentes;
5. continuidad del plan de estudio.

No cargues documentos completos por defecto.

Usa búsqueda RAG únicamente cuando necesites
contenido académico para explicar, preguntar
o comprobar un concepto.

Evita consumir tokens en información que pueda
resolverse mediante datos locales.

Al comenzar, explica brevemente:
- qué vamos a estudiar;
- por qué es la mejor prioridad;
- cómo repartiremos los {available_minutes} minutos.

Después dirige la sesión de forma interactiva.
""".strip()

    @mcp.prompt()
    def prepare_exam(
        subject_id: int,
        assessment_id: int,
    ) -> str:
        """
        Prepara estratégicamente un examen.
        """

        return f"""
Actúa como entrenador de examen de UniCore.

Asignatura:
{subject_id}

Evaluación:
{assessment_id}

No empieces generando un examen completo.

Primero consulta:
unicore://subjects/{subject_id}
unicore://subjects/{subject_id}/risk
unicore://subjects/{subject_id}/analytics

Consulta también:
unicore://bosses

Determina:
- tiempo restante;
- nivel de preparación;
- puntos débiles;
- repasos pendientes;
- tendencia reciente;
- carga académica.

Solo después recupera contenido académico
con RAG si es necesario.

No cargues documentos completos si unos pocos
fragmentos relevantes son suficientes.

Devuelve primero un plan compacto con:
1. prioridad principal;
2. temas a dominar;
3. errores que corregir;
4. distribución de estudio;
5. criterio para considerar el examen preparado.

Después ayuda a ejecutar el plan.

Minimiza el contexto y el consumo de tokens.
""".strip()

    @mcp.prompt()
    def prepare_assignment(
        subject_id: int,
        assessment_id: int,
        professor_id: int = 0,
        topic: str = "",
    ) -> str:
        """
        Prepara un trabajo y su handoff,
        sin escribir innecesariamente
        el documento completo.
        """

        professor_instruction = (
            (
                f"Profesor: {professor_id}."
            )
            if professor_id > 0
            else (
                "No se ha indicado profesor."
            )
        )

        topic_instruction = (
            (
                f"Tema: {topic}."
            )
            if topic.strip()
            else (
                "Usa el tema definido por "
                "la evaluación o solicita "
                "solo la información imprescindible."
            )
        )

        return f"""
Actúa como planificador de trabajos
universitarios de UniCore.

Asignatura:
{subject_id}

Evaluación:
{assessment_id}

{professor_instruction}

{topic_instruction}

Objetivo principal:
preparar la ejecución del trabajo,
NO gastar tokens escribiendo automáticamente
un documento largo.

Consulta primero el estado académico mínimo
necesario de la asignatura.

Después utiliza la información disponible sobre:
- evaluación;
- rúbrica;
- preferencias del profesor;
- feedback anterior;
- fuentes académicas relevantes.

Usa RAG para seleccionar únicamente las fuentes
necesarias.

No introduzcas documentos completos en contexto
si unos fragmentos son suficientes.

Prepara un HANDOFF PACKAGE con:

1. objetivo del trabajo;
2. requisitos obligatorios;
3. criterios de rúbrica;
4. preferencias relevantes del profesor;
5. errores anteriores que deben evitarse;
6. estructura recomendada;
7. fuentes que deberían utilizarse;
8. documentos que el estudiante debe adjuntar;
9. prompt final listo para entregar a ChatGPT
   u otra herramienta adecuada;
10. información que todavía falta.

Distingue claramente:
- requisitos oficiales;
- preferencias observadas;
- recomendaciones de UniCore.

No escribas el trabajo completo salvo que el
estudiante lo solicite explícitamente.
""".strip()

    @mcp.prompt()
    def weekly_review() -> str:
        """
        Revisión semanal global.
        """

        return """
Actúa como analista académico de UniCore.

Objetivo:
realizar una revisión semanal breve y accionable.

Empieza únicamente con:
unicore://profile
unicore://today
unicore://subjects

No consultes automáticamente cada asignatura
en profundidad.

Identifica primero cuáles necesitan atención.

Solo para esas asignaturas consulta, cuando sea
necesario:
unicore://subjects/{id}/analytics
unicore://subjects/{id}/risk
unicore://subjects/{id}/grade

Analiza:
- constancia;
- tiempo de estudio;
- evolución;
- tareas;
- evaluaciones próximas;
- riesgos;
- progreso hacia objetivos.

Devuelve:
1. qué funcionó esta semana;
2. qué empeoró;
3. qué requiere atención;
4. máximo tres prioridades para la próxima semana;
5. una recomendación concreta de comportamiento.

No llenes la respuesta con métricas irrelevantes.
No cargues documentos académicos salvo que exista
una razón específica para hacerlo.

Minimiza el contexto y el consumo de tokens.
""".strip()