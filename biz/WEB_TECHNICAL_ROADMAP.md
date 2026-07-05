# md2book Web App — Technical Roadmap

## Architecture Overview

### Frontend
- **React** with **CodeMirror** for the markdown editor (left pane)
- **`converter.ts`** runs client-side for live preview (right pane) — no server round-trips needed for preview
- Future: migrate left pane toward a "sort-of WYSIWYG" experience (headers/bold/italic rendered inline) using ProseMirror

### Backend
- **FastAPI** (Python), reusing `md2book.py` directly for HTML generation
- **Firebase Auth** (Google OAuth) — JWTs verified in FastAPI middleware
- **Playwright for Python** drives headless Chrome for PDF generation

### PDF Generation
```python
from playwright.sync_api import sync_playwright

def html_to_pdf(html: str) -> bytes:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        pdf = page.pdf(format="Letter", print_background=True)
        browser.close()
    return pdf
```

`md2book.py` produces the HTML → `html_to_pdf()` converts it → bytes streamed to browser. Minimal new code.

### Storage
- **S3** for file content (markdown source)
- **DynamoDB** for metadata (user ID, file name, created/modified timestamps, S3 key, tier)

### Infrastructure
- **ECS on EC2** (or plain EC2), Ubuntu 24.04
- Chrome and its dependencies baked into a Docker image (`playwright install chromium`)
- Reproducible, no cold starts, no Lambda size constraints

---

## Tier Model

| Feature | Free | Paid |
|---|---|---|
| Live preview | Yes | Yes |
| Saved files | ~3 | Unlimited |
| PDF download | No | Yes |

- Free tier: preview only, limited saved files — drives conversion
- Paid tier: flat monthly rate, PDF downloads, unlimited files
- Abuse throttling: deferred (add later once usage patterns are visible)

---

## Auth Flow

1. Browser authenticates via Firebase Auth (Google OAuth)
2. Firebase issues a signed JWT (ID token)
3. JWT sent in `Authorization: Bearer` header on API requests
4. FastAPI middleware verifies token against Google's public keys using `firebase-admin`
5. Firebase UID used as partition key throughout DynamoDB

---

## PDF Request Flow

1. Client sends markdown source + auth token to `POST /export/pdf`
2. FastAPI verifies JWT, checks user tier (paid only)
3. `md2book.py` generates HTML
4. Playwright/Chrome renders HTML and prints to PDF
5. PDF bytes streamed back to browser as a download

---

## Deferred / Future Work

- Payment integration (Stripe)
- Usage tracking and abuse throttling
- Left-pane WYSIWYG upgrade (ProseMirror)
- Multi-file book assembly (already in `md2book.py`, expose via UI later)
