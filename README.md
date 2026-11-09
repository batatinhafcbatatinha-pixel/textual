

[![Discord](https://img.shields.io/discord/1026214085173461072)](https://discord.gg/Enf6Z3qhVr)
[![Supported Python Versions](https://img.shields.io/pypi/pyversions/textual)](https://pypi.org/project/textual/)
[![PyPI version](https://badge.fury.io/py/textual.svg?)](https://badge.fury.io/py/textual)
![OS support](https://img.shields.io/badge/OS-macOS%20Linux%20Windows-red)

> [!IMPORTANT]
> ## ✨ O que este fork adiciona ao Textual
>
> | | Recurso | Exemplo |
> |---|---|---|
> | 🖼️ | **Widget `Image` nativo**: imagens de verdade com Sixel, ou blocos `▀` coloridos em terminais sem Sixel | `yield Image("foto.png", fit="cover")` |
> | 🎬 | **Widget `Video` com áudio**: PyAV + sounddevice, áudio como relógio mestre, descarte de quadros atrasados, ~27–30 fps no Windows Terminal | `yield Video("filme.mp4", autoplay=True)` |
> | 🌄 | **Imagem de fundo em qualquer widget** (inclusive na `Screen`), com widgets transparentes deixando a imagem aparecer | `Screen { background-image: "fundo.jpg"; }` |
> | 🎨 | **`background-color`** (alias de `background`) e **`background` aceitando imagem** | `background: $panel "textura.png" contain;` |
> | ⚡ | **Sem flicker** ao rolar, redimensionar, abrir menus ou digitar: o texto nunca apaga a imagem, a imagem só é reenviada quando muda (ou só o pedaço que precisa), e tudo sai num único frame sincronizado | — |
> | 🪟 | **Windows Terminal de primeira classe**: detecção automática de Sixel, tamanho da célula e *synchronized output*, que o Textual original nunca ativava no Windows | — |
> | 🚀 | **Codificador Sixel vetorizado** (NumPy): ~22 ms para um quadro de 880×520 px | — |
>
> ```bash
> pip install "textual[media] @ git+https://github.com/batatinhafcbatatinha-pixel/textual.git"
> python examples/media/background_demo.py    # ou image_demo.py / video_demo.py
> ```
>
> 📖 Documentação completa: [Imagens, vídeo e fundos (Sixel)](#imagens-e-vídeo-nativos-sixel--recurso-deste-fork)



![textual-splash](https://github.com/user-attachments/assets/4caeb77e-48c0-4cf7-b14d-c53ded855ffd)

# Textual

<img align="right" width="250" alt="clock" src="https://github.com/user-attachments/assets/63e839c3-5b8e-478d-b78e-cf7647eb85e8" />

Build cross-platform user interfaces with a simple Python API. Run your apps in the terminal *or* a web browser.

Textual's API combines modern Python with the best of developments from the web world, for a lean app development experience.
De-coupled components and an advanced [testing](https://textual.textualize.io/guide/testing/) framework ensure you can maintain your app for the long-term.

Want some more examples? See the [examples](https://github.com/Textualize/textual/tree/main/examples) directory.

```python
"""
An App to show the current time.
"""

from datetime import datetime

from textual.app import App, ComposeResult
from textual.widgets import Digits


class ClockApp(App):
    CSS = """
    Screen { align: center middle; }
    Digits { width: auto; }
    """

    def compose(self) -> ComposeResult:
        yield Digits("")

    def on_ready(self) -> None:
        self.update_clock()
        self.set_interval(1, self.update_clock)

    def update_clock(self) -> None:
        clock = datetime.now().time()
        self.query_one(Digits).update(f"{clock:%T}")


if __name__ == "__main__":
    app = ClockApp()
    app.run()
```

> [!TIP]
> Textual is an asynchronous framework under the hood. Which means you can integrate your apps with async libraries &mdash; if you want to.
> If you don't want or need to use async, Textual won't force it on you. 



<img src="https://img.spacergif.org/spacer.gif" width="1" height="64"/>

## Widgets

Textual's library of [widgets](https://textual.textualize.io/widget_gallery/) covers everything from buttons, tree controls, data tables, inputs, text areas, and more…
Combined with a flexible [layout](https://textual.textualize.io/how-to/design-a-layout/) system, you can realize any User Interface you need.

Predefined themes ensure your apps will look good out of the box. 


<table>

<tr>

  <td>
    
  ![buttons](https://github.com/user-attachments/assets/2ac26387-aaa3-41ed-bc00-7d488600343c)
    
  </td>

  <td>
    
![tree](https://github.com/user-attachments/assets/61ccd6e9-97ea-4918-8eda-3ee0f0d3770e)
    
  </td>
  
</tr>


<tr>

  <td>
    
  ![datatables](https://github.com/user-attachments/assets/3e1f9f7a-f965-4901-a114-3c188bd17695)
    
  </td>

  <td>
    
![inputs](https://github.com/user-attachments/assets/b02aa203-7c37-42da-a1bb-2cb244b7d0d3)
    
  </td>
  
</tr>
<tr>

<td>

![listview](https://github.com/user-attachments/assets/963603bc-aa07-4688-bd24-379962ece871)

</td>

<td>

![textarea](https://github.com/user-attachments/assets/cd4ba787-5519-40e2-8d86-8224e1b7e506)
  
</td>

  
</tr>

</table>


<img src="https://img.spacergif.org/spacer.gif" width="1" height="32"/>

## Imagens e vídeo nativos (Sixel) — recurso deste fork

> Este fork adiciona dois widgets que não existem no Textual oficial: **`Image`** e **`Video`**.
> Eles desenham pixels de verdade com **Sixel** quando o terminal suporta (por exemplo o
> Windows Terminal da Microsoft Store) e usam blocos coloridos `▀` em qualquer outro terminal.
> O foco é **não piscar** ao rolar a tela, redimensionar o terminal ou atualizar outros widgets.

### Instalação

```bash
pip install "textual[media] @ git+https://github.com/batatinhafcbatatinha-pixel/textual.git"
```

O extra `media` instala as dependências opcionais:

| Pacote | Usado por | Para quê |
|---|---|---|
| `pillow` | `Image`, `Video` | carregar e redimensionar imagens |
| `numpy` | `Image`, `Video` | codificador Sixel rápido e fallback em blocos |
| `av` (PyAV) | `Video` | decodificar vídeo e áudio (FFmpeg) |
| `sounddevice` | `Video` | tocar o áudio (opcional: sem ele o vídeo toca mudo) |

Se faltar alguma dependência, o widget mostra uma mensagem explicando o que instalar, em vez de derrubar o app.

### `Image`

```python
from textual.app import App, ComposeResult
from textual.widgets import Image


class ImageApp(App):
    CSS = "Image { width: 60; }"

    def compose(self) -> ComposeResult:
        yield Image("foto.png")                      # caminho
        yield Image(open("logo.png", "rb").read())   # bytes
        yield Image(pil_image, fit="cover")          # PIL.Image


ImageApp().run()
```

| Parâmetro | Padrão | Descrição |
|---|---|---|
| `image` | `None` | caminho, `bytes`, `PIL.Image` ou `None` |
| `fit` | `"contain"` | `contain` mantém a proporção e preenche as sobras com a cor de fundo; `cover` mantém a proporção e corta; `fill` estica |
| `render_mode` | `"auto"` | `auto` (Sixel se o terminal suportar), `sixel` ou `halfblock` |
| `colors` | `256` | número máximo de cores da paleta Sixel (2–256) |

- **Tamanho:** use CSS normal (`width`, `height`). Com `auto` (o padrão), o widget assume o tamanho natural da imagem, limitado à largura do container e mantendo a proporção.
- **Trocar a imagem:** basta atribuir, por exemplo `widget.image = "outra.png"`. Também dá para mudar `fit` e `render_mode` em tempo real.
- **Orientação:** a rotação EXIF é aplicada automaticamente, e PNGs com transparência são mesclados sobre a cor de fundo do widget.

### `Video`

```python
from textual.widgets import Video

yield Video("filme.mp4", autoplay=True, loop=False, audio=True)
```

| Parâmetro | Padrão | Descrição |
|---|---|---|
| `source` | — | caminho (ou URL aceita pelo FFmpeg) |
| `autoplay` | `False` | começa a tocar ao montar |
| `loop` | `False` | recomeça ao terminar |
| `audio` | `True` | toca a trilha de áudio |
| `max_fps` | `None` | limita os quadros por segundo exibidos |
| `fit` / `render_mode` | `"contain"` / `"auto"` | iguais aos do `Image` |
| `colors` | `128` | cores por quadro (menos cores = mais rápido) |

| API | Descrição |
|---|---|
| `play()`, `pause()`, `toggle()`, `stop()` | controle de reprodução |
| `seek(segundos)` | pula para uma posição |
| `position`, `duration`, `playing`, `muted` | estado (reativos) |
| `frames_shown`, `frames_dropped` | estatísticas de desempenho |
| `Video.Started`, `Video.Paused`, `Video.Finished` | mensagens |

**Teclas** (com o vídeo focado): `espaço` play/pause · `←`/`→` voltar/avançar 5 s · `m` mudo.

**Sincronia:** o áudio é o relógio mestre. A decodificação, o redimensionamento (swscale) e a codificação Sixel rodam numa thread separada, e a interface nunca espera por elas. Se o terminal não acompanhar, quadros atrasados são **descartados**, de modo que o vídeo nunca fica atrás do som. Sem áudio, é usado o relógio do sistema.

### Fundo de imagem: `background-image`

Qualquer widget, inclusive a `Screen`, pode ter uma imagem de fundo via CSS:

```css
Screen {
    background-image: "wallpaper.jpg";
    background-image-fit: cover;          /* cover (padrão) | contain | fill */
}

/* Forma curta: cor, imagem e ajuste juntos */
#painel { background: $panel "textura.png" contain; }

/* background-color agora existe (é um alias de background) */
Button { background-color: $primary; }
```

Ou em Python, em tempo de execução:

```python
self.screen.styles.background_image = "wallpaper.jpg"
self.screen.styles.background_image_fit = "contain"
self.screen.styles.background_image = "none"      # remove
widget.styles.background_color = "red"            # alias de styles.background
```

| Propriedade | Valores | Descrição |
|---|---|---|
| `background-image` | `"caminho"` ou `none` | imagem desenhada na área interna da borda (padding + conteúdo) |
| `background-image-fit` | `cover`, `contain`, `fill` | como a imagem é ajustada (padrão `cover`) |
| `background` | `<cor> ["caminho"] [ajuste]` | forma curta: aceita cor, imagem entre aspas e ajuste em qualquer ordem |
| `background-color` | `<cor>` | alias de `background` (cor apenas) |

**Caminhos relativos** são procurados primeiro a partir do diretório atual e depois a partir da pasta do módulo onde a sua classe `App` foi definida.

**O que aparece por cima do fundo:**

- **Widgets transparentes** (sem `background`, como `Label`, `Static` e containers) deixam a
  imagem aparecer nas células em branco. Só as células com caracteres cobrem a imagem.
- **Widgets com fundo** (`Input`, `Button`, `Select`, ou qualquer `background` com alpha > 0)
  cobrem a imagem na área que ocupam. Num terminal não há mistura parcial entre texto e Sixel,
  então um `background: $panel 60%` fica sólido sobre a imagem.
- Quando algo que cobria a imagem sai da frente (um menu fecha, um texto encurta, um widget
  rola ou some), o compositor reenvia **só aquele pedaço** da imagem, dentro do mesmo frame
  sincronizado, sem flicker.

Em terminais sem Sixel a imagem de fundo vira blocos `▀` coloridos. Nesse modo, os widgets
transparentes filhos mostram a cor de fundo normal, e não a imagem.

### Demos

```bash
python examples/media/image_demo.py [imagem ...]            # imagens num scroll + Select por cima
python examples/media/video_demo.py [video] --mute --loop   # vídeo com barra de progresso e fps
python examples/media/background_demo.py [imagem]           # background-image na Screen e num painel
```

`examples/media/make_sample.py` e `make_sample_video.py` geram os arquivos de exemplo (`sample.png` e `sample.mp4`).

### Como o flicker foi eliminado

No Windows Terminal (e na maioria dos terminais com Sixel), **escrever qualquer caractere sobre uma
célula apaga a parte da imagem naquela célula**. O Textual redesenha a tela escrevendo texto, então
a abordagem ingênua (desenhar a imagem depois de cada atualização) fica num ciclo de
*apaga → redesenha*: é o pisca-pisca. A solução fica dentro do próprio compositor:

1. **Células gráficas não são escritas.** O widget marca as células da imagem com um caractere
   de uso privado. Ao gerar a saída, `Strip.render` troca essas células por `CSI n C`, que move o
   cursor sem escrever nada, e a imagem permanece intacta.
2. **A imagem só é reenviada quando muda.** A cada frame o compositor calcula, para cada widget
   gráfico, a área visível (já considerando scroll e recorte) e a compara com o frame anterior.
   O Sixel só é gerado quando a imagem é nova, se moveu, foi recortada de outro jeito, mudou de
   conteúdo (novo quadro de vídeo) ou quando o terminal foi redimensionado. Digitar num `Input`
   não reenvia nada.
3. **Restos de imagem são limpos e buracos são consertados.** A área que uma imagem deixou de
   ocupar (depois de um scroll ou de remover o widget) é marcada para redesenho, e o texto escrito
   ali apaga a imagem antiga. O compositor também guarda, célula por célula, se o terminal está
   mostrando a imagem. Quando uma célula volta a ser de imagem depois de ter sido apagada por texto
   (menu fechado, texto encurtado), só aquele retângulo é reenviado.
4. **Tudo num frame só.** A imagem é escrita antes do texto, no mesmo bloco de
   *synchronized output* (`CSI ?2026h … l`). O terminal mostra o resultado de uma vez, e widgets
   sobrepostos (menus, notificações) são escritos depois, ficando por cima da imagem.
5. **Detecção automática.** Os drivers de Windows e Linux consultam o suporte a synchronized
   output, o DA1 (que indica Sixel) e o tamanho da célula em pixels (`CSI 16 t`). Antes deste fork,
   o driver de Windows nunca ativava o synchronized output.

O codificador Sixel (`textual/_sixel.py`) é vetorizado com NumPy: cerca de 22 ms para um quadro
de 880×520 px com 128 cores. No Windows Terminal, o `Video` alcança cerca de 27–30 fps nesse tamanho.

### Variáveis de ambiente

| Variável | Efeito |
|---|---|
| `TEXTUAL_GRAPHICS=sixel` | força Sixel (útil se o terminal não anunciar o suporte) |
| `TEXTUAL_GRAPHICS=halfblock` | força blocos coloridos em todos os widgets em modo `auto` |

### Limitações conhecidas

- Apenas Sixel; os protocolos Kitty e iTerm2 ainda não estão implementados (sem eles, usa-se `halfblock`).
- Imagens não aparecem no modo *inline* (`App.run(inline=True)`), onde é usado `halfblock`.
- Em telas com fundo esmaecido (por trás de um `ModalScreen`), a imagem não recebe o escurecimento.
- Degradês em vídeo podem mostrar faixas com 128 cores; use `colors=256` para mais qualidade (com menos fps).

Detalhes de design em [`docs/superpowers/specs/2026-11-09-sixel-image-video-design.md`](docs/superpowers/specs/2026-11-09-sixel-image-video-design.md).

<img src="https://img.spacergif.org/spacer.gif" width="1" height="32"/>

## Installing

Install Textual via pip:

```
pip install textual textual-dev
```

See [getting started](https://textual.textualize.io/getting_started/) for details.


<img src="https://img.spacergif.org/spacer.gif" width="1" height="32"/>

## Demo


Run the following command to see a little of what Textual can do:

```
python -m textual
```

Or try the [textual demo](https://github.com/textualize/textual-demo) *without* installing (requires [uv](https://docs.astral.sh/uv/)):

```bash
uvx --python 3.12 textual-demo
```

<img src="https://img.spacergif.org/spacer.gif" width="1" height="32"/>

## Dev Console

<img align="right" width="40%" alt="devtools" src="https://github.com/user-attachments/assets/12c60d65-e342-4b2f-9372-bae0459a7552" />


How do you debug an app in the terminal that is also running in the terminal?

The `textual-dev` package supplies a dev console that connects to your application from another terminal.
In addition to system messages and events, your logged messages and print statements will appear in the dev console.

See [the guide](https://textual.textualize.io/guide/devtools/) for other helpful tools provided by the `textual-dev` package.

<img src="https://img.spacergif.org/spacer.gif" width="1" height="32"/>

## Command Palette


Textual apps have a *fuzzy search* command palette.
Hit `ctrl+p` to open the command palette.

It is easy to extend the command palette with [custom commands](https://textual.textualize.io/guide/command_palette/) for your application.


![Command Palette](https://github.com/user-attachments/assets/94d8ec5d-b668-4033-a5cb-bf820e1b8d60)

<img src="https://img.spacergif.org/spacer.gif" width="1" height="32"/>

# Textual ❤️ Web

<img align="right" width="40%" alt="textual-serve" src="https://github.com/user-attachments/assets/a25820fb-87ae-433a-858b-ac3940169242">


Textual apps are equally at home in the browser as they are the terminal. Any Textual app may be served with `textual serve` &mdash; so you can share your creations on the web.
Here's how to serve the demo app:

```
textual serve "python -m textual"
```

In addition to serving your apps locally, you can serve apps with [Textual Web](https://github.com/Textualize/textual-web).

Textual Web's firewall-busting technology can serve an unlimited number of applications.

Since Textual apps have low system requirements, you can install them anywhere Python also runs. Turning any device into a connected device.
No desktop required!


<img src="https://img.spacergif.org/spacer.gif" width="1" height="32"/>


## Join us on Discord

Join the Textual developers and community on our [Discord Server](https://discord.gg/Enf6Z3qhVr).
