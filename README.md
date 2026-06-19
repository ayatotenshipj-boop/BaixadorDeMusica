# 🎵 Baixador de Música

Baixe músicas e playlists do YouTube em **MP3** direto no seu **celular Android**, usando o
app **Termux** — sem precisar de root, sem complicação.

Feito para ser **simples**: menu numerado, tudo em português, pensado para qualquer pessoa usar.

- ✅ Baixa **uma música** ou uma **playlist inteira**
- ✅ Salva em **MP3 de boa qualidade**, com a **capa** da música embutida
- ✅ Grava **direto no pen-drive USB**, na pasta `MusicasSC` (sem ocupar a memória do celular)
- ✅ Não baixa a mesma música duas vezes
- ✅ Cria um **atalho na tela inicial** (com um toque você abre o baixador)

---

## 📲 Como instalar (passo a passo)

> Faça isso **uma vez só**. Depois é só usar.

### 1) Instale o Termux

O Termux é um app gratuito. Baixe pela loja **F-Droid** (recomendado) ou pela Play Store:

- F-Droid: https://f-droid.org/packages/com.termux/

> ⚠️ A versão da Play Store é antiga e pode dar erro. Prefira a do **F-Droid**.

### 2) Abra o Termux e atualize

Digite estas duas linhas (uma de cada vez) e tecle **Enter**:

```bash
pkg update -y
pkg install -y python git
```

### 3) Libere o acesso à memória do celular

Digite:

```bash
termux-setup-storage
```

Vai aparecer uma janela do Android — toque em **Permitir**.

### 4) Baixe este programa

```bash
git clone https://github.com/ayatotenshipj-boop/BaixadorDeMusica.git
cd BaixadorDeMusica
```

### 5) Abra o baixador

```bash
python baixador.py
```

Na **primeira vez**, ele instala sozinho o que falta (pode demorar um pouco). Pronto! 🎉

---

## ▶️ Como usar no dia a dia

1. Abra o Termux e digite:

   ```bash
   cd BaixadorDeMusica
   python baixador.py
   ```

   *(ou use o atalho na tela inicial — veja abaixo)*

2. Aparece o menu:

   ```
     Baixador de Música
     ────────────────────
      1) Baixar música ou playlist
      2) Criar atalho na tela inicial (widget)
      3) Sair (fecha o Termux por completo)
   ```

   > A opção **3** fecha o Termux inteiro — assim o app não fica rodando em
   > segundo plano gastando bateria depois que você termina.

3. **Conecte o pen-drive** no celular pelo adaptador USB (OTG) **antes** de começar.
4. Digite **1** e tecle Enter.
5. O programa **procura o pen-drive** sozinho:
   - Se achar **um**, usa ele.
   - Se achar **vários**, mostra uma lista numerada para você escolher.
   - Se **não achar nenhum**, avisa para conectar o pen-drive e voltar.
6. **Cole o link** do YouTube (música ou playlist) e tecle Enter.
7. Escolha a **velocidade** (Rápido / Médio / Lento).
8. Espere terminar. As músicas vão **direto para o pen-drive**, na pasta `MusicasSC`.
   Quando acabar, pode tirar o pen-drive e usar onde quiser.

---

## 🔗 Atalho na tela inicial (opcional, recomendado)

Para abrir o baixador com **um toque**, sem digitar nada:

1. No menu, escolha a opção **2** (Criar atalho).
2. Instale o app **Termux:Widget**:
   - F-Droid: https://f-droid.org/packages/com.termux.widget/
3. Na tela inicial do celular, segure um espaço vazio → **Widgets** → escolha **Termux:Widget**.
4. Toque em **Baixar-Musica**. Pronto, abre o baixador na hora!

---

## 📁 Onde ficam as músicas

Tudo vai **direto para o pen-drive**, dentro de uma pasta chamada **`MusicasSC`**
(criada automaticamente na primeira vez). Nada fica na memória do celular.

```
Pen-drive
└── MusicasSC
    ├── Música 1.mp3
    ├── Música 2.mp3
    └── ... (todas as músicas e playlists)
```

Como já está tudo no pen-drive, é só **tirar o pen-drive** e plugar no computador,
som do carro, caixa de som etc.

> ℹ️ O pen-drive precisa estar acessível ao Termux em `/mnt/media_rw/...`. Em alguns
> aparelhos/versões do Android isso exige permissão especial. Se o programa disser que
> não encontrou o pen-drive mesmo conectado, veja a tabela de **Problemas comuns**.

---

## 🔐 Vídeos que pedem login (cookies — opcional)

Quase tudo baixa normalmente sem isso. Mas se **algum** vídeo exigir login:

1. No computador, exporte um arquivo `cookies.txt` (formato Netscape) do seu navegador
   logado no YouTube (existem extensões gratuitas para isso).
2. Coloque o `cookies.txt` **dentro da pasta** `BaixadorDeMusica`.
3. Rode o baixador normalmente — ele usa o arquivo automaticamente.

> O `cookies.txt` é pessoal. **Nunca** envie esse arquivo para ninguém nem para o GitHub
> (este projeto já o ignora no `.gitignore`).

---

## ❓ Problemas comuns

| Mensagem / problema | O que fazer |
|---|---|
| "Nenhum pen-drive encontrado" | Conecte o pen-drive pelo adaptador USB (OTG) e tente de novo. Veja se o adaptador funciona |
| "Não consegui escrever no pen-drive" | Reconecte o pen-drive. Se persistir, ele pode estar protegido ou com problema |
| "O pen-drive foi removido durante o download" | Reconecte e baixe de novo as que faltaram (as já baixadas não repetem) |
| "preciso de acesso à memória" | Rode `termux-setup-storage`, toque em **Permitir**, abra de novo |
| "Não consegui ler esse link" | Veja se está na internet e se o link está correto |
| Instalação travou | Feche e abra o Termux, rode `python baixador.py` de novo |
| `python: command not found` | Rode `pkg install -y python` |

---

## 🛠️ Para desenvolvedores

Arquivo principal único: **`baixador.py`** (Python 3, sem dependências exóticas).

**Motor:** [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) + `ffmpeg` · **Interface:** [`rich`](https://github.com/Textualize/rich)

**Como funciona, resumido:**
- **Destino no pen-drive:** a opção *Baixar música* detecta os pen-drives lendo `/proc/mounts`
  (volumes em `/mnt/media_rw/<UUID>` com fs `vfat|exfat|ntfs|fuseblk`), testa escrita, cria a
  pasta `MusicasSC` na raiz e grava todos os `.mp3` direto lá — sem passar pela memória interna.
- Um **subprocess** de `yt-dlp` por música; pool limitado (3/4/5 simultâneas conforme a velocidade).
- **Sem downloads repetidos** em dois níveis: histórico de IDs (`MusicasSC/.download_archive.txt`,
  escrito por uma única thread para evitar corrida) + comparação de nome por similaridade
  (`difflib`, limiar 0.85) contra os `.mp3` já presentes em `MusicasSC`.
- Segurança: nenhuma chamada usa `shell=True`; IDs de vídeo são validados (`^[A-Za-z0-9_-]{11}$`)
  e URLs passam após `--` para evitar injeção de argumento. Usa **só** a permissão de
  armazenamento padrão do Termux — **sem root**.

**Rodar os testes:**

```bash
pip install pytest
pytest tests/ -v
```

---

## 📜 Licença

Uso pessoal. Respeite os direitos autorais e os termos do YouTube ao baixar conteúdo.
