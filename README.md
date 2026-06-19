# 🎵 Baixador de Música

Baixe músicas do YouTube em **MP3**, direto no seu **pen-drive**, usando o celular Android.
Simples, em português, feito para qualquer pessoa usar — inclusive quem não tem intimidade
com tecnologia.

O programa conversa com você em **3 passos**, uma pergunta por vez, e salva tudo no pen-drive
para você ouvir onde quiser (carro, som, computador).

---

## ✅ O que ele faz

- Baixa **uma música** ou uma **lista de músicas** do YouTube.
- Salva em **MP3 de boa qualidade**, com a **capa** da música.
- Grava **direto no pen-drive** (não enche a memória do celular).
- **Não baixa repetido**: se você já baixou uma música, ele pula.
- Cria um **atalho na tela inicial** para abrir com um toque.

---

## 📋 O que você precisa

- Um celular **Android**.
- O app **Termux** (gratuito).
- Um **pen-drive** ligado ao celular por um **adaptador USB (OTG)**.

---

## 🚀 Como começar (passo a passo, só uma vez)

### 1) Instale o Termux

Baixe o **Termux** pela loja **F-Droid** (recomendado):

- https://f-droid.org/packages/com.termux/

> ⚠️ A versão da Play Store é antiga e pode falhar. Prefira a do **F-Droid**.

### 2) Prepare o Termux

Abra o Termux e digite estas linhas (uma de cada vez, teclando **Enter**):

```bash
pkg update -y
pkg install -y python git
termux-setup-storage
```

Quando aparecer a janela do Android, toque em **Permitir**.

### 3) Baixe e abra o programa

```bash
git clone https://github.com/ayatotenshipj-boop/BaixadorDeMusica.git
cd BaixadorDeMusica
python baixador.py
```

Na primeira vez, ele instala sozinho o que falta (pode demorar um pouco). Pronto! 🎉

---

## ▶️ Como usar no dia a dia

1. Conecte o **pen-drive** no celular pelo adaptador USB.
2. Abra o Termux e digite:

   ```bash
   cd BaixadorDeMusica
   python baixador.py
   ```

   *(ou use o atalho na tela inicial — veja abaixo)*

3. No menu, digite **1** (Baixar música). O programa segue **3 passos**:

   - **Passo 1 — Conectar o pen-drive:** ele encontra o pen-drive sozinho.
   - **Passo 2 — Escolher a música:** cole o link do YouTube. Ele conta quantas
     músicas achou e **pergunta se você quer baixar** (responda **sim** ou **nao**).
   - **Passo 3 — Baixar:** ele baixa e mostra cada música ficando pronta.

4. No final, é só **tirar o pen-drive** e usar onde quiser.

> 💡 Para copiar o link no YouTube: toque em **Compartilhar** e depois em **Copiar link**.

---

## 🔗 Atalho na tela inicial (opcional)

Para abrir o baixador com **um toque**:

1. No menu, escolha a opção **2** (Criar atalho).
2. Instale o app **Termux:Widget**:
   - https://f-droid.org/packages/com.termux.widget/
3. Na tela inicial, segure um espaço vazio, escolha **Widgets** e adicione o **Termux:Widget**.
4. Toque em **Baixar-Musica**. Pronto!

---

## ❓ Problemas comuns

| O que apareceu | O que fazer |
|---|---|
| "Nenhum pen-drive encontrado" | Conecte o pen-drive pelo adaptador USB e tente de novo |
| "Não consegui salvar no pen-drive" | Tire e conecte o pen-drive de novo |
| "O pen-drive foi removido no meio do download" | Conecte de novo e baixe as que faltaram (as prontas não repetem) |
| "Esse link não parece certo" | Copie o link de novo pelo botão **Compartilhar** do YouTube |
| `python: command not found` | Digite `pkg install -y python` |

---

## 🛠️ Para desenvolvedores

Arquivo principal único: **`baixador.py`** (Python 3, `pathlib`, sem `os.path`).

**Motor:** [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) + `ffmpeg` · **Interface:** [`rich`](https://github.com/Textualize/rich)

**Como funciona, resumido:**
- **Destino no pen-drive:** detecta volumes em `/mnt/media_rw/<UUID>` (fs `vfat|exfat|ntfs|fuseblk`)
  lendo `/proc/mounts`, testa escrita e grava os `.mp3` numa pasta `MusicasSC` na raiz do
  dispositivo (esse nome e caminho não são mostrados ao usuário).
- Um **subprocess** de `yt-dlp` por música; pool limitado (3/4/5 simultâneas conforme a velocidade).
- **Sem downloads repetidos** em dois níveis: histórico de IDs (`MusicasSC/.download_archive.txt`,
  escrito por uma única thread) + comparação de nome por similaridade (`difflib`, limiar 0.85).
- **Login por cookies (opcional):** se existir um `cookies.txt` na pasta do app, ele é usado
  automaticamente; nada disso aparece na interface.
- Segurança: nenhuma chamada usa `shell=True`; IDs de vídeo são validados (`^[A-Za-z0-9_-]{11}$`)
  e URLs passam após `--`. Usa **só** a permissão de armazenamento padrão do Termux — **sem root**.

**Rodar os testes:**

```bash
pip install pytest
pytest tests/ -v
```

---

## 📜 Licença

Uso pessoal. Respeite os direitos autorais e os termos do YouTube ao baixar conteúdo.
