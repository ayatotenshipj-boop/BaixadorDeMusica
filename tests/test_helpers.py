"""Testes das funções puras do baixador (normalização e deduplicação)."""
import sys
from pathlib import Path

# Permite importar baixador.py da raiz do projeto.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import baixador
from baixador import normalizar_titulo, eh_duplicata, nome_pasta_seguro, id_valido


# --- normalizar_titulo ---------------------------------------------------

def test_remove_acentos_caixa_pontuacao():
    assert normalizar_titulo("Coração (Official Video)!") == "coracao"


def test_remove_tags_colchetes_e_lyric():
    assert normalizar_titulo("Música [Lyrics] [HD]") == "musica"


def test_colapsa_espacos():
    assert normalizar_titulo("  A   B  ") == "a b"


def test_remove_ruido_solto():
    assert normalizar_titulo("Tema MV 4K HD") == "tema"


# --- eh_duplicata --------------------------------------------------------

def test_detecta_nome_parecido():
    existentes = ["coracao", "outra musica"]
    assert eh_duplicata("Coração (Official Video)", existentes) is True


def test_titulo_novo_nao_duplica():
    assert eh_duplicata("Cancao Inedita Totalmente Diferente", ["coracao"]) is False


def test_lista_vazia():
    assert eh_duplicata("qualquer", []) is False


# --- nome_pasta_seguro ---------------------------------------------------

def test_remove_chars_invalidos():
    assert nome_pasta_seguro('Top 10/Hits: "2024"') == "Top 10_Hits_ _2024"


def test_vazio_vira_padrao():
    assert nome_pasta_seguro("///") == "Playlist"


def test_limita_tamanho():
    assert len(nome_pasta_seguro("a" * 200)) == 80


# --- id_valido (anti-injeção de argumento) -------------------------------

def test_id_valido_aceita_11_chars():
    assert id_valido("dQw4w9WgXcQ") is True


def test_id_valido_rejeita_opcao():
    assert id_valido("--exec") is False
    assert id_valido("-x") is False


def test_id_valido_rejeita_tamanho_errado():
    assert id_valido("abc") is False
    assert id_valido("dQw4w9WgXcQextra") is False


# --- histórico (dedup exato por ID) --------------------------------------

def test_archive_round_trip(tmp_path, monkeypatch):
    arq = tmp_path / "baixados.txt"
    monkeypatch.setattr(baixador, "ARQUIVO_ARCHIVE", arq)
    assert baixador.ids_ja_baixados() == set()
    baixador.registrar_baixado("dQw4w9WgXcQ")
    baixador.registrar_baixado("abcdefghijk")
    assert baixador.ids_ja_baixados() == {"dQw4w9WgXcQ", "abcdefghijk"}
