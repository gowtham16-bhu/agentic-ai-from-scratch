# Chapter 41 — Multimodal

> Modern models can **look** at images, screenshots, scanned pages and video frames, and can **listen** through
> speech-to-text. Making them *produce* exact visuals is a different job: that belongs to **code**. Multimodal
> work is mostly the same agent engineering you already know, plus three new things: **image tokens cost
> money, models misread what they see, and pictures carry private data.**

**You will learn:** how images become tokens and what that costs; preparing inputs (resolution, format,
rotation, metadata); the **crop/zoom tool** pattern; what vision models still get wrong and how to check
their work; audio input (speech-to-text, diarization, word error rate); video as sampled frames plus a
transcript; the **output routing rule** (exact visuals → code, illustrations → image generation); multimodal
evals; and privacy and injection risks that arrive inside images.

**Where this fits:** builds on tokens and cost (Ch 02–03), hallucination (Ch 07), structured output (Ch 10),
tool calling (Ch 11), caching (Ch 12) and document RAG (Ch 21, which covers PDFs, tables and page images). It
feeds voice agents (Ch 42), computer-use agents that work from screenshots (Ch 43), evals (Ch 33) and security
(Ch 35–36).

> **Checked against:** Anthropic's Claude API reference as of October 2026 (image limits, image blocks, images
> inside tool results), the Ollama Python SDK 0.6.3 (`images` on a message), Pillow, matplotlib and
> faster-whisper 1.2.1 (PyPI README). All code in section 4 was run except the two model calls and the
> speech-to-text example, which need a model download or an API key.

---

## 1. The idea in plain words

"Multimodal" means a model works with more than text. In practice there are two directions:

| Direction | What it means | How you do it |
|---|---|---|
| **In: images** (photos, screenshots, scanned pages, charts) | The model reads pixels | A **vision-language model (VLM)**: send the image in the message |
| **In: documents** | PDFs, slides, forms | Text layer when it exists, page images when it doesn't (Ch 21) |
| **In: audio** | Calls, meetings, voice notes | **Speech-to-text (STT)** → text → the LLM; or a native audio model (Ch 42) |
| **In: video** | Recordings, screen captures | **Sampled frames + a transcript**; some models accept video directly |
| **Out: exact visuals** | Charts, diagrams, tables, slides | **Code** renders them from verified data |
| **Out: illustrations** | Marketing art, mock-ups, icons | An **image-generation model** |
| **Out: speech** | Voice replies | **Text-to-speech (TTS)** (Ch 42) |

The agent loop doesn't change. What changes is cost (an image can cost as much as a few pages of text), the
kinds of mistakes (misreading small print, miscounting), and privacy (a photo can reveal where someone lives).

---

## 2. Analogy

**A sharp colleague looking at a photo on your phone.** They understand the scene instantly, but at a glance.
Small print? They need to zoom in. Forty-seven bolts? They'll estimate. A blurry digit? They'll *guess*,
confidently, unless you told them "say if you can't read it". Give them a **magnifying glass** (a crop tool),
ask them to **quote what they actually see**, and **check their arithmetic**, and they become reliable.

---

## 3. How it works

### 3.1 How an image becomes tokens

A vision model cuts the image into small square **patches** (often 14–16 pixels a side), turns each patch into
a vector with a vision encoder, and projects those vectors into the same space as text tokens. To the language
model, an image is **a block of tokens**. More pixels means more patches, so more tokens, so more cost and
latency, up to a **cap**: images larger than the model's maximum are scaled down automatically.

Facts that change fast (Claude, October 2026; check your provider's vision docs):

| Model tier | Max long edge | Max tokens per image |
|---|---|---|
| Earlier models | 1568 px | ~1,600 |
| High-resolution models (from Opus 4.7 and Sonnet 5 on; check each model) | 2576 px (3.75 MP) | ~4,784 |

On high-resolution models the coordinates the model returns map 1:1 to image pixels, which matters for crop
tools and computer use (Ch 43). Other providers use different schemes (tiles, "low/high detail" settings), and
local VLMs each handle resolution their own way. **Don't memorize formulas.** Count tokens on a few
representative images with your provider's token-counting endpoint, then budget.

A rough feel: one full page as an image costs about as much as one to three pages of text. Ten screenshots per
agent step, over thirty steps, is a context-window problem (Ch 15) before it is a vision problem.

### 3.2 Preparing the input

| Decision | Rule |
|---|---|
| **Resolution** | Send the fidelity the task needs. A receipt total reads fine at ~1000 px; a dense engineering drawing wants the maximum. Downscale *at ingestion*, once, before the first request: changing an image later breaks prompt caching (Ch 12). |
| **Format** | **PNG** for screenshots, text and diagrams (sharp edges, no artefacts); **JPEG** (quality ~85) for photos. |
| **Rotation** | Phone photos often store "rotate 90°" as a metadata flag. Apply it before stripping metadata, or the model sees a sideways image. |
| **Metadata** | Strip EXIF: it can hold GPS location, device and timestamp (privacy, 3.9). |
| **Order and labels** | Put images before the question, and label several images ("Image 1: invoice; Image 2: delivery note"). Test placement with your model. |
| **Many images** | Each one costs tokens. Send thumbnails first and let the agent ask for full-size or crops. |

### 3.3 The crop/zoom tool: the highest-leverage vision pattern

Instead of sending one huge image and hoping, give the agent a **tool** that crops a region and returns it
enlarged. The agent looks at the overview, decides where to look closer, and calls the tool, the same way a
person zooms on a phone. The heavier version is a sandbox holding the raw images plus PIL/OpenCV, so the agent
can crop, measure and verify with code (Ch 43). Anthropic's guidance for its current models (October 2026): on
dense charts, tables, filings and technical drawings, a single crop tool delivers most of the gain of that full
sandbox, and giving tools is a more cost-effective lever than raising thinking effort. Extra compute goes into
image tokens exactly where detail is needed.

Newer models also read charts and screenshots much better *without* help. Re-test old prompt scaffolding (an
OCR pre-pass, "read the axis labels step by step") when you upgrade models: some of it now hurts. Keep the
tools; drop the ceremony.

### 3.4 What vision models still get wrong

| Weakness | Example | Mitigation |
|---|---|---|
| Small or degraded text | Blurry receipt digit, 6pt footnote | Crop tool; higher resolution; allow "unreadable" |
| Counting many objects | "How many pallets?" | Count per crop/grid cell; use a detector model for exact counts |
| Precise positions and sizes | "Is the gap 2 mm?" | Measure with code in a sandbox; never trust an eyeball estimate |
| **Hallucinated content** | Reads text that isn't there, "sees" a signature | Ask for **quotes** of visible text; check against OCR or the PDF text layer (Ch 21) |
| Dense charts | Misreads bar heights | Ask for the source data instead; crop; check totals |
| Rotation, glare, handwriting | Phone photos in a warehouse | Robustness slices in evals (3.8); human review route |

The general fix is the one from Ch 07: **turn a vision answer into a claim you can check.** Totals must add up,
quoted text must exist in OCR output, IDs must exist in the database. If a check fails, re-read with the crop
tool, then send it to a human.

### 3.5 Audio in

Two paths (Ch 42 covers real-time voice):

1. **STT → text → LLM** (the default for most business work). Cheap, every step is loggable, transcripts are
   searchable and evaluable. Open-source: Whisper and faster-whisper; many hosted STT APIs.
2. **Native audio models** take audio tokens directly and hear tone, hesitation and emphasis. Better for live
   conversation; harder to log, test and audit.

What matters in production:

- **Diarization**: who said what ("Agent:" vs "Customer:"). Many decisions depend on the speaker.
- **Timestamps**: segment or word level, so answers can cite "at 12:41" and you can jump to the audio.
- **Custom vocabulary**: product names, SKUs and people's names are where STT fails. Use the engine's hint or
  hotword feature, and fix names afterwards against your catalogue (entity resolution, Ch 20).
- **Word error rate (WER)**: (substitutions + deletions + insertions) ÷ words in the reference transcript.
  Measure it on *your* audio (phone lines, accents, noise), not on a benchmark.
- **Silence and noise**: voice activity detection (VAD) skips silence, which saves cost and removes
  hallucinated words that STT models sometimes invent in long silent stretches.

### 3.6 Video in

A model "watches" video as **frames + transcript**:

1. Extract the audio → STT with timestamps.
2. Sample frames: a fixed rate (1 frame per second or per 10 seconds), or only on **scene changes**.
3. Downscale frames to what the question needs.
4. **Map-reduce** (Ch 13): describe each segment (frames + transcript slice) → combine segment notes → answer
   with timestamps.

Cost decides the design. Ten minutes at 1 fps is 600 frames, which at full size can be close to a million tokens
(section 4.5). Sample on scene changes, shrink frames, or use a model that accepts video natively (check what
sampling it does internally). Ask for **timestamped** answers so a human can check the moment.

### 3.7 Output: the routing rule

| You need | Use | Why |
|---|---|---|
| A chart, diagram, table, slide, dashboard | **Code** (matplotlib, Vega-Lite, Mermaid, HTML, spreadsheet/slide libraries) from **verified data** | Numbers and labels must be exact; code is checkable and repeatable |
| A UI mock-up you will build | Code (HTML/CSS) | It becomes the real thing |
| An illustration, mood image, icon, photo-style scene | An **image-generation model** | Aesthetics, not exactness |
| Edited photos (remove background, resize) | Image libraries or editing models | Deterministic steps first |
| Speech | TTS (Ch 42) | |

Never ask an image generator to draw a chart with numbers in it: it will draw *a picture of* a chart, with
invented values and garbled labels. The model's job for exact visuals is to write a **spec** (structured output,
Ch 10); your code checks the spec against the source data and renders it.

For generated images in production: label them as AI-generated where required, run content-safety checks on
prompts and outputs, and respect rights (no trademarked characters or real people's likeness without
permission).

### 3.8 Multimodal evals

Same discipline as Ch 33, with modality-specific data:

- **Golden set from real inputs**: the customer's actual phone photos, scans and calls, not stock images.
  Pilots fail on glare and handwriting, not on clean samples.
- **Field-level scoring** for extraction (exact match per field, numeric tolerance for amounts).
- **Robustness slices**: blurred, rotated, low-light, cropped, handwritten, non-English. Report each slice
  separately.
- **Artifact verification** for outputs: does the chart spec match the source, does the render succeed, is
  there alt text.
- **Human review** only for what code can't judge (is this illustration on-brand?).
- **Cost per item** next to accuracy: image tokens dominate the bill.

### 3.9 Privacy and security

- **Metadata**: EXIF can contain GPS coordinates. Strip it at ingestion.
- **Faces, ID cards, licence plates, screens with secrets**: redact or blur what the task doesn't need *before*
  sending. Don't build "who is this person?" features: identifying people from images is a legal and ethical
  minefield (and often refused by providers).
- **Prompt injection in pixels**: text inside an image ("ignore previous instructions and…"), including
  low-contrast text a human won't notice, is **untrusted input** exactly like a web page (Ch 35–36). An agent
  that reads screenshots must not treat their text as instructions.
- **Retention**: images and recordings are often more sensitive than text. Set shorter retention, restrict who
  can view raw media in traces (Ch 34), and log references instead of bytes.

---

## 4. Code

```bash
pip install pillow matplotlib pydantic        # all section-4 code except the model calls runs offline
```

### 4.1 Prepare images: rotate, resize, pick format, strip metadata (runs anywhere)

```python
# image_prep.py — fix rotation, resize, choose format, strip metadata, and a crop tool for vision agents
from io import BytesIO
from PIL import Image, ImageDraw, ImageOps

def prepare(img: Image.Image, max_long_edge=1568, kind="photo"):
    """Downsample to the size you actually need; PNG for screenshots/text, JPEG for photos; no EXIF."""
    img = ImageOps.exif_transpose(img)                      # apply the phone's rotation flag BEFORE dropping EXIF
    img.thumbnail((max_long_edge, max_long_edge))          # keeps aspect ratio; never upsizes
    clean = img.copy()
    clean.info = {}                                         # drop metadata (EXIF: GPS location, device, time, ...)
    buf = BytesIO()
    if kind == "screenshot":
        clean.save(buf, format="PNG")                      # sharp text, no JPEG artefacts
    else:
        clean.convert("RGB").save(buf, format="JPEG", quality=85)
    return buf.getvalue(), clean.size

def crop(img: Image.Image, box, zoom=2):
    """Agent tool: return a region (x0, y0, x1, y1) enlarged, so the model can 'look closer'."""
    region = img.crop(box)
    return region.resize((region.width * zoom, region.height * zoom), Image.LANCZOS)

if __name__ == "__main__":
    photo = Image.new("RGB", (4000, 3000), "white")         # pretend 12-megapixel phone photo of a shoe box
    d = ImageDraw.Draw(photo)
    d.rectangle((1500, 1200, 2500, 1800), outline="black", width=12)
    d.text((1600, 1300), "ORDER A-1043", fill="black")
    for long_edge in (4000, 1568, 1024):
        data, size = prepare(photo, long_edge, kind="photo")
        print(f"long edge {long_edge}: {size[0]}x{size[1]} = {size[0] * size[1] / 1e6:.1f} MP, {len(data) / 1024:.0f} KB")
    zoomed = crop(photo, (1500, 1200, 2500, 1800))
    print("crop tool output:", zoomed.size)
```

Output:

```text
long edge 4000: 4000x3000 = 12.0 MP, 195 KB
long edge 1568: 1568x1176 = 1.8 MP, 34 KB
long edge 1024: 1024x768 = 0.8 MP, 15 KB
crop tool output: (2000, 1200)
```

A test with a real EXIF block (orientation "rotate 90°" plus a GPS tag) gave: input 400×300 with GPS → output
300×400 (correctly rotated) with no EXIF tags left. Without `exif_transpose` the output would have been sideways.

### 4.2 Send an image to a model

Local, with Ollama (pull a vision-capable model first, the same one as Ch 21: `ollama pull llama3.2-vision`;
the Ollama library tags others "vision"):

```python
# vision_local.py — needs a vision model in Ollama
import ollama
from PIL import Image
from image_prep import prepare

data, _ = prepare(Image.open("receipt.jpg"), max_long_edge=1024)
resp = ollama.chat(
    model="llama3.2-vision",
    messages=[{"role": "user",
               "content": "Read this receipt. Quote the merchant name and total exactly as printed. "
                          "If a value is unreadable, say 'unreadable' instead of guessing.",
               "images": [data]}],                 # bytes, a file path, or base64 all work
)
print(resp.message.content)
```

Hosted, with the Anthropic SDK (image block first, then the question):

```python
# vision_claude.py — needs ANTHROPIC_API_KEY
import base64
import anthropic
from PIL import Image
from image_prep import prepare

data, _ = prepare(Image.open("receipt.jpg"), max_long_edge=1568)
client = anthropic.Anthropic()
msg = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                     "data": base64.standard_b64encode(data).decode()}},
        {"type": "text", "text": "Read this receipt. Quote merchant and total exactly; say 'unreadable' if unsure."},
    ]}],
)
print("".join(b.text for b in msg.content if b.type == "text"))   # skip thinking blocks
print("input tokens (includes the image):", msg.usage.input_tokens)
```

### 4.3 The crop tool, with input validation (runs anywhere)

The model's tool arguments are untrusted input (Ch 11): boxes can be swapped, negative or outside the image.

```python
# crop_tool.py — the "look closer" tool for a vision agent (tool calling, Ch 11)
import base64
from io import BytesIO
from PIL import Image

CROP_TOOL = {
    "name": "crop_image",
    "description": ("Zoom into a region of the current image to read small text or check details. "
                    "Coordinates are pixels in the image you were shown: x0,y0 = top-left, x1,y1 = bottom-right."),
    "input_schema": {
        "type": "object",
        "properties": {"x0": {"type": "integer"}, "y0": {"type": "integer"},
                       "x1": {"type": "integer"}, "y1": {"type": "integer"}},
        "required": ["x0", "y0", "x1", "y1"],
    },
}

def crop_image(img: Image.Image, x0, y0, x1, y1, max_long_edge=1568):
    """Validate the box (model output is untrusted input), crop, enlarge up to the size limit, return PNG base64."""
    clamp = lambda v, hi: min(max(0, v), hi)
    x0, x1 = sorted((clamp(x0, img.width), clamp(x1, img.width)))
    y0, y1 = sorted((clamp(y0, img.height), clamp(y1, img.height)))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return {"error": "box too small or outside the image"}
    region = img.crop((x0, y0, x1, y1))
    scale = min(4.0, max_long_edge / max(region.size))          # enlarge small regions, never past the limit
    region = region.resize((int(region.width * scale), int(region.height * scale)), Image.LANCZOS)
    buf = BytesIO()
    region.save(buf, format="PNG")
    return {"media_type": "image/png", "data": base64.standard_b64encode(buf.getvalue()).decode(), "size": region.size}

def as_claude_tool_result(tool_use_id, result):
    """Claude: images can go INSIDE the tool_result content. (Ollama: add a message with images=[...] instead.)"""
    if "error" in result:
        return {"type": "tool_result", "tool_use_id": tool_use_id, "content": result["error"], "is_error": True}
    return {"type": "tool_result", "tool_use_id": tool_use_id, "content": [
        {"type": "image", "source": {"type": "base64", "media_type": result["media_type"], "data": result["data"]}}]}

if __name__ == "__main__":
    page = Image.new("RGB", (1568, 1176), "white")
    print("normal crop :", crop_image(page, 1200, 900, 1500, 1100)["size"])
    print("swapped box :", crop_image(page, 1500, 1100, 1200, 900)["size"])
    print("outside     :", crop_image(page, 5000, 5000, 6000, 6000))
    block = as_claude_tool_result("toolu_01", crop_image(page, 0, 0, 400, 300))
    print("tool_result :", block["type"], block["content"][0]["type"], block["content"][0]["source"]["media_type"])
```

Output (the "outside" case returns an error the model can recover from):

```text
normal crop : (1200, 800)
swapped box : (1200, 800)
outside     : {'error': 'box too small or outside the image'}
tool_result : tool_result image image/png
```

Wire `CROP_TOOL` into the agent loop from Ch 14. The model looks at the overview image, calls `crop_image` on
the part it can't read, and gets the enlarged region back inside the tool result.

### 4.4 Treat extraction as a claim: check it with arithmetic (runs anywhere)

```python
# receipt_check.py — vision extraction is a CLAIM; check it with arithmetic before you trust it
from pydantic import BaseModel

class Item(BaseModel):
    name: str
    amount: float

class Receipt(BaseModel):
    merchant: str
    items: list[Item]
    subtotal: float
    tax: float
    total: float
    unreadable_fields: list[str] = []          # the model may say "I can't read this" (abstention, Ch 07)

def check(r: Receipt, tol=0.01):
    problems = []
    if abs(sum(i.amount for i in r.items) - r.subtotal) > tol:
        problems.append(f"items sum {sum(i.amount for i in r.items):.2f} != subtotal {r.subtotal:.2f}")
    if abs(r.subtotal + r.tax - r.total) > tol:
        problems.append(f"subtotal + tax {r.subtotal + r.tax:.2f} != total {r.total:.2f}")
    if r.unreadable_fields:
        problems.append(f"unreadable: {r.unreadable_fields}")
    return problems

def route(r: Receipt):
    problems = check(r)
    if not problems:
        return "accept", problems
    return "re-read with crop tool, then human review if still failing", problems

if __name__ == "__main__":
    # what a vision model returned for two photos (structured output, Ch 10)
    good = Receipt(merchant="Cafe Uno", items=[Item(name="Latte", amount=4.50), Item(name="Bagel", amount=3.25)],
                   subtotal=7.75, tax=0.62, total=8.37)
    misread = Receipt(merchant="Cafe Uno", items=[Item(name="Latte", amount=4.50), Item(name="Bagel", amount=8.25)],
                      subtotal=7.75, tax=0.62, total=8.37)        # a blurry 3 read as an 8
    for r in (good, misread):
        print(route(r))
```

Output:

```text
('accept', [])
('re-read with crop tool, then human review if still failing', ['items sum 12.75 != subtotal 7.75'])
```

The misread is invisible if you only look at the model's answer, which reads fluently. The arithmetic catches
it. Use whatever invariant your domain has: totals, dates in order, IDs that exist, quantities that match a
purchase order.

### 4.5 Exact visuals by code, verified against the source (runs anywhere)

```python
# chart_by_code.py — EXACT visuals are produced by code from data, then the artifact is VERIFIED
import json
import matplotlib
matplotlib.use("Agg")                                   # render to a file; no screen needed (servers, CI)
import matplotlib.pyplot as plt

SOURCE = {"Jan": 120, "Feb": 135, "Mar": 160}          # numbers from the system of record (DB/tool), not from the model

def verify(spec, source):
    problems = [f"{label}: chart {value} != source {source.get(label)}"
                for label, value in zip(spec["labels"], spec["values"]) if source.get(label) != value]
    if len(spec["labels"]) != len(spec["values"]):
        problems.append("labels and values have different lengths")
    return problems or ["ok"]

def render(spec, path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.bar(spec["labels"], spec["values"])
    ax.set_title(spec["title"])
    fig.savefig(path, dpi=100)
    plt.close(fig)

if __name__ == "__main__":
    # the model's job: produce a chart SPEC (structured output, Ch 10) — not pixels
    good = json.loads('{"type": "bar", "title": "Returns per month", "labels": ["Jan", "Feb", "Mar"], "values": [120, 135, 160]}')
    bad = json.loads('{"type": "bar", "title": "Returns per month", "labels": ["Jan", "Feb", "Mar"], "values": [120, 153, 160]}')
    for name, spec in (("good", good), ("bad", bad)):
        result = verify(spec, SOURCE)
        print(name, "->", result)
        if result == ["ok"]:
            render(spec, f"returns_{name}.png")
            print("   rendered", f"returns_{name}.png")
```

Output:

```text
good -> ['ok']
   rendered returns_good.png
bad -> ['Feb: chart 153 != source 135']
```

The bad spec (a transposed digit) is never drawn. In a real agent the model would fetch the numbers with a
tool, emit the spec, and `verify` would gate the render: the same "verify before act" pattern as Ch 35.

### 4.6 Estimate video cost before you build (runs anywhere)

```python
# video_plan.py — estimate the token cost of "watching" a video before you build the pipeline
def plan(minutes, frames_per_sec, tokens_per_frame, transcript_words_per_min=150, tokens_per_word=1.3):
    frames = int(minutes * 60 * frames_per_sec)
    frame_tokens = frames * tokens_per_frame
    transcript_tokens = int(minutes * transcript_words_per_min * tokens_per_word)
    return frames, frame_tokens, transcript_tokens

if __name__ == "__main__":
    print(f"{'strategy':<38}{'frames':>8}{'frame tokens':>14}{'transcript':>12}")
    for name, fps, tpf in [("1 fps, full-size frames", 1.0, 1600),
                           ("1 fps, small frames (~512 px)", 1.0, 350),
                           ("1 frame / 10 s, small", 0.1, 350),
                           ("scene changes only (~40 per 10 min)", 40 / 600, 1600)]:
        frames, ft, tt = plan(10, fps, tpf)
        print(f"{name:<38}{frames:>8}{ft:>14,}{tt:>12,}")
```

Output (tokens per frame are assumptions: measure on your provider):

```text
strategy                                frames  frame tokens  transcript
1 fps, full-size frames                    600       960,000       1,950
1 fps, small frames (~512 px)              600       210,000       1,950
1 frame / 10 s, small                       60        21,000       1,950
scene changes only (~40 per 10 min)         40        64,000       1,950
```

The transcript is almost free; the frames are the bill. Extract frames with ffmpeg, either at a fixed rate
(`ffmpeg -i talk.mp4 -vf "fps=1/10,scale=512:-1" frames/%04d.jpg`) or on scene changes
(`-vf "select='gt(scene,0.3)',scale=512:-1" -vsync vfr`).

### 4.7 Speech-to-text with timestamps (needs a model download)

```python
# transcribe.py — pip install faster-whisper   (downloads the model on first run)
from faster_whisper import WhisperModel

model = WhisperModel("small", device="cpu", compute_type="int8")        # GPU: device="cuda", compute_type="float16"
segments, info = model.transcribe("call.wav", vad_filter=True, word_timestamps=True)
print("language:", info.language, round(info.language_probability, 2))
for seg in segments:                                                     # a generator: transcription runs here
    print(f"[{seg.start:6.2f} -> {seg.end:6.2f}] {seg.text}")
```

`vad_filter=True` skips long silences. Feed the timestamped text to the LLM and ask for answers that cite the
time ("refund promised at 03:12").

---

## 5. Production view

| Concern | What to do |
|---|---|
| **Cost** | Downscale at ingestion to the needed fidelity; thumbnails first; crop on demand; count image tokens on real samples; track cost per item |
| **Latency** | Images and audio add upload and encode time; resize client-side; stream STT for live use (Ch 42) |
| **Caching** | Fix image bytes once at ingestion; a re-encoded image is a cache miss (Ch 12) |
| **Context** | Old screenshots pile up in agent history; keep images inside tool results so they can be cleared, or summarize them (Ch 15) |
| **Quality** | Checkable invariants (sums, IDs, quotes vs OCR); crop tool; human review queue for failures |
| **Evals** | Real-world golden set with robustness slices; field-level metrics; WER for audio |
| **Privacy** | Strip EXIF; blur faces/IDs not needed; short retention for raw media; restricted trace access |
| **Security** | Text in images and audio is untrusted; never follow instructions found in media |
| **Output** | Exact visuals by code from verified data; generated images labelled and safety-checked |

---

## 6. Common mistakes

- Sending 12-megapixel photos when 1 megapixel answers the question, then wondering about the bill.
- Stripping metadata without applying rotation, so the model reads every phone photo sideways.
- Trusting a fluent extraction without an invariant check.
- Asking an image generator for a chart, or letting the model type the numbers into a chart instead of
  fetching them.
- Evaluating on clean sample images and launching on blurry warehouse photos.
- Keeping every screenshot in the agent's history until the context overflows.
- Treating text inside an image as an instruction.
- Building a vision pipeline before checking whether the document has a text layer (Ch 21).

---

## 7. Practice

**Level 1**
1. Run `image_prep.py` on three of your own photos at long edges 1568 and 1024. Check the output has no EXIF
   (`Image.open(...).getexif()`) and is the right way up.
2. Run `receipt_check.py`, then add a check that the receipt date is not in the future.

**Level 2**
3. With a local vision model, extract fields from 10 real receipts or invoices into the `Receipt` model. Score
   field-level accuracy against your hand-typed answers. Which fields fail, and does the crop tool fix them?
4. Wire `CROP_TOOL` into your Ch 14 agent and give it a dense chart. Log how often it calls the tool and
   whether answers improve.

**Level 3**
5. Build a "meeting video → action items with timestamps" pipeline: ffmpeg audio + scene-change frames,
   faster-whisper transcript, map-reduce summary. Report cost per hour of video and accuracy on 3 videos you
   annotate yourself.

---

## 8. Check yourself

1. Why does a bigger image cost more, and why does that stop at some point?
2. Why apply EXIF rotation before stripping metadata?
3. What is the crop/zoom tool pattern and why does it work?
4. A vision model extracts a total that reads perfectly but is wrong. How do you catch this automatically?
5. Why should charts be produced by code, not image generation?
6. How does a model "watch" a ten-minute video, and what dominates the cost?
7. Name two security or privacy risks specific to images.

<details>
<summary>Answers</summary>

1. The image is cut into patches; each becomes tokens, so more pixels means more tokens. Above the model's
   maximum size the image is scaled down, so tokens hit a cap (e.g. ~1,600 on earlier Claude models, ~4,784 on
   high-resolution ones).
2. Phones often store rotation as a metadata flag; if you drop the flag without rotating the pixels, the image
   is sideways.
3. The agent views an overview, then calls a tool that returns a region cropped and enlarged, so it spends
   image tokens only where detail is needed, like zooming on a phone. It gives large accuracy gains on dense
   material.
4. Check an invariant: items sum to subtotal, subtotal plus tax equals total, IDs exist, quoted text appears in
   OCR. On failure, re-read with the crop tool, then route to a human.
5. Exact numbers and labels must match the data; code renders from verified data and can be checked. Image
   generators draw a picture of a chart with invented values.
6. As sampled frames plus a timestamped transcript, often processed with map-reduce. Frames dominate the cost;
   sample on scene changes and downscale.
7. Any two: EXIF GPS location; faces, IDs or secrets visible in images; prompt injection written inside images;
   long retention of raw media.

</details>

---

## 9. Key terms

**multimodal** · **vision-language model (VLM)** · **patch / image tokens** · **max long edge** ·
**downscaling at ingestion** · **EXIF / orientation** · **crop/zoom tool** · **invariant check** · **OCR** ·
**speech-to-text (STT)** · **diarization** · **word error rate (WER)** · **voice activity detection (VAD)** ·
**frame sampling / scene detection** · **map-reduce over segments** · **routing rule (code vs image generation)** ·
**chart spec** · **robustness slices** · **injection in pixels**

Next: [Chapter 42 — Voice agents →](42-voice-agents.md)
