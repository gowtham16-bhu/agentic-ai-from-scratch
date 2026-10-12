# Chapter 42 — Voice agents

> A voice agent is the same agent you already built (an LLM, tools, memory, guardrails) with a mouth and ears
> attached, under a **hard real-time deadline**. In text, a 3-second answer is fine. On the phone, 3 seconds of
> silence makes callers say "Hello?" and talk over the agent. Voice engineering is mostly **latency, turn-taking
> and interruption**.

**You will learn:** the two architectures (the **cascade** VAD → STT → LLM → TTS, and **speech-to-speech**
models); the **latency budget** and how to cut it; **turn detection** (endpointing) and its trade-off;
**barge-in** (interruptions) and why history must hold only what the user *heard*; streaming TTS by sentence;
writing for the ear; tools and confirmations by voice; telephony (PSTN, SIP, WebRTC, codecs, transfer, DTMF,
consent); voice evals, observability and cost per minute.

**Where this fits:** uses streaming and timeouts (Ch 12), the agent loop and tools (Ch 11, 14), STT and audio
basics (Ch 41), latency and cost (Ch 03, 37), HITL handoff to a human (Ch 26, 44), guardrails (Ch 35) and
evals/tracing (Ch 33–34). The capstone (Ch 47) can add a voice channel as a stretch goal.

> **Checked against:** PyPI/README for Pipecat 1.12, LiveKit Agents 1.8.6, Silero VAD 6.2.3 and faster-whisper
> 1.2.1 (October 2026). Latency and price numbers are **rules of thumb and example values**: measure your own
> stack and use your vendors' current prices. All code in section 4 was run (it simulates audio, so it needs no
> microphone or API key).

---

## 1. The idea in plain words

A voice conversation has a rhythm. People take turns with gaps of a fraction of a second, interrupt each other,
say "uh-huh" without meaning "stop", and pause mid-sentence to think. A voice agent must:

1. **Hear**: notice speech, and decide when the user has *finished* their turn.
2. **Understand**: turn speech into text (or audio tokens).
3. **Think and act**: the normal agent loop, with tools.
4. **Speak**: start talking quickly, in short spoken sentences.
5. **Yield**: stop instantly when the user interrupts, and remember only what was actually said.

All of that within roughly **one second**, every turn.

---

## 2. Analogy

**A good phone receptionist.** They don't wait for a ten-second silence before answering, and they don't
start answering while you're mid-sentence. If they're looking something up they say "one moment, let me check"
instead of going silent. If you cut in with "no, the *other* account", they stop at once and remember that you
only heard half their sentence. They read your booking code back letter by letter. And they hand you to a
manager with a summary, so you don't repeat yourself.

---

## 3. How it works

### 3.1 Two architectures

```
Cascade:           mic → VAD → STT → [ LLM + tools ] → TTS → speaker
Speech-to-speech:  mic → [ one realtime model: audio in, audio out, can call tools ] → speaker
```

| | **Cascade (VAD → STT → LLM → TTS)** | **Speech-to-speech (realtime model)** |
|---|---|---|
| Latency | Sum of stages; needs streaming everywhere | Lower, fewer hops |
| Understanding tone, emotion, hesitation | Lost in transcription | Hears it |
| Choice of LLM | Any model, including your best tool-caller | Only the realtime model |
| Control and debugging | Every step is text you can log, test and guard | Harder: audio in, audio out |
| Guardrails | Check text before TTS speaks it | Must work on a live audio stream |
| Cost | Usually lower and predictable | Often higher per minute |
| Typical use | Business agents with tools and compliance needs | Natural conversation, companions, tutoring |

Examples of realtime models in October 2026: OpenAI Realtime, Google's Gemini Live API, AWS Nova Sonic and xAI's Grok voice agent.
The frameworks below support both styles. **Default for enterprise work: the cascade**, because you can log,
test and guard every step. Consider speech-to-speech when naturalness matters more than control, and run the
same evals on both.

**Frameworks** handle the plumbing: audio transport, VAD, streaming STT/LLM/TTS, interruption, telephony
adapters. Common open-source choices: **Pipecat** and **LiveKit Agents** (both Python). They plug in many STT,
TTS and LLM vendors, so you can swap one stage without rewriting the agent. Use a framework for production; the
toy code in section 4 is for understanding what it does.

### 3.2 The latency budget

The number that matters is **voice-to-voice latency**: from the moment the user stops speaking to the moment
they hear the first sound of the reply.

| Stage | What happens | Typical (rough) |
|---|---|---|
| **Endpointing** | Wait for enough silence to decide the turn is over | 200–800 ms |
| STT final | Final transcript after speech ends (streaming STT) | 100–300 ms |
| LLM time-to-first-token | Prompt processing + first token | 200–600 ms |
| LLM first sentence | Enough tokens for a speakable sentence | 100–300 ms |
| TTS time-to-first-audio | First audio chunk | 100–300 ms |
| Network / telephony | Audio transport both ways | 50–150 ms |

Rules of thumb: **under ~800 ms** feels responsive, **~1.2 s** is a typical first attempt, and **past ~1.5 s**
callers start talking over the agent. How to cut it:

- **Stream everything.** Speak the first sentence while the LLM writes the second (section 4.3). Without
  streaming you wait for the whole reply, often 2–3 extra seconds.
- **Smarter endpointing** (3.3) cuts the silence wait.
- **Fast first token**: a smaller or faster model for the conversational turn, a stable cached prompt prefix
  (Ch 12), short context, everything in one region, close to the phone carrier.
- **Short first sentence**: "Sure, let me check that." buys time honestly.
- **Mask slow tools**: say a filler ("One moment while I pull up your order") before a tool call that takes
  longer than about a second, and set tool timeouts.
- **Don't think out loud on the critical path**: long reasoning before the first word kills voice latency. Use
  low effort on conversational turns, and push heavy reasoning into a tool or background task.

### 3.3 Turn detection (endpointing)

**VAD (voice activity detection)** marks each 10–30 ms audio frame as speech or not (Silero VAD is a common
open-source model). **Endpointing** decides when the *turn* is over, usually after N ms of silence. The
trade-off (run section 4.2 to see it):

- **Short silence threshold** (200–300 ms): fast, but cuts people off when they pause to think ("I'd like to
  change my order… to the blue one").
- **Long threshold** (700–800 ms+): never cuts off, but every turn feels slow.

Better: **semantic turn detection**. A small model looks at the transcript so far (and sometimes the audio) and
predicts whether the user is done: "to the" is not finished; "That's all, thanks." is. Voice frameworks offer
these models; combine them with a VAD silence timer as a fallback. Also tune per use case: people reading out a
card number pause between groups of digits, so use a longer wait in that step.

### 3.4 Barge-in (interruptions)

Users interrupt. The agent must:

1. **Detect** user speech while the agent is talking. **Echo cancellation** is required so the agent doesn't
   hear its own voice and interrupt itself; telephony and WebRTC stacks provide it.
2. **Ignore backchannels.** "Uh-huh", "okay" and "right" are not interruptions. Require a minimum speech
   duration or a few words, or use the turn-detection model.
3. **Stop** TTS playback immediately and **cancel** in-flight LLM generation and queued audio.
4. **Truncate history to what was heard.** The LLM generated a full reply, but the user heard only the first
   part. If history keeps the full text, the agent "remembers" telling the user things they never heard
   ("as I said, I cancelled the replacement order"). Store the heard part plus an `[interrupted]` marker
   (section 4.4). Real systems use the TTS engine's word timestamps to know exactly where playback stopped.

A rule for actions: never let the *unspoken* part of a reply contain a side effect. If the agent planned to
"cancel the replacement order", that action happens through a tool call with confirmation, not as a sentence
cut off mid-air.

### 3.5 Writing for the ear

A good chat answer is a bad spoken answer. Put these rules in the voice agent's system prompt *and* enforce them
in code before TTS:

- **No markdown**, tables, bullets, emoji or URLs. TTS reads "asterisk asterisk" or spells out links. Offer to
  text or email links.
- **Short sentences**, one idea each. Lists of **at most three** options.
- **One question at a time.**
- **Numbers the way people say them**: "forty-two dollars", dates as words, and group long digit strings.
  Many TTS engines normalize text; test yours with your real data (amounts, SKUs, addresses).
- **Read back critical values** before acting: names, amounts, dates, codes. Spell codes with a phonetic
  alphabet ("A as in Alpha") and ask a yes/no question (section 4.5).
- **Pronunciation**: brand and product names often need a pronunciation lexicon or SSML. Check your TTS
  engine's support.
- **Persona and disclosure**: a short, consistent voice persona. Tell callers they are talking to an AI
  (required in some jurisdictions, and good practice everywhere).

### 3.6 Tools, actions and safety by voice

- **Confirm before side effects**, by reading back (3.5). Voice is error-prone: "fifteen" vs "fifty".
- **Sensitive data by keypad.** Card numbers and PINs go through **DTMF** (phone keypad tones) or a secure
  payment flow, not spoken aloud and transcribed into logs. This matters for PCI compliance.
- **Identity verification** before account actions, the same as a human agent would do (one-time code,
  knowledge checks). A voice alone is not proof of identity: voices can be cloned.
- **Escalation**: a clear path to a human. **Warm transfer** passes a summary (who, what they want, what was
  tried; see the handoff object in Ch 44) so the caller doesn't repeat everything.
- **Guardrails on text before speech**: check output with the same checks as Ch 35 before it reaches TTS.
  Once audio is spoken, you can't take it back.

### 3.7 Telephony basics

| Term | Meaning |
|---|---|
| **PSTN** | The public phone network. You reach it through a carrier or CPaaS provider (Twilio, Telnyx, Vonage, Plivo and others) |
| **SIP trunk** | The standard way to connect your system to phone numbers and contact centres |
| **WebRTC** | Real-time audio in browsers and apps: low latency, built-in echo cancellation |
| **Codec / sample rate** | Phone audio is often G.711 at **8 kHz** (narrowband), which loses detail and raises STT errors compared with 16 kHz+ wideband. Test STT on real phone audio, not studio recordings |
| **DTMF** | Keypad tones: menu choices, secure digit entry |
| **Transfer** | Cold (just connect) vs **warm** (agent briefs the human first) |
| **Voicemail / answering-machine detection** | For outbound calls: leave a message or hang up instead of talking to a recording |
| **Recording and consent** | Recording laws differ: some places need one party's consent, others everyone's. Announce recording |
| **Outbound rules** | Automated and AI-voice calls are regulated. In the US, the FCC ruled in 2024 that AI-generated voices count as "artificial" voices under robocall law, which requires prior consent. Get legal review per country |

### 3.8 Evals, observability and cost

**Evals** (Ch 33) for voice add:

- **Per-turn latency**: p50 and p95 voice-to-voice, and per stage. A p95 of 2.5 s ruins the experience even if
  p50 is fine.
- **STT quality**: WER on your real call audio, especially for names, numbers and product codes.
- **Turn-taking**: how often the agent cut the user off, and how often the user had to repeat themselves.
- **Interruption handling**: did it stop within ~200 ms, and is history truncated correctly?
- **Task success** per call, and **containment rate** (resolved without a human) next to escalation quality.
- **Simulated callers**: an LLM plays the caller (goal, persona, accent and noise added through TTS) against
  your agent at scale. Then listen to a sample of real calls every week; transcripts hide tone problems.

**Observability** (Ch 34): one trace per call, one span per turn, with child spans for endpointing, STT, LLM
(TTFT), tools and TTS (time to first audio). Store transcripts with speaker labels and timestamps. Keep audio
only with consent, with short retention and restricted access.

**Cost per minute** = STT + LLM + TTS + telephony (section 4.6). The LLM re-reads the full context *every turn*,
so long system prompts and histories add up. Use prompt caching, keep context short and summarize long calls.

---

## 4. Code

```bash
pip install numpy          # everything in this section runs offline and simulates the audio
```

### 4.1 The latency budget

```python
# latency_budget.py — where the time goes between "user stops talking" and "user hears the agent"
STAGES_MS = {                       # rough, typical ranges; measure your own stack (section 5)
    "endpointing (wait for silence)": 300,
    "STT final transcript":          150,
    "LLM time-to-first-token":       350,
    "LLM first sentence":            150,
    "TTS time-to-first-audio":       150,
    "network + telephony":           100,
}

def voice_to_voice(stages, streaming=True, full_reply_ms=2500):
    """Streaming: TTS starts on the first sentence. Not streaming: wait for the whole reply first."""
    total = sum(stages.values())
    if not streaming:
        total += full_reply_ms - stages["LLM first sentence"]
    return total

if __name__ == "__main__":
    for name, ms in STAGES_MS.items():
        print(f"  {name:<32}{ms:>6} ms")
    print(f"voice-to-voice, streaming     : {voice_to_voice(STAGES_MS):>6} ms")
    print(f"voice-to-voice, no streaming  : {voice_to_voice(STAGES_MS, streaming=False):>6} ms")
    tuned = {"endpointing (wait for silence)": 200,   # semantic turn detection allows a shorter silence wait
             "STT final transcript":          100,   # streaming STT: final arrives right after speech ends
             "LLM time-to-first-token":       200,   # small fast model, cached prompt prefix, server nearby
             "LLM first sentence":            100,   # short first sentence ("Sure — let me check.")
             "TTS time-to-first-audio":       100,   # streaming TTS
             "network + telephony":            50}   # co-locate services; same region as the phone carrier
    print(f"voice-to-voice, tuned         : {voice_to_voice(tuned):>6} ms")
```

Output:

```text
  endpointing (wait for silence)     300 ms
  STT final transcript               150 ms
  LLM time-to-first-token            350 ms
  LLM first sentence                 150 ms
  TTS time-to-first-audio            150 ms
  network + telephony                100 ms
voice-to-voice, streaming     :   1200 ms
voice-to-voice, no streaming  :   3550 ms
voice-to-voice, tuned         :    750 ms
```

### 4.2 Endpointing: the silence-threshold trade-off

A toy energy VAD on synthetic audio. The user pauses for 0.45 s mid-sentence to think.

```python
# endpointing.py — a toy energy VAD: when has the user FINISHED speaking?
import numpy as np

RATE, FRAME_MS = 16_000, 20                     # 16 kHz audio in 20 ms frames (typical for VAD)
FRAME = RATE * FRAME_MS // 1000

def synth(segments, seed=0):
    """segments: list of (seconds, is_speech). Speech = tone + noise, silence = low noise."""
    rng = np.random.default_rng(seed)
    parts = []
    for seconds, speech in segments:
        n = int(seconds * RATE)
        t = np.arange(n) / RATE
        sig = 0.01 * rng.standard_normal(n)
        if speech:
            sig += 0.3 * np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))
        parts.append(sig)
    return np.concatenate(parts)

def speech_frames(audio, threshold=0.05):
    frames = audio[: len(audio) // FRAME * FRAME].reshape(-1, FRAME)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    return rms > threshold                        # True = this 20 ms frame contains speech

def end_of_turn(is_speech, min_silence_ms):
    """Return the time (s) the turn is declared over: first run of silence >= min_silence after speech."""
    need, quiet, heard = min_silence_ms // FRAME_MS, 0, False
    for i, s in enumerate(is_speech):
        if s:
            heard, quiet = True, 0
        elif heard:
            quiet += 1
            if quiet >= need:
                return round((i + 1) * FRAME_MS / 1000, 2)
    return None

if __name__ == "__main__":
    # "I'd like to change my order ... [thinking pause 0.45 s] ... to the blue one." then silence
    audio = synth([(0.3, False), (1.2, True), (0.45, False), (0.8, True), (1.0, False)])
    frames = speech_frames(audio)
    print("user really finished at 2.75 s")
    for ms in (200, 300, 500, 800):
        t = end_of_turn(frames, ms)
        verdict = "CUT OFF mid-sentence" if t < 2.75 else f"ok, adds {int(round((t - 2.75) * 1000))} ms of waiting"
        print(f"min silence {ms:>3} ms -> turn ends at {t:.2f} s  ({verdict})")
```

Output:

```text
user really finished at 2.75 s
min silence 200 ms -> turn ends at 1.70 s  (CUT OFF mid-sentence)
min silence 300 ms -> turn ends at 1.80 s  (CUT OFF mid-sentence)
min silence 500 ms -> turn ends at 3.26 s  (ok, adds 510 ms of waiting)
min silence 800 ms -> turn ends at 3.56 s  (ok, adds 810 ms of waiting)
```

No silence threshold is both fast and safe. That is why production systems add semantic turn detection.
Production VAD is a trained model (e.g. Silero), not an energy threshold, because real noise isn't this tidy.

### 4.3 Stream sentences to TTS, written for the ear

```python
# speakable.py — turn a streaming LLM reply into speakable sentences, as early as possible
import re

def for_the_ear(text):
    """Text that's fine on screen sounds wrong spoken. Strip markdown, URLs and symbols the TTS would read aloud."""
    text = re.sub(r"https?://\S+", "the link I'll text you", text)
    text = re.sub(r"[*_#`>|]+", "", text)                   # **bold**, # headings, `code`, > quotes, | tables
    text = re.sub(r"^\s*[-•]\s+", "", text, flags=re.M)     # bullet markers
    text = text.replace("&", " and ").replace("%", " percent")
    return re.sub(r"\s+", " ", text).strip()

def sentences(token_stream, min_chars=20):
    """Yield complete sentences as soon as they end, so TTS can start speaking the first one immediately."""
    buf = ""
    for tok in token_stream:
        buf += tok
        while True:
            # first sentence end that leaves a chunk of at least min_chars ("Sure." waits for the next sentence)
            end = next((m.end() for m in re.finditer(r"[.!?]\s", buf) if m.end() >= min_chars), None)
            if end is None:
                break
            yield for_the_ear(buf[:end])
            buf = buf[end:]
    if buf.strip():
        yield for_the_ear(buf)

if __name__ == "__main__":
    reply = ("Sure. I found **order A-1043**. It shipped on Monday and should arrive by Thursday. "
             "You can track it here: https://example.com/t/A1043 - or I can text you updates. Anything else?")
    tokens = [reply[i:i + 4] for i in range(0, len(reply), 4)]   # pretend the LLM streams 4-char tokens
    for i, s in enumerate(sentences(iter(tokens)), 1):
        print(f"TTS chunk {i}: {s}")
```

Output:

```text
TTS chunk 1: Sure. I found order A-1043.
TTS chunk 2: It shipped on Monday and should arrive by Thursday.
TTS chunk 3: You can track it here: the link I'll text you - or I can text you updates.
TTS chunk 4: Anything else?
```

TTS starts speaking chunk 1 while the LLM is still writing chunk 3. Very short sentences ("Sure.") are joined
with the next one, because TTS sounds choppy on tiny fragments. Regex cleanup is a safety net: the system prompt
should already say "no markdown, no URLs".

### 4.4 Barge-in: keep only what was heard

```python
# barge_in.py — when the user interrupts, the agent's memory must hold only what the user actually HEARD
from dataclasses import dataclass

@dataclass
class Playback:
    text: str                    # the full reply the LLM generated
    chars_per_sec: float = 15.0  # speaking rate; real systems use word timestamps from the TTS engine

    def heard_until(self, seconds_played):
        cut = int(seconds_played * self.chars_per_sec)
        if cut >= len(self.text):
            return self.text
        space = self.text.rfind(" ", 0, cut)              # don't keep half a word
        return self.text[: space if space > 0 else cut]

def on_barge_in(history, playback, seconds_played, user_words):
    """Stop TTS (caller's job), then record the TRUNCATED reply plus the interruption."""
    heard = playback.heard_until(seconds_played)
    history.append({"role": "assistant", "content": heard + " [interrupted by user]"})
    history.append({"role": "user", "content": user_words})
    return history

if __name__ == "__main__":
    reply = ("Your refund of 42 dollars will go back to the card ending 1881 within five business days, "
             "and I've also cancelled the replacement order so you won't be charged twice.")
    history = [{"role": "user", "content": "I want a refund for the broken lamp."}]
    on_barge_in(history, Playback(reply), seconds_played=4.0, user_words="Wait, use store credit instead.")
    for m in history:
        print(f"{m['role']:>9}: {m['content']}")
```

Output:

```text
     user: I want a refund for the broken lamp.
assistant: Your refund of 42 dollars will go back to the card ending [interrupted by user]
     user: Wait, use store credit instead.
```

The user never heard "I've also cancelled the replacement order", so the agent must not assume they know it,
and that cancellation should have been a confirmed tool call anyway (3.4).

### 4.5 Read back critical values

```python
# readback.py — confirm critical values by voice: spell codes, group digits, ask yes/no
NATO = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                "Alpha Bravo Charlie Delta Echo Foxtrot Golf Hotel India Juliett Kilo Lima Mike November Oscar "
                "Papa Quebec Romeo Sierra Tango Uniform Victor Whiskey X-ray Yankee Zulu".split()))
DIGITS = "zero one two three four five six seven eight nine".split()

def spell(code):
    out = []
    for ch in code.upper():
        if ch.isalpha():
            out.append(f"{ch} as in {NATO[ch]}")
        elif ch.isdigit():
            out.append(DIGITS[int(ch)])
    return ", ".join(out)

def confirm(action, code):
    return f"Just to confirm: {action} for order {spell(code)}. Is that right?"

if __name__ == "__main__":
    print(confirm("a refund of 42 dollars", "A-1043"))
```

Output:

```text
Just to confirm: a refund of 42 dollars for order A as in Alpha, one, zero, four, three. Is that right?
```

### 4.6 Cost per call minute

```python
# voice_cost.py — cost per call minute for a cascaded voice agent (EXAMPLE prices: replace with your quotes)
PRICES = {
    "stt_per_min": 0.006,          # streaming speech-to-text, $ per audio minute
    "llm_in_per_mtok": 1.00,       # $ per million input tokens (cached prefix makes this much lower)
    "llm_out_per_mtok": 5.00,      # $ per million output tokens
    "tts_per_1k_chars": 0.03,      # $ per 1,000 characters spoken
    "telephony_per_min": 0.010,    # phone line, $ per minute
}

def per_minute(turns_per_min=4, context_tokens=3000, reply_tokens=60, chars_per_reply=250, p=PRICES):
    stt = p["stt_per_min"]
    # every turn re-sends the whole context (system prompt + tools + history): input tokens dominate
    llm = turns_per_min * (context_tokens * p["llm_in_per_mtok"] + reply_tokens * p["llm_out_per_mtok"]) / 1e6
    tts = turns_per_min * chars_per_reply / 1000 * p["tts_per_1k_chars"]
    tel = p["telephony_per_min"]
    return {"stt": stt, "llm": llm, "tts": tts, "telephony": tel, "total": stt + llm + tts + tel}

if __name__ == "__main__":
    for name, kw in [("short context", {}), ("long context (10k tokens)", {"context_tokens": 10_000})]:
        c = per_minute(**kw)
        print(f"{name:<26}" + "  ".join(f"{k} ${v:.4f}" for k, v in c.items()))
    print(f"5-minute call, short context: ${5 * per_minute()['total']:.3f}")
```

Output (example prices):

```text
short context             stt $0.0060  llm $0.0132  tts $0.0300  telephony $0.0100  total $0.0592
long context (10k tokens) stt $0.0060  llm $0.0412  tts $0.0300  telephony $0.0100  total $0.0872
5-minute call, short context: $0.296
```

Compare with the cost of a human-handled call to build the business case (Ch 45). Then add the costs this
script ignores: escalations, failed calls and engineering time.

---

## 5. Production view

| Concern | What to do |
|---|---|
| **Latency** | Stream every stage; measure p95 per stage; co-locate services; fast model for chat turns; fillers before slow tools |
| **Turn-taking** | VAD + semantic turn detection; longer waits for digit entry; ignore backchannels |
| **Interruptions** | Echo cancellation; stop TTS and cancel generation at once; truncate history to the heard text |
| **Speech output** | No markdown or URLs; short sentences; number formatting; pronunciation lexicon; AI disclosure |
| **Actions** | Read-back confirmation; DTMF for card numbers and PINs; identity verification; warm transfer with a summary |
| **Telephony** | Test on 8 kHz phone audio; voicemail detection for outbound; recording consent; outbound-call rules |
| **Reliability** | Fallback STT/TTS vendors behind an adapter; if the LLM fails, apologize and transfer instead of going silent |
| **Evals** | Simulated callers at scale; WER on real audio; latency percentiles; interruption tests; weekly listening sessions |
| **Cost** | Per-minute model; prompt caching; short context; summarize long calls |
| **Privacy** | Consent; short audio retention; redact PII in transcripts; restricted access |

---

## 6. Common mistakes

- Building a text agent, then bolting TTS onto non-streaming output: 3–4 s of silence every turn.
- A fixed 200 ms silence threshold that cuts off every caller who pauses to think.
- Keeping the full generated reply in history after an interruption.
- Letting the model speak markdown, URLs or long lists.
- Taking card numbers by voice, so they end up in transcripts and logs.
- Testing only with clean headset audio and launching on noisy phone lines.
- Measuring average latency and ignoring p95.
- No human escalation path, or a cold transfer that makes callers start over.

---

## 7. Practice

**Level 1**
1. Run `endpointing.py`, then change the mid-sentence pause to 0.7 s. Which thresholds now cut the user off?
2. Add three rules to `for_the_ear`: currency ("$42.50" → "42 dollars and 50 cents"), "e.g." and percentages
   with decimals. Test them with `sentences()`.

**Level 2**
3. Build a push-to-talk voice loop on your laptop: record → faster-whisper (Ch 41) → your Ch 14 agent → any
   local TTS. Log the time of each stage per turn and compute p50/p95 over 20 turns.
4. Add barge-in to that loop: while TTS plays, a key press means "user interrupted". Stop playback, truncate
   history with `on_barge_in` and continue.

**Level 3**
5. Build a phone-capable agent with Pipecat or LiveKit Agents: order status by phone with DTMF entry of the
   order number, read-back confirmation, filler before a slow tool, warm transfer with a summary, and a
   simulated-caller eval (20 scripted callers, with noise) reporting task success, p95 latency and cut-off
   rate.

---

## 8. Check yourself

1. Name the stages of the cascade and one advantage it has over speech-to-speech.
2. What is voice-to-voice latency, and roughly what target should you aim for?
3. Why do short silence thresholds cause problems, and what is the better approach?
4. After a barge-in, what must the conversation history contain and why?
5. Why stream the reply to TTS sentence by sentence?
6. Why should card numbers be entered by keypad?
7. What does a warm transfer include?

<details>
<summary>Answers</summary>

1. VAD → STT → LLM (with tools) → TTS. Advantages: any LLM, every step is loggable and testable text,
   guardrails can check text before it's spoken, often cheaper.
2. The time from when the user stops speaking to when they hear the first audio of the reply. Aim for under
   ~800 ms; past ~1.5 s people talk over the agent.
3. People pause mid-sentence; a short threshold ends their turn early and the agent talks over them.
   Semantic turn detection predicts whether the utterance is complete, with a silence timer as a fallback.
4. Only the part of the reply the user actually heard, plus an interruption marker. Otherwise the agent
   believes it told the user things they never heard.
5. TTS can start on the first sentence while the LLM is still generating the rest, cutting seconds of
   latency.
6. Spoken numbers get transcribed into logs and traces (a PCI and privacy problem), and STT can mishear
   digits. DTMF keeps them out of transcripts and is exact.
7. A summary for the human (who the caller is, what they want, what was tried, relevant IDs), so the caller
   doesn't repeat themselves.

</details>

---

## 9. Key terms

**cascade (VAD → STT → LLM → TTS)** · **speech-to-speech / realtime model** · **voice-to-voice latency** ·
**time to first audio** · **VAD** · **endpointing** · **semantic turn detection** · **backchannel** ·
**barge-in** · **echo cancellation** · **writing for the ear** · **read-back confirmation** · **DTMF** ·
**PSTN / SIP / WebRTC** · **narrowband (8 kHz)** · **warm transfer** · **answering-machine detection** ·
**containment rate** · **simulated callers** · **cost per minute**

Next: [Chapter 43 — Code, coding and computer-use agents →](43-code-and-computer-use-agents.md)
