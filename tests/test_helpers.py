"""Testes unitários do BaixadorDeMusica."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import baixador


def test_normalizar_remove_ruido():
    assert baixador.normalizar_titulo("Coração (Official Video) [HD]!") == "coracao"


def test_duplicata_exata_apos_normalizacao():
    assert baixador.eh_duplicata("Coração (Official Video)", ["coracao"]) is True


def test_nao_marca_titulo_apenas_parecido():
    assert baixador.eh_duplicata("Musica Remix", ["musica"]) is False


def test_nome_pasta_seguro():
    assert baixador.nome_pasta_seguro('Top 10/Hits: "2026"') == "Top 10_Hits_ _2026"
    assert baixador.nome_pasta_seguro("///") == "Playlist"
    assert len(baixador.nome_pasta_seguro("a" * 200)) == 80


def test_id_valido():
    assert baixador.id_valido("dQw4w9WgXcQ") is True
    assert baixador.id_valido("--exec") is False
    assert baixador.id_valido("abc") is False


def test_archive_round_trip(tmp_path):
    arq = tmp_path / "archive.txt"
    assert baixador.ids_ja_baixados(arq) == set()
    baixador.registrar_baixado("dQw4w9WgXcQ", arq)
    baixador.registrar_baixado("abcdefghijk", arq)
    assert baixador.ids_ja_baixados(arq) == {"dQw4w9WgXcQ", "abcdefghijk"}


def test_classifica_watch_com_playlist_como_video_exato():
    r = baixador.classificar_url_youtube(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123&index=7"
    )
    assert r == ("video", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")


def test_classifica_youtu_be():
    assert baixador.classificar_url_youtube("https://youtu.be/dQw4w9WgXcQ?t=5") == (
        "video", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )


def test_classifica_playlist():
    assert baixador.classificar_url_youtube("https://www.youtube.com/playlist?list=PLabc123") == (
        "playlist", "https://www.youtube.com/playlist?list=PLabc123"
    )


def test_rejeita_host_falso():
    assert baixador.classificar_url_youtube(
        "https://youtube.com.exemplo.org/watch?v=dQw4w9WgXcQ"
    ) is None


def test_runtime_prefere_node_compativel(monkeypatch):
    monkeypatch.setattr(baixador.shutil, "which", lambda nome: "/bin/node" if nome == "node" else None)
    monkeypatch.setattr(baixador, "_versao_comando", lambda exe: (26, 4, 0))
    assert baixador.runtime_javascript() == "node"


def test_runtime_rejeita_node_antigo_e_usa_deno(monkeypatch):
    caminhos = {"node": "/bin/node", "deno": "/bin/deno"}
    monkeypatch.setattr(baixador.shutil, "which", lambda nome: caminhos.get(nome))
    monkeypatch.setattr(
        baixador, "_versao_comando",
        lambda exe: (20, 19, 0) if exe.endswith("node") else (2, 9, 4),
    )
    assert baixador.runtime_javascript() == "deno"


def test_cmd_base_usa_modulo_python_e_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(baixador, "ARQUIVO_COOKIES", tmp_path / "nao-existe.txt")
    monkeypatch.setattr(baixador, "runtime_javascript", lambda: "node")
    cmd = baixador._cmd_base()
    assert cmd[:4] == [sys.executable, "-m", "yt_dlp", "--ignore-config"]
    assert cmd[-2:] == ["--js-runtimes", "node"]


def test_coletar_video_forca_no_playlist(monkeypatch):
    capturado = {}

    class Resultado:
        returncode = 0
        stdout = "dQw4w9WgXcQ\tTeste\n"
        stderr = ""

    monkeypatch.setattr(baixador, "_cmd_base", lambda: ["python", "-m", "yt_dlp"])
    monkeypatch.setattr(baixador, "_opcoes_rede", lambda: [])

    def fake_run(args, **kwargs):
        capturado["args"] = args
        return Resultado()

    monkeypatch.setattr(baixador.subprocess, "run", fake_run)
    itens, erro = baixador.coletar_itens("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "video")
    assert erro is None
    assert itens == [("dQw4w9WgXcQ", "Teste")]
    assert "--no-playlist" in capturado["args"]


def test_coletar_playlist_forca_yes_playlist(monkeypatch):
    capturado = {}

    class Resultado:
        returncode = 0
        stdout = "dQw4w9WgXcQ\tA\nabcdefghijk\tB\n"
        stderr = ""

    monkeypatch.setattr(baixador, "_cmd_base", lambda: ["python", "-m", "yt_dlp"])
    monkeypatch.setattr(baixador, "_opcoes_rede", lambda: [])

    def fake_run(args, **kwargs):
        capturado["args"] = args
        return Resultado()

    monkeypatch.setattr(baixador.subprocess, "run", fake_run)
    itens, erro = baixador.coletar_itens("https://www.youtube.com/playlist?list=PLx", "playlist")
    assert erro is None
    assert len(itens) == 2
    assert "--yes-playlist" in capturado["args"]


def test_baixar_uma_monta_comando_moderno(monkeypatch, tmp_path):
    capturado = {}

    class Resultado:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(baixador, "_cmd_base", lambda: ["python", "-m", "yt_dlp", "--js-runtimes", "node"])
    monkeypatch.setattr(baixador, "_opcoes_rede", lambda: [])

    def fake_run(args, **kwargs):
        capturado["args"] = args
        return Resultado()

    monkeypatch.setattr(baixador.subprocess, "run", fake_run)
    status, erro = baixador.baixar_uma("dQw4w9WgXcQ", tmp_path, None)
    assert (status, erro) == ("concluido", None)
    assert "--no-playlist" in capturado["args"]
    assert "bestaudio/best" in capturado["args"]
    assert capturado["args"][-2:] == ["--", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"]


def test_resumir_erros():
    assert "Node.js" in baixador.resumir_erro_yt_dlp("No supported JavaScript runtime")
    assert "limitou" in baixador.resumir_erro_yt_dlp("HTTP Error 429: Too Many Requests")
    assert "login" in baixador.resumir_erro_yt_dlp("Sign in to confirm cookies required")


def test_candidato_usb():
    assert baixador._candidato_usb("/storage/1234-ABCD", "vfat") is True
    assert baixador._candidato_usb("/storage/emulated/0", "fuseblk") is False
    assert baixador._candidato_usb("/mnt/media_rw/1234-ABCD", "exfat") is True
