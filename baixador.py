#!/data/data/com.termux/files/usr/bin/python
# -*- coding: utf-8 -*-
"""
Baixador de Música — YouTube para MP3 no Termux (Android, sem root).

Interface simples em português, pensada para qualquer pessoa usar.
Use SOMENTE a permissão de armazenamento padrão do Termux.
"""

import re
import sys
import shutil
import subprocess
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

# ---------------------------------------------------------------------------
# Configurações gerais
# ---------------------------------------------------------------------------

PASTA_APP = Path(__file__).resolve().parent          # onde mora este script
ARQUIVO_ARCHIVE = PASTA_APP / "baixados.txt"          # IDs já baixados (yt-dlp)
ARQUIVO_COOKIES = PASTA_APP / "cookies.txt"           # opcional, formato Netscape
PASTA_MUSICA = Path.home() / "storage" / "music"      # pasta padrão do celular
ATALHO = Path.home() / ".shortcuts" / "Baixar-Musica.sh"

LIMIAR_SIMILARIDADE = 0.85                             # nome "parecido" = duplicata

PASTA_DESTINO_PENDRIVE = "MusicasSC"                   # subpasta criada na raiz do pen-drive
ARQUIVO_HISTORICO_PENDRIVE = ".download_archive.txt"  # histórico de IDs dentro de MusicasSC
# Sistemas de arquivos típicos de pen-drive USB.
FS_PENDRIVE = {"vfat", "exfat", "ntfs", "fuseblk"}

# Velocidade escolhida -> (downloads simultâneos, limite de banda ou None)
VELOCIDADES = {
    "1": ("Rápido", 5, None),
    "2": ("Médio", 4, None),
    "3": ("Lento", 3, "2M"),
}

# ID de vídeo do YouTube válido (11 caracteres). Evita "injeção de argumento" no yt-dlp.
_ID_VALIDO = re.compile(r"^[A-Za-z0-9_-]{11}$")

# Trechos de ruído removidos ao comparar títulos.
_RUIDO = re.compile(
    r"\([^()]*\)|\[[^\[\]]*\]"                         # (...) e [...]
    r"|\b(?:official|video|lyric[s]?|audio|hd|4k|mv|oficial)\b",
    re.IGNORECASE,
)


# ===========================================================================
# Funções puras (testáveis) — normalização e deduplicação
# ===========================================================================

def normalizar_titulo(titulo: str) -> str:
    """Minúsculas, sem acentos, sem (…)/[…]/ruído e sem pontuação.

    Usada para comparar títulos de música e detectar duplicatas por nome.
    """
    txt = unicodedata.normalize("NFKD", titulo)
    txt = txt.encode("ascii", "ignore").decode("ascii")
    txt = _RUIDO.sub(" ", txt)
    txt = re.sub(r"[^a-z0-9 ]", " ", txt.lower())
    return re.sub(r"\s+", " ", txt).strip()


def eh_duplicata(titulo: str, normalizados_existentes: list[str]) -> bool:
    """True se o título for igual ou muito parecido (>= 0.85) com algo já baixado."""
    alvo = normalizar_titulo(titulo)
    if not alvo:
        return False
    for existente in normalizados_existentes:
        if SequenceMatcher(None, alvo, existente).ratio() >= LIMIAR_SIMILARIDADE:
            return True
    return False


def nome_pasta_seguro(nome: str) -> str:
    """Transforma o nome da playlist em um nome de pasta válido no Android."""
    limpo = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nome)
    limpo = re.sub(r"\s+", " ", limpo).strip(" ._")
    return limpo[:80] if limpo else "Playlist"


def mp3s_normalizados(destino: Path) -> list[str]:
    """Lista os títulos já presentes na pasta (normalizados) para comparação."""
    if not destino.exists():
        return []
    return [normalizar_titulo(p.stem) for p in destino.glob("*.mp3")]


def id_valido(video_id: str) -> bool:
    """True se o ID tem o formato esperado do YouTube (11 caracteres seguros)."""
    return bool(_ID_VALIDO.match(video_id))


def ids_ja_baixados(archive: Path = None) -> set[str]:
    """Lê o arquivo de histórico e devolve os IDs já baixados (dedup exato)."""
    archive = archive or ARQUIVO_ARCHIVE
    if not archive.exists():
        return set()
    ids = set()
    for linha in archive.read_text(encoding="utf-8").splitlines():
        partes = linha.split()
        if partes:
            ids.add(partes[-1])  # formato "youtube <id>"
    return ids


def registrar_baixado(video_id: str, archive: Path = None) -> None:
    """Anota um ID no histórico. Chamado por UMA thread só (sem corrida)."""
    archive = archive or ARQUIVO_ARCHIVE
    with archive.open("a", encoding="utf-8") as f:
        f.write(f"youtube {video_id}\n")


# ===========================================================================
# Pen-drive (USB OTG)
# ===========================================================================

def detectar_pendrives() -> list[Path]:
    """Procura pen-drives montados em /mnt/media_rw/<UUID> lendo /proc/mounts."""
    montagens = Path("/proc/mounts")
    if not montagens.exists():
        return []
    encontrados = []
    for linha in montagens.read_text(encoding="utf-8", errors="ignore").splitlines():
        partes = linha.split()
        if len(partes) < 3:
            continue
        ponto, sistema = partes[1], partes[2]
        # /proc/mounts escapa espaços como \040; desfaz para virar caminho real.
        ponto = ponto.replace("\\040", " ")
        if ponto.startswith("/mnt/media_rw/") and sistema in FS_PENDRIVE:
            encontrados.append(Path(ponto))
    return encontrados


def escolher_pendrive(cons) -> Path | None:
    """Detecta os pen-drives e, se houver vários, deixa o usuário escolher."""
    drives = detectar_pendrives()
    if not drives:
        cons.print(
            "  [red]Nenhum pen-drive encontrado.[/] "
            "Conecte pelo adaptador USB e tente de novo."
        )
        return None
    if len(drives) == 1:
        return drives[0]

    cons.print("\n  Encontrei mais de um pen-drive. Qual você quer usar?")
    for i, d in enumerate(drives, start=1):
        cons.print(f"   [bold]{i}[/]) {d.name}")
    escolha = input("  Digite o número e tecle Enter: ").strip()
    if escolha.isdigit() and 1 <= int(escolha) <= len(drives):
        return drives[int(escolha) - 1]
    cons.print("  [yellow]Opção inválida.[/]")
    return None


def testar_escrita(raiz: Path) -> bool:
    """Confere se dá para escrever no pen-drive criando e apagando um arquivo de teste."""
    teste = raiz / ".write_test"
    try:
        teste.touch()
        teste.unlink(missing_ok=True)
        return True
    except OSError:
        return False


# ===========================================================================
# Interface (rich é importado de forma preguiçosa, só quando existe)
# ===========================================================================

def console():
    """Devolve um Console do rich (importação preguiçosa)."""
    from rich.console import Console
    return Console()


def aviso(msg: str) -> None:
    print(msg)


# ===========================================================================
# Preparação do ambiente
# ===========================================================================

def _instalar(args: list[str]) -> bool:
    """Roda um instalador (pip/pkg) e diz se deu certo. Nunca usa shell=True."""
    try:
        subprocess.run(args, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def garantir_dependencias() -> bool:
    """Verifica e instala o que faltar: rich, yt-dlp e ffmpeg."""
    # rich e yt-dlp (Python)
    faltando = []
    try:
        import rich  # noqa: F401
    except ImportError:
        faltando.append("rich")
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        faltando.append("yt-dlp")

    if faltando:
        aviso("Instalando programas necessários (rich, yt-dlp)... aguarde.")
        ok = _instalar([sys.executable, "-m", "pip", "install", "--upgrade", *faltando])
        if not ok:
            aviso(
                "Não consegui instalar automaticamente.\n"
                "Por favor, digite no Termux:\n"
                "   pip install --upgrade rich yt-dlp\n"
                "e abra o app de novo."
            )
            return False

    # ffmpeg (converte o áudio em MP3)
    if shutil.which("ffmpeg") is None:
        aviso("Instalando o conversor de áudio (ffmpeg)... aguarde.")
        ok = _instalar(["pkg", "install", "-y", "ffmpeg"])
        if not ok or shutil.which("ffmpeg") is None:
            aviso(
                "Não consegui instalar o ffmpeg.\n"
                "Por favor, digite no Termux:\n"
                "   pkg install -y ffmpeg\n"
                "e abra o app de novo."
            )
            return False
    return True


def verificar_armazenamento() -> bool:
    """Confere se o acesso ao armazenamento já foi liberado (termux-setup-storage)."""
    if not (Path.home() / "storage").exists():
        aviso(
            "\n  Antes de usar, preciso de acesso à memória do celular.\n\n"
            "  1) Digite no Termux:  termux-setup-storage\n"
            '  2) Toque em "Permitir" na tela que aparecer.\n'
            "  3) Abra este app de novo.\n\n"
            "  É só uma vez. Até já!\n"
        )
        return False
    return True


# ===========================================================================
# Coleta e download
# ===========================================================================

def _cmd_base() -> list[str]:
    """Argumentos comuns do yt-dlp, com cookies se houver."""
    base = []
    if ARQUIVO_COOKIES.exists():
        # Protege o arquivo de sessão: só o dono pode ler.
        try:
            ARQUIVO_COOKIES.chmod(0o600)
        except OSError:
            pass
        base += ["--cookies", str(ARQUIVO_COOKIES)]
    return base


def coletar_itens(url: str) -> list[tuple[str, str]]:
    """Lista (id, título) de um link (música ou playlist inteira)."""
    args = [
        "yt-dlp", "--flat-playlist", "--no-warnings",
        "--print", "%(id)s\t%(title)s",
        *_cmd_base(), "--", url,
    ]
    saida = subprocess.run(args, capture_output=True, text=True)
    if saida.returncode != 0:
        return []
    itens = []
    for linha in saida.stdout.splitlines():
        if "\t" in linha:
            vid, titulo = linha.split("\t", 1)
            if vid.strip():
                itens.append((vid.strip(), titulo.strip()))
    return itens


def nome_playlist(url: str) -> str:
    """Tenta descobrir o nome da playlist para criar a subpasta."""
    args = ["yt-dlp", "--flat-playlist", "--no-warnings",
            "--print", "%(playlist_title)s", *_cmd_base(), "--", url]
    saida = subprocess.run(args, capture_output=True, text=True)
    primeira = saida.stdout.splitlines()[0].strip() if saida.stdout.strip() else ""
    return nome_pasta_seguro(primeira) if primeira and primeira != "NA" else "Playlist"


def baixar_uma(video_id: str, destino: Path, limite_banda) -> str:
    """Baixa UMA música (um subprocess). Retorna 'concluido' ou 'erro'.

    A URL é montada a partir do id validado — nunca interpolada em shell.
    Não usa --download-archive aqui: o histórico é gravado pela orquestração,
    numa thread só, para evitar corrida de escrita entre os processos paralelos.
    """
    if not id_valido(video_id):
        return "erro"
    url = "https://www.youtube.com/watch?v=" + video_id
    args = [
        "yt-dlp",
        "-x", "--audio-format", "mp3", "--audio-quality", "0",
        "--embed-metadata", "--embed-thumbnail",
        "--no-warnings",
        "-o", str(destino / "%(title)s.%(ext)s"),
    ]
    args += _cmd_base()
    if limite_banda:
        args += ["--limit-rate", limite_banda]
    args += ["--", url]  # '--' impede o yt-dlp de tratar a URL como opção

    resultado = subprocess.run(args, capture_output=True, text=True)
    return "concluido" if resultado.returncode == 0 else "erro"


# ===========================================================================
# Orquestração com barra de progresso
# ===========================================================================

def baixar_tudo(itens, destino: Path, simultaneos: int, limite_banda,
                archive: Path = None) -> None:
    """Baixa a lista de músicas em paralelo (um subprocess por música)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from rich.progress import (Progress, SpinnerColumn, TextColumn,
                               BarColumn, TaskProgressColumn)

    archive = archive or ARQUIVO_ARCHIVE
    destino.mkdir(parents=True, exist_ok=True)
    existentes = mp3s_normalizados(destino)        # dedup por nome: só o que já está aqui
    ja_baixados = ids_ja_baixados(archive)         # dedup exato pelo ID do YouTube

    # Separa o que vai baixar do que já existe (ID igual OU nome parecido).
    a_baixar, pulados = [], []
    for vid, titulo in itens:
        if not id_valido(vid):
            continue  # ignora linhas estranhas
        if vid in ja_baixados or eh_duplicata(titulo, existentes):
            pulados.append(titulo)
        else:
            a_baixar.append((vid, titulo))
            existentes.append(normalizar_titulo(titulo))  # evita duplicar na própria lista

    cons = console()
    for titulo in pulados:
        cons.print(f"  [yellow]Pulado (já existe):[/] {titulo}")

    if not a_baixar:
        cons.print("\n  [green]Tudo certo! Nada novo para baixar.[/]")
        return

    concluidos = erros = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=cons,
    ) as prog:
        tarefa = prog.add_task("Baixando músicas...", total=len(a_baixar))
        with ThreadPoolExecutor(max_workers=simultaneos) as pool:
            futuros = {
                pool.submit(baixar_uma, vid, destino, limite_banda): (vid, titulo)
                for vid, titulo in a_baixar
            }
            for fut in as_completed(futuros):
                vid, titulo = futuros[fut]
                try:
                    status = fut.result()
                except Exception:
                    status = "erro"
                if status == "concluido":
                    concluidos += 1
                    try:
                        registrar_baixado(vid, archive)  # uma thread só, sem corrida
                    except OSError:
                        pass  # pen-drive pode ter saído; não trava o resto
                    cons.print(f"  [green]Concluído:[/] {titulo}")
                else:
                    erros += 1
                    cons.print(f"  [red]Erro ao baixar:[/] {titulo}")
                prog.advance(tarefa)

    cons.print(f"\n  [green]{concluidos} música(s) baixada(s).[/]", end="")
    if erros:
        cons.print(f"  [red]{erros} com erro.[/]")
    else:
        cons.print("")


# ===========================================================================
# Mensagens e menus
# ===========================================================================

def mensagem_final(subpasta: str) -> None:
    cons = console()
    cons.print(
        f"\n  [bold green]Pronto![/] As músicas estão na pasta Música, "
        f"dentro de '[bold]{subpasta}[/]'.\n\n"
        "  Para passar pro pendrive:\n"
        "   1) Abra o gerenciador de arquivos do celular (Meus Arquivos).\n"
        "   2) Conecte o pendrive pelo adaptador.\n"
        "   3) Selecione a pasta e use 'Copiar' -> 'Pendrive'.\n"
    )


def mensagem_final_pendrive(pendrive: Path) -> None:
    cons = console()
    cons.print(
        f"\n  [bold green]Pronto![/] As músicas já estão no pen-drive "
        f"'[bold]{pendrive.name}[/]', dentro da pasta "
        f"'[bold]{PASTA_DESTINO_PENDRIVE}[/]'.\n\n"
        "  Pode tirar o pen-drive com segurança e usar onde quiser.\n"
    )


def aviso_cookies() -> None:
    if not ARQUIVO_COOKIES.exists():
        cons = console()
        cons.print(
            "  [dim](Dica: se algum vídeo pedir login, coloque um arquivo "
            "'cookies.txt' nesta pasta. Sem ele, baixo normalmente.)[/]"
        )


def escolher_velocidade() -> tuple[int, str]:
    cons = console()
    cons.print("\n  Qual velocidade?")
    cons.print("   [bold]1[/]) Rápido   (5 músicas ao mesmo tempo)")
    cons.print("   [bold]2[/]) Médio    (4 ao mesmo tempo)")
    cons.print("   [bold]3[/]) Lento    (3 ao mesmo tempo, mais leve)")
    escolha = input("  Digite 1, 2 ou 3: ").strip() or "2"
    _, simultaneos, banda = VELOCIDADES.get(escolha, VELOCIDADES["2"])
    return simultaneos, banda


def fluxo_baixar() -> None:
    cons = console()

    # 1) Detectar o pen-drive ANTES de pedir o link (sem usar a memória interna).
    cons.print("\n  Procurando o pen-drive...")
    pendrive = escolher_pendrive(cons)
    if pendrive is None:
        return  # mensagem já mostrada; volta ao menu

    # 2) Testar escrita no pen-drive escolhido.
    if not testar_escrita(pendrive):
        cons.print("  [red]Não consegui escrever no pen-drive.[/] "
                   "Tente reconectar pelo adaptador USB.")
        return

    # 3) Garantir a pasta MusicasSC na raiz do pen-drive.
    destino = pendrive / PASTA_DESTINO_PENDRIVE
    try:
        destino.mkdir(parents=True, exist_ok=True)
    except OSError:
        cons.print("  [red]Não consegui criar a pasta no pen-drive.[/] "
                   "Tente reconectar e repetir.")
        return
    archive = destino / ARQUIVO_HISTORICO_PENDRIVE  # histórico de IDs dentro de MusicasSC

    cons.print(f"  [green]Pen-drive pronto:[/] {pendrive.name} -> "
               f"{PASTA_DESTINO_PENDRIVE}/")

    # 4) Pedir o link.
    url = input("\n  Cole aqui o link do YouTube e tecle Enter: ").strip()
    if not url.startswith("http"):
        cons.print("  [red]Esse link não parece válido. Tente de novo.[/]")
        return

    aviso_cookies()
    simultaneos, banda = escolher_velocidade()

    cons.print("\n  Lendo o link, um momento...")
    # Link de UMA música (mesmo que venha com '&list='): só essa música.
    # Página de playlist ('playlist?list='): baixa todas, juntas em MusicasSC.
    eh_link_de_musica = ("watch?v=" in url) or ("youtu.be/" in url)
    itens = coletar_itens(url)
    if not itens:
        cons.print(
            "  [red]Não consegui ler esse link.[/] "
            "Veja se você está conectado à internet e se o link está certo."
        )
        return
    if eh_link_de_musica:
        itens = itens[:1]

    cons.print(f"  Encontrei [bold]{len(itens)}[/] música(s). Começando...\n")
    try:
        baixar_tudo(itens, destino, simultaneos, banda, archive)
    except KeyboardInterrupt:
        cons.print("\n  [yellow]Cancelado por você.[/]")
        return
    except Exception:
        cons.print("  [red]Algo deu errado durante o download.[/] Tente novamente.")
        return

    # Se o pen-drive sumiu no meio, avisa claramente.
    if not destino.exists():
        cons.print("\n  [red]O pen-drive foi removido durante o download.[/] "
                   "Reconecte e baixe de novo as que faltaram.")
        return
    mensagem_final_pendrive(pendrive)


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
        f"\n  [green]Atalho criado![/]\n\n"
        "  Para colocar na tela inicial:\n"
        "   1) Instale o app [bold]Termux:Widget[/] (na loja).\n"
        "   2) Segure um espaço vazio na tela inicial -> Widgets.\n"
        "   3) Escolha o Termux:Widget e toque em 'Baixar-Musica'.\n\n"
        "  Aí é só um toque para abrir o baixador!\n"
    )


def menu_principal() -> None:
    cons = console()
    while True:
        cons.print("\n[bold cyan]  Baixador de Música[/]")
        cons.print("  ────────────────────")
        cons.print("   [bold]1[/]) Baixar música ou playlist")
        cons.print("   [bold]2[/]) Criar atalho na tela inicial (widget)")
        cons.print("   [bold]3[/]) Sair")
        escolha = input("  Digite o número e tecle Enter: ").strip()
        if escolha == "1":
            fluxo_baixar()
        elif escolha == "2":
            criar_atalho()
        elif escolha == "3":
            cons.print("  Até logo!")
            return
        else:
            cons.print("  [yellow]Digite 1, 2 ou 3.[/]")


# ===========================================================================
# Início
# ===========================================================================

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
        # Nunca mostrar erro técnico cru para o usuário.
        print(
            "\nOps! Algo inesperado aconteceu.\n"
            "Feche e abra o app de novo. Se continuar, verifique sua internet."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
