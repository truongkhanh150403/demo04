import csv
import io
import json
import ssl
import urllib.error
import urllib.request

URL = "https://data.ntpc.gov.tw/api/datasets/781b822e-214a-4b9a-b4db-32c9f4626d98/csv/file"


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


def main() -> None:
    print(f"正在下載資料: {URL}")

    try:
        raw, content_type = fetch_data(URL)
    except urllib.error.URLError as e:
        print(f"下載失敗: {e}")
        return

    text = decode_text(raw)
    print(f"下載成功，Content-Type: {content_type}\n")

    if "json" in content_type.lower() and show_json(text):
        return
    if show_json(text):
        return
    if show_csv(text):
        return

    show_plain_text(text)


if __name__ == "__main__":
    main()
