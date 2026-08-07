import html
import json
from http.server import (
    BaseHTTPRequestHandler,
    HTTPServer,
)
from urllib.parse import (
    parse_qs,
    urlparse,
)

from src.unicore_dashboard import (
    build_dashboard_data,
)


HOST = "127.0.0.1"
PORT = 8765


def escape(
    value,
) -> str:
    """Escapa texto antes de mostrarlo en HTML."""

    if value is None:
        return ""

    return html.escape(
        str(value)
    )


def format_percentage(
    value,
    decimals: int = 0,
    signed: bool = False,
) -> str:
    """
    Formatea porcentajes.

    Ejemplos:
    80 -> 80%
    12.3 -> +12.3%
    None -> —
    """

    if value is None:
        return "—"

    if signed:
        return (
            f"{value:+.{decimals}f}%"
        )

    return (
        f"{value:.{decimals}f}%"
    )


def progress_bar(
    percentage: float | None,
    extra_class: str = "",
) -> str:
    """Genera una barra visual de progreso."""

    if percentage is None:
        percentage = 0

    safe_percentage = max(
        0,
        min(
            float(percentage),
            100,
        ),
    )

    return f"""
    <div class="progress-track {extra_class}">
        <div
            class="progress-fill"
            style="width:{safe_percentage}%"
        ></div>
    </div>
    """


def risk_class(
    level: str,
) -> str:
    """Convierte nivel de riesgo en clase CSS."""

    mapping = {
        "low": "risk-low",
        "medium": "risk-medium",
        "high": "risk-high",
    }

    return mapping.get(
        level,
        "risk-medium",
    )


def risk_label(
    level: str,
) -> str:
    """Traduce nivel de riesgo."""

    mapping = {
        "low": "Bajo",
        "medium": "Medio",
        "high": "Alto",
    }

    return mapping.get(
        level,
        level,
    )


def trend_class(
    value,
    inverse: bool = False,
) -> str:
    """
    Devuelve clase visual para una tendencia.

    inverse=True sirve cuando una subida sería negativa.
    """

    if value is None or value == 0:
        return "trend-neutral"

    positive = value > 0

    if inverse:
        positive = not positive

    return (
        "trend-positive"
        if positive
        else "trend-negative"
    )


def render_activity_chart(
    activity: list[dict],
) -> str:
    """Renderiza actividad de estudio de 7 días."""

    maximum = max(
        [
            item["minutes"]
            for item in activity
        ]
        + [1]
    )

    bars = []

    weekday_names = {
        "Mon": "L",
        "Tue": "M",
        "Wed": "X",
        "Thu": "J",
        "Fri": "V",
        "Sat": "S",
        "Sun": "D",
    }

    for item in activity:
        percentage = (
            item["minutes"]
            / maximum
            * 100
        )

        weekday = weekday_names.get(
            item["weekday"],
            item["weekday"],
        )

        bars.append(
            f"""
            <div class="activity-day">

                <div class="activity-value">
                    {item["minutes"]}m
                </div>

                <div class="activity-bar-track">

                    <div
                        class="activity-bar"
                        style="height:{percentage}%"
                    ></div>

                </div>

                <div class="activity-label">
                    {escape(weekday)}
                </div>

            </div>
            """
        )

    return "".join(bars)


def render_missions(
    missions: dict,
) -> str:
    """Renderiza misiones del día."""

    items = missions.get(
        "items",
        [],
    )

    if not items:
        return """
        <div class="empty-state">
            No hay misiones generadas para hoy.
        </div>
        """

    output = []

    for mission in items:
        completed = (
            mission["status"]
            == "completed"
        )

        symbol = (
            "✓"
            if completed
            else "○"
        )

        progress = min(
            100,
            (
                mission["current_value"]
                / mission["target_value"]
                * 100
            )
            if mission["target_value"]
            else 0,
        )

        row_class = (
            "mission-completed"
            if completed
            else ""
        )

        output.append(
            f"""
            <div class="mission-row {row_class}">

                <div class="mission-symbol">
                    {symbol}
                </div>

                <div class="mission-content">

                    <div class="mission-title">
                        {escape(mission["title"])}
                    </div>

                    <div class="mission-meta">
                        {mission["current_value"]}
                        /
                        {mission["target_value"]}
                    </div>

                    {progress_bar(progress)}

                </div>

                <div class="xp-pill">
                    +{mission["reward_xp"]} XP
                </div>

            </div>
            """
        )

    return "".join(output)


def render_priorities(
    priorities: list[dict],
) -> str:
    """Renderiza tareas prioritarias."""

    if not priorities:
        return """
        <div class="empty-state">
            No hay tareas pendientes.
        </div>
        """

    rows = []

    for task in priorities:
        days = task[
            "days_remaining"
        ]

        if days is None:
            deadline = "Sin fecha"
            deadline_class = ""

        elif days < 0:
            deadline = (
                f"Vencida hace "
                f"{abs(days)} día(s)"
            )
            deadline_class = "deadline-danger"

        elif days == 0:
            deadline = "Vence hoy"
            deadline_class = "deadline-danger"

        elif days == 1:
            deadline = "Vence mañana"
            deadline_class = "deadline-warning"

        elif days <= 3:
            deadline = (
                f"Quedan {days} días"
            )
            deadline_class = "deadline-warning"

        else:
            deadline = (
                f"Quedan {days} días"
            )
            deadline_class = ""

        rows.append(
            f"""
            <div class="priority-row">

                <div class="priority-main">

                    <div class="priority-title">
                        {escape(task["title"])}
                    </div>

                    <div
                        class="
                            priority-deadline
                            {deadline_class}
                        "
                    >
                        {escape(deadline)}
                    </div>

                </div>

                <div class="priority-right">

                    <div class="priority-number">
                        P{task["priority"]}
                    </div>

                    <div class="small-progress">
                        {task["progress_percentage"]}%
                    </div>

                </div>

            </div>
            """
        )

    return "".join(rows)


def render_boss(
    boss: dict | None,
) -> str:
    """Renderiza próximo Boss Battle."""

    if boss is None:
        return """
        <div class="empty-state boss-empty">
            No hay ningún Boss Battle activo.
        </div>
        """

    readiness = boss[
        "readiness_percentage"
    ]

    weak_topics = boss.get(
        "weak_topics",
        [],
    )

    weak_text = ""

    if weak_topics:
        topic_names = []

        for item in weak_topics[:3]:
            if isinstance(item, dict):
                topic_name = item.get(
                    "topic"
                )

                if topic_name:
                    topic_names.append(
                        str(topic_name)
                    )

        if topic_names:
            weak_text = (
                "<div class='boss-weak'>"
                "<strong>Puntos débiles</strong><br>"
                + escape(
                    " · ".join(
                        topic_names
                    )
                )
                + "</div>"
            )

    days = boss.get(
        "days_remaining"
    )

    if days is None:
        day_text = "Sin fecha"

    elif days < 0:
        day_text = (
            f"{abs(days)} días vencido"
        )

    elif days == 0:
        day_text = "Hoy"

    elif days == 1:
        day_text = "Mañana"

    else:
        day_text = (
            f"{days} días"
        )

    return f"""
    <div class="boss-header">

        <div>
            <div class="eyebrow">
                PRÓXIMO DESAFÍO
            </div>

            <div class="boss-title">
                {escape(boss["assessment_title"])}
            </div>
        </div>

        <div class="boss-days">
            {escape(day_text)}
        </div>

    </div>

    <div class="boss-center">

        <div class="boss-percentage">
            {readiness:.0f}%
        </div>

        <div class="boss-caption">
            preparación actual
        </div>

    </div>

    {progress_bar(readiness)}

    {weak_text}

    <div class="boss-footer">

        <div>
            Objetivo ·
            {boss["target_score_percentage"]:.0f}%
        </div>

        <div class="boss-reward">
            +{boss["reward_xp"]} XP
        </div>

    </div>
    """


def render_subjects(
    subjects: list[dict],
) -> str:
    """Renderiza tarjetas de asignaturas."""

    if not subjects:
        return """
        <div class="empty-state">
            No hay asignaturas.
        </div>
        """

    cards = []

    for subject in subjects:
        quiz = (
            f"{subject['quiz_average_percentage']:.0f}%"
            if (
                subject[
                    "quiz_average_percentage"
                ]
                is not None
            )
            else "—"
        )

        hours = (
            subject["study_minutes"]
            / 60
        )

        next_assessment = (
            subject.get(
                "next_assessment"
            )
        )

        if next_assessment:
            next_text = (
                next_assessment["title"]
            )
        else:
            next_text = (
                "Sin evaluación próxima"
            )

        grade = subject.get(
            "grade",
            {},
        )

        current_grade = grade.get(
            "current_grade_out_of_10"
        )

        grade_text = (
            f"{current_grade:.1f}"
            if current_grade
            is not None
            else "—"
        )

        cards.append(
            f"""
            <a
                class="subject-card"
                href="/?subject_id={subject["id"]}"
            >

                <div class="subject-card-top">

                    <div class="subject-name">
                        {escape(subject["name"])}
                    </div>

                    <div class="subject-arrow">
                        →
                    </div>

                </div>

                <div class="subject-stats">

                    <div>
                        <span>
                            {subject["xp"]}
                        </span>
                        XP
                    </div>

                    <div>
                        <span>
                            {hours:.1f}h
                        </span>
                        estudio
                    </div>

                    <div>
                        <span>
                            {quiz}
                        </span>
                        quiz
                    </div>

                    <div>
                        <span>
                            {grade_text}
                        </span>
                        nota
                    </div>

                </div>

                <div class="subject-next">
                    Próximo ·
                    {escape(next_text)}
                </div>

            </a>
            """
        )

    return "".join(cards)


def render_analytics(
    analytics: dict | None,
) -> str:
    """
    Renderiza métricas inteligentes de estudio.
    """

    if not analytics:
        return """
        <div class="empty-state">
            Todavía no hay suficientes datos
            para calcular tendencias.
        </div>
        """

    current = analytics.get(
        "current",
        {},
    )

    trends = analytics.get(
        "trends",
        {},
    )

    efficiency = current.get(
        "study_efficiency_index"
    )

    plan_completion = current.get(
        "plan_completion_percentage"
    )

    average_focus = current.get(
        "average_focus"
    )

    quiz_trend = trends.get(
        "quiz_average_change_percentage"
    )

    study_trend = trends.get(
        "study_minutes_change_percentage"
    )

    active_days_trend = trends.get(
        "active_days_change_percentage"
    )

    efficiency_text = (
        format_percentage(
            efficiency,
            decimals=0,
        )
    )

    plan_text = (
        format_percentage(
            plan_completion,
            decimals=0,
        )
    )

    focus_text = (
        f"{average_focus:.1f}/5"
        if average_focus is not None
        else "—"
    )

    quiz_trend_text = (
        format_percentage(
            quiz_trend,
            decimals=1,
            signed=True,
        )
    )

    study_trend_text = (
        format_percentage(
            study_trend,
            decimals=1,
            signed=True,
        )
    )

    active_days_text = (
        format_percentage(
            active_days_trend,
            decimals=1,
            signed=True,
        )
    )

    return f"""
    <div class="analytics-grid">

        <div class="analytics-card">
            <div class="analytics-icon">
                ⚡
            </div>

            <div class="analytics-value">
                {efficiency_text}
            </div>

            <div class="analytics-label">
                Eficiencia de estudio
            </div>

            <div class="analytics-help">
                Foco + quizzes + cumplimiento
            </div>
        </div>

        <div class="analytics-card">
            <div class="analytics-icon">
                ✓
            </div>

            <div class="analytics-value">
                {plan_text}
            </div>

            <div class="analytics-label">
                Cumplimiento del plan
            </div>

            <div class="analytics-help">
                Sesiones planificadas completadas
            </div>
        </div>

        <div class="analytics-card">
            <div class="analytics-icon">
                ◎
            </div>

            <div class="analytics-value">
                {focus_text}
            </div>

            <div class="analytics-label">
                Foco medio
            </div>

            <div class="analytics-help">
                Valoración de las sesiones
            </div>
        </div>

        <div class="analytics-card">

            <div class="analytics-trend-label">
                QUIZZES
            </div>

            <div
                class="
                    analytics-trend
                    {trend_class(quiz_trend)}
                "
            >
                {quiz_trend_text}
            </div>

            <div class="analytics-help">
                frente al periodo anterior
            </div>

        </div>

        <div class="analytics-card">

            <div class="analytics-trend-label">
                TIEMPO DE ESTUDIO
            </div>

            <div
                class="
                    analytics-trend
                    {trend_class(study_trend)}
                "
            >
                {study_trend_text}
            </div>

            <div class="analytics-help">
                frente al periodo anterior
            </div>

        </div>

        <div class="analytics-card">

            <div class="analytics-trend-label">
                DÍAS ACTIVOS
            </div>

            <div
                class="
                    analytics-trend
                    {trend_class(active_days_trend)}
                "
            >
                {active_days_text}
            </div>

            <div class="analytics-help">
                frente al periodo anterior
            </div>

        </div>

    </div>
    """


def render_risk(
    risk: dict | None,
) -> str:
    """Renderiza panel de riesgo académico."""

    if not risk:
        return """
        <div class="empty-state">
            Selecciona una asignatura para
            analizar sus señales de riesgo.
        </div>
        """

    risk_data = risk.get(
        "risk",
        {},
    )

    score = risk_data.get(
        "score",
        0,
    )

    level = risk_data.get(
        "level",
        "low",
    )

    css_class = risk_class(
        level
    )

    signals = risk.get(
        "signals",
        [],
    )

    signal_html = []

    for signal in signals[:5]:
        points = signal.get(
            "points",
            0,
        )

        signal_html.append(
            f"""
            <div class="risk-signal">

                <div class="risk-signal-dot"></div>

                <div class="risk-signal-content">

                    <div class="risk-signal-message">
                        {escape(signal["message"])}
                    </div>

                    <div class="risk-signal-points">
                        +{points} señal
                    </div>

                </div>

            </div>
            """
        )

    if not signal_html:
        signal_html.append(
            """
            <div class="risk-good">
                ✓ No hay señales académicas
                importantes en este momento.
            </div>
            """
        )

    return f"""
    <div class="risk-top">

        <div>

            <div class="risk-score">
                {score}
            </div>

            <div class="risk-score-caption">
                sobre 100
            </div>

        </div>

        <div
            class="
                risk-badge
                {css_class}
            "
        >
            Riesgo {escape(risk_label(level))}
        </div>

    </div>

    {
        progress_bar(
            score,
            "risk-progress"
        )
    }

    <div class="risk-explanation">
        Esta puntuación no predice tu nota.
        Agrupa señales que requieren atención.
    </div>

    <div class="risk-signals">
        {"".join(signal_html)}
    </div>
    """


def render_grade_section(
    grade: dict | None,
) -> str:
    """Renderiza métricas de nota para una asignatura."""

    if not grade:
        return ""

    current_grade = grade.get(
        "current_grade_out_of_10"
    )

    target_grade = grade.get(
        "target_grade"
    )

    required = grade.get(
        "required_average_on_remaining"
    )

    evaluated = grade.get(
        "evaluated_weight_percentage"
    )

    current_text = (
        f"{current_grade:.2f}"
        if current_grade is not None
        else "—"
    )

    target_text = (
        f"{target_grade:.1f}"
        if target_grade is not None
        else "—"
    )

    required_text = (
        f"{required:.2f}"
        if required is not None
        else "—"
    )

    evaluated_text = (
        f"{evaluated:.0f}%"
        if evaluated is not None
        else "—"
    )

    return f"""
    <section class="panel">

        <div class="panel-header">

            <div>
                <div class="eyebrow">
                    RESULTADOS
                </div>

                <h2>
                    Situación académica
                </h2>
            </div>

        </div>

        <div class="grade-grid">

            <div class="grade-card">

                <div class="grade-big">
                    {current_text}
                </div>

                <div class="grade-label">
                    Nota actual
                </div>

            </div>

            <div class="grade-card">

                <div class="grade-big">
                    {target_text}
                </div>

                <div class="grade-label">
                    Objetivo
                </div>

            </div>

            <div class="grade-card">

                <div class="grade-big">
                    {required_text}
                </div>

                <div class="grade-label">
                    Necesario en lo restante
                </div>

            </div>

            <div class="grade-card">

                <div class="grade-big">
                    {evaluated_text}
                </div>

                <div class="grade-label">
                    Asignatura evaluada
                </div>

            </div>

        </div>

    </section>
    """


def render_achievements(
    achievements: list[dict],
) -> str:
    """Renderiza logros recientes."""

    if not achievements:
        return """
        <div class="empty-state">
            Tus próximos logros aparecerán aquí.
        </div>
        """

    output = []

    for achievement in achievements:
        output.append(
            f"""
            <div class="achievement">

                <div class="achievement-icon">
                    ★
                </div>

                <div>

                    <div class="achievement-title">
                        {escape(achievement["title"])}
                    </div>

                    <div class="achievement-description">
                        {escape(achievement["description"])}
                    </div>

                </div>

            </div>
            """
        )

    return "".join(output)


def render_page(
    data: dict,
) -> str:
    """Construye la página principal."""

    hero = data[
        "hero"
    ]

    metrics = data[
        "metrics"
    ]

    subject = data.get(
        "subject"
    )

    title = (
        subject["name"]
        if subject
        else "Tu universidad"
    )

    view_label = (
        "Vista de asignatura"
        if subject
        else "Vista global"
    )

    xp_progress = hero[
        "level_progress_percentage"
    ]

    quiz_average = metrics[
        "quiz_average_percentage"
    ]

    quiz_text = (
        f"{quiz_average:.0f}%"
        if quiz_average is not None
        else "—"
    )

    week_hours = (
        metrics[
            "study_minutes_last_7_days"
        ]
        / 60
    )

    back_button = (
        """
        <a href="/" class="back-button">
            ← Vista global
        </a>
        """
        if subject
        else ""
    )

    risk_panel = ""

    if subject:
        risk_panel = f"""
        <section class="panel">

            <div class="panel-header">
                <div>
                    <div class="eyebrow">
                        ATENCIÓN ACADÉMICA
                    </div>

                    <h2>
                        Riesgo actual
                    </h2>
                </div>
            </div>

            {
                render_risk(
                    data.get(
                        "academic_risk"
                    )
                )
            }

        </section>
        """

    grade_section = (
        render_grade_section(
            data.get(
                "grade"
            )
        )
    )

    return f"""
<!DOCTYPE html>

<html lang="es">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="
        width=device-width,
        initial-scale=1.0
    "
>

<title>
    UniCore Dashboard
</title>

<style>

:root {{
    --background: #080b12;
    --surface: #111622;
    --surface-2: #171d2b;
    --surface-3: #1d2434;

    --border:
        rgba(
            255,
            255,
            255,
            .08
        );

    --text: #f5f7fb;
    --muted: #8892a6;

    --accent: #8b5cf6;
    --accent-2: #6366f1;

    --green: #41d69c;
    --red: #ff6b78;
    --warning: #ffb454;
}}

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;

    background:
        radial-gradient(
            circle at 10% 0%,
            rgba(
                99,
                102,
                241,
                .16
            ),
            transparent 30%
        ),
        radial-gradient(
            circle at 90% 10%,
            rgba(
                139,
                92,
                246,
                .12
            ),
            transparent 28%
        ),
        var(--background);

    color: var(--text);

    font-family:
        Inter,
        ui-sans-serif,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;

    min-height: 100vh;
}}

.container {{
    width:
        min(
            1380px,
            calc(
                100% - 40px
            )
        );

    margin: 0 auto;

    padding:
        42px 0 80px;
}}

header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;

    margin-bottom: 34px;
}}

.brand {{
    display: flex;
    align-items: center;
    gap: 14px;
}}

.logo {{
    width: 48px;
    height: 48px;

    border-radius: 15px;

    display: grid;
    place-items: center;

    font-size: 20px;
    font-weight: 900;

    background:
        linear-gradient(
            135deg,
            var(--accent),
            var(--accent-2)
        );

    box-shadow:
        0 15px 50px
        rgba(
            99,
            102,
            241,
            .32
        );
}}

h1 {{
    margin: 0;

    font-size: 28px;

    letter-spacing: -.8px;
}}

.subtitle {{
    color: var(--muted);

    margin-top: 5px;

    font-size: 14px;
}}

.view-label {{
    margin-top: 5px;

    color: #616c82;

    font-size: 11px;

    text-transform: uppercase;

    letter-spacing: 1px;
}}

.back-button {{
    color: var(--text);

    text-decoration: none;

    border:
        1px solid
        var(--border);

    background:
        rgba(
            255,
            255,
            255,
            .04
        );

    padding: 10px 14px;

    border-radius: 12px;

    font-size: 13px;

    transition:
        background .15s ease;
}}

.back-button:hover {{
    background:
        rgba(
            255,
            255,
            255,
            .08
        );
}}

.hero {{
    padding: 28px;

    border:
        1px solid
        var(--border);

    border-radius: 24px;

    background:
        linear-gradient(
            120deg,
            rgba(
                139,
                92,
                246,
                .14
            ),
            rgba(
                17,
                22,
                34,
                .9
            )
        );

    margin-bottom: 20px;
}}

.hero-top {{
    display: flex;

    justify-content:
        space-between;

    gap: 30px;

    align-items: flex-end;
}}

.eyebrow {{
    font-size: 11px;

    letter-spacing: 1.6px;

    color: #9ca8bf;

    font-weight: 800;

    margin-bottom: 8px;
}}

.hero-level {{
    font-size: 50px;

    letter-spacing: -2.5px;

    font-weight: 850;
}}

.hero-xp {{
    font-size: 18px;

    font-weight: 750;
}}

.hero-next {{
    color: var(--muted);

    margin-top: 4px;

    font-size: 13px;
}}

.progress-track {{
    height: 7px;

    background:
        rgba(
            255,
            255,
            255,
            .07
        );

    border-radius: 999px;

    overflow: hidden;

    margin-top: 13px;
}}

.progress-fill {{
    height: 100%;

    border-radius: inherit;

    background:
        linear-gradient(
            90deg,
            var(--accent),
            #a78bfa
        );

    transition:
        width .25s ease;
}}

.metrics {{
    display: grid;

    grid-template-columns:
        repeat(
            5,
            minmax(
                0,
                1fr
            )
        );

    gap: 14px;

    margin-bottom: 20px;
}}

.metric-card {{
    padding: 20px;

    border-radius: 20px;

    border:
        1px solid
        var(--border);

    background:
        rgba(
            17,
            22,
            34,
            .92
        );
}}

.metric-icon {{
    font-size: 20px;

    margin-bottom: 16px;
}}

.metric-value {{
    font-size: 28px;

    font-weight: 850;

    letter-spacing: -1px;
}}

.metric-label {{
    color: var(--muted);

    font-size: 12px;

    margin-top: 5px;
}}

.grid {{
    display: grid;

    grid-template-columns:
        1.15fr .85fr;

    gap: 20px;

    margin-bottom: 20px;
}}

.grid-equal {{
    grid-template-columns:
        1fr 1fr;
}}

.panel {{
    border-radius: 22px;

    border:
        1px solid
        var(--border);

    background:
        rgba(
            17,
            22,
            34,
            .92
        );

    padding: 24px;
}}

.panel-header {{
    display: flex;

    justify-content:
        space-between;

    margin-bottom: 22px;
}}

.panel h2 {{
    margin: 0;

    font-size: 19px;

    letter-spacing: -.4px;
}}

.mission-row {{
    display: flex;

    gap: 13px;

    align-items: center;

    padding: 15px 0;

    border-bottom:
        1px solid
        var(--border);
}}

.mission-row:last-child {{
    border-bottom: 0;
}}

.mission-completed {{
    opacity: .72;
}}

.mission-symbol {{
    width: 30px;
    height: 30px;

    border-radius: 10px;

    background:
        rgba(
            139,
            92,
            246,
            .12
        );

    display: grid;
    place-items: center;

    color: #b9a2ff;

    font-weight: 800;
}}

.mission-completed
.mission-symbol {{
    color: var(--green);

    background:
        rgba(
            65,
            214,
            156,
            .10
        );
}}

.mission-content {{
    flex: 1;
}}

.mission-title {{
    font-size: 14px;

    font-weight: 650;
}}

.mission-meta {{
    color: var(--muted);

    font-size: 11px;

    margin-top: 4px;
}}

.xp-pill {{
    color: #bca8ff;

    font-weight: 750;

    font-size: 12px;

    background:
        rgba(
            139,
            92,
            246,
            .11
        );

    padding: 6px 9px;

    border-radius: 999px;
}}

.boss-header {{
    display: flex;

    justify-content:
        space-between;

    gap: 20px;
}}

.boss-title {{
    font-size: 22px;

    font-weight: 800;
}}

.boss-days {{
    font-size: 12px;

    color:
        var(--warning);

    background:
        rgba(
            255,
            180,
            84,
            .1
        );

    padding: 7px 10px;

    border-radius: 999px;

    height: fit-content;
}}

.boss-center {{
    margin-top: 26px;
}}

.boss-percentage {{
    font-size: 55px;

    font-weight: 900;

    letter-spacing: -3px;
}}

.boss-caption {{
    color: var(--muted);

    font-size: 12px;
}}

.boss-weak {{
    color: var(--muted);

    margin-top: 20px;

    font-size: 12px;

    line-height: 1.6;
}}

.boss-footer {{
    margin-top: 18px;

    display: flex;

    justify-content:
        space-between;

    color: var(--muted);

    font-size: 12px;
}}

.boss-reward {{
    color: #bca8ff;

    font-weight: 750;
}}

.activity-chart {{
    height: 210px;

    display: flex;

    gap: 14px;

    align-items: stretch;
}}

.activity-day {{
    flex: 1;

    display: flex;

    flex-direction: column;

    align-items: center;
}}

.activity-value {{
    color: var(--muted);

    font-size: 10px;

    height: 24px;
}}

.activity-bar-track {{
    flex: 1;

    width:
        min(
            32px,
            70%
        );

    background:
        rgba(
            255,
            255,
            255,
            .04
        );

    border-radius: 8px;

    display: flex;

    align-items: flex-end;

    overflow: hidden;
}}

.activity-bar {{
    width: 100%;

    min-height: 2px;

    background:
        linear-gradient(
            180deg,
            #a78bfa,
            #6366f1
        );

    border-radius: 8px;
}}

.activity-label {{
    margin-top: 10px;

    color: var(--muted);

    font-size: 11px;
}}

.priority-row {{
    display: flex;

    justify-content:
        space-between;

    align-items: center;

    padding: 14px 0;

    border-bottom:
        1px solid
        var(--border);
}}

.priority-row:last-child {{
    border-bottom: none;
}}

.priority-main {{
    min-width: 0;
}}

.priority-title {{
    font-weight: 650;

    font-size: 14px;
}}

.priority-deadline {{
    color: var(--muted);

    margin-top: 4px;

    font-size: 11px;
}}

.deadline-danger {{
    color: var(--red);
}}

.deadline-warning {{
    color: var(--warning);
}}

.priority-right {{
    text-align: right;

    padding-left: 15px;
}}

.priority-number {{
    font-size: 11px;

    font-weight: 800;

    color: var(--warning);
}}

.small-progress {{
    font-size: 11px;

    color: var(--muted);

    margin-top: 3px;
}}

.analytics-grid {{
    display: grid;

    grid-template-columns:
        repeat(
            3,
            minmax(
                0,
                1fr
            )
        );

    gap: 12px;
}}

.analytics-card {{
    border-radius: 16px;

    background:
        var(--surface-2);

    padding: 18px;

    min-height: 128px;
}}

.analytics-icon {{
    font-size: 17px;

    margin-bottom: 12px;
}}

.analytics-value {{
    font-size: 27px;

    font-weight: 850;

    letter-spacing: -1px;
}}

.analytics-label {{
    color: #c8cfdd;

    font-size: 11px;

    margin-top: 5px;

    font-weight: 650;
}}

.analytics-help {{
    color: var(--muted);

    font-size: 10px;

    margin-top: 6px;

    line-height: 1.4;
}}

.analytics-trend-label {{
    font-size: 9px;

    letter-spacing: 1px;

    font-weight: 800;

    color: var(--muted);

    margin-bottom: 12px;
}}

.analytics-trend {{
    font-size: 26px;

    font-weight: 850;
}}

.trend-positive {{
    color: var(--green);
}}

.trend-negative {{
    color: var(--red);
}}

.trend-neutral {{
    color: var(--muted);
}}

.risk-top {{
    display: flex;

    justify-content:
        space-between;

    align-items: flex-start;
}}

.risk-score {{
    font-size: 50px;

    font-weight: 900;

    letter-spacing: -3px;
}}

.risk-score-caption {{
    color: var(--muted);

    font-size: 11px;
}}

.risk-badge {{
    padding: 7px 10px;

    border-radius: 999px;

    font-size: 11px;

    font-weight: 800;
}}

.risk-low {{
    color: var(--green);

    background:
        rgba(
            65,
            214,
            156,
            .10
        );
}}

.risk-medium {{
    color: var(--warning);

    background:
        rgba(
            255,
            180,
            84,
            .10
        );
}}

.risk-high {{
    color: var(--red);

    background:
        rgba(
            255,
            107,
            120,
            .10
        );
}}

.risk-progress
.progress-fill {{
    background:
        linear-gradient(
            90deg,
            var(--green),
            var(--warning),
            var(--red)
        );
}}

.risk-explanation {{
    color: var(--muted);

    font-size: 10px;

    line-height: 1.5;

    margin-top: 10px;
}}

.risk-signals {{
    margin-top: 18px;
}}

.risk-signal {{
    display: flex;

    align-items:
        flex-start;

    gap: 10px;

    padding: 10px 0;

    border-bottom:
        1px solid
        var(--border);
}}

.risk-signal:last-child {{
    border-bottom: 0;
}}

.risk-signal-dot {{
    width: 7px;
    height: 7px;

    border-radius: 999px;

    margin-top: 5px;

    flex: 0 0 auto;

    background:
        var(--warning);
}}

.risk-signal-content {{
    flex: 1;
}}

.risk-signal-message {{
    color: #c8cfdd;

    font-size: 12px;

    line-height: 1.5;
}}

.risk-signal-points {{
    color: var(--muted);

    font-size: 9px;

    margin-top: 3px;
}}

.risk-good {{
    color: var(--green);

    font-size: 12px;

    line-height: 1.5;

    padding-top: 10px;
}}

.grade-grid {{
    display: grid;

    grid-template-columns:
        repeat(
            4,
            1fr
        );

    gap: 14px;
}}

.grade-card {{
    background:
        var(--surface-2);

    padding: 20px;

    border-radius: 16px;
}}

.grade-big {{
    font-size: 31px;

    font-weight: 850;
}}

.grade-label {{
    color: var(--muted);

    margin-top: 5px;

    font-size: 11px;
}}

.subjects-grid {{
    display: grid;

    grid-template-columns:
        repeat(
            2,
            minmax(
                0,
                1fr
            )
        );

    gap: 14px;
}}

.subject-card {{
    text-decoration: none;

    color: inherit;

    padding: 20px;

    border-radius: 18px;

    background:
        var(--surface-2);

    border:
        1px solid
        transparent;

    transition:
        transform .15s ease,
        border-color .15s ease,
        background .15s ease;
}}

.subject-card:hover {{
    transform:
        translateY(-2px);

    border-color:
        rgba(
            139,
            92,
            246,
            .5
        );

    background:
        var(--surface-3);
}}

.subject-card-top {{
    display: flex;

    justify-content:
        space-between;

    align-items: center;
}}

.subject-name {{
    font-weight: 800;
}}

.subject-arrow {{
    color: var(--muted);
}}

.subject-stats {{
    display: grid;

    grid-template-columns:
        repeat(
            4,
            1fr
        );

    margin-top: 22px;

    gap: 8px;

    color: var(--muted);

    font-size: 10px;
}}

.subject-stats span {{
    display: block;

    color: var(--text);

    font-size: 16px;

    font-weight: 800;

    margin-bottom: 2px;
}}

.subject-next {{
    margin-top: 17px;

    color: var(--muted);

    font-size: 11px;
}}

.achievement {{
    display: flex;

    gap: 12px;

    padding: 13px 0;

    border-bottom:
        1px solid
        var(--border);
}}

.achievement:last-child {{
    border-bottom: 0;
}}

.achievement-icon {{
    width: 31px;
    height: 31px;

    border-radius: 10px;

    display: grid;

    place-items: center;

    background:
        rgba(
            255,
            180,
            84,
            .11
        );

    color: var(--warning);
}}

.achievement-title {{
    font-weight: 700;

    font-size: 13px;
}}

.achievement-description {{
    color: var(--muted);

    font-size: 11px;

    margin-top: 3px;
}}

.empty-state {{
    color: var(--muted);

    padding: 20px 0;

    font-size: 13px;

    line-height: 1.5;
}}

.section-margin {{
    margin-top: 20px;
}}

footer {{
    text-align: center;

    color: #4e586d;

    margin-top: 32px;

    font-size: 11px;
}}

@media (
    max-width: 1100px
) {{
    .analytics-grid {{
        grid-template-columns:
            repeat(
                2,
                1fr
            );
    }}

    .grade-grid {{
        grid-template-columns:
            repeat(
                2,
                1fr
            );
    }}
}}

@media (
    max-width: 950px
) {{
    .metrics {{
        grid-template-columns:
            repeat(
                2,
                1fr
            );
    }}

    .grid {{
        grid-template-columns:
            1fr;
    }}

    .subjects-grid {{
        grid-template-columns:
            1fr;
    }}
}}

@media (
    max-width: 600px
) {{
    .container {{
        width:
            min(
                100% - 24px,
                1380px
            );

        padding-top: 24px;
    }}

    .metrics {{
        grid-template-columns:
            1fr 1fr;
    }}

    .hero-level {{
        font-size: 39px;
    }}

    .hero-top {{
        align-items:
            flex-start;

        flex-direction:
            column;
    }}

    .analytics-grid {{
        grid-template-columns:
            1fr;
    }}

    .grade-grid {{
        grid-template-columns:
            1fr;
    }}

    .subject-stats {{
        grid-template-columns:
            1fr 1fr;
    }}
}}

</style>

</head>

<body>

<div class="container">

<header>

    <div class="brand">

        <div class="logo">
            U
        </div>

        <div>

            <h1>
                UniCore
            </h1>

            <div class="subtitle">
                {escape(title)}
            </div>

            <div class="view-label">
                {escape(view_label)}
            </div>

        </div>

    </div>

    {back_button}

</header>


<section class="hero">

    <div class="hero-top">

        <div>

            <div class="eyebrow">
                PROGRESO ACADÉMICO
            </div>

            <div class="hero-level">
                Nivel {hero["level"]}
            </div>

        </div>

        <div>

            <div class="hero-xp">
                {hero["total_xp"]} XP
            </div>

            <div class="hero-next">
                {hero["xp_until_next_level"]}
                XP para nivel
                {hero["level"] + 1}
            </div>

        </div>

    </div>

    {progress_bar(xp_progress)}

</section>


<div class="metrics">

    <div class="metric-card">

        <div class="metric-icon">
            🔥
        </div>

        <div class="metric-value">
            {hero["current_streak"]}
        </div>

        <div class="metric-label">
            Días de racha
        </div>

    </div>


    <div class="metric-card">

        <div class="metric-icon">
            ⏱
        </div>

        <div class="metric-value">
            {week_hours:.1f}h
        </div>

        <div class="metric-label">
            Estudio · 7 días
        </div>

    </div>


    <div class="metric-card">

        <div class="metric-icon">
            🎯
        </div>

        <div class="metric-value">
            {quiz_text}
        </div>

        <div class="metric-label">
            Media de quizzes
        </div>

    </div>


    <div class="metric-card">

        <div class="metric-icon">
            📌
        </div>

        <div class="metric-value">
            {metrics["pending_task_count"]}
        </div>

        <div class="metric-label">
            Tareas pendientes
        </div>

    </div>


    <div class="metric-card">

        <div class="metric-icon">
            🧠
        </div>

        <div class="metric-value">
            {metrics["due_review_count"]}
        </div>

        <div class="metric-label">
            Repasos pendientes
        </div>

    </div>

</div>


<div class="grid">

    <section class="panel">

        <div class="panel-header">

            <div>

                <div class="eyebrow">
                    OBJETIVOS
                </div>

                <h2>
                    Misiones de hoy
                </h2>

            </div>

        </div>

        {
            render_missions(
                data["missions"]
            )
        }

    </section>


    <section class="panel">

        {
            render_boss(
                data["next_boss"]
            )
        }

    </section>

</div>


<div class="grid">

    <section class="panel">

        <div class="panel-header">

            <div>

                <div class="eyebrow">
                    CONSTANCIA
                </div>

                <h2>
                    Últimos 7 días
                </h2>

            </div>

        </div>

        <div class="activity-chart">

            {
                render_activity_chart(
                    data["daily_activity"]
                )
            }

        </div>

    </section>


    <section class="panel">

        <div class="panel-header">

            <div>

                <div class="eyebrow">
                    AHORA
                </div>

                <h2>
                    Prioridades
                </h2>

            </div>

        </div>

        {
            render_priorities(
                data["priorities"]
            )
        }

    </section>

</div>


<div class="grid grid-equal">

    <section class="panel">

        <div class="panel-header">

            <div>

                <div class="eyebrow">
                    INTELIGENCIA DE ESTUDIO
                </div>

                <h2>
                    Cómo estás progresando
                </h2>

            </div>

        </div>

        {
            render_analytics(
                data.get(
                    "analytics"
                )
            )
        }

    </section>

    {risk_panel}

</div>


{grade_section}


<section
    class="
        panel
        section-margin
    "
>

    <div class="panel-header">

        <div>

            <div class="eyebrow">
                MAPA ACADÉMICO
            </div>

            <h2>
                Asignaturas
            </h2>

        </div>

    </div>

    <div class="subjects-grid">

        {
            render_subjects(
                data["subjects"]
            )
        }

    </div>

</section>


<section
    class="
        panel
        section-margin
    "
>

    <div class="panel-header">

        <div>

            <div class="eyebrow">
                TROFEOS
            </div>

            <h2>
                Logros recientes
            </h2>

        </div>

    </div>

    {
        render_achievements(
            data["achievements"]
        )
    }

</section>


<footer>
    UniCore · datos locales ·
    coste IA del dashboard: 0 €
</footer>

</div>

</body>

</html>
"""


class DashboardHandler(
    BaseHTTPRequestHandler,
):
    """Servidor HTTP del dashboard."""

    def do_GET(self):
        parsed = urlparse(
            self.path
        )

        query = parse_qs(
            parsed.query
        )

        subject_value = query.get(
            "subject_id",
            [None],
        )[0]

        try:
            subject_id = (
                int(subject_value)
                if subject_value
                else None
            )

        except ValueError:
            subject_id = None

        data = build_dashboard_data(
            subject_id=subject_id
        )

        if parsed.path == "/api/dashboard":
            body = json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ).encode(
                "utf-8"
            )

            status_code = (
                200
                if data.get("ok")
                else 400
            )

            self.send_response(
                status_code
            )

            self.send_header(
                "Content-Type",
                (
                    "application/json; "
                    "charset=utf-8"
                ),
            )

            self.send_header(
                "Content-Length",
                str(len(body)),
            )

            self.end_headers()

            self.wfile.write(
                body
            )

            return

        if not data.get("ok"):
            body = (
                "<h1>Error</h1>"
                f"<p>"
                f"{escape(data.get('error'))}"
                f"</p>"
            ).encode(
                "utf-8"
            )

            self.send_response(
                400
            )

        else:
            body = render_page(
                data
            ).encode(
                "utf-8"
            )

            self.send_response(
                200
            )

        self.send_header(
            "Content-Type",
            (
                "text/html; "
                "charset=utf-8"
            ),
        )

        self.send_header(
            "Content-Length",
            str(len(body)),
        )

        self.end_headers()

        self.wfile.write(
            body
        )

    def log_message(
        self,
        format,
        *args,
    ):
        return


def main() -> None:
    """Inicia el dashboard local."""

    server = HTTPServer(
        (
            HOST,
            PORT,
        ),
        DashboardHandler,
    )

    print()
    print(
        "UniCore Dashboard"
    )

    print(
        "================="
    )

    print()

    print(
        f"Abre: http://{HOST}:{PORT}"
    )

    print()

    print(
        "Ctrl + C para detener."
    )

    print()

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        pass

    finally:
        server.server_close()

        print()

        print(
            "Dashboard detenido."
        )


if __name__ == "__main__":
    main()