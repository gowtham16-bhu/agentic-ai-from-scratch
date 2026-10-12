# Chapter 21 — Document and multimodal RAG

> Enterprise knowledge lives in PDFs, scans, slides, spreadsheets and diagrams — not in
> clean `.txt` files. **Parsing quality caps RAG quality**: if a table is flattened into
> word soup or a scanned page is never OCR'd, no retriever or model can recover it.

**You will learn:** why documents are hard (layout, reading order, tables, scans, charts),
the parsing toolbox (PyMuPDF, pdfplumber, Docling, Unstructured, OCR engines, cloud document
AI, vision-language models), **per-page routing**, representing tables and images for
retrieval, metadata extraction at ingestion, **visual retrieval** with ColPali-style models,
multimodal embeddings, and how to evaluate parsing.

**Where this fits:** builds on RAG (Ch 17–18), structured output (Ch 10) and image token costs
(Ch 02). Tree navigation of long documents (Ch 19) depends on good structure extraction;
ingestion at scale is Ch 23; multimodal models as an interface (vision in, charts out) are Ch 41.

---

## 1. The idea in plain words

RAG pipelines quietly assume text. Real documents break that assumption:

| Document problem | What goes wrong if you just "extract text" |
|---|---|
| **Multi-column layout** | Lines from two columns get interleaved — sentences become nonsense |
| **Headers, footers, page numbers** | Repeated junk in every chunk; pollutes embeddings |
| **Tables** | Rows and columns flattened into a stream of numbers; header meaning lost |
| **Scanned pages / photos** | No text layer at all — the page is *empty* to a text extractor |
| **Charts, diagrams, screenshots** | The information exists only visually |
| **Footnotes, sidebars, callouts** | Inserted mid-sentence or lost |
| **Forms** | Field labels separated from their values |
| **Slides** | Fragmented bullets; meaning is in the layout and images |

So document RAG adds a serious **ingestion** stage: detect what each page is, extract it with the
right tool, and turn it into clean, structured, retrievable units with metadata.

---

## 2. Analogy

**Photocopying vs reading.** A photocopier (naive text extraction) reproduces marks on paper; it
doesn't know a table is a table or which column comes first. A careful reader (a good parser)
understands layout: "this is a heading, this is a table with these columns, this chart shows
revenue rising". Your retriever can only find what the reader wrote down.

---

## 3. How it works

### 3.1 The parsing toolbox

| Tool type | Examples | Strengths | Limits |
|---|---|---|---|
| **PDF text extraction** | PyMuPDF, pdfplumber, pypdf | Fast, cheap, exact text from digital PDFs; blocks with positions; basic table finding | No text for scans; layout/table quality varies |
| **Layout-aware parsers** | Docling, Unstructured, Marker, MinerU | Reading order, headings, tables, figures → Markdown/JSON elements | Slower; heavier dependencies |
| **OCR engines** | Tesseract, PaddleOCR | Text from scans and images; confidence scores | Errors on low quality scans; tables/layout weak |
| **Cloud document AI** | AWS Textract, Azure AI Document Intelligence, Google Document AI | Strong OCR, forms (key-value), tables at scale | Cost per page; data leaves your environment (check residency, Ch 08) |
| **Vision-language models (VLMs)** | Any capable vision model reading a page image | Understand charts, complex tables, handwriting; output Markdown directly | Cost per page (images are many tokens); can hallucinate numbers — verify |
| **Office formats** | python-docx, python-pptx, openpyxl, or the parsers above | Structure is often explicit in the file | Embedded images/charts still need vision |

### 3.2 Per-page routing

Don't send every page through the most expensive path. Decide **per page**:

```
for each page:
    text = extract_text(page)
    if len(text) is tiny and page has images        → SCANNED: OCR; if OCR confidence low → VLM
    elif page has tables                            → table extractor (keep structure) [+ VLM if complex]
    elif page has charts/figures                    → text extraction + VLM description of the figure
    else                                            → plain text extraction (cheap)
```

Mixed documents are the norm (a digital report with a scanned signature page and three charts).
Routing per page keeps costs down while handling each page properly.

### 3.3 Representing tables for retrieval

| Representation | Good for | Note |
|---|---|---|
| Markdown/HTML table in the chunk | Small tables; model reads structure well | **Repeat the header row** in every chunk if you split a table |
| **Row-as-record text** ("Product: Trail Runner; Size: 42; Price: 89.00") | Precise row lookup with embeddings/BM25 | Each row self-contained |
| **Table summary** ("Pricing table for 2026 running shoes, 40 rows, columns...") | Finding *which* table is relevant | Index the summary, return the full table |
| **Load into SQL/DataFrame** | Big tables, aggregation questions ("average price of trail shoes") | Then query, don't embed (Ch 19) |

### 3.4 Images, charts and figures

- Generate a **text description** (with a VLM) of each chart/diagram and index it — include
  numbers you can read, axes, trends, and a caption.
- Keep a link to the **original image** so the answering model (if multimodal) can look at it
  too, and so users can verify.
- **Verify numbers** read from charts when they matter — VLMs can misread values.

### 3.5 Visual retrieval: ColPali-style models

Instead of converting pages to text, **embed the page image directly**. ColPali (and successors
such as ColQwen) use a vision-language model to produce **multi-vector** embeddings of page
images (one vector per image patch, ColBERT-style late interaction, Ch 18). The query's token
vectors are matched against patch vectors.

```
indexing:   page image ──► VLM encoder ──► ~hundreds of patch vectors per page
query:      question  ──► token vectors ──► MaxSim against every page's patches ──► top pages
answering:  top page IMAGES ──► multimodal LLM ──► answer (citing page numbers)
```

| Pros | Cons |
|---|---|
| No OCR/layout pipeline; works on slides, charts, forms, visually rich pages | Multi-vector storage is large; needs GPU for indexing |
| Captures visual information text extraction misses | Answering needs a multimodal model (image tokens cost more) |

### 3.6 Multimodal embeddings (CLIP-style)

Models that put **images and text in the same vector space**, so "red running shoe" retrieves
product photos. Useful for product catalogs, image search, and mixed media collections.

### 3.7 Metadata extraction at ingestion

While parsing, extract metadata with structured output (Ch 10): document type, title, dates
(effective, expiry), parties, product names, region, language, confidentiality. This powers
**filters** (Ch 17) and **self-query** (Ch 18): "contracts with Acme effective after 2025".

### 3.8 Evaluating parsing

Parsing errors are invisible downstream ("the answer was wrong") unless you test parsing directly:

| Check | How |
|---|---|
| Text fidelity | Compare extracted text with ground truth for 20–50 sample pages (character/word error rate) |
| Reading order | Spot-check multi-column pages |
| Table accuracy | Cell-level comparison on sample tables |
| OCR confidence | Track average confidence; route low-confidence pages to review/VLM |
| Coverage | % of pages with near-empty text (undetected scans) |

---

## 4. Code

```bash
pip install pymupdf
ollama pull llama3.2-vision        # or another vision model, e.g. a Qwen-VL variant
```

### 4.1 Per-page routing with PyMuPDF

```python
# doc_ingest.py
import pymupdf          # PyMuPDF

def classify_page(page):
    text = page.get_text("text").strip()
    tables = page.find_tables().tables
    has_images = bool(page.get_images(full=True))
    if len(text) < 30 and has_images:
        return "scanned", text, tables
    if tables:
        return "table", text, tables
    if has_images:
        return "figure", text, tables
    return "text", text, tables

def table_chunks(table, doc_id, page_no, rows_per_chunk=20):
    rows = table.extract()                         # list of rows, each a list of cell strings
    header, body = rows[0], rows[1:]
    chunks = []
    for i in range(0, len(body), rows_per_chunk):
        part = body[i:i + rows_per_chunk]
        lines = ["| " + " | ".join(str(c or "") for c in header) + " |",          # header repeated
                 "|" + "---|" * len(header)]
        lines += ["| " + " | ".join(str(c or "") for c in row) + " |" for row in part]
        records = ["; ".join(f"{h}: {c}" for h, c in zip(header, row)) for row in part]   # row-as-record
        chunks.append({"id": f"{doc_id}#p{page_no}.t{i // rows_per_chunk}", "page": page_no,
                       "kind": "table", "text": "\n".join(lines), "records": records})
    return chunks

def text_outside_tables(page, tables):
    """Page text minus the table areas, so tables aren't indexed twice as flattened word soup."""
    boxes = [pymupdf.Rect(t.bbox) for t in tables]
    blocks = page.get_text("blocks")        # (x0, y0, x1, y1, text, block_no, block_type)
    return "\n".join(b[4].strip() for b in blocks
                     if not any(pymupdf.Rect(b[:4]).intersects(box) for box in boxes)).strip()

def ingest(path, doc_id):
    doc = pymupdf.open(path)
    chunks, report = [], {"text": 0, "table": 0, "figure": 0, "scanned": 0}
    for page_no, page in enumerate(doc, start=1):
        kind, text, tables = classify_page(page)
        report[kind] += 1
        if kind == "scanned":
            page.get_pixmap(dpi=150).save(f"{doc_id}_p{page_no}.png")    # route to OCR / VLM (4.2)
            chunks.append({"id": f"{doc_id}#p{page_no}", "page": page_no, "kind": "needs_ocr",
                           "image": f"{doc_id}_p{page_no}.png", "text": ""})
            continue
        for t in tables:
            chunks += table_chunks(t, doc_id, page_no)
        if tables:
            text = text_outside_tables(page, tables)
        if text:
            chunks.append({"id": f"{doc_id}#p{page_no}", "page": page_no, "kind": kind, "text": text})
    return chunks, report

if __name__ == "__main__":
    # make a small test PDF with one text page and one table page
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "Return Policy\nDamaged items can be returned within 60 days.")
    p2 = doc.new_page()
    y = 72
    for row in [("Product", "Size", "Price"), ("Trail Runner", "42", "89.00"), ("City Walker", "40", "65.00")]:
        x = 72
        for cell in row:
            p2.insert_text((x + 4, y + 14), cell)
            p2.draw_rect(pymupdf.Rect(x, y, x + 120, y + 20))
            x += 120
        y += 20
    doc.save("sample.pdf")

    chunks, report = ingest("sample.pdf", "sample")
    print(report)
    for c in chunks:
        print(c["id"], c["kind"], "\n", c["text"][:200], "\n", c.get("records", ""))
```

### 4.2 Transcribe a page or describe a chart with a vision model

```python
# vlm_page.py
import ollama

PROMPT = """Transcribe this page into clean Markdown.
- Keep headings as #/## headings and tables as Markdown tables with header rows.
- For charts or diagrams, write a short description including axis labels and the values you can read.
- If a value is unreadable, write [unreadable] — never guess numbers."""

def transcribe(image_path, model="llama3.2-vision"):
    r = ollama.chat(model=model, options={"temperature": 0},
                    messages=[{"role": "user", "content": PROMPT, "images": [image_path]}])
    return r["message"]["content"]

# for c in chunks:
#     if c["kind"] == "needs_ocr":
#         c["text"], c["kind"] = transcribe(c["image"]), "vlm_transcribed"
```

### 4.3 Metadata extraction at ingestion

```python
# doc_metadata.py
import json
import ollama

META = {"type": "object", "properties": {
    "doc_type": {"type": "string", "enum": ["policy", "contract", "invoice", "manual", "report", "other"]},
    "title": {"type": "string"},
    "effective_date": {"type": ["string", "null"], "description": "ISO date or null"},
    "parties": {"type": "array", "items": {"type": "string"}},
    "language": {"type": "string"}},
    "required": ["doc_type", "title", "effective_date", "parties", "language"]}

def extract_metadata(first_pages_text):
    r = ollama.chat(model="llama3.2", format=META, options={"temperature": 0}, messages=[{
        "role": "user", "content": "Extract document metadata. Use null when unknown.\n\n" + first_pages_text[:6000]}])
    return json.loads(r["message"]["content"])
```

Store this metadata on every chunk of the document so retrieval can filter by it.

---

## 5. Production view

| Concern | Do |
|---|---|
| Cost per page | Route per page; VLM only where needed; cache parsed results by file hash |
| Throughput | Parse in parallel workers off a queue (Ch 23, 38); large PDFs page by page |
| Silent failures | Coverage metric (near-empty pages), OCR confidence, parse-error rate per source |
| Number accuracy | Verify table/chart numbers used in answers against the extracted table or source |
| Data residency | Cloud OCR/VLM sends documents out — confirm with the customer's security team (Ch 45) |
| Reprocessing | Version your parser; re-parse when you upgrade it; keep raw files to re-run |

---

## 6. Common mistakes

- Running plain text extraction on scanned PDFs and indexing empty pages.
- Splitting tables without repeating headers.
- Embedding huge tables instead of loading them into SQL.
- Sending every page to a VLM (slow, expensive) when 90% are plain text.
- Trusting VLM-read numbers without verification.
- No parsing eval — discovering bad extraction only through wrong answers.

---

## 7. Practice

**Level 1**
1. Run `doc_ingest.py`. Look at the table chunk: is the header present? Are the row records usable?
2. Take any real PDF you have (a bill, a product manual). Run `ingest` and read the report: how many
   pages of each kind?

**Level 2**
3. Add OCR for scanned pages (Tesseract via `pytesseract`, or the VLM in 4.2). Create a "scanned"
   test page by rendering a text page to an image and inserting the image into a new PDF.
4. Build a 10-question eval over a PDF with tables. Compare answers using (a) plain text extraction
   and (b) your table-aware chunks. Record accuracy.

**Level 3**
5. Build a parsing quality report for a folder of PDFs: per document — pages by kind, empty-page
   rate, tables found, average text length, and a sample of 3 random chunks for human review.
   Output it as a Markdown file. This is the first artifact an FDE should produce when receiving a
   customer's document dump.

---

## 8. Check yourself

1. Name four document features that break naive text extraction.
2. What is per-page routing and why does it matter for cost?
3. Give three ways to represent a table for retrieval and when to use each.
4. How does ColPali-style retrieval avoid OCR?
5. Why must numbers read by a VLM from a chart be verified?
6. How do you detect undetected scanned pages at scale?

<details>
<summary>Answers</summary>

1. Any four: multi-column layout, headers/footers, tables, scanned pages, charts/diagrams,
   footnotes/sidebars, forms.
2. Choosing the extraction method per page (text, table, OCR, VLM) based on what the page contains,
   so expensive methods are used only where needed.
3. Markdown table with header (small tables), row-as-record text (precise row lookups), a table
   summary for finding the table (with the full table returned), or loading into SQL for big tables
   and aggregations.
4. It embeds page images directly with a vision-language model into multi-vector representations
   and matches query tokens against image patches, so no text extraction is needed for retrieval.
5. VLMs can misread or hallucinate values; numbers that drive decisions need checking against a
   reliable source.
6. Track the percentage of pages with near-empty extracted text (especially those with images), and
   OCR confidence; alert on sources with high rates.

</details>

---

## 9. Key terms

**document parsing** · **reading order** · **layout analysis** · **OCR** · **document AI** ·
**vision-language model (VLM)** · **per-page routing** · **table chunking** · **row-as-record** ·
**table summary** · **figure description** · **ColPali / ColQwen** · **visual retrieval** ·
**multimodal embeddings (CLIP-style)** · **metadata extraction** · **parsing eval**

Next: [Chapter 22 — Personalization and personal knowledge →](22-personalization.md)
