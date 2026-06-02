from __future__ import annotations

import csv
import io
import json
import re
import ssl
import urllib.error
import urllib.request
from functools import lru_cache
from typing import Any

from flask import Flask, render_template_string, request, url_for

DATA_URL = "https://data.kcg.gov.tw/File/DirectDownload/30c58c88-4f53-45a0-8393-e655feaaa65b"

app = Flask(__name__)

DISPLAY_ORDER = (
    "型式",
    "行政區",
    "場名",
    "位置",
    "收費標準",
    "大車",
    "小車",
    "機車",
    "管理業者",
    "聯絡電話",
    "履約起迄",
    "緯度",
    "經度",
)

PARKING_TYPE_OPTIONS = ("平面", "立體")
VEHICLE_OPTIONS = (("large", "大車"), ("small", "小車"), ("motor", "機車"))
EMPTY_MARKERS = {"", "-", "－", "—", "–", "N/A", "n/a", "NA", "null", "None"}
VEHICLE_FIELD_MAP = {
    "large": "大車",
    "small": "小車",
    "motor": "機車",
}

PAGE_TEMPLATE = """
<!doctype html>
<html lang="zh-Hant" data-theme="light">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>高雄停車場資料查詢</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #f4f0e8;
        --bg-2: #e2efe9;
        --surface: rgba(255, 255, 255, 0.8);
        --surface-strong: rgba(255, 255, 255, 0.95);
        --surface-soft: rgba(246, 243, 236, 0.82);
        --border: rgba(16, 32, 24, 0.08);
        --text: #15211d;
        --muted: #5f6e67;
        --brand: #0d7861;
        --brand-strong: #0b4d3f;
        --brand-soft: rgba(13, 120, 97, 0.12);
        --accent: #c98d3c;
        --danger-bg: rgba(255, 243, 240, 0.95);
        --danger-text: #94342b;
        --shadow: 0 24px 80px rgba(22, 42, 34, 0.12);
        --chip-bg: rgba(255, 255, 255, 0.8);
      }

      html[data-theme="dark"] {
        color-scheme: dark;
        --bg: #081513;
        --bg-2: #112722;
        --surface: rgba(12, 25, 22, 0.8);
        --surface-strong: rgba(15, 31, 27, 0.95);
        --surface-soft: rgba(16, 30, 27, 0.9);
        --border: rgba(233, 255, 248, 0.09);
        --text: #e8f5f0;
        --muted: #9fb3ad;
        --brand: #6dd4bf;
        --brand-strong: #8ff0da;
        --brand-soft: rgba(109, 212, 191, 0.14);
        --accent: #f0b56c;
        --danger-bg: rgba(72, 28, 24, 0.9);
        --danger-text: #ffb9b0;
        --shadow: 0 28px 90px rgba(0, 0, 0, 0.35);
        --chip-bg: rgba(16, 30, 27, 0.95);
      }

      * {
        box-sizing: border-box;
      }

      html,
      body {
        min-height: 100%;
      }

      body {
        margin: 0;
        font-family: "Noto Sans TC", "Segoe UI", sans-serif;
        color: var(--text);
        background:
          radial-gradient(circle at top left, rgba(13, 120, 97, 0.2), transparent 30%),
          radial-gradient(circle at bottom right, rgba(201, 141, 60, 0.16), transparent 26%),
          linear-gradient(180deg, var(--bg), var(--bg-2));
      }

      body::before {
        content: "";
        position: fixed;
        inset: 0;
        pointer-events: none;
        background-image: linear-gradient(rgba(255, 255, 255, 0.16) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255, 255, 255, 0.12) 1px, transparent 1px);
        background-size: 34px 34px;
        mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.5), transparent 88%);
      }

      .page-shell {
        width: min(1280px, calc(100% - 32px));
        margin: 0 auto;
        padding: 42px 0 64px;
        position: relative;
        z-index: 1;
      }

      .hero {
        display: grid;
        gap: 20px;
        grid-template-columns: minmax(0, 1.55fr) minmax(280px, 0.95fr);
        align-items: end;
        margin-bottom: 20px;
      }

      .eyebrow {
        margin: 0 0 10px;
        color: var(--brand);
        font-size: 0.84rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }

      h1,
      h2,
      h3,
      p {
        margin-top: 0;
      }

      h1 {
        margin-bottom: 12px;
        font-size: clamp(2.2rem, 4.8vw, 4.4rem);
        line-height: 1.02;
        letter-spacing: -0.03em;
        max-width: 11ch;
      }

      .lead {
        margin: 0;
        max-width: 62ch;
        line-height: 1.85;
        color: var(--muted);
        font-size: 1.03rem;
      }

      .panel,
      .source-card,
      .stat-card {
        background: var(--surface);
        border: 1px solid var(--border);
        box-shadow: var(--shadow);
        backdrop-filter: blur(16px);
      }

      .source-card {
        border-radius: 24px;
        padding: 22px 24px;
      }

      .source-label,
      .section-label {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 10px;
        font-size: 0.82rem;
        font-weight: 800;
        color: var(--muted);
        letter-spacing: 0.06em;
        text-transform: uppercase;
      }

      .source-text {
        display: block;
        line-height: 1.6;
        word-break: break-all;
        color: var(--brand-strong);
      }

      .meta-grid {
        display: grid;
        gap: 12px;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin-top: 18px;
      }

      .meta-item {
        padding-top: 14px;
        border-top: 1px solid var(--border);
      }

      .meta-item span {
        display: block;
        margin-bottom: 4px;
        color: var(--muted);
        font-size: 0.88rem;
      }

      .meta-item strong {
        color: var(--text);
      }

      .panel {
        border-radius: 28px;
        padding: 24px;
      }

      .panel-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 16px;
        margin-bottom: 18px;
      }

      .panel-header h2 {
        margin-bottom: 6px;
        font-size: 1.42rem;
      }

      .panel-header p {
        margin-bottom: 0;
        color: var(--muted);
      }

      .filters {
        display: grid;
        gap: 16px;
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }

      .field {
        display: grid;
        gap: 8px;
      }

      .field label,
      .field > span {
        color: var(--muted);
        font-size: 0.92rem;
        font-weight: 700;
      }

      .field input,
      .field select {
        width: 100%;
        border: 1px solid var(--border);
        border-radius: 14px;
        background: var(--surface-strong);
        color: var(--text);
        font: inherit;
        padding: 12px 14px;
        outline: none;
      }

      .field input:focus,
      .field select:focus,
      .theme-toggle:focus,
      .action-link:focus,
      .page-link:focus,
      .submit-btn:focus {
        box-shadow: 0 0 0 3px var(--brand-soft);
      }

      .vehicle-group {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        padding-top: 2px;
      }

      .chip {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        min-height: 42px;
        padding: 10px 14px;
        border: 1px solid var(--border);
        border-radius: 999px;
        background: var(--chip-bg);
        color: var(--text);
        cursor: pointer;
        user-select: none;
      }

      .chip input {
        margin: 0;
        accent-color: var(--brand);
      }

      .actions-row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: center;
        justify-content: space-between;
        margin-top: 18px;
      }

      .action-group {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }

      .theme-toggle,
      .submit-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 42px;
        border-radius: 999px;
        border: 1px solid transparent;
        padding: 0 16px;
        font: inherit;
        font-weight: 800;
        text-decoration: none;
        cursor: pointer;
        transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
      }

      .theme-toggle {
        background: var(--surface-strong);
        border-color: var(--border);
        color: var(--text);
      }

      .submit-btn {
        background: var(--brand);
        color: #fff;
        box-shadow: 0 10px 24px rgba(13, 120, 97, 0.22);
      }

      .theme-toggle:hover,
      .submit-btn:hover,
      .page-link:hover {
        transform: translateY(-1px);
      }

      .summary-strip {
        display: grid;
        gap: 12px;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        margin-bottom: 18px;
      }

      .stat-card {
        border-radius: 22px;
        padding: 18px;
      }

      .stat-card span {
        display: block;
        color: var(--muted);
        font-size: 0.86rem;
        margin-bottom: 8px;
      }

      .stat-card strong {
        display: block;
        font-size: 1.2rem;
        letter-spacing: -0.01em;
      }

      .notice {
        border-radius: 22px;
        padding: 18px 20px;
        background: var(--danger-bg);
        color: var(--danger-text);
        border: 1px solid rgba(190, 55, 55, 0.16);
      }

      .card-list {
        display: grid;
        gap: 16px;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      }

      .parking-card {
        border-radius: 24px;
        border: 1px solid var(--border);
        background: var(--surface-strong);
        padding: 18px;
        box-shadow: 0 12px 32px rgba(22, 42, 34, 0.08);
      }

      .parking-card h3 {
        margin-bottom: 8px;
        font-size: 1.1rem;
        line-height: 1.35;
      }

      .card-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 14px;
      }

      .badge {
        display: inline-flex;
        align-items: center;
        padding: 6px 10px;
        border-radius: 999px;
        background: var(--brand-soft);
        color: var(--brand-strong);
        font-size: 0.82rem;
        font-weight: 800;
      }

      .field-list {
        display: grid;
        gap: 10px;
      }

      .field-row {
        display: grid;
        gap: 6px;
        grid-template-columns: minmax(88px, 108px) minmax(0, 1fr);
        padding: 11px 12px;
        border-radius: 14px;
        background: var(--surface-soft);
      }

      .field-name {
        color: var(--brand-strong);
        font-weight: 800;
      }

      .field-value {
        min-width: 0;
        color: var(--text);
        word-break: break-word;
        white-space: pre-wrap;
      }

      .empty-state {
        display: grid;
        gap: 12px;
        place-items: center;
        min-height: 220px;
        text-align: center;
        color: var(--muted);
        border: 1px dashed var(--border);
        border-radius: 24px;
        background: var(--surface-soft);
      }

      .empty-state h3 {
        margin: 0;
        color: var(--text);
      }

      @media (max-width: 1080px) {
        .hero,
        .summary-strip,
        .filters {
          grid-template-columns: 1fr;
        }
      }

      @media (max-width: 760px) {
        .page-shell {
          width: min(100% - 18px, 1280px);
          padding-top: 18px;
        }

        .panel,
        .source-card {
          border-radius: 22px;
        }

        .panel {
          padding: 18px;
        }

        .panel-header {
          flex-direction: column;
        }

        .meta-grid {
          grid-template-columns: 1fr;
        }

        .field-row {
          grid-template-columns: 1fr;
        }
      }
    </style>
  </head>
  <body>
    <main class="page-shell">
      <section class="hero">
        <div>
          <p class="eyebrow">Kaohsiung Parking Lot Explorer</p>
          <h1>高雄停車場資料查詢</h1>
          <p class="lead">
            從高雄市開放資料即時讀取停車場清單，並以卡片逐筆顯示。可依停車形式、地名與車種快速篩選，介面同時支援 light / dark 主題切換與 RWD。
          </p>
        </div>

        <aside class="source-card">
          <div class="source-label">資料來源</div>
          <div class="source-text">高雄市停車場開放資料，已直接讀取並顯示全部資料</div>
          <div class="meta-grid">
            <div class="meta-item">
              <span>檔案格式</span>
              <strong>{{ content_type or '未知' }}</strong>
            </div>
            <div class="meta-item">
              <span>主題</span>
              <strong>可切換 light / dark</strong>
            </div>
          </div>
        </aside>
      </section>

      {% if error_message %}
        <section class="notice">
          <h2>資料讀取失敗</h2>
          <p style="margin-bottom: 0;">{{ error_message }}</p>
        </section>
      {% else %}
        <section class="panel">
          <div class="panel-header">
            <div>
              <div class="section-label">查詢條件</div>
              <h2>篩選停車場資料</h2>
              <p>可同時依停車形式、地名與車種篩選；地名支援模糊搜尋。</p>
            </div>
            <button class="theme-toggle" type="button" id="themeToggle" aria-pressed="false" onclick="toggleTheme()">
              目前主題
            </button>
          </div>

          <form method="get">
            <div class="filters">
              <label class="field">
                <span>停車形式</span>
                <select name="parking_type">
                  <option value="">全部</option>
                  {% for option in parking_type_options %}
                    <option value="{{ option }}" {% if option == selected_parking_type %}selected{% endif %}>{{ option }}</option>
                  {% endfor %}
                </select>
              </label>

              <label class="field">
                <span>地名</span>
                <input type="text" name="district" value="{{ selected_district }}" placeholder="例如：岡山、旗山、楠梓" list="district-list" />
                <datalist id="district-list">
                  {% for district in district_options %}
                    <option value="{{ district }}"></option>
                  {% endfor %}
                </datalist>
              </label>

              <div class="field">
                <span>車輛種類</span>
                <div class="vehicle-group">
                  {% for value, label in vehicle_options %}
                    <label class="chip">
                      <input type="checkbox" name="vehicle" value="{{ value }}" {% if value in selected_vehicles %}checked{% endif %} />
                      <span>{{ label }}</span>
                    </label>
                  {% endfor %}
                </div>
              </div>
            </div>

            <div class="actions-row">
              <div class="action-group">
                <button class="submit-btn" type="submit">套用篩選</button>
                <a class="action-link" href="{{ url_for('index') }}">清除條件</a>
              </div>
            </div>
          </form>
        </section>

        <section class="summary-strip" aria-label="查詢摘要">
          <article class="stat-card">
            <span>篩選後筆數</span>
            <strong>{{ filtered_count }}</strong>
          </article>
          <article class="stat-card">
            <span>顯示方式</span>
            <strong>全部顯示</strong>
          </article>
          <article class="stat-card">
            <span>地名條件</span>
            <strong>{{ selected_district or '未指定' }}</strong>
          </article>
          <article class="stat-card">
            <span>車種條件</span>
            <strong>{{ selected_vehicles|length }} 項</strong>
          </article>
        </section>

        <section class="panel">
          <div class="panel-header">
            <div>
              <div class="section-label">資料卡片</div>
              <h2>逐筆顯示停車場資料</h2>
              <p>共 {{ filtered_count }} 筆符合條件，以下直接完整顯示。</p>
            </div>
          </div>

          {% if filtered_records %}
            <div class="card-list">
              {% for row in filtered_records %}
                <article class="parking-card">
                  <h3>{{ row_title(row) }}</h3>
                  <div class="card-badges">
                    {% if row.get('型式') %}
                      <span class="badge">{{ row.get('型式') }}</span>
                    {% endif %}
                    {% if row.get('行政區') %}
                      <span class="badge">{{ row.get('行政區') }}</span>
                    {% endif %}
                    {% if row.get('大車') %}
                      <span class="badge">大車 {{ row.get('大車') }}</span>
                    {% endif %}
                    {% if row.get('小車') %}
                      <span class="badge">小車 {{ row.get('小車') }}</span>
                    {% endif %}
                    {% if row.get('機車') %}
                      <span class="badge">機車 {{ row.get('機車') }}</span>
                    {% endif %}
                  </div>

                  <div class="field-list">
                    {% for label, value in row_fields(row) %}
                      <div class="field-row">
                        <div class="field-name">{{ label }}</div>
                        <div class="field-value">{{ value }}</div>
                      </div>
                    {% endfor %}
                  </div>
                </article>
              {% endfor %}
            </div>
          {% else %}
            <div class="empty-state">
              <h3>沒有符合條件的資料</h3>
              <p>請調整停車形式、地名或車種條件後再試一次。</p>
            </div>
          {% endif %}
        </section>
      {% endif %}
    </main>

    <script>
      (function () {
        const storageKey = "parking-lot-theme";
        const root = document.documentElement;
        const toggle = document.getElementById("themeToggle");

        function applyTheme(theme) {
          root.dataset.theme = theme;
          if (toggle) {
            toggle.setAttribute("aria-pressed", theme === "light" ? "true" : "false");
            toggle.textContent = theme === "light" ? "切換至深色主題" : "切換至明亮主題";
          }
        }

        const savedTheme = localStorage.getItem(storageKey);
        const preferredTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
        applyTheme(savedTheme || preferredTheme);

        window.toggleTheme = function () {
          const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
          localStorage.setItem(storageKey, nextTheme);
          applyTheme(nextTheme);
        };
      })();
    </script>
  </body>
</html>
"""


def fetch_data(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read(), response.headers.get("Content-Type", "")
    except urllib.error.URLError as error:
        if isinstance(error.reason, ssl.SSLCertVerificationError):
            print("憑證驗證失敗，改用不驗證 SSL 模式重試...")
            context = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=30, context=context) as response:
                return response.read(), response.headers.get("Content-Type", "")
        raise


def decode_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "big5", "cp950"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if text in EMPTY_MARKERS:
        return ""
    return text


def sniff_csv_dialect(text: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(text[:4096])
    except csv.Error:
        return csv.excel


def load_csv_records(text: str) -> tuple[list[dict[str, str]], list[str]]:
    reader = csv.reader(io.StringIO(text), sniff_csv_dialect(text))
    rows = list(reader)
    if not rows:
        return [], []

    headers = [header.strip() for header in rows[0]]
    records: list[dict[str, str]] = []
    carry_fields = {"型式", "行政區", "場名"}
    carry_state = {field: "" for field in carry_fields}

    for raw_row in rows[1:]:
        record: dict[str, str] = {}
        for index, header in enumerate(headers):
            value = normalize_text(raw_row[index]) if index < len(raw_row) else ""
            if header in carry_fields:
                if value:
                    carry_state[header] = value
                else:
                    value = carry_state[header]
            record[header] = value
        records.append(record)

    return records, headers


def load_json_records(text: str) -> tuple[list[dict[str, str]], list[str]]:
    data = json.loads(text)
    if isinstance(data, dict):
        items = data.get("records") or data.get("result") or data.get("data") or []
    else:
        items = data

    if not isinstance(items, list):
        return [], []

    headers: list[str] = []
    records: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        record = {str(key): normalize_text(value) for key, value in item.items()}
        records.append(record)
        for key in record:
            if key not in headers:
                headers.append(key)

    return records, headers


@lru_cache(maxsize=1)
def load_dataset() -> dict[str, Any]:
    raw, content_type = fetch_data(DATA_URL)
    text = decode_text(raw)

    try:
        if "json" in content_type.lower() or text.lstrip().startswith(("[", "{")):
            records, headers = load_json_records(text)
            kind = "json"
        else:
            records, headers = load_csv_records(text)
            kind = "csv"
    except Exception:
        records, headers = [], []
        kind = "text"

    if not headers and records:
        for record in records:
            for key in record:
                if key not in headers:
                    headers.append(key)

    return {
        "kind": kind,
        "content_type": content_type,
        "raw_text": text,
        "records": records,
        "headers": headers,
        "row_count": len(records),
    }


def numeric_value(value: Any) -> int:
    text = normalize_text(value)
    if not text:
        return 0

    match = re.search(r"-?\d+", text.replace(",", ""))
    if not match:
        return 0

    try:
        return int(match.group())
    except ValueError:
        return 0


def row_supports_vehicle(row: dict[str, str], vehicle: str) -> bool:
    field_name = VEHICLE_FIELD_MAP[vehicle]
    if numeric_value(row.get(field_name, "")) > 0:
        return True

    return field_name in " ".join(
        part for part in (row.get("收費標準", ""), row.get("場名", ""), row.get("位置", "")) if part
    )


def row_matches_filters(
    row: dict[str, str],
    parking_type: str,
    district: str,
    selected_vehicles: list[str],
) -> bool:
    if parking_type and normalize_text(row.get("型式")) != parking_type:
        return False

    if district:
        haystack = " ".join(
            filter(
                None,
                (
                    row.get("行政區", ""),
                    row.get("場名", ""),
                    row.get("位置", ""),
                ),
            )
        )
        if district.lower() not in haystack.lower():
            return False

    if selected_vehicles and not any(row_supports_vehicle(row, vehicle) for vehicle in selected_vehicles):
        return False

    return True


def row_title(row: dict[str, str]) -> str:
    for key in ("場名", "位置", "行政區"):
        value = normalize_text(row.get(key))
        if value:
            return value
    return "未命名停車場"


def row_fields(row: dict[str, str]) -> list[tuple[str, str]]:
    ordered_keys: list[str] = []
    for key in DISPLAY_ORDER:
        if key in row and key not in ordered_keys:
            ordered_keys.append(key)

    for key in row:
        if key not in ordered_keys and normalize_text(row.get(key)):
            ordered_keys.append(key)

    fields: list[tuple[str, str]] = []
    for key in ordered_keys:
        value = normalize_text(row.get(key))
        if value:
            fields.append((key, value))
    return fields


def paginate_rows(rows: list[dict[str, str]], page: int, per_page: int) -> tuple[list[dict[str, str]], int, int, int]:
  total_rows = len(rows)
  total_pages = max(1, (total_rows + per_page - 1) // per_page)
  current_page = min(max(page, 1), total_pages)
  start = (current_page - 1) * per_page
  end = start + per_page
  return rows[start:end], current_page, total_pages, start


@app.context_processor
def inject_helpers() -> dict[str, Any]:
    return {"row_title": row_title, "row_fields": row_fields}


@app.route("/")
def index() -> str:
    try:
        dataset = load_dataset()
        error_message = None
    except urllib.error.URLError as error:
        dataset = {"kind": "error", "content_type": "", "records": [], "headers": [], "row_count": 0}
        error_message = f"下載失敗：{error}"
    except Exception as error:
        dataset = {"kind": "error", "content_type": "", "records": [], "headers": [], "row_count": 0}
        error_message = f"資料處理失敗：{error}"

    selected_parking_type = normalize_text(request.args.get("parking_type"))
    selected_district = normalize_text(request.args.get("district"))
    selected_vehicles = [value for value in request.args.getlist("vehicle") if value in VEHICLE_FIELD_MAP]

    filtered_records = [
        row
        for row in dataset.get("records", [])
        if isinstance(row, dict)
        and row_matches_filters(row, selected_parking_type, selected_district, selected_vehicles)
    ]
    district_options = sorted(
        {
            normalize_text(row.get("行政區"))
            for row in dataset.get("records", [])
            if isinstance(row, dict) and normalize_text(row.get("行政區"))
        }
    )

    return render_template_string(
        PAGE_TEMPLATE,
        source_url=DATA_URL,
        error_message=error_message,
        content_type=dataset.get("content_type", ""),
        parking_type_options=PARKING_TYPE_OPTIONS,
        vehicle_options=VEHICLE_OPTIONS,
        selected_parking_type=selected_parking_type,
        selected_district=selected_district,
        selected_vehicles=selected_vehicles,
        filtered_count=len(filtered_records),
        filtered_records=filtered_records,
        district_options=district_options,
    )


def main() -> None:
    app.run(host="127.0.0.1", port=5000, debug=True)


if __name__ == "__main__":
    main()