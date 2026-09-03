#!/data/data/com.termux/files/usr/bin/python
# -*- coding: utf-8 -*-
"""Baixador de Música — YouTube para MP3 no Termux (Android, sem root)."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PASTA_APP = Path(__file__).resolve().parent
ARQUIVO_COOKIES = PASTA_APP / "cookies.txt"
ARQUIVO_ATUALIZACAO = PASTA_APP / ".ultima_atualizacao_yt_dlp"
ATALHO = Path.home() / ".shortcuts" / "Baixar-Musica.sh"

PASTA_DESTINO_PENDRIVE = "MusicasSC"
ARQUIVO_HISTORICO_PENDRIVE = ".download_archive.txt"
FS_PENDRIVE = {"vfat", "exfat", "ntfs", "fuseblk", "msdos", "ext4", "f2fs"}
INTERVALO_ATUALIZACAO = 7 * 24 * 60 * 60

VELOCIDADES = {
    "1": ("Rápido", 4, None),
    "2": ("Médio", 3, None),
    "3": ("Lento", 2, "2M"),
}

_ID_VALIDO = re.compile(r"^[A-Za-z0-9_-]{11}$")
_RUIDO = re.compile(
    r"\([^()]*\)|\[[^\[\]]*\]"
    r"|\b(?:official|video|lyric[s]?|audio|hd|4k|mv|oficial)\b",
    re.IGNORECASE,
)
_HOSTS_YOUTUBE = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}


# ---------------------------------------------------------------------------
# Funções puras
# ---------------------------------------------------------------------------

def normalizar_titulo(titulo: str) -> str:
    txt = unicodedata.normalize("NFKD", titulo)
    txt = txt.encode("ascii", "ignore").decode("ascii")
    txt = _RUIDO.sub(" ", txt)
    txt = re.sub(r"[^a-z0-9 ]", " ", txt.lower())
    return re.sub(r"\s+", " ", txt).strip()


def eh_duplicata(titulo: str, normalizados_existentes: list[str]) -> bool:
    """Evita falsos positivos: só considera duplicata quando o título normalizado coincide."""
    alvo = normalizar_titulo(titulo)
    return bool(alvo) and alvo in normalizados_existentes


def nome_pasta_seguro(nome: str) -> str:
    limpo = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nome)
    limpo = re.sub(r"\s+", " ", limpo).strip(" ._")
    return limpo[:80] if limpo else "Playlist"


def mp3s_normalizados(destino: Path) -> list[str]:
    if not destino.exists():
        return []
    return [normalizar_titulo(p.stem) for p in destino.glob("*.mp3")]


def id_valido(video_id: str) -> bool:
    return bool(_ID_VALIDO.fullmatch(video_id or ""))


def ids_ja_baixados(archive: Path) -> set[str]:
    if not archive.exists():
        return set()
    ids: set[str] = set()
    try:
        linhas = archive.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return set()
    for linha in linhas:
        partes = linha.split()
        if partes and id_valido(partes[-1]):
            ids.add(partes[-1])
    return ids


def registrar_baixado(video_id: str, archive: Path) -> None:
    if not id_valido(video_id):
        return
    with archive.open("a", encoding="utf-8") as f:
        f.write(f"youtube {video_id}\n")


def classificar_url_youtube(url: str) -> tuple[str, str] | None:
    """Retorna ('video'|'playlist', URL canônica) ou None.

    Um link watch com &list= continua sendo tratado como o vídeo selecionado,
    evitando baixar a playlist inteira e depois escolher o primeiro item errado.
    """
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"}:
        return None

    host = parsed.netloc.lower().split(":", 1)[0]
    if host == "youtu.be":
        vid = parsed.path.strip("/").split("/", 1)[0]
        return ("video", f"https://www.youtube.com/watch?v={vid}") if id_valido(vid) else None

    if host not in _HOSTS_YOUTUBE:
        return None

    query = parse_qs(parsed.query)
    path = parsed.path.rstrip("/")

    if path == "/watch":
        vid = query.get("v", [""])[0]
        if id_valido(vid):
            return "video", f"https://www.youtube.com/watch?v={vid}"

    for prefix in ("/shorts/", "/live/", "/embed/"):
        if path.startswith(prefix):
            vid = path[len(prefix):].split("/", 1)[0]
            if id_valido(vid):
                return "video", f"https://www.youtube.com/watch?v={vid}"

    playlist_id = query.get("list", [""])[0]
    if path == "/playlist" and playlist_id:
        return "playlist", f"https://www.youtube.com/playlist?list={playlist_id}"

    return None


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

def console():
    from rich.console import Console
    return Console()


def aviso(msg: str) -> None:
    print(msg)


def limpar_tela(cons=None) -> None:
    (cons or console()).clear()


def cabecalho_passo(cons, numero: int, titulo: str) -> None:
    cons.print(f"  Passo {numero} de 3: {titulo}\n")


def pausa(cons) -> None:
    input("\n  Tecle Enter para voltar ao menu...")


# ---------------------------------------------------------------------------
# Dependências e yt-dlp moderno (EJS + runtime JS)
# ---------------------------------------------------------------------------

def _instalar(args: list[str]) -> bool:
    try:
        subprocess.run(args, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return False


def _modulo_existe(nome: str) -> bool:
    try:
        __import__(nome)
        return True
    except ImportError:
        return False


def _versao_comando(executavel: str) -> tuple[int, ...]:
    try:
        r = subprocess.run(
            [executavel, "--version"], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    texto = (r.stdout or r.stderr).strip().lstrip("vV")
    numeros = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", texto)
    if not numeros:
        return ()
    return tuple(int(x or 0) for x in numeros.groups())


def runtime_javascript() -> str | None:
    node = shutil.which("node")
    if node and _versao_comando(node) >= (22, 0, 0):
        return "node"
    deno = shutil.which("deno")
    if deno and _versao_comando(deno) >= (2, 3, 0):
        return "deno"
    if shutil.which("qjs") or shutil.which("quickjs"):
        return "quickjs"
    return None


def atualizacao_necessaria(agora: float | None = None) -> bool:
    agora = agora if agora is not None else time.time()
    try:
        ultima = float(ARQUIVO_ATUALIZACAO.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return True
    return agora - ultima >= INTERVALO_ATUALIZACAO


def marcar_atualizacao(agora: float | None = None) -> None:
    try:
        ARQUIVO_ATUALIZACAO.write_text(str(agora if agora is not None else time.time()), encoding="utf-8")
    except OSError:
        pass


def garantir_dependencias() -> bool:
    """Instala/atualiza yt-dlp com EJS e garante ffmpeg + runtime JS."""
    tem_yt = _modulo_existe("yt_dlp")
    tem_rich = _modulo_existe("rich")

    if (not tem_yt) or (not tem_rich) or atualizacao_necessaria():
        aviso("Atualizando o baixador do YouTube e componentes necessários...")
        ok = _instalar([
            sys.executable, "-m", "pip", "install", "--upgrade",
            "yt-dlp[default]", "rich",
        ])
        if ok:
            marcar_atualizacao()
        elif not (tem_yt and tem_rich):
            aviso(
                "Não consegui instalar o yt-dlp. Verifique a internet e digite:\n"
                '   python -m pip install -U "yt-dlp[default]" rich\n'
            )
            return False

    if shutil.which("ffmpeg") is None:
        aviso("Instalando o conversor de áudio (ffmpeg)...")
        if not _instalar(["pkg", "install", "-y", "ffmpeg"]):
            aviso("Não consegui instalar o ffmpeg. Digite: pkg install -y ffmpeg")
            return False

    if runtime_javascript() is None:
        aviso("Instalando/atualizando o componente necessário para o YouTube (Node.js)...")
        _instalar(["pkg", "update", "-y"])
        if not _instalar(["pkg", "install", "-y", "nodejs"]):
            aviso("Não consegui instalar o Node.js 22 ou superior. Digite: pkg update && pkg install nodejs")
            return False

    if runtime_javascript() is None:
        aviso("O runtime JavaScript instalado é antigo demais. Atualize o Node.js (versão 22 ou superior).")
        return False
    return True


def verificar_armazenamento() -> bool:
    if not (Path.home() / "storage").exists():
        aviso(
            "\n  Antes de usar, preciso de acesso ao armazenamento.\n\n"
            "  1) Digite: termux-setup-storage\n"
            '  2) Toque em "Permitir".\n'
            "  3) Abra o programa de novo.\n"
        )
        return False
    return True


def _cmd_base() -> list[str]:
    args = [sys.executable, "-m", "yt_dlp", "--ignore-config"]
    runtime = runtime_javascript()
    if runtime:
        args += ["--js-runtimes", runtime]
    if ARQUIVO_COOKIES.exists():
        try:
            ARQUIVO_COOKIES.chmod(0o600)
        except OSError:
            pass
        args += ["--cookies", str(ARQUIVO_COOKIES)]
    return args


def _opcoes_rede() -> list[str]:
    return [
        "--socket-timeout", "20",
        "--retries", "3",
        "--fragment-retries", "3",
    ]


def resumir_erro_yt_dlp(stderr: str) -> str:
    texto = (stderr or "").lower()
    if "sign in to confirm" in texto or "cookies" in texto and "required" in texto:
        return "O YouTube pediu login. Adicione um cookies.txt válido na pasta do programa."
    if "http error 429" in texto or "too many requests" in texto:
        return "O YouTube limitou temporariamente esta conexão. Tente novamente mais tarde."
    if "http error 403" in texto or "forbidden" in texto:
        return "O YouTube recusou o arquivo de áudio. Atualize o programa e tente novamente."
    if "no supported javascript runtime" in texto:
        return "O componente JavaScript do YouTube não está disponível. Instale/atualize o Node.js."
    if "video unavailable" in texto or "this video is not available" in texto:
        return "Esse vídeo não está disponível para esta conta ou região."
    return "Não consegui abrir ou baixar esse conteúdo do YouTube."


# ---------------------------------------------------------------------------
# Pen-drive
# ---------------------------------------------------------------------------

def _candidato_usb(ponto: str, sistema: str) -> bool:
    if sistema not in FS_PENDRIVE:
        return False
    if ponto.startswith("/storage/"):
        nome = ponto.removeprefix("/storage/").split("/", 1)[0]
        return nome not in {"emulated", "self", "enc_emulated"} and bool(nome)
    return ponto.startswith("/mnt/media_rw/")


def detectar_pendrives() -> list[Path]:
    encontrados: list[Path] = []
    montagens = Path("/proc/mounts")
    if montagens.exists():
        try:
            linhas = montagens.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            linhas = []
        for linha in linhas:
            partes = linha.split()
            if len(partes) < 3:
                continue
            ponto = partes[1].replace("\\040", " ")
            sistema = partes[2].lower()
            if _candidato_usb(ponto, sistema):
                encontrados.append(Path(ponto))

    # Alguns Androids expõem o volume em /storage/<UUID>, mas /proc/mounts mostra
    # apenas a camada interna. Procura também esses pontos de montagem visíveis.
    storage = Path("/storage")
    try:
        if storage.exists():
            for p in storage.iterdir():
                if p.name not in {"emulated", "self", "enc_emulated"}:
                    encontrados.append(p)
    except OSError:
        pass

    unicos: list[Path] = []
    vistos: set[str] = set()
    for p in encontrados:
        chave = str(p)
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(p)
    return unicos


def escolher_pendrive(cons) -> Path | None:
    drives = [p for p in detectar_pendrives() if testar_escrita(p)]
    if not drives:
        cons.print(
            "  [red]Nenhum pen-drive gravável foi encontrado.[/]\n"
            "  Conecte o USB pelo adaptador OTG, autorize o acesso no Android e tente de novo."
        )
        return None
    if len(drives) == 1:
        return drives[0]

    cons.print("  Encontrei mais de um armazenamento removível. Qual você quer usar?\n")
    for i in range(1, len(drives) + 1):
        cons.print(f"   {i}) Pen-drive {i}")
    escolha = input("\n  Digite o número e tecle Enter: ").strip()
    if escolha.isdigit() and 1 <= int(escolha) <= len(drives):
        return drives[int(escolha) - 1]
    cons.print("  Não entendi a escolha.")
    return None


def testar_escrita(raiz: Path) -> bool:
    teste = raiz / ".baixador_write_test"
    try:
        teste.touch(exist_ok=False)
        teste.unlink(missing_ok=True)
        return True
    except OSError:
        try:
            teste.unlink(missing_ok=True)
        except OSError:
            pass
        return False


# ---------------------------------------------------------------------------
# Coleta e download
# ---------------------------------------------------------------------------

def coletar_itens(url: str, tipo: str) -> tuple[list[tuple[str, str]], str | None]:
    args = [
        *_cmd_base(),
        "--flat-playlist", "--no-warnings",
        "--print", "%(id)s\t%(title)s",
        *_opcoes_rede(),
        "--no-playlist" if tipo == "video" else "--yes-playlist",
        "--", url,
    ]
    saida = subprocess.run(args, capture_output=True, text=True)
    if saida.returncode != 0:
        return [], resumir_erro_yt_dlp(saida.stderr)

    itens: list[tuple[str, str]] = []
    vistos: set[str] = set()
    for linha in saida.stdout.splitlines():
        if "\t" not in linha:
            continue
        vid, titulo = linha.split("\t", 1)
        vid, titulo = vid.strip(), titulo.strip()
        if id_valido(vid) and vid not in vistos:
            vistos.add(vid)
            itens.append((vid, titulo or vid))
    if tipo == "video" and itens:
        itens = itens[:1]
    return itens, None


def baixar_uma(video_id: str, destino: Path, limite_banda: str | None) -> tuple[str, str | None]:
    if not id_valido(video_id):
        return "erro", "ID de vídeo inválido."

    url = f"https://www.youtube.com/watch?v={video_id}"
    args = [
        *_cmd_base(),
        "--no-playlist", "--no-warnings",
        *_opcoes_rede(),
        "-f", "bestaudio/best",
        "-x", "--audio-format", "mp3", "--audio-quality", "0",
        "--embed-metadata", "--embed-thumbnail",
        "--windows-filenames", "--trim-filenames", "180",
        "-o", str(destino / "%(title)s [%(id)s].%(ext)s"),
    ]
    if limite_banda:
        args += ["--limit-rate", limite_banda]
    args += ["--", url]

    resultado = subprocess.run(args, capture_output=True, text=True)
    if resultado.returncode == 0:
        return "concluido", None
    return "erro", resumir_erro_yt_dlp(resultado.stderr)


def baixar_tudo(itens, destino: Path, simultaneos: int, limite_banda: str | None, archive: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    destino.mkdir(parents=True, exist_ok=True)
    existentes = mp3s_normalizados(destino)
    ja_baixados = ids_ja_baixados(archive)

    a_baixar: list[tuple[str, str]] = []
    pulados: list[str] = []
    for vid, titulo in itens:
        if not id_valido(vid):
            continue
        if vid in ja_baixados or eh_duplicata(titulo, existentes):
            pulados.append(titulo)
            continue
        a_baixar.append((vid, titulo))
        normalizado = normalizar_titulo(titulo)
        if normalizado:
            existentes.append(normalizado)

    cons = console()
    for titulo in pulados:
        cons.print(f"  Esta você já tem: {titulo}")

    if not a_baixar:
        cons.print("\n  [green]Você já tem todas essas músicas.[/]")
        return

    total = len(a_baixar)
    concluidos = erros = 0
    with ThreadPoolExecutor(max_workers=simultaneos) as pool:
        futuros = {
            pool.submit(baixar_uma, vid, destino, limite_banda): (vid, titulo)
            for vid, titulo in a_baixar
        }
        for i, fut in enumerate(as_completed(futuros), start=1):
            vid, titulo = futuros[fut]
            try:
                status, detalhe = fut.result()
            except Exception:
                status, detalhe = "erro", "Erro inesperado durante o download."

            if status == "concluido":
                concluidos += 1
                try:
                    registrar_baixado(vid, archive)
                except OSError:
                    pass
                cons.print(f"  [green]Pronto {i}/{total}:[/] {titulo}")
            else:
                erros += 1
                cons.print(f"  [red]Falhou {i}/{total}:[/] {titulo}")
                if detalhe:
                    cons.print(f"    {detalhe}")

    cons.print(f"\n  [green]Concluí: {concluidos} música(s).[/]")
    if erros:
        cons.print(f"  [red]Falharam: {erros} música(s).[/]")


def escolher_velocidade() -> tuple[int, str | None]:
    cons = console()
    cons.print("\n  Qual velocidade?")
    cons.print("   [bold]1[/]) Rápido   (4 músicas ao mesmo tempo)")
    cons.print("   [bold]2[/]) Médio    (3 ao mesmo tempo)")
    cons.print("   [bold]3[/]) Lento    (2 ao mesmo tempo, mais leve)")
    escolha = input("  Digite 1, 2 ou 3: ").strip() or "2"
    _, simultaneos, banda = VELOCIDADES.get(escolha, VELOCIDADES["2"])
    return simultaneos, banda


def fluxo_baixar() -> None:
    cons = console()

    limpar_tela(cons)
    cabecalho_passo(cons, 1, "Conectar o pen-drive")
    cons.print("  Procurando um armazenamento USB gravável...\n")
    pendrive = escolher_pendrive(cons)
    if pendrive is None:
        return

    destino = pendrive / PASTA_DESTINO_PENDRIVE
    try:
        destino.mkdir(parents=True, exist_ok=True)
    except OSError:
        cons.print("\n  [red]Não consegui criar a pasta no pen-drive.[/]")
        return
    archive = destino / ARQUIVO_HISTORICO_PENDRIVE

    cons.print("\n  [green]Pen-drive conectado![/]")
    input("\n  Tecle Enter para continuar...")

    limpar_tela(cons)
    cabecalho_passo(cons, 2, "Escolher a música")
    cons.print('  No YouTube, toque em "Compartilhar" e depois em "Copiar link".\n')
    recebido = input("  Cole o link: ").strip()
    classificado = classificar_url_youtube(recebido)
    if classificado is None:
        cons.print("\n  [red]Esse não parece ser um link válido do YouTube.[/]")
        return
    tipo, url = classificado

    cons.print("\n  Lendo o link, um momento...")
    itens, erro = coletar_itens(url, tipo)
    if not itens:
        cons.print(f"\n  [red]{erro or 'Não encontrei músicas nesse link.'}[/]")
        return

    resposta = input(
        f"\n  Encontrei {len(itens)} música(s). Quer baixar? (sim/nao) "
    ).strip().lower()
    if not resposta.startswith("s"):
        cons.print("\n  Tudo bem, não vou baixar.")
        return

    limpar_tela(cons)
    simultaneos, banda = escolher_velocidade()

    limpar_tela(cons)
    cabecalho_passo(cons, 3, "Baixar")
    try:
        baixar_tudo(itens, destino, simultaneos, banda, archive)
    except KeyboardInterrupt:
        cons.print("\n  Você cancelou.")
        return

    if not destino.exists():
        cons.print("\n  [red]O pen-drive foi removido durante o download.[/]")
        return

    cons.print(
        "\n  [green]Pronto![/] As músicas foram salvas no pen-drive, "
        f"na pasta [bold]{PASTA_DESTINO_PENDRIVE}[/]."
    )


def criar_atalho() -> None:
    cons = console()
    ATALHO.parent.mkdir(parents=True, exist_ok=True)
    conteudo = (
        "#!/data/data/com.termux/files/usr/bin/bash\n"
        f'python "{Path(__file__).resolve()}"\n'
    )
    ATALHO.write_text(conteudo, encoding="utf-8")
    ATALHO.chmod(0o700)
    cons.print(
        "\n  [green]Atalho criado![/]\n\n"
        "  Instale o Termux:Widget pelo F-Droid, adicione o widget à tela inicial "
        "e toque em 'Baixar-Musica'."
    )


def menu_principal() -> None:
    cons = console()
    while True:
        limpar_tela(cons)
        cons.print("\n  [bold]Baixador de Música[/]\n")
        cons.print("   1) Baixar música")
        cons.print("   2) Criar atalho na tela inicial")
        cons.print("   3) Sair\n")
        escolha = input("  Digite o número e tecle Enter: ").strip()
        if escolha == "1":
            fluxo_baixar()
            pausa(cons)
        elif escolha == "2":
            criar_atalho()
            pausa(cons)
        elif escolha == "3":
            cons.print("\n  Até logo!")
            return
        else:
            cons.print("\n  Não entendi. Digite 1, 2 ou 3.")
            pausa(cons)


def main() -> int:
    try:
        if not garantir_dependencias():
            return 1
        if not verificar_armazenamento():
            return 0
        menu_principal()
        return 0
    except KeyboardInterrupt:
        print("\nAté logo!")
        return 0
    except Exception:
        print(
            "\nOps! Algo inesperado aconteceu.\n"
            "Feche e abra o programa de novo. Se continuar, verifique sua internet."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
