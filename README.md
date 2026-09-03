# 🎵 Baixador de Música

Baixador simples de músicas do YouTube em **MP3** para Android/Termux, com suporte a **vídeo individual**, **playlist** e gravação em **pen-drive USB OTG**.

> Use apenas em conteúdo que você tenha permissão para baixar e respeite os termos do YouTube e direitos autorais aplicáveis.

## O que mudou nesta versão

O YouTube passou a exigir desafios JavaScript que versões modernas do `yt-dlp` resolvem por meio de **EJS + runtime JavaScript**. Por isso o programa agora:

- instala/atualiza `yt-dlp[default]`, incluindo o componente `yt-dlp-ejs`;
- garante um runtime JavaScript compatível no Termux (preferencialmente **Node.js**);
- executa `yt-dlp` via `python -m yt_dlp`, evitando depender de um executável antigo no `PATH`;
- atualiza o `yt-dlp` periodicamente em vez de instalar uma vez e ficar desatualizado;
- separa corretamente **link de vídeo** e **link de playlist**;
- um link `watch?v=...&list=...` baixa somente o vídeo que foi compartilhado;
- usa `--no-playlist` para vídeo único e `--yes-playlist` para playlist;
- detecta armazenamento removível tanto em `/storage/<UUID>` quanto em `/mnt/media_rw/<UUID>`;
- mostra erros amigáveis para 403, 429, login/cookies e runtime JavaScript ausente;
- reduz falsos positivos na detecção de músicas duplicadas;
- salva nomes compatíveis com FAT/Windows e inclui o ID do vídeo no nome final.

## Requisitos

- Android
- Termux atualizado (preferencialmente F-Droid)
- Python
- pen-drive + adaptador USB OTG
- internet

As dependências `yt-dlp`, EJS, `rich`, `ffmpeg` e Node.js são verificadas pelo programa.

## Instalação

```bash
pkg update -y
pkg install -y python git
git clone https://github.com/ayatotenshipj-boop/BaixadorDeMusica.git
cd BaixadorDeMusica
termux-setup-storage
python baixador.py
```

Na primeira execução o programa pode instalar/atualizar componentes adicionais.

## Uso

1. Conecte o pen-drive via OTG.
2. Execute:

```bash
cd BaixadorDeMusica
python baixador.py
```

3. Escolha **Baixar música**.
4. Cole um link de vídeo ou playlist do YouTube.
5. Confirme e escolha a velocidade.

Os arquivos ficam em:

```text
<pen-drive>/MusicasSC/
```

Cada MP3 recebe um nome semelhante a:

```text
Nome da Música [ID_DO_VIDEO].mp3
```

O histórico de IDs fica em `MusicasSC/.download_archive.txt` e evita baixar novamente o mesmo vídeo.

## Cookies opcionais

Se o YouTube exigir login para determinado conteúdo, coloque um `cookies.txt` em formato Netscape ao lado de `baixador.py`. O arquivo é usado automaticamente.

Não publique `cookies.txt` no GitHub.

## Atualização

O programa tenta atualizar `yt-dlp[default]` periodicamente. Para forçar manualmente:

```bash
python -m pip install -U "yt-dlp[default]" rich
pkg upgrade -y nodejs ffmpeg
```

## Testes

```bash
python -m pip install pytest
python -m pytest -q
```

Os testes cobrem normalização/deduplicação, parsing de URLs, histórico, seleção de runtime e montagem dos comandos do `yt-dlp`.
