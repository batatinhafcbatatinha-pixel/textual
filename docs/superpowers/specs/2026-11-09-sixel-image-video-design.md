# Widgets nativos `Image` e `Video` com Sixel sem flicker

Data: 2026-11-09 · Branch: `feat/sixel-graphics` · Repo: `batatinhafcbatatinha-pixel/textual` (fork de uso próprio)

## Objetivo

Adicionar ao Textual dois widgets nativos, `Image` e `Video`, que desenham com Sixel
quando o terminal suporta (alvo principal: Windows Terminal da Microsoft Store) e
com blocos meia-célula (`▀`) caso contrário, **sem flicker** ao rolar (scroll),
redimensionar o terminal ou atualizar outras partes da tela.

Referência anterior: branch `lucashartmann/textual@teste` (somente leitura; nada é
enviado para lá).

### Critérios de sucesso

1. Rolar um `VerticalScroll` com várias `Image` não pisca e não deixa "fantasmas"
   da imagem na posição antiga.
2. Redimensionar o terminal reposiciona/redimensiona as imagens sem piscar nem
   deixar restos.
3. Atualizar outros widgets (digitar num `Input`, relógio, animação) não reenvia as
   imagens.
4. Um widget sobreposto (menu de `Select`, toast) aparece por cima da imagem.
5. `Video` toca com áudio sincronizado; quando o terminal não acompanha, frames são
   descartados em vez de dessincronizar.
6. Em terminal sem sixel, ambos funcionam em half-block.

### Fatos medidos no Windows Terminal do usuário (sondagem 2026-11-09)

| Consulta | Resposta | Uso |
|---|---|---|
| `CSI c` (DA1) | `CSI ?61;4;6;7;14;21;22;23;24;28;32;42;52c` | `4` ⇒ sixel suportado |
| `CSI ?2026$p` | `CSI ?2026;2$y` | synchronized output suportado |
| `CSI 16t` | `CSI 6;20;10t` | célula = 10×20 px |
| cursor após sixel | fica na última linha de texto tocada pela imagem | sixel na última linha não rola a tela |

O `WindowsDriver` atual nunca consulta `?2026`, então o Textual no Windows não usa
synchronized output: cada frame aparece em pedaços.

## Causa do flicker na abordagem anterior

O sixel era escrito fora do frame do compositor (`call_after_refresh` /
`write_update`). O compositor escrevia espaços nas células da imagem (o que apaga o
sixel no WT) e depois a imagem era redesenhada: apaga → redesenha = pisca.

## Arquitetura

### 1. Capacidades do terminal

- `WindowsDriver.start_application_mode` passa a enviar `CSI ?2026$p`, `CSI c` e
  `CSI 16t` (o `LinuxDriver` também envia `CSI c` e `CSI 16t`).
- `_xterm_parser.XTermParser` reconhece:
  - DA1 `CSI ? <params> c` → `messages.TerminalGraphicsInfo(sixel=...)`;
  - `CSI 6 ; h ; w t` → `messages.TerminalGraphicsInfo(cell_size=(w, h))`.
- `App` guarda `app.graphics_info: GraphicsInfo` (`sixel: bool`, `cell_size: Size`,
  padrão `False` / `10×20`). Ao mudar, faz refresh dos widgets gráficos.
- Variável de ambiente `TEXTUAL_GRAPHICS=sixel|halfblock|auto` força o modo
  (útil para testes e terminais que mentem).

### 2. Células gráficas (marcador)

- `textual/_graphics.py` define `GRAPHICS_STYLE = Style(meta={"@graphics": True})`.
- Um widget gráfico em modo sixel devolve, para a área de conteúdo, `Strip`s de
  espaços com `GRAPHICS_STYLE`. Borda, padding e scrollbars continuam texto normal.
- `Strip.render` converte cada segmento marcado em `CSI n C` (avança o cursor sem
  escrever), de modo que o texto nunca sobrescreve a imagem. O teste do marcador é
  por identidade de estilo e, como fallback, pela meta, para sobreviver a
  `crop`/`divide`/`apply_style`.

### 3. Placements e diff por frame

- `Compositor` ganha `_graphics_placements: dict[Widget, Placement]` do frame
  anterior.
- Em `render_update`, para cada widget gráfico visível (`visible_widgets`):
  `rect = content_region ∩ clip` (coordenadas de tela).
  `Placement(rect, crop, generation, cell_size)`, onde `crop` é a parte do
  conteúdo visível (em células, relativa ao widget) e `generation` é um contador
  que o widget incrementa quando o conteúdo muda (nova imagem, novo frame,
  novo `fit`).
- Diferenças em relação ao frame anterior:
  - placement novo ou alterado → gera o sixel desse recorte e adiciona `rect` às
    regiões sujas (assim widgets sobrepostos são reescritos **depois** do sixel e
    o cobrem);
  - área de placement antigo que deixou de ser gráfica (widget rolou, saiu,
    encolheu) → adicionada às regiões sujas; o texto escrito apaga o resto da
    imagem antiga;
  - full update (resize, troca de tela) → reemite todos os placements.
- O resultado é uma lista `graphics: list[tuple[Offset, str]]` anexada ao
  `LayoutUpdate`/`ChopsUpdate`.

### 4. Escrita do frame

`App._display` monta uma única sequência:

```
CSI ?2026h  →  [ESC 7, CUP(y,x), <sixel>, ESC 8] por placement  →  texto/chops  →  CUP cursor  →  CSI ?2026l
```

O sixel vem antes do texto para que widgets sobrepostos sejam escritos por cima.

### 5. Encoder sixel (`textual/_sixel.py`)

- Entrada: `PIL.Image` RGB já no tamanho final em pixels.
- Quantização: `Image.quantize(colors=N, method=FASTOCTREE)` (C). `N` padrão 256
  para `Image`, 128 para `Video` (mais rápido).
- Para cada banda de 6 linhas (NumPy): calcula o valor sixel (0..63) por coluna
  para cada cor presente na banda, converte para bytes (`+63`) e aplica RLE com
  `re.sub` em bytes (velocidade de C). Emite `#c` + dados + `$`, e `-` entre bandas.
- Cabeçalho `DCS 0;1;0 q "1;1;W;H` (P2=1: pixels de valor 0 não alteram a tela;
  como todos os pixels são pintados, a imagem é opaca).
- Cache LRU por `(id da fonte, generation, tamanho em px, crop)`.

### 6. Fallback half-block

`textual/_halfblock.py`: redimensiona para `(w, h*2)` e produz `Strip`s com `▀`
(cor de frente = pixel de cima, fundo = pixel de baixo). É texto normal, então não
participa dos placements.

## Widgets

### Base: `GraphicsWidget` (interno, `textual/_graphics.py`)

- Responsável por: modo de renderização (`auto|sixel|halfblock`), `generation`,
  cálculo do retângulo em pixels a partir de `cell_size`, aplicação de `fit`
  (`contain|cover|fill`; em `contain` as sobras recebem a cor de fundo do widget),
  `render_lines` (marcador ou half-block) e `get_sixel(crop) -> str` usado pelo
  compositor.
- Subclasses implementam `get_frame() -> PIL.Image | None`.
- `get_content_width/height` para `auto`: tamanho natural da imagem em células.

### `Image` (`textual/widgets/_image.py`)

```python
Image(source: str | Path | bytes | PIL.Image.Image | None = None, *,
      fit: Literal["contain", "cover", "fill"] = "contain",
      render: Literal["auto", "sixel", "halfblock"] = "auto",
      name=None, id=None, classes=None, disabled=False)
```

- Reativos: `image` (aceita os mesmos tipos de `source`), `fit`, `render`.
- Exportado em `textual.widgets`.

### `Video` (`textual/widgets/_video.py`)

```python
Video(source: str | Path, *, autoplay: bool = False, loop: bool = False,
      audio: bool = True, max_fps: float | None = None,
      fit=..., render=..., name=None, id=None, classes=None, disabled=False)
```

- Métodos: `play()`, `pause()`, `toggle()`, `seek(seconds)`, `stop()`.
- Reativos somente leitura: `position`, `duration`, `playing`, `muted`.
- Teclas (com foco): `space` play/pause, `left`/`right` ±5 s, `m` mudo.
- Mensagens: `Video.Started`, `Video.Paused`, `Video.Finished`.
- Threads:
  - **decoder** (PyAV): decodifica, descarta frames atrasados em relação ao
    relógio, redimensiona com `frame.reformat(w, h, "rgb24")` (swscale) para o
    tamanho em pixels atual, quantiza e codifica o sixel; entrega o frame pronto
    ao widget via `call_from_thread`. Fila de tamanho 1–2 (sempre o mais recente).
  - **áudio** (`sounddevice.OutputStream` com callback): fonte do relógio mestre
    (amostras tocadas ÷ sample rate). Sem áudio ou sem `sounddevice` → relógio de
    `time.perf_counter`.
- Controle de vazão: se o frame anterior ainda não foi exibido quando o próximo
  fica pronto, o anterior é descartado (o fps se adapta ao terminal). `max_fps`
  limita explicitamente.
- `seek` reinicia decoder e áudio na nova posição; `on_unmount` encerra as threads.

## Dependências

Extra opcional no `pyproject.toml`: `media = ["pillow", "numpy", "av", "sounddevice"]`.
Se faltar uma dependência, o widget renderiza uma mensagem como
`Image requer Pillow: pip install textual[media]` em vez de lançar exceção.

## Tratamento de erros

- Falha ao abrir arquivo/decodificar → widget mostra a mensagem de erro em texto e
  posta `Video.Error`/loga; o app não cai.
- Terminal sem resposta às consultas → permanece em half-block.
- Placement com área zero → ignorado.

## Testes

- `tests/test_sixel.py`: encoder (cabeçalho, RLE, decodificação de volta com um
  decodificador mínimo no teste e comparação de pixels quantizados).
- `tests/test_graphics_compositor.py` (app headless com
  `TEXTUAL_GRAPHICS=sixel`): células marcadas viram `CSI n C`; sixel emitido só
  quando placement muda; scroll marca área antiga como suja; widget sobreposto é
  escrito depois do sixel.
- `tests/test_xterm_parser.py`: novos casos para DA1 e `16t`.
- Teste manual: `examples/media_demo.py` (imagens num scroll, `Select` por cima,
  vídeo) executado no Windows Terminal, verificado com screenshots durante scroll
  e resize.

## Fora do escopo

Protocolo Kitty/iTerm2, playlist, legendas, controle de velocidade, imagens
animadas (GIF) — a base permite adicionar depois.
