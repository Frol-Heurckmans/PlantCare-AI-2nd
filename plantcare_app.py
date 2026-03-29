"""
PlantCare AI — Streamlit conversion of the React/TypeScript Figma export.
Python 3.11 | Streamlit | OpenRouter Vision (free tier)

Requirements (pip install):
    streamlit>=1.35
    requests>=2.31
    pillow>=10.0

Run:
    streamlit run plantcare_app.py

Get a FREE OpenRouter API key at: https://openrouter.ai  (no credit card needed)
Add it to .streamlit/secrets.toml next to this script:
    OPENROUTER_API_KEY = "sk-or-..."

History is persisted to  ./plantcare_history/  next to this script:
  - history.json  — metadata (result dicts) for all past scans, newest first
  - images/       — JPEG thumbnails named by scan ID
"""

import base64
import datetime
import io
import json
import os
import pathlib
import uuid

import requests
import streamlit as st
from PIL import Image

# ─── File-based persistence helpers ──────────────────────────────────────────
HISTORY_DIR   = pathlib.Path(__file__).parent / "plantcare_history"
IMAGES_DIR    = HISTORY_DIR / "images"
HISTORY_FILE  = HISTORY_DIR / "history.json"

IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _load_history_file() -> list[dict]:
    """Return history list from disk, newest first. Never raises."""
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_history_file(history: list[dict]) -> None:
    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _save_image(scan_id: str, pil_image: Image.Image) -> str:
    """Save a JPEG thumbnail and return a data-URI for in-app display."""
    thumb = pil_image.copy()
    thumb.thumbnail((600, 600))
    dest = IMAGES_DIR / f"{scan_id}.jpg"
    thumb.save(dest, format="JPEG", quality=82)
    # Also return data-URI so the UI renders without hitting the filesystem again
    buf = io.BytesIO()
    thumb.save(buf, format="JPEG", quality=82)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


def _load_image_uri(scan_id: str) -> str:
    """Return a data-URI for a previously saved scan image, or empty string."""
    path = IMAGES_DIR / f"{scan_id}.jpg"
    if not path.exists():
        return ""
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/jpeg;base64,{b64}"


def persist_scan(result: dict, pil_image: Image.Image) -> str:
    """Save result metadata + image to disk. Returns data-URI of the thumbnail."""
    scan_id   = result["id"]
    image_uri = _save_image(scan_id, pil_image)
    history   = _load_history_file()
    # Avoid duplicates if re-run
    history   = [h for h in history if h.get("id") != scan_id]
    history.insert(0, result)           # newest first
    _save_history_file(history)
    return image_uri

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PlantCare AI",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Custom CSS (mirrors the green/emerald theme from the React app) ───────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

    /* Page background */
    .stApp { background: linear-gradient(160deg, #f0fdf4 0%, #ecfdf5 100%); }

    /* Hide default Streamlit header chrome */
    #MainMenu, footer, header { visibility: hidden; }

    /* Custom header */
    .pc-header {
        background: #14532d;
        color: white;
        padding: 1rem 2rem;
        border-radius: 0 0 1rem 1rem;
        display: flex;
        align-items: center;
        gap: .75rem;
        margin-bottom: 2rem;
        font-size: 1.4rem;
        font-weight: 700;
        letter-spacing: -.5px;
    }
    .pc-header span.badge {
        margin-left: auto;
        background: #ea580c;
        font-size: .75rem;
        font-weight: 600;
        padding: .25rem .75rem;
        border-radius: 9999px;
    }

    /* Card shell */
    .pc-card {
        background: white;
        border: 2px solid #bbf7d0;
        border-radius: 1.25rem;
        padding: 1.75rem;
        box-shadow: 0 4px 24px rgba(20,83,45,.07);
        margin-bottom: 1.25rem;
    }

    /* Result header — healthy */
    .result-healthy {
        background: linear-gradient(135deg, #22c55e, #10b981);
        color: white;
        border-radius: 1rem 1rem 0 0;
        padding: 1.25rem 1.5rem;
    }
    /* Result header — sick */
    .result-sick {
        background: linear-gradient(135deg, #f97316, #ef4444);
        color: white;
        border-radius: 1rem 1rem 0 0;
        padding: 1.25rem 1.5rem;
    }
    .result-body { padding: 1.5rem; }

    /* Instruction step badge */
    .step-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.5rem;
        height: 1.5rem;
        background: #ea580c;
        color: white;
        border-radius: 9999px;
        font-size: .75rem;
        font-weight: 700;
        flex-shrink: 0;
        margin-right: .5rem;
    }

    /* How-it-works card */
    .how-card {
        background: linear-gradient(135deg, #fff7ed, #fffbeb);
        border: 2px solid #fed7aa;
        border-radius: 1.25rem;
        padding: 1.25rem 1.5rem;
    }

    /* Health score bar */
    .health-bar-bg {
        background: #dcfce7;
        border-radius: 9999px;
        height: .65rem;
        overflow: hidden;
        margin-top: .35rem;
    }
    .health-bar-fill {
        height: 100%;
        border-radius: 9999px;
        transition: width .6s ease;
    }

    /* History item */
    .hist-item {
        display: flex;
        gap: 1rem;
        align-items: flex-start;
        background: #f0fdf4;
        border: 2px solid #bbf7d0;
        border-radius: 1rem;
        padding: .9rem 1rem;
        margin-bottom: .75rem;
        cursor: pointer;
        transition: border-color .2s;
    }
    .hist-item:hover { border-color: #ea580c; }

    /* Buttons */
    div.stButton > button {
        border-radius: .75rem !important;
        font-weight: 600 !important;
        font-family: 'DM Sans', sans-serif !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Session state init (history loaded from disk once per session) ───────────
if "history_meta" not in st.session_state:
    st.session_state.history_meta = _load_history_file()
if "current_result" not in st.session_state:
    st.session_state.current_result = None
if "view" not in st.session_state:
    st.session_state.view = "home"        # "home" | "search" | "history"
if "search_result" not in st.session_state:
    st.session_state.search_result = None
if "search_query" not in st.session_state:
    st.session_state.search_query = ""


# ─── OpenRouter analysis ──────────────────────────────────────────────────────
def analyze_with_openrouter(pil_image: Image.Image) -> dict:
    """Call OpenRouter free vision models with automatic fallback on rate limit."""
    api_key = os.environ.get("OPENROUTER_API_KEY", st.secrets.get("OPENROUTER_API_KEY", ""))
    if not api_key:
        st.error("⚠️  OPENROUTER_API_KEY not set. Add it to .streamlit/secrets.toml — get one free at openrouter.ai")
        st.stop()

    # Convert image to base64 JPEG
    rgb = pil_image.convert("RGB")
    buf = io.BytesIO()
    rgb.save(buf, format="JPEG", quality=85)
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    prompt = """You are an expert botanist and plant health specialist.
Analyse the plant in this image and respond ONLY with a valid JSON object — no markdown, no extra text.

JSON schema:
{
  "plantName": "Common name",
  "scientificName": "Genus species",
  "isHealthy": true or false,
  "healthScore": integer 0-100,
  "diagnosis": "2-3 sentence assessment of the plant's condition",
  "careInstructions": ["instruction 1", "instruction 2", "instruction 3", "instruction 4"]
}

Rules:
- healthScore 80-100 = healthy, 50-79 = mild issues, below 50 = serious problems
- careInstructions: if healthy give maintenance tips; if sick give recovery steps
- Be specific, practical and concise"""

    # Try these models in order — if one is rate-limited, move to the next
    models = [
        "openrouter/free",
        "meta-llama/llama-4-scout:free",
        "google/gemma-3-12b-it:free",
        "mistralai/mistral-small-3.1-24b-instruct:free",
    ]

    last_error = None
    for model in models:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            },
            timeout=60,
        )

        # On rate limit, 404 (bad provider), or server error — try next model
        if response.status_code in (429, 503, 502, 404):
            last_error = f"Model {model} unavailable, trying next…"
            continue

        if not response.ok:
            raise RuntimeError(f"OpenRouter error {response.status_code}: {response.text}")

        raw = response.json()["choices"][0]["message"]["content"].strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        data["id"]        = str(uuid.uuid4())
        data["timestamp"] = datetime.datetime.now().isoformat(timespec="seconds")
        return data

    raise RuntimeError("All free models are currently rate-limited. Please try again in a moment.")


def search_plant(query: str) -> dict:
    """Look up a plant by name using OpenRouter. Returns structured info card."""
    api_key = os.environ.get("OPENROUTER_API_KEY", st.secrets.get("OPENROUTER_API_KEY", ""))
    if not api_key:
        st.error("⚠️  OPENROUTER_API_KEY not set.")
        st.stop()

    prompt = f"""You are an expert botanist. The user wants to learn about: "{query}"

Respond ONLY with a valid JSON object — no markdown, no extra text.

JSON schema:
{{
  "plantName": "Most common name",
  "scientificName": "Genus species",
  "found": true,
  "emoji": "a single relevant emoji for this plant",
  "shortDescription": "1-2 sentence overview of the plant",
  "careInstructions": {{
    "water": "Watering frequency and tips",
    "sunlight": "Light requirements",
    "soil": "Soil type and drainage needs",
    "difficulty": "Beginner / Intermediate / Expert"
  }},
  "natureImpact": {{
    "role": "Its role in the ecosystem (pollinator magnet, nitrogen fixer, etc.)",
    "invasive": true or false,
    "invasiveNote": "explanation if invasive, else empty string",
    "benefits": "Positive impacts on nature and environment",
    "concerns": "Any negative or harmful effects on nature, or empty string if none"
  }},
  "funFact": "One genuinely interesting or surprising fact"
}}

If the query is not a real plant, return: {{"found": false, "plantName": "{query}", "scientificName": "", "emoji": "❓", "shortDescription": "", "careInstructions": {{}}, "natureImpact": {{}}, "funFact": ""}}"""

    models = [
        "openrouter/free",
        "meta-llama/llama-4-scout:free",
        "google/gemma-3-12b-it:free",
        "mistralai/mistral-small-3.1-24b-instruct:free",
    ]

    for model in models:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        if response.status_code in (429, 503, 502, 404):
            continue
        if not response.ok:
            raise RuntimeError(f"OpenRouter error {response.status_code}: {response.text}")
        raw = response.json()["choices"][0]["message"]["content"].strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(raw)

    raise RuntimeError("All models are rate-limited. Please try again in a moment.")



# ─── UI helpers ───────────────────────────────────────────────────────────────
def render_easter_egg():
    """
    Easter egg: type 'plantdaddy' anywhere on the page (no input focused needed).
    Triggers Plant Daddy Mode — confetti explosion + funny takeover message.
    """
    import streamlit.components.v1 as components
    components.html(
        """
        <script>
        (function() {
            var secret = 'plantdaddy';
            var typed  = '';

            document.addEventListener('keydown', function(e) {
                typed += e.key.toLowerCase();
                if (typed.length > secret.length) {
                    typed = typed.slice(-secret.length);
                }
                if (typed === secret) {
                    typed = '';
                    launchPlantDaddy();
                }
            }, true);

            function launchPlantDaddy() {
                var doc = window.parent.document;

                /* ── confetti canvas ── */
                var old = doc.getElementById('pd-canvas');
                if (old) old.remove();
                var cv = doc.createElement('canvas');
                cv.id = 'pd-canvas';
                cv.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;pointer-events:none;z-index:99998';
                doc.body.appendChild(cv);
                cv.width  = window.parent.innerWidth;
                cv.height = window.parent.innerHeight;
                var ctx = cv.getContext('2d');

                var pieces = Array.from({length: 120}, function() {
                    var hue = Math.random() * 360;
                    return {
                        x:    Math.random() * cv.width,
                        y:    -20 - Math.random() * cv.height * .5,
                        w:     6  + Math.random() * 10,
                        h:     10 + Math.random() * 14,
                        color: 'hsl(' + hue + ',90%,55%)',
                        vy:   3   + Math.random() * 5,
                        vx:   (Math.random() - .5) * 4,
                        angle: Math.random() * Math.PI * 2,
                        spin:  (Math.random() - .5) * .15,
                        alpha: 1,
                    };
                });

                var DURATION = 5000;
                var start    = performance.now();

                function animConf(now) {
                    var elapsed = now - start;
                    var fade = Math.max(0, 1 - Math.max(0, elapsed - (DURATION-1000))/1000);
                    ctx.clearRect(0, 0, cv.width, cv.height);
                    pieces.forEach(function(p) {
                        p.x += p.vx; p.y += p.vy; p.angle += p.spin;
                        if (p.y > cv.height + 20) { p.y = -20; p.x = Math.random()*cv.width; }
                        ctx.save();
                        ctx.globalAlpha = fade;
                        ctx.translate(p.x, p.y);
                        ctx.rotate(p.angle);
                        ctx.fillStyle = p.color;
                        ctx.fillRect(-p.w/2, -p.h/2, p.w, p.h);
                        ctx.restore();
                    });
                    if (elapsed < DURATION) requestAnimationFrame(animConf);
                    else cv.remove();
                }
                requestAnimationFrame(animConf);

                /* ── funny popup banner ── */
                var oldBanner = doc.getElementById('pd-banner');
                if (oldBanner) oldBanner.remove();

                var banner = doc.createElement('div');
                banner.id = 'pd-banner';
                banner.innerHTML = [
                    '<div style="font-size:3rem;margin-bottom:.5rem">🌵👨‍🌾🌵</div>',
                    '<div style="font-size:1.6rem;font-weight:900;letter-spacing:-.5px">PLANT DADDY MODE</div>',
                    '<div style="font-size:.95rem;margin-top:.4rem;opacity:.9">',
                    'You are now legally responsible for every plant on Earth.<br>',
                    'Water them. ALL of them. Good luck.',
                    '</div>',
                    '<div style="font-size:.75rem;margin-top:.75rem;opacity:.6">',
                    '(type "plantdaddy" again to escape... just kidding, there is no escape)',
                    '</div>',
                ].join('');
                banner.style.cssText = [
                    'position:fixed', 'top:50%', 'left:50%',
                    'transform:translate(-50%,-50%) scale(0)',
                    'background:linear-gradient(135deg,#14532d,#166534)',
                    'color:white', 'padding:2rem 2.5rem',
                    'border-radius:1.5rem',
                    'box-shadow:0 20px 60px rgba(0,0,0,.4)',
                    'z-index:99999', 'text-align:center',
                    'font-family:DM Sans,sans-serif',
                    'max-width:420px', 'width:90vw',
                    'transition:transform .4s cubic-bezier(.34,1.56,.64,1)',
                    'pointer-events:none',
                ].join(';');
                doc.body.appendChild(banner);

                /* pop in */
                setTimeout(function() {
                    banner.style.transform = 'translate(-50%,-50%) scale(1)';
                }, 50);

                /* pop out after 4s */
                setTimeout(function() {
                    banner.style.transform = 'translate(-50%,-50%) scale(0)';
                    setTimeout(function() { banner.remove(); }, 400);
                }, 4200);
            }
        })();
        </script>
        """,
        height=1,
        scrolling=False,
    )


def render_header():
    st.markdown(
        """
        <div class="pc-header">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#ea580c"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8
                       0 5.5-4.78 10-10 10Z"/>
              <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>
            </svg>
            PlantCare AI
            <span class="badge">Powered by AI</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_falling_leaves():
    """Inject falling leaves into the parent page by accessing window.parent."""
    import streamlit.components.v1 as components
    components.html(
        """
        <script>
        (function() {
            var doc = window.parent.document;
            var old = doc.getElementById('pc-leaf-canvas');
            if (old) old.remove();

            var canvas = doc.createElement('canvas');
            canvas.id = 'pc-leaf-canvas';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;pointer-events:none;z-index:99999';
            doc.body.appendChild(canvas);
            canvas.width  = window.parent.innerWidth;
            canvas.height = window.parent.innerHeight;
            var ctx = canvas.getContext('2d');

            var DURATION = 5000;
            var start    = performance.now();
            var colors   = ['#22c55e','#16a34a','#4ade80','#86efac','#14532d','#bbf7d0','#dcfce7'];

            function drawLeaf(x, y, size, angle, color, alpha) {
                ctx.save();
                ctx.globalAlpha = alpha;
                ctx.translate(x, y);
                ctx.rotate(angle);
                ctx.beginPath();
                ctx.moveTo(0, -size);
                ctx.bezierCurveTo( size*.7,-size*.5, size*.7, size*.5, 0, size*.3);
                ctx.bezierCurveTo(-size*.7, size*.5,-size*.7,-size*.5, 0,-size);
                ctx.closePath();
                ctx.fillStyle = color;
                ctx.fill();
                ctx.strokeStyle = 'rgba(255,255,255,.3)';
                ctx.lineWidth = size * .07;
                ctx.beginPath();
                ctx.moveTo(0,-size);
                ctx.lineTo(0, size*.3);
                ctx.stroke();
                ctx.restore();
            }

            var leaves = Array.from({length: 65}, function() {
                return {
                    x:    Math.random() * canvas.width,
                    y:   -Math.random() * canvas.height,
                    size: 10 + Math.random() * 22,
                    vy:   1.5 + Math.random() * 2.5,
                    vx:   (Math.random()-.5) * 1.5,
                    angle: Math.random() * Math.PI * 2,
                    spin:  (Math.random()-.5) * .05,
                    color: colors[Math.floor(Math.random()*colors.length)],
                    alpha: .6 + Math.random() * .4,
                    wobble: Math.random() * Math.PI * 2,
                    ws:    .02 + Math.random() * .03,
                };
            });

            function animate(now) {
                var elapsed = now - start;
                var fade = Math.max(0, 1 - Math.max(0, elapsed-(DURATION-1000))/1000);
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                leaves.forEach(function(l) {
                    l.wobble += l.ws;
                    l.x += l.vx + Math.sin(l.wobble)*.9;
                    l.y += l.vy;
                    l.angle += l.spin;
                    if (l.y > canvas.height+30) { l.y=-30; l.x=Math.random()*canvas.width; }
                    drawLeaf(l.x, l.y, l.size, l.angle, l.color, l.alpha*fade);
                });
                if (elapsed < DURATION) requestAnimationFrame(animate);
                else canvas.remove();
            }
            requestAnimationFrame(animate);
        })();
        </script>
        """,
        height=1,
        scrolling=False,
    )


def render_result(result: dict, image_uri: str):
    is_healthy = result.get("isHealthy", True)
    score = result.get("healthScore", 0)

    # 🍃 Trigger falling leaves for healthy plants
    if score > 80:
        render_falling_leaves()

    header_cls = "result-healthy" if is_healthy else "result-sick"
    status_label = "Healthy Plant" if is_healthy else "Needs Attention"

    # SVG check vs alert icon
    status_icon = """
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white"
           stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
        <polyline points="22 4 12 14.01 9 11.01"/>
      </svg>""" if is_healthy else """
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white"
           stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>"""

    # SVG leaf icon for section headings
    leaf_svg = """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#14532d"
         stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline;vertical-align:middle;margin-right:.35rem">
      <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/>
      <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>
    </svg>"""

    # SVG magnifier for diagnosis
    search_svg = """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#14532d"
         stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline;vertical-align:middle;margin-right:.35rem">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>"""

    care_label = f"{leaf_svg} Maintenance Tips" if is_healthy else f"{leaf_svg} Recovery Instructions"

    st.markdown(
        f"""
        <div style="border:2px solid #bbf7d0;border-radius:1.25rem;overflow:hidden;
                    box-shadow:0 4px 24px rgba(20,83,45,.1);background:white;margin-bottom:1rem">
          <div class="{header_cls}">
            <div style="display:flex;align-items:center;gap:.6rem;font-size:1.35rem;font-weight:700">
              {status_icon}{status_label}
            </div>
            <div style="font-size:.875rem;opacity:.9;margin-top:.4rem">
              Health Score: {score}%
              <div class="health-bar-bg" style="background:rgba(255,255,255,.3)">
                <div class="health-bar-fill"
                     style="width:{score}%;background:white;opacity:.85"></div>
              </div>
            </div>
          </div>
          <div class="result-body">
            <p style="font-size:1.2rem;font-weight:700;color:#14532d;margin:0">
              {result.get('plantName','Unknown')}
            </p>
            <p style="font-style:italic;color:#6b7280;font-size:.875rem;margin:.1rem 0 1rem">
              {result.get('scientificName','')}
            </p>
            <p style="font-weight:600;color:#14532d;margin-bottom:.4rem">{search_svg} Diagnosis</p>
            <p style="color:#374151;line-height:1.6;margin-bottom:1rem">
              {result.get('diagnosis','')}
            </p>
            <p style="font-weight:600;color:#14532d;margin-bottom:.6rem">{care_label}</p>
        """,
        unsafe_allow_html=True,
    )

    for i, tip in enumerate(result.get("careInstructions", []), 1):
        st.markdown(
            f"""
            <div style="display:flex;align-items:flex-start;gap:.6rem;
                        background:#f0fdf4;border:1px solid #bbf7d0;
                        border-radius:.75rem;padding:.7rem .9rem;margin-bottom:.5rem">
              <span class="step-badge">{i}</span>
              <span style="color:#374151;font-size:.9rem;line-height:1.5">{tip}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;
                    border-top:1px solid #e5e7eb;margin-top:1rem;padding-top:1rem;text-align:center">
          <div>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#3b82f6"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                 style="margin:0 auto .3rem;display:block">
              <path d="M12 2v1M12 21v1M4.22 4.22l.7.7M19.07 19.07l.71.71
                       M2 12h1M21 12h1M4.22 19.78l.7-.71M19.07 4.93l.71-.71"/>
              <path d="M12 6a6 6 0 0 1 0 12 6 6 0 0 1 0-12z"/>
            </svg>
            <span style="font-size:.75rem;color:#6b7280">Water regularly</span>
          </div>
          <div>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#eab308"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                 style="margin:0 auto .3rem;display:block">
              <circle cx="12" cy="12" r="4"/>
              <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41
                       M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>
            </svg>
            <span style="font-size:.75rem;color:#6b7280">Bright light</span>
          </div>
          <div>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#22c55e"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                 style="margin:0 auto .3rem;display:block">
              <path d="M9.59 4.59A2 2 0 1 1 11 8H2m10.59 11.41A2 2 0 1 0 14 16H2
                       m15.73-8.27A2.5 2.5 0 1 1 19.5 12H2"/>
            </svg>
            <span style="font-size:.75rem;color:#6b7280">Good airflow</span>
          </div>
        </div>
        </div></div>
        """,
        unsafe_allow_html=True,
    )


def render_history():
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:1rem">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#14532d"
               stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
          <span style="font-size:1.3rem;font-weight:700;color:#14532d">Analysis History</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    history_meta = st.session_state.history_meta
    if not history_meta:
        st.info("No scans yet — upload a plant image to get started.")
        return

    # Delete-all button
    if st.button("🗑️ Clear all history", type="secondary"):
        _save_history_file([])
        for f in IMAGES_DIR.glob("*.jpg"):
            f.unlink(missing_ok=True)
        st.session_state.history_meta = []
        st.rerun()

    for result in history_meta:
        is_healthy = result.get("isHealthy", True)
        icon  = "✔" if is_healthy else "!"
        score = result.get("healthScore", 0)
        name  = result.get("plantName", "Unknown")
        sci   = result.get("scientificName", "")
        ts    = result.get("timestamp", "")
        sid   = result.get("id", "")

        col_img, col_info, col_btn = st.columns([1, 4, 1.2])
        with col_img:
            uri = _load_image_uri(sid)
            if uri:
                st.image(uri, width=80)
            else:
                st.markdown("🌿", unsafe_allow_html=True)
        with col_info:
            st.markdown(
                f"**{name}** {icon}  \n"
                f"*{sci}*  \n"
                f"🕐 {ts} &nbsp;|&nbsp; "
                f"<span style='background:{'#dcfce7' if is_healthy else '#ffedd5'};"
                f"color:{'#166534' if is_healthy else '#9a3412'};"
                f"padding:.15rem .5rem;border-radius:9999px;font-size:.8rem'>"
                f"{score}% Health</span>",
                unsafe_allow_html=True,
            )
        with col_btn:
            if st.button("View", key=f"hist_{sid}"):
                image_uri = _load_image_uri(sid)
                st.session_state.current_result = {"result": result, "image_uri": image_uri}
                st.session_state.view = "main"
                st.rerun()
        st.divider()


def render_search_result(data: dict):
    """Render a plant info card from search_plant() result."""
    if not data.get("found", True):
        st.markdown(
            f"""<div class="pc-card" style="text-align:center;padding:2rem">
              <div style="font-size:3rem;margin-bottom:.75rem">&#10067;</div>
              <h3 style="color:#14532d;margin:0 0 .5rem">Plant not found</h3>
              <p style="color:#6b7280">We couldn&#39;t find <strong>{data.get("plantName","")}</strong>.
              Try a different name or spelling.</p>
            </div>""",
            unsafe_allow_html=True,
        )
        return

    care    = data.get("careInstructions", {})
    nature  = data.get("natureImpact", {})
    diff    = care.get("difficulty", "")
    diff_color = {"Beginner": "#16a34a", "Intermediate": "#d97706", "Expert": "#dc2626"}.get(diff, "#6b7280")
    invasive   = nature.get("invasive", False)

    # ── Header ──
    st.markdown(
        f"""<div style="border:2px solid #bbf7d0;border-radius:1.25rem;overflow:hidden;
                        box-shadow:0 4px 24px rgba(20,83,45,.1);background:white;margin-bottom:.5rem">
          <div style="background:linear-gradient(135deg,#14532d,#166534);color:white;padding:1.5rem;">
            <div style="font-size:2.5rem;margin-bottom:.4rem">{data.get("emoji","&#127807;")}</div>
            <div style="font-size:1.4rem;font-weight:800">{data.get("plantName","")}</div>
            <div style="font-style:italic;opacity:.85;font-size:.9rem">{data.get("scientificName","")}</div>
            <div style="margin-top:.6rem;font-size:.9rem;opacity:.9;line-height:1.5">{data.get("shortDescription","")}</div>
          </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── Difficulty badge ──
    st.markdown(
        f"""<div style="margin:.75rem 0">
          <span style="background:{diff_color};color:white;padding:.3rem .85rem;
                       border-radius:9999px;font-size:.85rem;font-weight:700">{diff} difficulty</span>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── Care instructions header ──
    st.markdown(
        """<p style="font-weight:700;color:#14532d;margin:.75rem 0 .5rem;font-size:1rem">
          &#127807; Care Instructions</p>""",
        unsafe_allow_html=True,
    )

    # ── Care tiles — use Streamlit columns so they always render correctly ──
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f"""<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:.9rem;
                            padding:.9rem;text-align:center;height:100%">
              <div style="font-weight:700;font-size:.75rem;color:#1d4ed8;margin-bottom:.4rem">&#128167; WATER</div>
              <div style="font-size:.82rem;color:#374151;line-height:1.5">{care.get("water","—")}</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:.9rem;
                            padding:.9rem;text-align:center;height:100%">
              <div style="font-weight:700;font-size:.75rem;color:#a16207;margin-bottom:.4rem">&#9728; SUNLIGHT</div>
              <div style="font-size:.82rem;color:#374151;line-height:1.5">{care.get("sunlight","—")}</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""<div style="background:#faf5ff;border:1px solid #e9d5ff;border-radius:.9rem;
                            padding:.9rem;text-align:center;height:100%">
              <div style="font-weight:700;font-size:.75rem;color:#7e22ce;margin-bottom:.4rem">&#127807; SOIL</div>
              <div style="font-size:.82rem;color:#374151;line-height:1.5">{care.get("soil","—")}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    # ── Nature impact header ──
    st.markdown(
        """<p style="font-weight:700;color:#14532d;margin:1.25rem 0 .5rem;font-size:1rem">
          &#127758; Impact on Nature</p>""",
        unsafe_allow_html=True,
    )

    # ── Invasive warning ──
    if invasive:
        st.markdown(
            f"""<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:.75rem;
                            padding:.75rem;margin-bottom:.5rem;font-size:.875rem;color:#991b1b">
              <strong>&#9888; Invasive species</strong> — {nature.get("invasiveNote","")}
            </div>""",
            unsafe_allow_html=True,
        )

    # ── Ecosystem role ──
    st.markdown(
        f"""<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:.75rem;
                        padding:.75rem;margin-bottom:.5rem;font-size:.875rem;color:#374151">
          <strong style="color:#15803d">Ecosystem role:</strong> {nature.get("role","—")}
        </div>""",
        unsafe_allow_html=True,
    )

    # ── Benefits ──
    st.markdown(
        f"""<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:.75rem;
                        padding:.75rem;margin-bottom:.5rem;font-size:.875rem;color:#374151">
          <strong style="color:#15803d">Benefits:</strong> {nature.get("benefits","—")}
        </div>""",
        unsafe_allow_html=True,
    )

    # ── Concerns ──
    if nature.get("concerns"):
        st.markdown(
            f"""<div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:.75rem;
                            padding:.75rem;margin-bottom:.5rem;font-size:.875rem;color:#374151">
              <strong style="color:#c2410c">Concerns:</strong> {nature.get("concerns","")}
            </div>""",
            unsafe_allow_html=True,
        )

    # ── Fun fact ──
    st.markdown(
        f"""<div style="background:linear-gradient(135deg,#fff7ed,#fffbeb);
                        border:2px solid #fed7aa;border-radius:.9rem;
                        padding:1rem;margin-top:.75rem;margin-bottom:1.5rem">
          <p style="font-weight:700;color:#92400e;margin:0 0 .35rem;font-size:.875rem">&#127381; Did you know?</p>
          <p style="color:#374151;font-size:.875rem;line-height:1.5;margin:0">{data.get("funFact","")}</p>
        </div>""",
        unsafe_allow_html=True,
    )


def render_search_view():
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:1.25rem">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#14532d"
               stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <span style="font-size:1.3rem;font-weight:700;color:#14532d">Plant Library</span>
        </div>
        <p style="color:#6b7280;font-size:.9rem;margin-bottom:1.25rem">
          Search any plant to get care instructions and its impact on nature.
        </p>
        """,
        unsafe_allow_html=True,
    )

    search_col, btn_col = st.columns([5, 1])
    with search_col:
        query = st.text_input(
            "Search",
            value=st.session_state.search_query,
            placeholder="e.g. Monstera, Lavender, Japanese Knotweed...",
            label_visibility="collapsed",
            key="search_input",
        )
    with btn_col:
        search_clicked = st.button("Search", use_container_width=True, type="primary", key="search_btn")

    if search_clicked and query.strip():
        st.session_state.search_query = query.strip()

        # 🥚 Easter egg — searching "plantdaddy" triggers Plant Daddy Mode
        if query.strip().lower().replace(" ", "") == "plantdaddy":
            st.session_state.search_result = {"_easter_egg": True}
            st.rerun()

        with st.spinner(f"Looking up {query.strip()}..."):
            try:
                result = search_plant(query.strip())
                st.session_state.search_result = result
                st.rerun()
            except Exception as exc:
                st.error(f"Search failed: {exc}")

    if st.session_state.search_result:
        # 🥚 Render easter egg if triggered
        if st.session_state.search_result.get("_easter_egg"):
            import streamlit.components.v1 as components
            st.markdown(
                """
                <div style="background:linear-gradient(135deg,#14532d,#166534);
                            border-radius:1.25rem;padding:2rem;text-align:center;
                            color:white;margin-bottom:1rem;
                            box-shadow:0 8px 32px rgba(20,83,45,.3)">
                  <div style="font-size:4rem;margin-bottom:.75rem">🌵👨‍🌾🌵</div>
                  <div style="font-size:1.8rem;font-weight:900;letter-spacing:-.5px;
                              margin-bottom:.5rem">PLANT DADDY MODE</div>
                  <div style="font-size:1rem;opacity:.9;line-height:1.7;margin-bottom:1rem">
                    Congratulations. You have found the secret.<br>
                    You are now legally responsible for every plant on Earth.<br>
                    <strong>Water them. ALL of them. Good luck.</strong>
                  </div>
                  <div style="font-size:.8rem;opacity:.6">
                    Scientific name: <em>Daddius planticus maximus</em>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            # Difficulty: Extreme
            st.markdown(
                """<div style="margin:.5rem 0 1rem">
                  <span style="background:#7c3aed;color:white;padding:.3rem .85rem;
                               border-radius:9999px;font-size:.85rem;font-weight:700">
                    &#128293; Extreme difficulty
                  </span>
                </div>""",
                unsafe_allow_html=True,
            )
            # Care tiles
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(
                    """<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:.9rem;
                                    padding:.9rem;text-align:center">
                      <div style="font-weight:700;font-size:.75rem;color:#1d4ed8;margin-bottom:.4rem">
                        &#128167; WATER
                      </div>
                      <div style="font-size:.82rem;color:#374151;line-height:1.5">
                        Every plant on Earth, twice a day. You signed up for this.
                      </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    """<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:.9rem;
                                    padding:.9rem;text-align:center">
                      <div style="font-weight:700;font-size:.75rem;color:#a16207;margin-bottom:.4rem">
                        &#9728; SUNLIGHT
                      </div>
                      <div style="font-size:.82rem;color:#374151;line-height:1.5">
                        Relocate the sun if needed. The plants come first.
                      </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(
                    """<div style="background:#faf5ff;border:1px solid #e9d5ff;border-radius:.9rem;
                                    padding:.9rem;text-align:center">
                      <div style="font-weight:700;font-size:.75rem;color:#7e22ce;margin-bottom:.4rem">
                        &#127807; SOIL
                      </div>
                      <div style="font-size:.82rem;color:#374151;line-height:1.5">
                        Only the finest. Sourced from the tears of other plant daddies.
                      </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
            st.markdown(
                """<div style="background:linear-gradient(135deg,#fff7ed,#fffbeb);
                                border:2px solid #fed7aa;border-radius:.9rem;
                                padding:1rem;margin-top:.75rem;margin-bottom:1rem">
                  <p style="font-weight:700;color:#92400e;margin:0 0 .35rem;font-size:.875rem">
                    &#127381; Did you know?
                  </p>
                  <p style="color:#374151;font-size:.875rem;line-height:1.5;margin:0">
                    There are over 390,000 known plant species on Earth.
                    As Plant Daddy, you are personally responsible for all of them.
                    We suggest starting with a cactus.
                  </p>
                </div>""",
                unsafe_allow_html=True,
            )
            # Launch the confetti too
            components.html(
                """
                <script>
                (function() {
                    var doc = window.parent.document;
                    var old = doc.getElementById('pd-canvas');
                    if (old) old.remove();
                    var cv = doc.createElement('canvas');
                    cv.id = 'pd-canvas';
                    cv.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;pointer-events:none;z-index:99998';
                    doc.body.appendChild(cv);
                    cv.width = window.parent.innerWidth;
                    cv.height = window.parent.innerHeight;
                    var ctx = cv.getContext('2d');
                    var pieces = Array.from({length: 140}, function() {
                        return {
                            x: Math.random()*cv.width, y: -20-Math.random()*cv.height*.5,
                            w: 6+Math.random()*10, h: 10+Math.random()*14,
                            color: 'hsl('+Math.random()*360+',90%,55%)',
                            vy: 3+Math.random()*5, vx: (Math.random()-.5)*4,
                            angle: Math.random()*Math.PI*2, spin: (Math.random()-.5)*.15,
                        };
                    });
                    var start = performance.now();
                    var DURATION = 6000;
                    function anim(now) {
                        var e = now-start;
                        var fade = Math.max(0,1-Math.max(0,e-(DURATION-1000))/1000);
                        ctx.clearRect(0,0,cv.width,cv.height);
                        pieces.forEach(function(p) {
                            p.x+=p.vx; p.y+=p.vy; p.angle+=p.spin;
                            if(p.y>cv.height+20){p.y=-20;p.x=Math.random()*cv.width;}
                            ctx.save(); ctx.globalAlpha=fade;
                            ctx.translate(p.x,p.y); ctx.rotate(p.angle);
                            ctx.fillStyle=p.color;
                            ctx.fillRect(-p.w/2,-p.h/2,p.w,p.h);
                            ctx.restore();
                        });
                        if(e<DURATION) requestAnimationFrame(anim); else cv.remove();
                    }
                    requestAnimationFrame(anim);
                })();
                </script>
                """,
                height=1,
                scrolling=False,
            )
        else:
            render_search_result(st.session_state.search_result)


# ─── Main render ──────────────────────────────────────────────────────────────
render_header()
render_easter_egg()   # 🥚 always listening for "plantdaddy"

# ── Style the tabs to match the app theme ─────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Tab container ── */
    div[data-baseweb="tab-list"] {
        gap: .3rem !important;
        background: transparent !important;
        border-bottom: 2px solid #bbf7d0 !important;
        margin-bottom: 1.5rem !important;
    }

    /* ── Every tab — target by ALL possible Streamlit selectors ── */
    div[data-baseweb="tab-list"] button,
    div[data-baseweb="tab-list"] [role="tab"],
    button[data-baseweb="tab"],
    [data-testid="stTab"] button {
        background: #e5e7eb !important;
        color: #374151 !important;
        border-radius: .75rem .75rem 0 0 !important;
        border: none !important;
        padding: .55rem 1.5rem !important;
        font-weight: 600 !important;
        font-size: .95rem !important;
        font-family: 'DM Sans', sans-serif !important;
        opacity: 1 !important;
    }

    /* ── Active tab ── */
    div[data-baseweb="tab-list"] button[aria-selected="true"],
    div[data-baseweb="tab-list"] [role="tab"][aria-selected="true"],
    [data-testid="stTab"] button[aria-selected="true"] {
        background: #14532d !important;
        color: white !important;
        opacity: 1 !important;
    }

    /* ── Hover on inactive tab ── */
    div[data-baseweb="tab-list"] button:hover,
    div[data-baseweb="tab-list"] [role="tab"]:hover {
        background: #d1fae5 !important;
        color: #14532d !important;
    }

    /* ── Hide default underline indicators ── */
    div[data-baseweb="tab-highlight"],
    div[data-baseweb="tab-border"] { display: none !important; }

    /* ── Orange primary buttons ── */
    button[kind="primary"] {
        background: #ea580c !important;
        border-color: #ea580c !important;
    }
    button[kind="primary"]:hover {
        background: #c2410c !important;
        border-color: #c2410c !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

tab_home, tab_search, tab_history = st.tabs(["Home", "Plant Library", "History"])

with tab_home:
    left_col, right_col = st.columns([1, 1], gap="large")

    with left_col:
        # Upload card
        st.markdown(
            """
            <div class="pc-card">
              <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:1.25rem">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ea580c"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8
                           0 5.5-4.78 10-10 10Z"/>
                  <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>
                </svg>
                <span style="font-weight:700;font-size:1.1rem;color:#14532d">Upload Plant Image</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Single file uploader that accepts both gallery and camera photos.
        # On mobile, the OS sheet lets the user choose "Camera" or "Photo Library".
        # CSS below makes the Browse Files button look like our two styled buttons.
        st.markdown(
            """
            <style>
            /* Hide drag-drop zone text, keep only the clickable button */
            [data-testid="stFileUploaderDropzoneInstructions"] { display:none !important; }
            [data-testid="stFileUploaderDropzone"] {
                background: transparent !important;
                border: none !important;
                padding: 0 !important;
                display: flex !important;
                justify-content: stretch !important;
            }
            [data-testid="stFileUploaderDropzone"] button {
                width: 100% !important;
                background: #ea580c !important;
                color: white !important;
                border: none !important;
                border-radius: .9rem !important;
                padding: 1rem !important;
                font-weight: 700 !important;
                font-size: 1rem !important;
                font-family: 'DM Sans', sans-serif !important;
                cursor: pointer !important;
            }
            [data-testid="stFileUploaderDropzone"] button:hover {
                background: #c2410c !important;
            }
            [data-testid="stFileUploader"] small { display:none !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )

        uploaded_file = st.file_uploader(
            "Choose an image",
            type=["jpg", "jpeg", "png", "webp"],
            label_visibility="collapsed",
            key="uploader_gallery",
        )
        camera_file = None  # camera_input removed — use phone's native camera via file picker

        # Determine active file (gallery upload takes priority over camera)
        active_file = uploaded_file or camera_file
        pil_img = None

        if active_file:
            pil_img = Image.open(active_file)
            st.markdown(
                """<div style="border-radius:.9rem;overflow:hidden;
                              border:2px dashed #bbf7d0;margin-bottom:.75rem">""",
                unsafe_allow_html=True,
            )
            st.image(pil_img, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

            if st.button("Analyse Plant", use_container_width=True, type="primary"):
                with st.spinner("Analysing your plant…"):
                    try:
                        result    = analyze_with_openrouter(pil_img)
                        image_uri = persist_scan(result, pil_img)
                        entry     = {"result": result, "image_uri": image_uri}
                        st.session_state.current_result = entry
                        st.session_state.history_meta = _load_history_file()
                        st.rerun()
                    except json.JSONDecodeError:
                        st.error("Unexpected response from AI. Please try again.")
                    except Exception as exc:
                        st.error(f"Analysis failed: {exc}")
        else:
            st.markdown(
                "<p style='color:#6b7280;font-size:.875rem;text-align:center;"
                "margin-top:.25rem'>Upload or take a photo of your plant to get started</p>",
                unsafe_allow_html=True,
            )

        # How it works card
        st.markdown(
            """
            <div class="how-card">
              <p style="font-weight:700;color:#14532d;margin-bottom:.5rem;display:flex;align-items:center;gap:.4rem">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#ea580c"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8
                           0 5.5-4.78 10-10 10Z"/>
                  <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>
                </svg>
                How it works
              </p>
              <ul style="margin:0;padding-left:1.1rem;color:#374151;font-size:.875rem;line-height:1.9">
                <li>Upload a clear photo of your plant</li>
                <li>AI identifies the species and health status</li>
                <li>Get personalised care or recovery instructions</li>
              </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right_col:
        current = st.session_state.current_result
        if current:
            render_result(current["result"], current["image_uri"])
        else:
            st.markdown(
                """
                <div class="pc-card" style="min-height:300px;display:flex;flex-direction:column;
                            align-items:center;justify-content:center;text-align:center">
                  <div style="background:#dcfce7;border-radius:9999px;width:5rem;height:5rem;
                              display:flex;align-items:center;justify-content:center;margin-bottom:1rem">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#14532d"
                         stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8
                               0 5.5-4.78 10-10 10Z"/>
                      <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>
                    </svg>
                  </div>
                  <h3 style="color:#14532d;margin:0 0 .5rem">Ready to analyse your plant</h3>
                  <p style="color:#6b7280;font-size:.9rem;max-width:280px">
                    Upload an image to get instant AI-powered identification
                    and health insights.
                  </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

with tab_search:
    render_search_view()

with tab_history:
    render_history()


# ─── OPTIONAL: swap in Supabase backend ───────────────────────────────────────
# Replace `analyze_with_claude()` with something like:
#
# import requests, os
# SUPABASE_PROJECT_ID = os.environ["SUPABASE_PROJECT_ID"]
# SUPABASE_ANON_KEY   = os.environ["SUPABASE_ANON_KEY"]
# API_BASE = f"https://{SUPABASE_PROJECT_ID}.supabase.co/functions/v1/make-server-3c18dd01"
#
# def analyze_with_supabase(pil_image):
#     buf = io.BytesIO()
#     pil_image.save(buf, format="JPEG")
#     buf.seek(0)
#     r = requests.post(
#         f"{API_BASE}/analyze-plant",
#         headers={"Authorization": f"Bearer {SUPABASE_ANON_KEY}"},
#         files={"image": ("plant.jpg", buf, "image/jpeg")},
#         timeout=30,
#     )
#     r.raise_for_status()
#     return r.json()
