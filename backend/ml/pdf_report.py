"""Build patient-specific, paginated PDF assessment reports."""
from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from math import ceil, isfinite
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


INK = colors.HexColor("#243b3a")
TEAL = colors.HexColor("#17665e")
MUTED = colors.HexColor("#5c6e70")
GRID = colors.HexColor("#d8e1df")
PALE = colors.HexColor("#f1f6f5")
LOW = colors.HexColor("#7bb49b")
MODERATE = colors.HexColor("#e3bd67")
HIGH = colors.HexColor("#cf827a")
DISCLAIMER = (
    "This report contains an AI-generated risk assessment based on the clinical data provided to the "
    "SepsiGuard system. It is intended for educational and research purposes and is not a substitute "
    "for professional medical evaluation, diagnosis, or treatment."
)

CLINICAL_FIELDS = (
    ("heart_rate", "Heart Rate", "bpm"),
    ("respiratory_rate", "Respiratory Rate", "breaths/min"),
    ("temperature", "Temperature", "°C"),
    ("systolic_bp", "Systolic Blood Pressure", "mmHg"),
    ("diastolic_bp", "Diastolic Blood Pressure", "mmHg"),
    ("oxygen_saturation", "Oxygen Saturation (SpO2)", "%"),
    ("wbc", "WBC", "×10³/µL"),
    ("lactate", "Lactate", "mmol/L"),
    ("creatinine", "Creatinine", "mg/dL"),
    ("platelets", "Platelets", "×10³/µL"),
    ("bilirubin", "Bilirubin", "mg/dL"),
    ("age", "Age", "years"),
)

TREND_SPECS = (
    ("heart_rate", "Heart Rate Trend", "Heart Rate (bpm)"),
    ("respiratory_rate", "Respiratory Rate Trend", "Respiratory Rate (breaths/min)"),
    ("temperature", "Temperature Trend", "Temperature (°C)"),
    ("blood_pressure", "Blood Pressure Trend", "Blood Pressure (mmHg)"),
    ("oxygen_saturation", "Oxygen Saturation Trend", "SpO2 (%)"),
    ("wbc", "WBC Trend", "WBC (×10³/µL)"),
    ("lactate", "Lactate Trend", "Lactate (mmol/L)"),
    ("creatinine", "Creatinine Trend", "Creatinine (mg/dL)"),
    ("platelets", "Platelet Trend", "Platelets (×10³/µL)"),
    ("bilirubin", "Bilirubin Trend", "Bilirubin (mg/dL)"),
)


def _register_fonts() -> tuple[str, str]:
    """Use an embedded Unicode font for units and symbols, with safe fallbacks."""
    regular_name, bold_name = "SepsiGuardSans", "SepsiGuardSans-Bold"
    registered = set(pdfmetrics.getRegisteredFontNames())
    if regular_name in registered and bold_name in registered:
        return regular_name, bold_name

    package_fonts = Path(reportlab.__file__).parent / "fonts"
    candidates = (
        (package_fonts / "Vera.ttf", package_fonts / "VeraBd.ttf"),
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
    )
    for regular_path, bold_path in candidates:
        if regular_path.is_file() and bold_path.is_file():
            pdfmetrics.registerFont(TTFont(regular_name, str(regular_path)))
            pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
            return regular_name, bold_name
    return "Helvetica", "Helvetica-Bold"


def _styles(font_regular: str, font_bold: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ReportTitle", parent=base["Title"], fontName=font_bold, fontSize=20, leading=24, textColor=INK, alignment=TA_LEFT, spaceAfter=2),
        "subtitle": ParagraphStyle("ReportSubtitle", parent=base["Normal"], fontName=font_regular, fontSize=9, leading=12, textColor=MUTED, spaceAfter=12),
        "section": ParagraphStyle("ReportSection", parent=base["Heading2"], fontName=font_bold, fontSize=11.5, leading=14, textColor=TEAL, spaceBefore=9, spaceAfter=6, keepWithNext=True),
        "body": ParagraphStyle("ReportBody", parent=base["BodyText"], fontName=font_regular, fontSize=8.5, leading=11.2, textColor=INK, spaceAfter=4),
        "summary": ParagraphStyle("ReportSummary", parent=base["BodyText"], fontName=font_regular, fontSize=8.5, leading=21, textColor=INK),
        "small": ParagraphStyle("ReportSmall", parent=base["BodyText"], fontName=font_regular, fontSize=7.2, leading=9, textColor=MUTED),
        "table_label": ParagraphStyle("ReportTableLabel", parent=base["Normal"], fontName=font_bold, fontSize=7.5, leading=9, textColor=INK),
        "table_header": ParagraphStyle("ReportTableHeader", parent=base["Normal"], fontName=font_bold, fontSize=7.2, leading=8.4, textColor=colors.white),
        "series_header": ParagraphStyle("SeriesTableHeader", parent=base["Normal"], fontName=font_bold, fontSize=5.7, leading=6.5, textColor=colors.white, alignment=TA_CENTER),
        "series_cell": ParagraphStyle("SeriesTableCell", parent=base["Normal"], fontName=font_regular, fontSize=6.5, leading=7.5, textColor=INK, alignment=TA_CENTER),
        "disclaimer": ParagraphStyle("ReportDisclaimer", parent=base["BodyText"], fontName=font_regular, fontSize=8, leading=10.5, textColor=INK, backColor=PALE, borderColor=GRID, borderWidth=0.5, borderPadding=8, spaceBefore=5),
    }


def _para(text: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(text)), style)


def _number(value: object, digits: int = 2) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "Not Available"
    if not isfinite(numeric):
        return "Not Available"
    if digits == 0:
        return str(int(numeric))
    return f"{numeric:.{digits}f}".rstrip("0").rstrip(".")


def _ordered_observations(observations: list[dict]) -> list[dict]:
    rows = [dict(item) for item in observations if isinstance(item, dict)]
    return sorted(rows, key=lambda row: int(row.get("time_step", 0) or 0))


def _table_style(header: bool = True) -> TableStyle:
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, PALE]),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), TEAL),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ])
    return TableStyle(commands)


class RiskScale(Flowable):
    def __init__(self, score: float, low_threshold: float, high_threshold: float, font_regular: str, font_bold: str):
        super().__init__()
        self.score = max(0.0, min(1.0, score))
        self.low_threshold = max(0.0, min(1.0, low_threshold))
        self.high_threshold = max(self.low_threshold, min(1.0, high_threshold))
        self.font_regular = font_regular
        self.font_bold = font_bold
        self.height = 52

    def wrap(self, avail_width: float, _avail_height: float) -> tuple[float, float]:
        self.width = avail_width
        return self.width, self.height

    def draw(self) -> None:
        canvas = self.canv
        x, y, width = 0, 22, self.width
        split_low = self.low_threshold * width
        split_high = self.high_threshold * width
        canvas.setFillColor(LOW)
        canvas.roundRect(x, y, split_low, 11, 4, fill=1, stroke=0)
        canvas.setFillColor(MODERATE)
        canvas.rect(split_low, y, max(0, split_high - split_low), 11, fill=1, stroke=0)
        canvas.setFillColor(HIGH)
        canvas.roundRect(split_high, y, max(0, width - split_high), 11, 4, fill=1, stroke=0)
        marker = x + self.score * width
        canvas.setStrokeColor(INK)
        canvas.setLineWidth(1.5)
        canvas.line(marker, y - 3, marker, y + 16)
        canvas.setFillColor(INK)
        canvas.setFont(self.font_bold, 7.5)
        canvas.drawCentredString(marker, y + 18, f"{self.score * 100:.1f}%")
        canvas.setFont(self.font_regular, 7.3)
        canvas.setFillColor(MUTED)
        canvas.drawString(0, 8, "Low")
        canvas.drawCentredString((split_low + split_high) / 2, 8, "Moderate")
        canvas.drawRightString(width, 8, "High")


class ClinicalTrendChart(Flowable):
    """Small vector chart that stays sharp in print and includes every row."""

    def __init__(self, title: str, y_label: str, steps: list[float], series: list[tuple[str, list[float | None], colors.Color]], font_regular: str, font_bold: str):
        super().__init__()
        self.title = title
        self.y_label = y_label
        self.steps = steps
        self.series = series
        self.font_regular = font_regular
        self.font_bold = font_bold
        self.height = 218

    def wrap(self, avail_width: float, _avail_height: float) -> tuple[float, float]:
        self.width = avail_width
        return self.width, self.height

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        left, right, top, bottom = 59, 14, 43, 42
        plot_x, plot_y = left, bottom
        plot_w, plot_h = self.width - left - right, self.height - top - bottom
        all_values = [value for _, values, _ in self.series for value in values if value is not None and isfinite(value)]
        if not all_values or not self.steps:
            canvas.setFillColor(MUTED)
            canvas.setFont(self.font_regular, 8)
            canvas.drawString(0, self.height - 17, self.title)
            canvas.drawString(0, self.height / 2, "No recorded values are available for this measurement.")
            canvas.restoreState()
            return

        low_value, high_value = min(all_values), max(all_values)
        padding = max((high_value - low_value) * 0.08, abs(high_value) * 0.01, 0.1)
        y_min, y_max = low_value - padding, high_value + padding
        canvas.setFillColor(INK)
        canvas.setFont(self.font_bold, 9.5)
        canvas.drawString(0, self.height - 15, self.title)

        if len(self.series) > 1:
            legend_x = 0
            canvas.setFont(self.font_regular, 7)
            for label, _values, color in self.series:
                canvas.setStrokeColor(color)
                canvas.setLineWidth(2)
                canvas.line(legend_x, self.height - 31, legend_x + 13, self.height - 31)
                canvas.setFillColor(MUTED)
                canvas.drawString(legend_x + 17, self.height - 34, label)
                legend_x += 17 + pdfmetrics.stringWidth(label, self.font_regular, 7) + 18

        canvas.setFont(self.font_regular, 6.8)
        for tick in range(5):
            value = y_min + (y_max - y_min) * tick / 4
            y = plot_y + plot_h * tick / 4
            canvas.setStrokeColor(GRID)
            canvas.setLineWidth(0.45)
            canvas.line(plot_x, y, plot_x + plot_w, y)
            canvas.setFillColor(MUTED)
            canvas.drawRightString(plot_x - 5, y - 2.4, _number(value, 1))

        canvas.saveState()
        canvas.translate(10, plot_y + plot_h / 2)
        canvas.rotate(90)
        canvas.setFillColor(MUTED)
        canvas.setFont(self.font_regular, 7)
        canvas.drawCentredString(0, 0, self.y_label)
        canvas.restoreState()

        min_step, max_step = min(self.steps), max(self.steps)
        def x_for(step: float) -> float:
            return plot_x + plot_w / 2 if min_step == max_step else plot_x + (step - min_step) / (max_step - min_step) * plot_w
        def y_for(value: float) -> float:
            return plot_y + (value - y_min) / (y_max - y_min) * plot_h

        canvas.setStrokeColor(MUTED)
        canvas.setLineWidth(0.7)
        canvas.line(plot_x, plot_y, plot_x + plot_w, plot_y)
        canvas.line(plot_x, plot_y, plot_x, plot_y + plot_h)

        label_stride = max(1, ceil(len(self.steps) / 7))
        label_indices = set(range(0, len(self.steps), label_stride)) | {len(self.steps) - 1}
        canvas.setFont(self.font_regular, 6.8)
        for index in sorted(label_indices):
            x = x_for(self.steps[index])
            canvas.setStrokeColor(MUTED)
            canvas.line(x, plot_y, x, plot_y - 3)
            canvas.setFillColor(MUTED)
            canvas.drawCentredString(x, plot_y - 12, _number(self.steps[index], 0))
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(plot_x + plot_w / 2, 4, "Time Step")

        for _label, values, color in self.series:
            canvas.setStrokeColor(color)
            canvas.setFillColor(color)
            canvas.setLineWidth(1.8)
            path = canvas.beginPath()
            started = False
            for index, value in enumerate(values):
                if value is None or not isfinite(value):
                    started = False
                    continue
                point_x, point_y = x_for(self.steps[index]), y_for(value)
                if started:
                    path.lineTo(point_x, point_y)
                else:
                    path.moveTo(point_x, point_y)
                    started = True
                canvas.circle(point_x, point_y, 1.55, fill=1, stroke=0)
            canvas.drawPath(path, stroke=1, fill=0)
        canvas.restoreState()


def _direction(start: float, end: float) -> str:
    if end > start:
        return "increased"
    if end < start:
        return "decreased"
    return "remained unchanged"


def _observations(rows: list[dict], styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    result: list[Flowable] = []
    if len(rows) < 2:
        return [_para("Only one time step is available, so a change over time cannot be calculated.", styles["body"])]
    step_rows = []
    for row in rows:
        try:
            step_rows.append((int(row["time_step"]), row))
        except (KeyError, TypeError, ValueError):
            continue
    if len(step_rows) < 2:
        return [_para("At least two ordered time-step records are required to summarize changes.", styles["body"])]

    for name, label, unit in CLINICAL_FIELDS:
        if name == "age":
            continue
        try:
            first = float(step_rows[0][1][name])
            last = float(step_rows[-1][1][name])
        except (KeyError, TypeError, ValueError):
            continue
        if not isfinite(first) or not isfinite(last):
            continue
        text = f"{label} {_direction(first, last)} from {_number(first)} to {_number(last)} {unit} across the observed time steps."
        result.append(_para(text, styles["body"]))
    return result or [_para("No numeric trend observations were available in the stored records.", styles["body"])]


def _chart_series(key: str, rows: list[dict]) -> list[tuple[str, list[float | None], colors.Color]]:
    if key == "blood_pressure":
        return [
            ("Systolic BP", [_finite_value(row.get("systolic_bp")) for row in rows], TEAL),
            ("Diastolic BP", [_finite_value(row.get("diastolic_bp")) for row in rows], colors.HexColor("#bd793c")),
        ]
    spec = next(item for item in TREND_SPECS if item[0] == key)
    return [(spec[1].removesuffix(" Trend"), [_finite_value(row.get(key)) for row in rows], TEAL)]


def _finite_value(value: object) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if isfinite(numeric) else None


def build_prediction_report(
    *,
    patient_id: str,
    age: int | None,
    observations: list[dict],
    prediction_probability: float,
    risk_category: str,
    model_version: str,
    created_at: datetime | None,
    input_source: str,
    observed_label: int | None,
    synthetic_data: bool,
    explanation: dict | str | None,
    low_threshold: float,
    high_threshold: float,
) -> bytes:
    """Return a complete PDF generated exclusively from the persisted assessment."""
    rows = _ordered_observations(observations)
    if not rows:
        raise ValueError("No stored clinical time-series records are available for this prediction.")
    score = float(prediction_probability)
    if not isfinite(score) or not 0 <= score <= 1:
        raise ValueError("The stored prediction score is invalid.")

    generated = datetime.now().astimezone()
    report_date = generated.strftime("%d-%m-%Y")
    report_time = generated.strftime("%H:%M")
    age_value = age if age is not None else rows[-1].get("age")
    font_regular, font_bold = _register_fonts()
    styles = _styles(font_regular, font_bold)
    buffer = BytesIO()
    page_width, page_height = A4
    margin = 15 * mm
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=19 * mm,
        bottomMargin=17 * mm,
        title="Sepsis Risk Assessment Report",
        author="SepsiGuard AI",
        subject=f"Patient-specific longitudinal sepsis risk assessment for {patient_id}",
    )

    def decorate_page(canvas, document):
        canvas.saveState()
        canvas.setFillColor(TEAL)
        canvas.rect(0, page_height - 12 * mm, page_width, 12 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont(font_bold, 9)
        canvas.drawString(margin, page_height - 8 * mm, "SEPSIGUARD AI")
        canvas.setFont(font_regular, 7)
        canvas.drawRightString(page_width - margin, page_height - 8 * mm, "Sepsis Risk Assessment Report")
        canvas.setStrokeColor(GRID)
        canvas.line(margin, 12 * mm, page_width - margin, 12 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont(font_regular, 7)
        canvas.drawString(margin, 8 * mm, "Educational and research use only")
        canvas.drawRightString(page_width - margin, 8 * mm, f"Page {document.page}")
        canvas.restoreState()

    story: list[Flowable] = [
        _para("SepsiGuard AI", styles["title"]),
        _para("Sepsis Risk Assessment Report", styles["subtitle"]),
        _para("Patient Information", styles["section"]),
    ]
    patient_rows = [
        [_para("Patient ID", styles["table_label"]), _para(patient_id, styles["body"]), _para("Age", styles["table_label"]), _para(f"{age_value} years" if age_value is not None else "Not Available", styles["body"])],
        [_para("Report Date", styles["table_label"]), _para(report_date, styles["body"]), _para("Report Time", styles["table_label"]), _para(report_time, styles["body"])],
        [_para("Prediction Time", styles["table_label"]), _para(created_at.astimezone().strftime("%d-%m-%Y %H:%M") if created_at else "Not Available", styles["body"]), _para("Input Source", styles["table_label"]), _para(input_source or "Not Available", styles["body"])],
    ]
    patient_table = Table(patient_rows, colWidths=[76, 174, 72, doc.width - 322])
    patient_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), PALE), ("BACKGROUND", (2, 0), (2, -1), PALE),
        ("GRID", (0, 0), (-1, -1), 0.35, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([patient_table, _para("Sepsis Risk Assessment", styles["section"])])

    risk_phrase = f"{risk_category.title()} risk of sepsis"
    summary_rows = [[
        Paragraph(f"<b>Risk Score</b><br/><font size='18'>{score * 100:.1f}%</font>", styles["summary"]),
        Paragraph(f"<b>Risk Level</b><br/><font size='13'>{escape(risk_category.upper())}</font>", styles["summary"]),
        Paragraph(f"<b>AI Predicted Risk</b><br/>{escape(risk_phrase)}", styles["summary"]),
    ]]
    summary = Table(summary_rows, colWidths=[doc.width * 0.27, doc.width * 0.27, doc.width * 0.46])
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE), ("BOX", (0, 0), (-1, -1), 0.7, GRID),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.extend([summary, Spacer(1, 4), RiskScale(score, low_threshold, high_threshold, font_regular, font_bold)])

    latest = rows[-1]
    story.append(_para("Current Clinical Measurements", styles["section"]))
    current_data: list[list[Flowable | str]] = [[
        _para("Parameter", styles["table_header"]), _para("Value", styles["table_header"]), _para("Unit", styles["table_header"]),
    ]]
    for name, label, unit in CLINICAL_FIELDS:
        value = age_value if name == "age" else latest.get(name)
        current_data.append([_para(label, styles["body"]), _para(_number(value), styles["body"]), _para(unit, styles["body"])])
    current_table = Table(current_data, colWidths=[doc.width * 0.52, doc.width * 0.23, doc.width * 0.25], repeatRows=1)
    current_table.setStyle(_table_style())
    story.append(current_table)

    label_text = "Positive" if observed_label == 1 else "Negative" if observed_label == 0 else "Not Available"
    story.extend([
        _para("Observed Dataset Label", styles["section"]),
        _para(f"Observed Dataset Label: {label_text}. This is a stored dataset target and is separate from the AI Predicted Risk.", styles["body"]),
    ])
    if synthetic_data:
        story.append(_para("This model was trained with synthetic data. The output is an artificial software result and has no clinical meaning.", styles["small"]))

    story.extend([PageBreak(), _para("Complete Patient Time-Series Records", styles["section"]), _para(f"All {len(rows)} stored time-step records for patient {patient_id} are listed below.", styles["small"])])
    header_labels = (
        "Time",
        "HR<br/>(bpm)",
        "RR",
        "Temp<br/>(°C)",
        "Sys BP<br/>(mmHg)",
        "Dia BP<br/>(mmHg)",
        "O₂ sat.<br/>(%)",
        "WBC<br/>(×10³/µL)",
        "Lactate<br/>(mmol/L)",
        "Creat.<br/>(mg/dL)",
        "Platelets<br/>(×10³/µL)",
        "Bili<br/>(mg/dL)",
        "Age<br/>(years)",
    )
    table_data: list[list[Flowable | str]] = [[Paragraph(label, styles["series_header"]) for label in header_labels]]
    value_keys = ("time_step", "heart_rate", "respiratory_rate", "temperature", "systolic_bp", "diastolic_bp", "oxygen_saturation", "wbc", "lactate", "creatinine", "platelets", "bilirubin", "age")
    for row in rows:
        table_data.append([_para(_number(row.get(key), 0 if key == "time_step" else 2), styles["series_cell"]) for key in value_keys])
    widths = [31, 40, 39, 39, 42, 42, 40, 40, 38, 47, 43, 39, 29]
    width_scale = doc.width / sum(widths)
    widths = [width * width_scale for width in widths]
    time_table = Table(table_data, colWidths=widths, repeatRows=1, splitByRow=1, hAlign="LEFT")
    time_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, GRID), ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 1.5), ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, 0), 5), ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
    ]))
    story.extend([time_table, Spacer(1, 8), _para("Clinical Trend Observations", styles["section"])])
    story.extend(_observations(rows, styles))
    story.extend([
        _para("Sepsis Risk Trend", styles["section"]),
        _para("Risk trend is unavailable because the model produces a final sequence-level prediction. Historical per-time-step risk scores are not generated.", styles["body"]),
    ])

    chart_keys = [item[0] for item in TREND_SPECS]
    for pair_start in range(0, len(chart_keys), 2):
        pair: list[Flowable] = []
        if pair_start == 0:
            pair.append(_para("Clinical Trend Analysis", styles["section"]))
        for key in chart_keys[pair_start:pair_start + 2]:
            _spec = next(item for item in TREND_SPECS if item[0] == key)
            title = _spec[1]
            label = _spec[2]
            if key == "blood_pressure":
                series = _chart_series(key, rows)
            else:
                series = [(title.removesuffix(" Trend"), [_finite_value(row.get(key)) for row in rows], TEAL)]
            steps = [float(row.get("time_step", index + 1)) for index, row in enumerate(rows)]
            pair.extend([ClinicalTrendChart(title, label, steps, series, font_regular, font_bold), Spacer(1, 8)])
        story.append(KeepTogether(pair))

    story.extend([PageBreak(), _para("AI Risk Assessment", styles["section"])])
    story.append(_para("The SepsiGuard GRU model analyzes the patient's sequential clinical measurements across the available time steps and generates an AI-based sepsis risk assessment.", styles["body"]))
    explanation_text = explanation.strip() if isinstance(explanation, str) else ""
    if isinstance(explanation, dict):
        explanation_text = next((
            explanation[key].strip() for key in ("summary", "text", "explanation")
            if isinstance(explanation.get(key), str) and explanation[key].strip()
        ), "")
    if explanation_text:
        story.append(_para(f"Model-provided explanation: {explanation_text}", styles["body"]))
        story.append(_para("No additional variable-level attribution is inferred in this report.", styles["body"]))
    else:
        story.append(_para("A per-prediction explanation is unavailable for this model. This report does not assign causality to individual measurements.", styles["body"]))

    story.append(_para("Model Information", styles["section"]))
    variables = ", ".join(label for name, label, _unit in CLINICAL_FIELDS if name != "age") + ", Age"
    model_rows = [
        [_para("Model Type", styles["table_label"]), _para("GRU (Gated Recurrent Unit)", styles["body"])],
        [_para("Task", styles["table_label"]), _para("Sepsis Risk Prediction", styles["body"])],
        [_para("Input Type", styles["table_label"]), _para("Longitudinal Clinical Time-Series", styles["body"])],
        [_para("Input Variables", styles["table_label"]), _para(f"12: {variables}", styles["body"])],
        [_para("Target", styles["table_label"]), _para("Observed sepsis label, when supplied with the dataset", styles["body"])],
        [_para("Prediction Model Version", styles["table_label"]), _para(model_version, styles["body"])],
    ]
    model_table = Table(model_rows, colWidths=[doc.width * 0.28, doc.width * 0.72])
    model_table.setStyle(_table_style(header=False))
    story.extend([model_table, Spacer(1, 6)])
    story.append(_para(f"Report Generated: {report_date} {report_time} | Patient ID: {patient_id} | Number of Time Steps: {len(rows)} | Prediction Model: GRU", styles["small"]))
    story.extend([_para("Disclaimer", styles["section"]), _para(DISCLAIMER, styles["disclaimer"])])

    doc.build(story, onFirstPage=decorate_page, onLaterPages=decorate_page)
    return buffer.getvalue()


def report_filename(patient_id: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", patient_id).strip("_-") or "Patient"
    return f"SepsiGuard_Patient_{safe_id}_Report.pdf"
