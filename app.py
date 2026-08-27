"""
ELCIA Monsoon, Roads and Civic Infrastructure Intelligence Dashboard.

The dashboard reads YOLOv8 detection incidents from events.db and turns them
into an operator workspace for detection review, prioritization and closure.
"""

from __future__ import annotations

import html
import sqlite3
from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import time
import cv2
try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None
import database_setup

st.set_page_config(
    page_title="ELCIA | Monsoon operations",
    page_icon=":material/rainy:",
    layout="wide",
    initial_sidebar_state="expanded",
)

refresh_count = 0
if not st.session_state.get("playing_video", False):
    # Auto-refresh the page every 2 seconds to fetch live results
    refresh_count = st_autorefresh(interval=2000, key="data_refresh")


DB_PATH = Path(__file__).parent / "events.db"
Path("tmp").mkdir(exist_ok=True)
Path("thumbnails").mkdir(exist_ok=True)
TABLE = "incidents"

STATUS_OPTIONS = ["Open", "Acknowledged", "Resolved"]
STATUS_META = {
    "Open": {"label": "Open", "class": "open"},
    "Acknowledged": {"label": "Acknowledged", "class": "ack"},
    "Resolved": {"label": "Resolved", "class": "resolved"},
}

CLASS_DISPLAY = {
    "pothole": "Pothole",
    "waterlogged_road": "Waterlogging",
    "drain_overflow": "Drain overflow",
    "damaged_footpath": "Damaged footpath",
}

SEVERITY_META = {
    "Critical": {"class": "critical", "score": 4},
    "High": {"class": "high", "score": 3},
    "Watch": {"class": "watch", "score": 2},
    "Low": {"class": "low", "score": 1},
}

RECOMMENDATIONS = {
    "pothole": "Route to road maintenance crew and flag lane risk.",
    "waterlogged_road": "Dispatch drainage sweep and stage traffic control.",
    "drain_overflow": "Notify drainage response team and inspect overflow path.",
    "damaged_footpath": "Schedule civic inspection and mark pedestrian risk.",
}


CSS = """
<style>
:root {
    --bg: #08110f;
    --panel: rgba(16, 30, 27, 0.86);
    --panel-soft: rgba(20, 42, 37, 0.70);
    --line: rgba(138, 172, 160, 0.22);
    --line-strong: rgba(87, 178, 132, 0.44);
    --text: #f4f7f4;
    --muted: #a8b9b1;
    --green: #38b778;
    --mint: #6ee7b7;
    --cyan: #67e8f9;
    --amber: #f4b740;
    --red: #ef6a5b;
}

.stApp {
    background:
        linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px),
        linear-gradient(0deg, rgba(255,255,255,0.025) 1px, transparent 1px),
        radial-gradient(circle at 18% 12%, rgba(56, 183, 120, 0.16), transparent 32%),
        radial-gradient(circle at 78% 4%, rgba(103, 232, 249, 0.11), transparent 28%),
        #08110f;
    background-size: 42px 42px, 42px 42px, auto, auto, auto;
    color: var(--text);
}

header[data-testid="stHeader"] {
    background: transparent;
}

.block-container {
    max-width: 1480px;
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}

[data-testid="stSidebar"] {
    background: #0c1714;
    border-right: 1px solid var(--line);
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] label {
    color: var(--muted);
}

h1, h2, h3, p {
    letter-spacing: 0;
}

.command-header {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 1.5rem;
    align-items: end;
    padding: 1.35rem 1.45rem;
    border: 1px solid var(--line);
    border-radius: 8px;
    background:
        linear-gradient(135deg, rgba(9, 20, 18, 0.92), rgba(13, 32, 27, 0.84)),
        linear-gradient(90deg, rgba(56, 183, 120, 0.20), transparent 42%);
    box-shadow: 0 20px 70px rgba(0, 0, 0, 0.28);
}

.eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    color: var(--mint);
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
}

.command-header h1 {
    margin: 0.35rem 0 0.35rem;
    font-size: clamp(1.65rem, 3vw, 2.7rem);
    line-height: 1.05;
    color: var(--text);
}

.command-header p {
    margin: 0;
    max-width: 760px;
    color: var(--muted);
    font-size: 0.98rem;
}

.header-status {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    align-items: flex-end;
}

.system-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    width: max-content;
    padding: 0.38rem 0.65rem;
    border: 1px solid rgba(110, 231, 183, 0.40);
    border-radius: 999px;
    color: var(--mint);
    background: rgba(16, 185, 129, 0.10);
    font-size: 0.74rem;
    font-weight: 700;
    text-transform: uppercase;
}

.pulse-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--mint);
    box-shadow: 0 0 0 5px rgba(110, 231, 183, 0.11);
}

.last-event {
    min-width: 190px;
    padding: 0.72rem 0.82rem;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.035);
    text-align: right;
}

.last-event span {
    color: var(--muted);
    display: block;
    font-size: 0.73rem;
}

.last-event strong {
    color: var(--text);
    font-size: 0.93rem;
}

.mission-panel {
    margin-top: 1rem;
    display: grid;
    grid-template-columns: auto minmax(220px, 1.2fr) repeat(3, minmax(170px, 1fr));
    gap: 1rem;
    align-items: center;
    padding: 1rem;
    border: 1px solid var(--line);
    border-left: 5px solid var(--green);
    border-radius: 8px;
    background: rgba(247, 255, 251, 0.05);
}

.track-number {
    display: grid;
    place-items: center;
    width: 58px;
    height: 58px;
    border-radius: 50%;
    color: white;
    background: linear-gradient(135deg, #1c8b5a, #40bf86);
    font-size: 1.35rem;
    font-weight: 800;
}

.mission-title h2 {
    margin: 0 0 0.28rem;
    font-size: 1.18rem;
    color: var(--text);
}

.mission-title p {
    margin: 0;
    color: var(--muted);
    font-size: 0.9rem;
}

.pipeline-step {
    min-height: 88px;
    padding-left: 0.95rem;
    border-left: 1px solid var(--line);
}

.pipeline-step strong {
    color: var(--mint);
    display: block;
    margin-bottom: 0.28rem;
    font-size: 0.82rem;
}

.pipeline-step span {
    color: var(--text);
    font-size: 0.9rem;
    line-height: 1.42;
}

div[data-testid="stMetric"] {
    background: rgba(15, 29, 25, 0.74);
    border-color: var(--line) !important;
}

div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: var(--text);
    font-weight: 750;
}

div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
    color: var(--muted);
}

.section-kicker {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    color: var(--mint);
    font-size: 0.75rem;
    font-weight: 800;
    text-transform: uppercase;
}

.feed-shell {
    position: relative;
    width: 100%;
    max-width: 100%;
    height: 340px;
    overflow: hidden;
    border: 1px solid rgba(103, 232, 249, 0.32);
    border-radius: 8px;
    background:
        linear-gradient(0deg, rgba(3, 7, 6, 0.55), rgba(3, 7, 6, 0.02)),
        repeating-linear-gradient(90deg, rgba(255,255,255,0.06) 0 1px, transparent 1px 95px),
        repeating-linear-gradient(0deg, rgba(255,255,255,0.04) 0 1px, transparent 1px 65px),
        linear-gradient(150deg, #0b1514 0%, #17251f 48%, #34321f 100%);
}

.feed-shell::before {
    content: "";
    position: absolute;
    left: -10%;
    right: -10%;
    bottom: -22%;
    height: 62%;
    transform: skewY(-7deg);
    background:
        repeating-linear-gradient(90deg, rgba(244,183,64,0.42) 0 2px, transparent 2px 118px),
        linear-gradient(180deg, rgba(27,42,35,0.35), rgba(7,12,11,0.82));
    border-top: 1px solid rgba(244,183,64,0.24);
}

.feed-shell::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(to bottom, transparent 50%, rgba(255,255,255,0.035) 50%);
    background-size: 100% 4px;
    opacity: 0.32;
    pointer-events: none;
}

.feed-top,
.feed-bottom {
    position: absolute;
    z-index: 2;
    left: 0.8rem;
    right: 0.8rem;
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: center;
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
}

.feed-top {
    top: 0.78rem;
}

.feed-bottom {
    bottom: 0.78rem;
}

.feed-chip {
    padding: 0.26rem 0.45rem;
    border: 1px solid rgba(255,255,255,0.18);
    border-radius: 4px;
    background: rgba(0,0,0,0.46);
}

.target-box {
    position: absolute;
    z-index: 3;
    border: 2px solid var(--red);
    background: rgba(239, 106, 91, 0.08);
    box-shadow: 0 0 28px rgba(239, 106, 91, 0.16);
}

.target-box span {
    position: absolute;
    top: -1.35rem;
    left: -2px;
    padding: 0.2rem 0.38rem;
    color: white;
    background: var(--red);
    font-size: 0.68rem;
    font-weight: 800;
    white-space: nowrap;
    font-family: 'JetBrains Mono', monospace;
}

.chip {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.28rem 0.52rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 760;
    white-space: nowrap;
}

.chip-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: currentColor;
}

.chip-open {
    color: #ffb3aa;
    background: rgba(239, 106, 91, 0.13);
    border: 1px solid rgba(239, 106, 91, 0.34);
}

.chip-ack {
    color: #ffe2a3;
    background: rgba(244, 183, 64, 0.13);
    border: 1px solid rgba(244, 183, 64, 0.34);
}

.chip-resolved {
    color: #b7f7d4;
    background: rgba(56, 183, 120, 0.13);
    border: 1px solid rgba(56, 183, 120, 0.34);
}

.severity {
    display: inline-flex;
    align-items: center;
    padding: 0.2rem 0.45rem;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 800;
    text-transform: uppercase;
}

.severity-critical {
    color: #fff;
    background: rgba(239, 106, 91, 0.22);
    border: 1px solid rgba(239, 106, 91, 0.46);
}

.severity-high {
    color: #ffe2a3;
    background: rgba(244, 183, 64, 0.16);
    border: 1px solid rgba(244, 183, 64, 0.36);
}

.severity-watch {
    color: #b6f6ff;
    background: rgba(103, 232, 249, 0.12);
    border: 1px solid rgba(103, 232, 249, 0.32);
}

.severity-low {
    color: #b7f7d4;
    background: rgba(56, 183, 120, 0.12);
    border: 1px solid rgba(56, 183, 120, 0.30);
}

.queue-card {
    margin: 0 0 0.72rem;
    padding: 0.82rem;
    border: 1px solid var(--line);
    border-left: 4px solid var(--green);
    border-radius: 8px;
    background: rgba(255,255,255,0.035);
}

.queue-card-critical {
    border-left-color: var(--red);
}

.queue-card-high {
    border-left-color: var(--amber);
}

.queue-card-watch {
    border-left-color: var(--cyan);
}

.queue-top {
    display: flex;
    justify-content: space-between;
    gap: 0.7rem;
    align-items: start;
}

.queue-card h4 {
    margin: 0 0 0.28rem;
    color: var(--text);
    font-size: 0.94rem;
}

.queue-card p {
    margin: 0;
    color: var(--muted);
    font-size: 0.8rem;
}

.queue-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-top: 0.7rem;
}

.meta-item {
    color: var(--muted);
    font-size: 0.72rem;
    font-family: 'JetBrains Mono', monospace;
}

.detail-line {
    display: grid;
    grid-template-columns: 92px minmax(0, 1fr);
    gap: 0.75rem;
    padding: 0.72rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.07);
}

.detail-line:last-child {
    border-bottom: 0;
}

.detail-line span {
    color: var(--muted);
    font-size: 0.78rem;
}

.detail-line strong {
    color: var(--text);
    font-size: 0.86rem;
}

@media (max-width: 980px) {
    .command-header,
    .mission-panel {
        grid-template-columns: 1fr;
    }

    .header-status {
        align-items: flex-start;
    }

    .last-event {
        text-align: left;
    }

    .pipeline-step {
        border-left: 0;
        padding-left: 0;
        padding-top: 0.8rem;
        border-top: 1px solid var(--line);
    }

    .feed-shell {
        height: 270px;
    }
}
</style>
"""


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def severity_label(score: float) -> str:
    if score >= 0.80:
        return "Critical"
    if score >= 0.60:
        return "High"
    if score >= 0.30:
        return "Watch"
    return "Low"


def percent(value: float) -> str:
    return f"{value * 100:.0f}%"


def format_timestamp(value: object, *, include_date: bool = True) -> str:
    if pd.isna(value):
        return "Unknown"
    ts = pd.Timestamp(value)
    return ts.strftime("%d %b, %H:%M") if include_date else ts.strftime("%H:%M")


def format_age(value: object) -> str:
    if pd.isna(value):
        return "Unknown age"
    delta = pd.Timestamp.now() - pd.Timestamp(value)
    minutes = max(int(delta.total_seconds() // 60), 0)
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h {minutes % 60}m ago"
    return f"{hours // 24}d {hours % 24}h ago"


def connect() -> sqlite3.Connection:
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


@st.cache_data(ttl=15, show_spinner=False)
def load_incidents() -> pd.DataFrame:
    if not DB_PATH.exists():
        with connect() as conn:
            database_setup.create_table(conn)

    with connect() as conn:
        df = pd.read_sql_query(
            f"SELECT * FROM {TABLE} ORDER BY timestamp DESC",
            conn,
        )

    if df.empty:
        for col in ["hazard_label", "severity_label", "severity_rank", "age"]:
            df[col] = pd.Series(dtype='object')
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["confidence_score"] = pd.to_numeric(df["confidence_score"], errors="coerce").fillna(0)
    df["severity_score"] = pd.to_numeric(df["severity_score"], errors="coerce").fillna(0)
    df["zone"] = df["zone"].fillna("Unknown zone")
    df["hazard_class"] = df["hazard_class"].fillna("unknown")
    df["status"] = df["status"].where(df["status"].isin(STATUS_OPTIONS), "Open")
    df["hazard_label"] = df["hazard_class"].map(CLASS_DISPLAY).fillna(df["hazard_class"])
    df["severity_label"] = df["severity_score"].apply(severity_label)
    df["severity_rank"] = df["severity_label"].map(
        {name: meta["score"] for name, meta in SEVERITY_META.items()}
    )
    df["age"] = df["timestamp"].apply(format_age)
    return df.sort_values(["timestamp", "severity_score"], ascending=[False, False])


def update_incident_status(incident_id: int, new_status: str) -> int:
    if new_status not in STATUS_OPTIONS:
        raise ValueError(f"Unsupported status: {new_status}")

    with connect() as conn:
        cur = conn.execute(
            f"UPDATE {TABLE} SET status = ? WHERE id = ?",
            (new_status, incident_id),
        )
        conn.commit()
        return int(cur.rowcount)


def recommendation_for(row: pd.Series) -> str:
    return RECOMMENDATIONS.get(
        str(row.get("hazard_class", "")),
        "Assign field inspection and attach evidence before closure.",
    )


def status_chip(status: str) -> str:
    meta = STATUS_META.get(status, STATUS_META["Open"])
    return (
        f'<span class="chip chip-{meta["class"]}">'
        '<span class="chip-dot"></span>'
        f"{esc(meta['label'])}</span>"
    )


def severity_badge(label: str) -> str:
    meta = SEVERITY_META.get(label, SEVERITY_META["Low"])
    return f'<span class="severity severity-{meta["class"]}">{esc(label)}</span>'


def render_header(df: pd.DataFrame) -> None:
    latest = format_timestamp(df["timestamp"].max()) if not df.empty else "No events"
    st.html(
        f"""
        <section class="command-header">
            <div>
                <div class="eyebrow">
                    ELCIA civic operations
                </div>
                <h1>Monsoon operations center</h1>
            </div>
            <div class="header-status">
                <div class="system-pill"><span class="pulse-dot"></span> System online</div>
                <div class="last-event">
                    <span>Last detection</span>
                    <strong>{esc(latest)}</strong>
                </div>
            </div>
        </section>
        """
    )


# Removed mission panel


def render_live_frame(row: pd.Series) -> str:
    incident_id = int(row["id"])
    target_left = 18 + (incident_id * 11) % 44
    target_top = 26 + (incident_id * 7) % 20
    target_width = 25 + (incident_id * 3) % 13
    target_height = 22 + (incident_id * 5) % 14
    hazard = str(row["hazard_label"]).upper()

    return f"""
    <div class="feed-shell">
        <div class="feed-top">
            <span class="feed-chip">LIVE / YOLOv8</span>
            <span class="feed-chip">{esc(format_timestamp(row["timestamp"], include_date=False))}</span>
        </div>
        <div
            class="target-box"
            style="left:{target_left}%; top:{target_top}%; width:{target_width}%; height:{target_height}%;"
        >
            <span>{esc(hazard)} : {esc(percent(float(row["confidence_score"])))}</span>
        </div>
        <div class="feed-bottom">
            <span class="feed-chip">{esc(row["zone"])}</span>
            <span class="feed-chip">Severity {esc(percent(float(row["severity_score"])))}</span>
        </div>
    </div>
    """


def render_queue_card(row: pd.Series) -> str:
    severity = str(row["severity_label"])
    severity_class = SEVERITY_META.get(severity, SEVERITY_META["Low"])["class"]
    return f"""
    <div class="queue-card queue-card-{severity_class}">
        <div class="queue-top">
            <div>
                <h4>#{int(row["id"])} {esc(row["hazard_label"])}</h4>
                <p>{esc(row["zone"])} / {esc(row["age"])}</p>
            </div>
            {severity_badge(severity)}
        </div>
        <div class="queue-meta">
            <span class="meta-item">conf {esc(percent(float(row["confidence_score"])))}</span>
            <span class="meta-item">sev {esc(percent(float(row["severity_score"])))}</span>
            <span class="meta-item">{status_chip(str(row["status"]))}</span>
        </div>
    </div>
    """


def render_detail_line(label: str, value: object) -> None:
    st.html(
        f"""
        <div class="detail-line">
            <span>{esc(label)}</span>
            <strong>{esc(value)}</strong>
        </div>
        """
    )


def filtered_incidents(
    df: pd.DataFrame,
    zones: list[str],
    classes: list[str],
    statuses: list[str],
    severity_range: tuple[float, float],
) -> pd.DataFrame:
    selected_zones = zones or sorted(df["zone"].unique().tolist())
    selected_classes = classes or sorted(df["hazard_class"].unique().tolist())
    selected_statuses = statuses or STATUS_OPTIONS
    lo, hi = severity_range

    return df[
        df["zone"].isin(selected_zones)
        & df["hazard_class"].isin(selected_classes)
        & df["status"].isin(selected_statuses)
        & df["severity_score"].between(lo, hi)
    ].copy()


st.markdown(CSS, unsafe_allow_html=True)

try:
    df_all = load_incidents()
except (sqlite3.Error, pd.errors.DatabaseError) as exc:
    st.error("Unable to read the incidents table from events.db.")
    st.caption(f"Database error: {exc}")
    st.stop()

# Dashboard will natively render zero-state UI if empty

if "status_flash" in st.session_state:
    st.toast(st.session_state.pop("status_flash"), icon=":material/check_circle:")


zone_options = sorted(df_all["zone"].unique().tolist())
class_options = sorted(df_all["hazard_class"].unique().tolist())

with st.sidebar:
    st.caption("Detection stack")
    st.title("Command filters")

    if st.button("Reset filters", icon=":material/filter_alt_off:", width="stretch"):
        for key in ("zone_filter", "class_filter", "status_filter", "severity_filter", "sort_mode"):
            st.session_state.pop(key, None)
        st.rerun()

    zone_filter = st.multiselect(
        "Zones",
        zone_options,
        default=zone_options,
        key="zone_filter",
    )
    class_filter = st.pills(
        "Hazards",
        class_options,
        default=class_options,
        selection_mode="multi",
        format_func=lambda item: CLASS_DISPLAY.get(str(item), str(item)),
        key="class_filter",
        width="stretch",
    )
    status_filter = st.pills(
        "Status",
        STATUS_OPTIONS,
        default=STATUS_OPTIONS,
        selection_mode="multi",
        key="status_filter",
        width="stretch",
    )
    severity_filter = st.slider(
        "Severity score",
        min_value=0.0,
        max_value=1.0,
        value=(0.0, 1.0),
        step=0.05,
        key="severity_filter",
    )
    sort_mode = st.selectbox(
        "Queue order",
        ["Severity first", "Newest first", "Confidence first"],
        key="sort_mode",
    )
    st.divider()
    st.caption(f"SQLite source: `{DB_PATH.name}`")


filtered = filtered_incidents(
    df_all,
    list(zone_filter or []),
    list(class_filter or []),
    list(status_filter or []),
    severity_filter,
)

with st.sidebar:
    st.metric(
        "Visible incidents",
        len(filtered),
        f"of {len(df_all)} total",
        delta_color="off",
        delta_arrow="off",
    )


render_header(df_all)

st.write("")

open_count = int((filtered["status"] == "Open").sum()) if not filtered.empty else 0
ack_count = int((filtered["status"] == "Acknowledged").sum()) if not filtered.empty else 0
critical_count = int((filtered["severity_label"] == "Critical").sum()) if not filtered.empty else 0
field_queue_count = int((filtered["status"] != "Resolved").sum()) if not filtered.empty else 0
resolution_rate = (
    int((filtered["status"] == "Resolved").sum()) / len(filtered)
    if len(filtered) > 0
    else 0
)
avg_confidence = float(filtered["confidence_score"].mean()) if len(filtered) else 0.0

kpi_cols = st.columns(4, gap="medium", vertical_alignment="center")
kpi_cols[0].metric(
    "Open incidents",
    open_count,
    f"{ack_count} acknowledged",
    delta_color="off",
    delta_arrow="off",
    icon=":material/report:",
    border=True,
)
kpi_cols[1].metric(
    "Critical now",
    critical_count,
    "severity >= 80%",
    delta_color="off",
    delta_arrow="off",
    icon=":material/priority_high:",
    border=True,
)
kpi_cols[2].metric(
    "Field queue",
    field_queue_count,
    "not resolved",
    delta_color="off",
    delta_arrow="off",
    icon=":material/engineering:",
    border=True,
)
kpi_cols[3].metric(
    "Resolution rate",
    percent(resolution_rate),
    f"avg confidence {percent(avg_confidence)}",
    delta_color="off",
    delta_arrow="off",
    icon=":material/task_alt:",
    border=True,
)

st.write("")

if sort_mode == "Newest first":
    queue_df = filtered.sort_values(["timestamp", "severity_score"], ascending=[False, False])
elif sort_mode == "Confidence first":
    queue_df = filtered.sort_values(["confidence_score", "severity_score"], ascending=[False, False])
else:
    queue_df = filtered.sort_values(
        ["severity_score", "confidence_score", "timestamp"],
        ascending=[False, False, False],
    )

priority_candidates = queue_df[queue_df["status"] != "Resolved"]
priority = (
    priority_candidates.iloc[0]
    if not priority_candidates.empty
    else queue_df.iloc[0]
    if not queue_df.empty
    else None
)

main_left, main_right = st.columns([1.55, 1], gap="medium")

with main_left:
    with st.container(border=True):
        st.markdown(
            '<span class="section-kicker">Priority evidence</span>',
            unsafe_allow_html=True,
        )
        priority_candidates = queue_df[queue_df["status"] != "Resolved"]
        total_in_queue = len(priority_candidates) if not priority_candidates.empty else len(queue_df)
        
        selected_id = st.session_state.get("selected_incident_id", None)
        priority = None
        
        if selected_id is not None:
            match = queue_df[queue_df["id"] == selected_id]
            if not match.empty:
                priority = match.iloc[0]
            else:
                st.session_state["selected_incident_id"] = None
                
        if priority is None and total_in_queue > 0:
            # Cycle every 6 seconds (3 refreshes of 2s each)
            auto_index = (refresh_count // 3) % total_in_queue
            manual_offset = st.session_state.get("manual_offset", 0)
            
            # Start from the end (oldest) and go towards 0 (newest) so it plays chronologically forward in time like a video
            current_index = (total_in_queue - 1 - (auto_index + manual_offset)) % total_in_queue
            
            priority = (
                priority_candidates.iloc[current_index]
                if not priority_candidates.empty
                else queue_df.iloc[current_index]
            )

        if priority is None:
            st.info("No incidents match the active filters.")
        else:
            evidence_col, detail_col = st.columns([1.35, 1], gap="medium")
            with evidence_col:
                if "thumbnail_path" in priority and pd.notna(priority["thumbnail_path"]) and priority["thumbnail_path"] and Path(priority["thumbnail_path"]).exists():
                    st.image(priority["thumbnail_path"], use_container_width=True)
                else:
                    st.html(render_live_frame(priority))
            with detail_col:
                st.subheader(f"Incident #{int(priority['id'])}")
                if selected_id is not None:
                    st.caption("Viewing selected incident from queue")
                    if st.button("⬅️ Resume Live Auto-Cycle", use_container_width=True):
                        st.session_state["selected_incident_id"] = None
                        st.rerun()
                else:
                    st.caption(f"Showing **#{current_index + 1}** of **{total_in_queue}** active incidents in the queue")
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button("⏮️ Previous", use_container_width=True):
                            st.session_state["manual_offset"] = st.session_state.get("manual_offset", 0) - 1
                            st.rerun()
                    with btn_col2:
                        if st.button("Next ⏭️", use_container_width=True):
                            st.session_state["manual_offset"] = st.session_state.get("manual_offset", 0) + 1
                            st.rerun()
                st.progress(
                    float(priority["severity_score"]),
                    text=f"Severity {percent(float(priority['severity_score']))}",
                )
                st.progress(
                    float(priority["confidence_score"]),
                    text=f"Model confidence {percent(float(priority['confidence_score']))}",
                )
                render_detail_line("Hazard", priority["hazard_label"])
                render_detail_line("Zone", priority["zone"])
                render_detail_line("Detected", format_timestamp(priority["timestamp"]))
                render_detail_line("Status", priority["status"])
                st.info(recommendation_for(priority), icon=":material/assignment:")

with main_right:
    with st.container(border=True, height=680):
        st.markdown(
            '<span class="section-kicker">Response queue</span>',
            unsafe_allow_html=True,
        )
        st.caption("Open and acknowledged incidents ordered by the active queue mode.")
        response_queue = queue_df[queue_df["status"] != "Resolved"].head(15)
        if response_queue.empty:
            st.success("No active response items in the current filter.", icon=":material/check_circle:")
        else:
            for _, incident in response_queue.iterrows():
                st.html(render_queue_card(incident))
                if st.button("🔍 View in Priority Panel", key=f"report_btn_{int(incident['id'])}", use_container_width=True):
                    st.session_state["selected_incident_id"] = incident["id"]
                    st.rerun()

st.write("")

analytics_left, analytics_right = st.columns([1.1, 1], gap="medium")

with analytics_left:
    with st.container(border=True):
        st.markdown(
            '<span class="section-kicker">Hazard load</span>',
            unsafe_allow_html=True,
        )
        if filtered.empty:
            st.info("No hazard data to chart for the active filters.")
        else:
            hazard_counts = (
                filtered.groupby("hazard_label", as_index=False)
                .size()
                .rename(columns={"size": "incidents"})
                .sort_values("incidents", ascending=False)
            )
            hazard_chart = (
                alt.Chart(hazard_counts)
                .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
                .encode(
                    x=alt.X("incidents:Q", title=None, axis=alt.Axis(grid=False, tickMinStep=1)),
                    y=alt.Y("hazard_label:N", title=None, sort="-x"),
                    color=alt.Color(
                        "hazard_label:N",
                        scale=alt.Scale(range=["#38b778", "#67e8f9", "#f4b740", "#ef6a5b"]),
                        legend=None,
                    ),
                    tooltip=[
                        alt.Tooltip("hazard_label:N", title="Hazard"),
                        alt.Tooltip("incidents:Q", title="Incidents"),
                    ],
                )
                .properties(height=230)
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(hazard_chart, width="stretch")

with analytics_right:
    with st.container(border=True):
        st.markdown(
            '<span class="section-kicker">Closure state</span>',
            unsafe_allow_html=True,
        )
        if filtered.empty:
            st.info("No status data to chart for the active filters.")
        else:
            status_counts = (
                filtered.groupby("status", as_index=False)
                .size()
                .rename(columns={"size": "incidents"})
            )
            status_chart = (
                alt.Chart(status_counts)
                .mark_arc(innerRadius=46, outerRadius=80, cornerRadius=3)
                .encode(
                    theta=alt.Theta("incidents:Q"),
                    color=alt.Color(
                        "status:N",
                        scale=alt.Scale(
                            domain=STATUS_OPTIONS,
                            range=["#ef6a5b", "#f4b740", "#38b778"],
                        ),
                        legend=alt.Legend(title=None, orient="bottom"),
                    ),
                    tooltip=[
                        alt.Tooltip("status:N", title="Status"),
                        alt.Tooltip("incidents:Q", title="Incidents"),
                    ],
                )
                .properties(height=230)
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(status_chart, width="stretch")

st.write("")

queue_tab, analytics_tab, video_tab = st.tabs(["Incident queue", "Operations analytics", "Live CCTV Feed"])

with queue_tab:
    table_col, action_col = st.columns([1.65, 0.95], gap="medium")

    with table_col:
        with st.container(border=True):
            st.subheader("Incident log")
            st.caption("Sortable, filter-aware incident evidence from SQLite.")

            table_df = queue_df[
                [
                    "id",
                    "timestamp",
                    "zone",
                    "hazard_label",
                    "confidence_score",
                    "severity_score",
                    "severity_label",
                    "status",
                ]
            ].rename(
                columns={
                    "id": "ID",
                    "timestamp": "Timestamp",
                    "zone": "Zone",
                    "hazard_label": "Hazard",
                    "confidence_score": "Confidence",
                    "severity_score": "Severity",
                    "severity_label": "Priority",
                    "status": "Status",
                }
            )

            st.dataframe(
                table_df,
                hide_index=True,
                height=360,
                width="stretch",
                column_config={
                    "ID": st.column_config.NumberColumn("ID", format="#%d"),
                    "Timestamp": st.column_config.DatetimeColumn("Timestamp", format="DD MMM, HH:mm"),
                    "Confidence": st.column_config.ProgressColumn(
                        "Confidence",
                        min_value=0,
                        max_value=1,
                    ),
                    "Severity": st.column_config.ProgressColumn(
                        "Severity",
                        min_value=0,
                        max_value=1,
                    ),
                },
            )

            export_csv = table_df.to_csv(index=False).encode("utf-8")
            export_json = table_df.to_json(
                orient="records",
                date_format="iso",
                indent=2,
            ).encode("utf-8")

            dl1, dl2 = st.columns(2)
            dl1.download_button(
                "Download CSV",
                export_csv,
                file_name=f"elcia_incidents_{datetime.now():%Y%m%d_%H%M}.csv",
                mime="text/csv",
                icon=":material/download:",
                width="stretch",
            )
            dl2.download_button(
                "Download JSON",
                export_json,
                file_name=f"elcia_incidents_{datetime.now():%Y%m%d_%H%M}.json",
                mime="application/json",
                icon=":material/data_object:",
                width="stretch",
            )

    with action_col:
        with st.container(border=True):
            st.subheader("Action tracker")
            st.caption("Update the operational status for one incident.")

            action_candidates = queue_df if not queue_df.empty else df_all
            action_index = action_candidates.set_index("id", drop=False)

            if action_candidates.empty:
                st.info("No incidents available to update.")
            else:
                def format_incident_option(incident_id: int) -> str:
                    row = action_index.loc[incident_id]
                    return f"#{int(row['id'])} / {row['zone']} / {row['hazard_label']}"

                selected_id = st.selectbox(
                    "Incident",
                    action_candidates["id"].astype(int).tolist(),
                    format_func=format_incident_option,
                    key="action_incident",
                )
                selected_row = action_index.loc[int(selected_id)]

                render_detail_line("Current status", selected_row["status"])
                render_detail_line("Recommended action", recommendation_for(selected_row))

                with st.form("status_update_form"):
                    new_status = st.selectbox(
                        "New status",
                        STATUS_OPTIONS,
                        index=STATUS_OPTIONS.index(str(selected_row["status"])),
                    )
                    submitted = st.form_submit_button(
                        "Update status",
                        type="primary",
                        icon=":material/done_all:",
                        width="stretch",
                    )

                if submitted:
                    if new_status == selected_row["status"]:
                        st.session_state["status_flash"] = (
                            f"Incident #{int(selected_id)} is already {new_status}."
                        )
                    else:
                        changed = update_incident_status(int(selected_id), new_status)
                        load_incidents.clear()
                        st.session_state["status_flash"] = (
                            f"Incident #{int(selected_id)} updated to {new_status}."
                            if changed
                            else f"Incident #{int(selected_id)} was not found."
                        )
                    st.rerun()

with analytics_tab:
    timeline_col, severity_col = st.columns([1.35, 1], gap="medium")

    with timeline_col:
        with st.container(border=True):
            st.subheader("Detection timeline")
            if filtered.empty:
                st.info("No detections match the active filters.")
            else:
                timeline_df = filtered.copy()
                timeline_df["hour"] = timeline_df["timestamp"].dt.floor("h")
                timeline_counts = (
                    timeline_df.groupby(["hour", "hazard_label"], as_index=False)
                    .size()
                    .rename(columns={"size": "incidents"})
                )
                timeline_chart = (
                    alt.Chart(timeline_counts)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("hour:T", title=None),
                        y=alt.Y("incidents:Q", title="Incidents", axis=alt.Axis(tickMinStep=1)),
                        color=alt.Color(
                            "hazard_label:N",
                            scale=alt.Scale(range=["#38b778", "#67e8f9", "#f4b740", "#ef6a5b"]),
                            legend=alt.Legend(title=None, orient="bottom"),
                        ),
                        tooltip=[
                            alt.Tooltip("hour:T", title="Time", format="%d %b, %H:%M"),
                            alt.Tooltip("hazard_label:N", title="Hazard"),
                            alt.Tooltip("incidents:Q", title="Incidents"),
                        ],
                    )
                    .properties(height=300)
                    .configure_view(strokeWidth=0)
                )
                st.altair_chart(timeline_chart, width="stretch")

    with severity_col:
        with st.container(border=True):
            st.subheader("Severity profile")
            if filtered.empty:
                st.info("No severity data to summarize.")
            else:
                severity_profile = (
                    filtered.groupby("severity_label", as_index=False)
                    .agg(
                        incidents=("id", "count"),
                        avg_confidence=("confidence_score", "mean"),
                        avg_severity=("severity_score", "mean"),
                    )
                    .sort_values(
                        "severity_label",
                        key=lambda col: col.map({"Critical": 0, "High": 1, "Watch": 2, "Low": 3}),
                    )
                )
                severity_profile["Avg confidence"] = severity_profile["avg_confidence"].map(percent)
                severity_profile["Avg severity"] = severity_profile["avg_severity"].map(percent)

                st.dataframe(
                    severity_profile[
                        ["severity_label", "incidents", "Avg confidence", "Avg severity"]
                    ].rename(
                        columns={
                            "severity_label": "Priority",
                            "incidents": "Incidents",
                        }
                    ),
                    hide_index=True,
                    height=300,
                    width="stretch",
                )

with video_tab:
    st.subheader("Live CCTV Feed")
    st.caption("Stream a video file directly into the dashboard with live YOLOv8 inference.")
    
    video_col1, video_col2 = st.columns(2)
    with video_col1:
        uploaded_video = st.file_uploader("Upload Footage (MP4/AVI)", type=["mp4", "avi", "mov", "mkv"])
        if uploaded_video is not None:
            video_source = f"tmp/{uploaded_video.name}"
            with open(video_source, "wb") as f:
                f.write(uploaded_video.getbuffer())
        else:
            video_source = st.text_input("Or enter local file path", value="test_video11.mp4")
            
    with video_col2:
        model_path = st.text_input("YOLOv8 Model Path", value="best.pt")
    
    start_btn, stop_btn, view_btn = st.columns(3)
    start_stream = start_btn.button("Start Stream", type="primary", use_container_width=True)
    stop_stream = stop_btn.button("Stop Stream", use_container_width=True)
    view_dashboard = view_btn.button("View Dashboard 📊", use_container_width=True)
    
    if view_dashboard:
        st.session_state["playing_video"] = False
        st.components.v1.html(
            """
            <script>
            const tabs = window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
            if(tabs.length > 0) {
                tabs[0].click();
            }
            </script>
            """,
            height=0
        )
    
    if start_stream:
        st.session_state["playing_video"] = True
        st.rerun()
    if stop_stream:
        st.session_state["playing_video"] = False
        st.rerun()
        
    if st.session_state.get("playing_video", False):
        if YOLO is None:
            st.error("ultralytics library is not installed.")
        else:
            try:
                model = YOLO(model_path)
                cap = cv2.VideoCapture(video_source)
                if not cap.isOpened():
                    st.error(f"Could not open video source: {video_source}")
                else:
                    st.success(f"Streaming from {video_source}...")
                    frame_window = st.empty()
                    
                    CLASS_MAP = {0: "pothole", 1: "waterlogged_road", 2: "drain_overflow", 3: "damaged_footpath"}
                    conn = database_setup.get_connection()
                    
                    while cap.isOpened() and st.session_state.get("playing_video", False):
                        success, frame = cap.read()
                        if not success:
                            st.info("Video stream ended.")
                            st.session_state["playing_video"] = False
                            break
                            
                        # Run inference
                        results = model(frame, verbose=False)
                        result = results[0]
                        annotated_frame = result.plot()
                        
                        # Convert BGR to RGB for Streamlit
                        rgb_frame = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
                        frame_window.image(rgb_frame, channels="RGB", use_container_width=True)
                        
                        # Log to database (optional throttling can be added here)
                        for box in result.boxes:
                            confidence = box.conf[0].item()
                            if confidence > 0.5:
                                class_id = int(box.cls[0].item())
                                hazard_class = CLASS_MAP.get(class_id, "unknown")
                                severity = min(confidence * 1.2, 1.0)
                                
                                ts = datetime.now().isoformat(timespec="seconds")
                                thumb_path = f"tmp/frame_{ts.replace(':', '')}.jpg"
                                cv2.imwrite(thumb_path, annotated_frame)
                                
                                database_setup.insert_incident(
                                    conn=conn,
                                    timestamp=ts,
                                    zone="CCTV Stream",
                                    hazard_class=hazard_class,
                                    confidence_score=confidence,
                                    severity_score=severity,
                                    thumbnail_path=thumb_path,
                                    status="Open"
                                )
                                
                        time.sleep(0.03) # roughly 30fps
            except Exception as e:
                st.error(f"Error during video stream: {e}")
