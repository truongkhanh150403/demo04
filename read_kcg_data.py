import csv
import io
import json
import math
import ssl
import urllib.error
import urllib.request

from flask import Flask, render_template, request

URL = "https://data.ntpc.gov.tw/api/datasets/781b822e-214a-4b9a-b4db-32c9f4626d98/csv/file"

app = Flask(__name__)


def fetch_data(url: str) -> tuple[bytes, str]:
    """Download raw bytes from URL and return content type."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
        return raw, content_type
    except urllib.error.URLError as e:
        if isinstance(e.reason, ssl.SSLCertVerificationError):
            print("憑證驗證失敗，改用不驗證 SSL 模式重試...")
            unverified = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=30, context=unverified) as response:
                raw = response.read()
                content_type = response.headers.get("Content-Type", "")
            return raw, content_type
        raise


def decode_text(raw: bytes) -> str:
    """Decode bytes with common encodings used by open data files."""
    for enc in ("utf-8-sig", "utf-8", "big5", "cp950"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def show_json(text: str) -> bool:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return False

    print("=== 偵測到 JSON 資料 ===")

    if isinstance(data, list):
        print(f"總筆數: {len(data)}")
        print("完整資料如下:\n")
        for i, item in enumerate(data, start=1):
            print(f"[{i}] {json.dumps(item, ensure_ascii=False, indent=2)}")
    elif isinstance(data, dict):
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(data)

    return True


def show_csv(text: str) -> bool:
    sample = text[:2048]

    try:
        dialect = csv.Sniffer().sniff(sample)
    except csv.Error:
        # If sniffing fails, assume comma-separated format.
        dialect = csv.excel

    reader = csv.reader(io.StringIO(text), dialect)
    rows = list(reader)
    if not rows or len(rows[0]) <= 1:
        return False

    headers = rows[0]
    data_rows = rows[1:]

    print("=== 偵測到 CSV 資料 ===")
    print(f"欄位數: {len(headers)}")
    print(f"資料筆數: {len(data_rows)}")
    print("完整資料如下:\n")

    for i, row in enumerate(data_rows, start=1):
        print(f"[{i}]")
        for h, v in zip(headers, row):
            print(f"  {h}: {v}")
        print()

    return True


def show_plain_text(text: str) -> None:
    lines = text.splitlines()
    print("=== 文字資料 ===")
    print(f"總行數: {len(lines)}")
    print("完整資料如下:\n")
    for i, line in enumerate(lines, start=1):
        print(f"{i:>2}: {line}")


def build_csv_rows(headers: list[str], data_rows: list[list[str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in data_rows:
        rows.append(
            {
                header: row[index] if index < len(row) else ""
                for index, header in enumerate(headers)
            }
        )
    return rows


def load_dataset(url: str) -> dict[str, object]:
    raw, content_type = fetch_data(url)
    text = decode_text(raw)

    if "json" in content_type.lower():
        return {
            "kind": "json",
            "content_type": content_type,
            "raw_text": text,
            "json_text": json.dumps(json.loads(text), ensure_ascii=False, indent=2),
        }

    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample)
    except csv.Error:
        dialect = csv.excel

    reader = csv.reader(io.StringIO(text), dialect)
    rows = list(reader)
    if rows and len(rows[0]) > 1:
        headers = rows[0]
        data_rows = rows[1:]
        return {
            "kind": "csv",
            "content_type": content_type,
            "raw_text": text,
            "headers": headers,
            "rows": build_csv_rows(headers, data_rows),
            "row_count": len(data_rows),
        }

    return {
        "kind": "text",
        "content_type": content_type,
        "raw_text": text,
        "lines": text.splitlines(),
    }


def paginate_rows(rows: list[dict[str, str]], page: int, per_page: int) -> tuple[list[dict[str, str]], int, int]:
    total_rows = len(rows)
    total_pages = max(1, math.ceil(total_rows / per_page))
    current_page = min(max(page, 1), total_pages)
    start = (current_page - 1) * per_page
    end = start + per_page
    return rows[start:end], current_page, total_pages


@app.route("/")
def index() -> str:
    try:
        dataset = load_dataset(URL)
        error_message = None
    except urllib.error.URLError as e:
        dataset = {
            "kind": "error",
            "content_type": "",
            "raw_text": "",
        }
        error_message = f"下載失敗：{e}"

    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=10, type=int)
    per_page = min(max(per_page, 5), 50)

    paginated_rows: list[dict[str, str]] = []
    start_index = 0
    total_pages = 1
    current_page = 1

    if dataset.get("kind") == "csv":
        all_rows = dataset.get("rows", [])
        if isinstance(all_rows, list):
            paginated_rows, current_page, total_pages = paginate_rows(all_rows, page, per_page)
            start_index = (current_page - 1) * per_page

    page_numbers = list(range(max(1, current_page - 2), min(total_pages, current_page + 2) + 1))

    return render_template(
        "index.html",
        source_url=URL,
        error_message=error_message,
        page=current_page,
        per_page=per_page,
        total_pages=total_pages,
        page_numbers=page_numbers,
        start_index=start_index,
        paginated_rows=paginated_rows,
        **dataset,
    )


def main() -> None:
    app.run(host="127.0.0.1", port=5000, debug=True)


if __name__ == "__main__":
    main()
