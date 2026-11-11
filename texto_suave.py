"""Texto TrueType com cobertura suave, em texturas OpenGL reutilizáveis.

Pillow rasteriza a fonte em resolução 4x; a redução com Lanczos preserva
cobertura parcial nas bordas. Isso funciona mesmo sem MSAA no contexto.
"""

from collections import OrderedDict
from dataclasses import dataclass
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from OpenGL.GL import (
    GL_ALPHA_TEST, GL_BLEND, GL_CLIENT_PIXEL_STORE_BIT, GL_COLOR_BUFFER_BIT,
    GL_CURRENT_BIT, GL_DEPTH_BUFFER_BIT, GL_ENABLE_BIT, GL_FALSE, GL_LIGHTING,
    GL_LINEAR, GL_MODULATE, GL_ONE_MINUS_SRC_ALPHA, GL_QUADS, GL_RGBA,
    GL_SRC_ALPHA, GL_TEXTURE_2D, GL_TEXTURE_BIT, GL_TEXTURE_ENV,
    GL_TEXTURE_ENV_MODE, GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE,
    GL_UNPACK_ALIGNMENT, GL_UNPACK_ROW_LENGTH, GL_UNPACK_SKIP_PIXELS,
    GL_UNPACK_SKIP_ROWS, GL_UNSIGNED_BYTE, GLuint,
    glBegin, glBindTexture, glBlendFunc, glColor4f, glDeleteTextures,
    glDepthMask, glDisable, glEnable, glEnd, glGenTextures, glPixelStorei,
    glPopAttrib, glPopClientAttrib, glPushAttrib, glPushClientAttrib,
    glTexCoord2f, glTexEnvi, glTexImage2D, glTexParameteri, glVertex3f,
)


@dataclass(frozen=True)
class TextoRasterizado:
    imagem: Image.Image
    esquerda: int
    topo: int
    avanco: float


class RenderizadorTexto:
    """As coordenadas de desenho usam linha-base e projeção com Y para baixo."""

    AMOSTRAS = 4

    def __init__(self, limite_texturas=256, limite_fontes=32):
        self.limite_texturas = max(1, limite_texturas)
        self.limite_fontes = max(1, limite_fontes)
        self._fontes = OrderedDict()
        self._texturas = OrderedDict()
        self.caminho_fonte = self._encontrar_fonte()

    @staticmethod
    def _encontrar_fonte():
        fontes = (
            Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        )
        for caminho in fontes:
            if caminho.is_file():
                try:
                    ImageFont.truetype(str(caminho), 16)
                    return str(caminho)
                except OSError:
                    continue
        # A fonte TrueType padrão é distribuída com o próprio Pillow.
        return None

    @staticmethod
    def _pixels(pixels):
        return max(1, int(round(pixels)))

    def _fonte(self, pixels):
        pixels = self._pixels(pixels)
        if pixels in self._fontes:
            self._fontes.move_to_end(pixels)
            return self._fontes[pixels]
        tamanho = pixels * self.AMOSTRAS
        fonte = (ImageFont.truetype(self.caminho_fonte, tamanho)
                 if self.caminho_fonte else ImageFont.load_default(size=tamanho))
        self._fontes[pixels] = fonte
        if len(self._fontes) > self.limite_fontes:
            self._fontes.popitem(last=False)
        return fonte

    def medir(self, conteudo, pixels):
        """Avanço horizontal físico, sem criar textura nem exigir contexto GL."""
        return self._fonte(pixels).getlength(str(conteudo)) / self.AMOSTRAS

    def rasterizar(self, conteudo, pixels):
        """Imagem RGBA e deslocamentos físicos relativos à linha-base.

        Não acessa OpenGL. A imagem preserva os acentos e descendentes da fonte;
        a cor branca permite tingir a mesma textura para qualquer jogador.
        """
        conteudo = str(conteudo)
        fonte = self._fonte(pixels)
        amostras = self.AMOSTRAS
        esquerda, topo, direita, fundo = fonte.getbbox(conteudo, anchor="ls")
        # Dois pixels transparentes evitam cortar a filtragem nas extremidades.
        esquerda = math.floor(esquerda / amostras) - 2
        topo = math.floor(topo / amostras) - 2
        direita = math.ceil(direita / amostras) + 2
        fundo = math.ceil(fundo / amostras) + 2
        dimensoes = (max(1, direita - esquerda), max(1, fundo - topo))
        cobertura = Image.new("L", tuple(v * amostras for v in dimensoes), 0)
        ImageDraw.Draw(cobertura).text(
            (-esquerda * amostras, -topo * amostras), conteudo,
            font=fonte, fill=255, anchor="ls",
        )
        cobertura = cobertura.resize(dimensoes, Image.Resampling.LANCZOS)
        imagem = Image.new("RGBA", dimensoes, (255, 255, 255, 0))
        imagem.putalpha(cobertura)
        return TextoRasterizado(imagem, esquerda, topo, self.medir(conteudo, pixels))

    def _textura(self, conteudo, pixels):
        chave = (conteudo, self._pixels(pixels))
        if chave in self._texturas:
            self._texturas.move_to_end(chave)
            return self._texturas[chave]
        raster = self.rasterizar(*chave)
        identificadores = (GLuint * 1)()
        glGenTextures(1, identificadores)
        textura = identificadores[0]
        glBindTexture(GL_TEXTURE_2D, textura)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glPushClientAttrib(GL_CLIENT_PIXEL_STORE_BIT)
        try:
            glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
            glPixelStorei(GL_UNPACK_ROW_LENGTH, 0)
            glPixelStorei(GL_UNPACK_SKIP_PIXELS, 0)
            glPixelStorei(GL_UNPACK_SKIP_ROWS, 0)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, *raster.imagem.size, 0,
                         GL_RGBA, GL_UNSIGNED_BYTE, raster.imagem.tobytes())
        finally:
            glPopClientAttrib()
        dados = (textura, raster.imagem.width, raster.imagem.height,
                 raster.esquerda, raster.topo)
        self._texturas[chave] = dados
        if len(self._texturas) > self.limite_texturas:
            _, antigo = self._texturas.popitem(last=False)
            glDeleteTextures([antigo[0]])
        return dados

    def desenhar(self, x, y, conteudo, pixels, cor, escala=1.0, z=0.0):
        """Desenha sem modificar projeção, teste de profundidade ou estado alheio.

        O chamador fornece X/Y lógicos e tamanho físico em pixels. Z permite
        desenhar rótulos projetados da cena mantendo a oclusão da geometria.
        """
        conteudo = str(conteudo)
        if not conteudo:
            return
        if escala <= 0:
            raise ValueError("A escala do texto precisa ser positiva.")
        glPushAttrib(GL_ENABLE_BIT | GL_COLOR_BUFFER_BIT | GL_TEXTURE_BIT
                     | GL_CURRENT_BIT | GL_DEPTH_BUFFER_BIT)
        try:
            textura, largura, altura, esquerda, topo = self._textura(conteudo, pixels)
            glDisable(GL_LIGHTING)
            glDisable(GL_ALPHA_TEST)
            glEnable(GL_TEXTURE_2D)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            # Pixels transparentes não devem preencher o buffer de profundidade.
            glDepthMask(GL_FALSE)
            glBindTexture(GL_TEXTURE_2D, textura)
            glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE)
            glColor4f(*cor[:3], cor[3] if len(cor) > 3 else 1.0)
            x1, y1 = x + esquerda / escala, y + topo / escala
            x2, y2 = x1 + largura / escala, y1 + altura / escala
            glBegin(GL_QUADS)
            for u, v, vx, vy in ((0, 0, x1, y1), (1, 0, x2, y1),
                                 (1, 1, x2, y2), (0, 1, x1, y2)):
                glTexCoord2f(u, v)
                glVertex3f(vx, vy, z)
            glEnd()
        finally:
            glPopAttrib()

    def limpar(self):
        """Libera o cache GPU enquanto o contexto OpenGL ainda está ativo."""
        if self._texturas:
            glDeleteTextures([dados[0] for dados in self._texturas.values()])
            self._texturas.clear()
