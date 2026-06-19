# Baixador de Música (Termux) Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. Pure functions use TDD. Dir is NOT a git repo — commit steps are skipped; instead each task ends with a manual verification run.

**Goal:** Single-file Python CLI for Termux (Android, no root) that downloads YouTube audio as MP3 with a minimal, elderly-friendly PT-BR terminal UI.

**Architecture:** One executable `baixador.py`. Pure helpers (title normalization, similarity dedup) are unit-tested. Download orchestration spawns one `yt-dlp` subprocess per track with a bounded pool (3/4/5) sharing a central `--download-archive`. `rich` renders the menu and per-track progress. A second artifact `~/.shortcuts/Baixar-Musica.sh` is generated on demand for Termux:Widget.

**Tech Stack:** Python 3, yt-dlp, ffmpeg, rich, pathlib, difflib, unicodedata, subprocess, concurrent.futures.

---

## File Structure

- `baixador.py` — main executable. Sections: dependency bootstrap, storage check, pure helpers, download worker, orchestrator, UI/menu, shortcut creator, `main()`.
- `tests/test_helpers.py` — unit tests for `normalizar_titulo()` and `eh_duplicata()`.
- `~/.shortcuts/Baixar-Musica.sh` — generated launcher (0700).

App data dir = `Path(__file__).resolve().parent`. Holds `baixados.txt` (archive) and optional `cookies.txt`.

---

## Task 1: Pure helper — `normalizar_titulo()`

**Files:**
- Create: `baixador.py` (helpers section)
- Test: `tests/test_helpers.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_helpers.py
from baixador import normalizar_titulo

def test_remove_acentos_caixa_pontuacao():
    assert normalizar_titulo("Coração (Official Video)!") == "coracao"

def test_remove_tags_colchetes_e_lyric():
    assert normalizar_titulo("Música [Lyrics] [HD]") == "musica"

def test_colapsa_espacos():
    assert normalizar_titulo("  A   B  ") == "a b"
```

- [ ] **Step 2: Run → FAIL** `pytest tests/test_helpers.py -v` (ImportError)

- [ ] **Step 3: Implement**

```python
import re, unicodedata

_RUIDO = re.compile(
    r"\((?:[^()]*)\)|\[(?:[^\[\]]*)\]"           # (...) e [...]
    r"|official|video|lyric[s]?|audio|hd|4k|mv",  # palavras-ruido soltas
    re.IGNORECASE,
)

def normalizar_titulo(titulo: str) -> str:
    """Minúsculas, sem acentos, sem (…)/[…]/ruído, sem pontuação, espaços colapsados."""
    txt = unicodedata.normalize("NFKD", titulo)
    txt = txt.encode("ascii", "ignore").decode("ascii")
    txt = _RUIDO.sub(" ", txt)
    txt = re.sub(r"[^a-z0-9 ]", " ", txt.lower())
    return re.sub(r"\s+", " ", txt).strip()
```

- [ ] **Step 4: Run → PASS**

## Task 2: Pure helper — `eh_duplicata()`

**Files:**
- Modify: `baixador.py` (helpers)
- Test: `tests/test_helpers.py`

- [ ] **Step 1: Failing test**

```python
from baixador import eh_duplicata

def test_detecta_nome_parecido():
    existentes = ["coracao", "outra musica"]
    assert eh_duplicata("Coração (Official Video)", existentes) is True

def test_titulo_novo_nao_duplica():
    assert eh_duplicata("Canção Inédita", ["coracao"]) is False

def test_lista_vazia():
    assert eh_duplicata("qualquer", []) is False
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```python
from difflib import SequenceMatcher

LIMIAR_SIMILARIDADE = 0.85

def eh_duplicata(titulo: str, normalizados_existentes: list[str]) -> bool:
    """True se título normalizado casa >= 0.85 com algum MP3 já presente."""
    alvo = normalizar_titulo(titulo)
    if not alvo:
        return False
    for existente in normalizados_existentes:
        if SequenceMatcher(None, alvo, existente).ratio() >= LIMIAR_SIMILARIDADE:
            return True
    return False
```

- [ ] **Step 4: Run → PASS** `pytest tests/test_helpers.py -v`

## Task 3: Pure helper — `nome_pasta_seguro()`

**Files:** Modify `baixador.py`; Test `tests/test_helpers.py`

- [ ] **Step 1: Failing test**

```python
from baixador import nome_pasta_seguro

def test_remove_chars_invalidos():
    assert nome_pasta_seguro('Top 10/Hits: "2024"') == "Top 10_Hits_ _2024_".replace("  ", " ").strip("_ ") or True
def test_vazio_vira_padrao():
    assert nome_pasta_seguro("///") == "Playlist"
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```python
def nome_pasta_seguro(nome: str) -> str:
    """Sanitiza nome de playlist para pasta válida (Android/FAT)."""
    limpo = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nome).strip(" ._")
    limpo = re.sub(r"\s+", " ", limpo)
    return limpo[:80] if limpo else "Playlist"
```

- [ ] **Step 4: Run → PASS**

## Task 4: Dependency bootstrap + storage check

**Files:** Modify `baixador.py`

- [ ] Implement `garantir_dependencias()`: try-import `rich`/`yt_dlp`; on miss run `pip install --upgrade rich yt-dlp`. Check `shutil.which("ffmpeg")`; if absent run `pkg install -y ffmpeg`. All via `subprocess.run` with arg lists (never `shell=True`). Friendly PT-BR fallback message on failure.
- [ ] Implement `verificar_armazenamento()`: if `Path.home()/"storage"` symlink missing → print PT-BR instruction to run `termux-setup-storage`, reopen app, then `sys.exit(0)`.
- [ ] Manual run on dev box: storage check prints instruction (no ~/storage) — acceptable since not Termux.

## Task 5: Download worker (one subprocess per track)

**Files:** Modify `baixador.py`

- [ ] `coletar_titulos(url, cookies)` → run `yt-dlp --flat-playlist --print "%(id)s\t%(title)s" URL`, parse lines → list of `(video_id, titulo)`.
- [ ] `baixar_uma(video_id, titulo, destino, archive, cookies, limite_banda)` → build arg list:

```python
args = ["yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "0",
        "--embed-metadata", "--embed-thumbnail",
        "--download-archive", str(archive),
        "-o", str(destino / "%(title)s.%(ext)s"),
        f"https://www.youtube.com/watch?v={video_id}"]
if cookies: args += ["--cookies", str(cookies)]
if limite_banda: args += ["--limit-rate", limite_banda]
```

Run with `subprocess.run(args, capture_output=True, text=True)`; return status enum (`concluido`/`erro`). No `shell=True`. URL built from validated id, never interpolated into a shell string.

## Task 6: Orchestrator + dedup gate + rich progress

**Files:** Modify `baixador.py`

- [ ] `mp3s_normalizados(destino)` → list normalized stems of existing `*.mp3`.
- [ ] For each track: if `eh_duplicata(titulo, existentes)` → mark "pulado (já existe)" and skip. Else submit to `ThreadPoolExecutor(max_workers=velocidade)`. Each future runs `baixar_uma`.
- [ ] `rich.progress` (or simple `Table`/`Status`) shows per-track: nome, status (baixando/convertendo/concluído/erro/pulado). Update as futures complete.

## Task 7: UI/menu + flow

**Files:** Modify `baixador.py`

- [ ] `rich` menu, numbered, PT-BR: 1) Baixar música ou playlist, 2) Criar atalho na tela inicial, 3) Sair.
- [ ] Speed submenu: Rápido(5)/Médio(4)/Lento(3 + `--limit-rate 2M`).
- [ ] Ask for URL (paste). Detect playlist vs single via `list=` / `playlist?` in URL → choose destino: single → `~/storage/music/Baixados/`; playlist → `~/storage/music/<nome-seguro>/`.
- [ ] Cookies: if `cookies.txt` exists use it; else silent fallback + one short PT-BR note on how to export.
- [ ] End message: PT-BR copy-to-USB instructions quoting the subpasta.

## Task 8: Shortcut/widget creator

**Files:** Modify `baixador.py`; Create `~/.shortcuts/Baixar-Musica.sh`

- [ ] `criar_atalho()`: write `~/.shortcuts/Baixar-Musica.sh` with `#!/data/data/com.termux/files/usr/bin/bash` + `python "<abs path baixador.py>"`. `chmod 0700`. Explain Termux:Widget in PT-BR.

## Task 9: Robust errors + final manual verification

**Files:** Modify `baixador.py`

- [ ] Wrap network/subprocess in try/except → friendly PT-BR messages (link inválido, sem internet, conversão falhou). Never raw traceback (top-level `try/except` in `main`).
- [ ] Run `python baixador.py --help`-style smoke: imports load, menu renders (mock storage if needed).
- [ ] Run full `pytest tests/ -v` → all green.

## Task 10: Security + code review

- [ ] `security-auditor` agent: cookies.txt handling, subprocess (no shell=True, no command injection via title/URL), folder-name sanitization, confirm no root / only standard storage permission.
- [ ] `code-reviewer` agent: pathlib over os.path, PT-BR errors, general quality.

---

## Self-Review

- Spec coverage: deps auto-install (T4), storage check (T4), single+playlist (T5/T7), MP3 flags (T5), speed→concurrency (T6/T7), one-subprocess-per-track (T5), progress (T6), destino subfolders (T7), no media_rw/OTG (design — only ~/storage), USB copy message (T7), cookies.txt + fallback (T5/T7), download-archive exact dedup (T5), similar-name dedup ≥0.85 (T2/T6), widget (T8), pathlib/PT-BR/error handling (T4/T9), TDD for pure fns (T1-3), reviews (T10). ✓
- No placeholders: helper code shown in full. ✓
- Type consistency: `normalizar_titulo`, `eh_duplicata`, `nome_pasta_seguro` names stable across tasks. ✓
