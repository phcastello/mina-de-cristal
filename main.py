"""Mina de Cristal: cena 3D e interface visual em PyOpenGL/FreeGLUT."""

import math
import random
import sys

try:
    from OpenGL.GL import *
    from OpenGL.GLU import gluPerspective, gluProject
    from OpenGL.GLUT import *
    from texto_suave import RenderizadorTexto
except ImportError:
    raise SystemExit("Instale as dependências: python -m pip install -r requirements.txt")

import jogo

letras = RenderizadorTexto()

estado = None
tela = "menu"
origem_instrucoes = "menu"
quantidade = 2
largura, altura = 1280, 800
escala = min(largura / 1440, altura / 900)
largura_logica, altura_logica = largura / escala, altura / escala
origem_painel = (0, 0)
amostras_msaa = 0
distancia, azimute, incidencia = 15.8, 0.0, 26.0
arrastando = False
mouse_anterior = (0, 0)
mouse_inicio = None
ponteiro = (-1, -1)
botoes = []
texturas = {}
alvos_casas = {}
centros_casas = {}
selecionada = None
modo_sondagem = False

FUNDO = (0.035, 0.052, 0.073)
PAINEL = (0.065, 0.092, 0.12)
BORDA = (0.16, 0.22, 0.28)
TEXTO = (0.94, 0.96, 0.98)
SUAVE = (0.59, 0.69, 0.76)
OURO = (1.0, 0.77, 0.32)
VERDE = (0.32, 0.9, 0.66)
CIANO = (0.23, 0.84, 1.0)
PERIGO = (1.0, 0.43, 0.38)

def restaurar_camera():
    global distancia, azimute, incidencia
    distancia, azimute, incidencia = 15.8, 0.0, 26.0

def ajustar_camera(giro=0, elevacao=0, zoom=0):
    global distancia, azimute, incidencia
    azimute = (azimute + giro) % 360
    incidencia = max(15, min(75, incidencia + elevacao))
    distancia = max(9, min(27, distancia + zoom))

def iniciar_partida():
    global estado, tela, arrastando, modo_sondagem, selecionada
    estado = jogo.novo_jogo(quantidade)
    tela, arrastando, modo_sondagem = "jogo", False, False
    selecionada = None
    restaurar_camera()


def criar_textura(tipo):
    """Texturas RGB determinísticas; não precisam de imagens externas nem NumPy."""
    gerador = random.Random(42)
    pixels = bytearray()
    for y in range(64):
        for x in range(64):
            ruido = gerador.randint(-15, 15)
            if tipo == "pedra":
                base = 150 + ruido - (22 if (x + 2 * y) % 31 < 2 else 0)
                cor = (base, base - 8, base - 18)
            else:
                veio = int(16 * math.sin(x * 0.7 + math.sin(y * 0.17)))
                base = 145 + veio + ruido
                cor = (base, int(base * 0.68), int(base * 0.39))
            pixels.extend(max(0, min(255, canal)) for canal in cor)
    # Buffer nativo evita exigir NumPy para receber o identificador da textura.
    nomes = (GLuint * 1)()
    glGenTextures(1, nomes)
    textura = nomes[0]
    glBindTexture(GL_TEXTURE_2D, textura)
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, 64, 64, 0, GL_RGB, GL_UNSIGNED_BYTE, bytes(pixels))
    return textura


def material(cor, brilho=12):
    glColor3f(*cor)
    glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, (0.55, 0.55, 0.55, 1.0))
    glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, brilho)


def bloco(x, y, z, sx, sy, sz, cor, textura=None):
    """Cubo com uma normal por face e coordenadas de textura explícitas."""
    glPushMatrix()
    glTranslatef(x, y, z)
    glScalef(sx, sy, sz)
    material(cor)
    if textura:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texturas[textura])
    faces = [
        ((0, 0, 1), ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))),
        ((0, 0, -1), ((-1, 1, -1), (1, 1, -1), (1, -1, -1), (-1, -1, -1))),
        ((0, 1, 0), ((-1, 1, 1), (1, 1, 1), (1, 1, -1), (-1, 1, -1))),
        ((0, -1, 0), ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1))),
        ((1, 0, 0), ((1, -1, 1), (1, -1, -1), (1, 1, -1), (1, 1, 1))),
        ((-1, 0, 0), ((-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1))),
    ]
    glBegin(GL_QUADS)
    for normal, vertices in faces:
        glNormal3f(*normal)
        for uv, vertice in zip(((0, 0), (1, 0), (1, 1), (0, 1)), vertices):
            glTexCoord2f(*uv)
            glVertex3f(*(coordenada * 0.5 for coordenada in vertice))
    glEnd()
    glDisable(GL_TEXTURE_2D)
    glPopMatrix()


def forma_avatar(indice, tamanho=1):
    glPushMatrix()
    glScalef(tamanho, tamanho, tamanho)
    material(jogo.IDENTIDADES[indice][1], 45)
    if indice == 0:
        glutSolidSphere(0.19, 16, 12)
    elif indice == 1:
        glutSolidCube(0.33)
    elif indice == 2:
        glTranslatef(0, 0, -0.18)
        glutSolidCone(0.21, 0.4, 16, 2)
    else:
        glScalef(0.23, 0.23, 0.23)
        glutSolidOctahedron()
    glPopMatrix()


def diamante(valor):
    material((0.25, 0.87, 0.96), 100)
    glPushMatrix()
    glTranslatef(0.09, 0.05, 0.37)
    glRotatef(20, 0, 0, 1)
    glScalef(0.19, 0.19, 0.29)
    glutSolidOctahedron()
    glPopMatrix()
    texto_3d(0.03, 0.06, 0.77, str(valor), (0.65, 0.96, 1.0))


def tunel():
    # Abertura escura, duas colunas e uma viga de madeira.
    bloco(0.08, 0.08, 0.11, 0.55, 0.48, 0.06, (0.035, 0.045, 0.055))
    for x in (-0.17, 0.33):
        bloco(x, 0.18, 0.30, 0.09, 0.12, 0.49, (0.95, 0.83, 0.67), "madeira")
    bloco(0.08, 0.18, 0.56, 0.64, 0.15, 0.12, (0.95, 0.83, 0.67), "madeira")


def esconderijo():
    bloco(0.08, 0.09, 0.22, 0.53, 0.46, 0.28, (0.42, 0.38, 0.63), "pedra")
    bloco(0.08, 0.09, 0.39, 0.60, 0.51, 0.07, (0.67, 0.53, 0.86))
    bloco(0.08, -0.15, 0.27, 0.19, 0.03, 0.22, (0.09, 0.07, 0.15))


def pista():
    bloco(0.06, 0.12, 0.31, 0.07, 0.08, 0.52, (0.94, 0.83, 0.65), "madeira")
    bloco(0.06, 0.12, 0.54, 0.51, 0.10, 0.23, (0.38, 0.86, 0.64))
    material((0.85, 1.0, 0.82))
    glPushMatrix()
    glTranslatef(0.21, 0.12, 0.54)
    glRotatef(90, 0, 1, 0)
    glutSolidCone(0.16, 0.23, 3, 1)
    glPopMatrix()


def texto_3d(x, y, z, conteudo, cor=TEXTO):
    glRasterPos3f(x, y, z)
    if not glGetBooleanv(GL_CURRENT_RASTER_POSITION_VALID):
        return
    px, py, profundidade, _ = glGetDoublev(GL_CURRENT_RASTER_POSITION)
    # Mantém a oclusão da cena, mas desenha os glifos alinhados aos pixels.
    modo_anterior = int(glGetIntegerv(GL_MATRIX_MODE))
    viewport_anterior = tuple(glGetIntegerv(GL_VIEWPORT))
    glViewport(0, 0, largura, altura)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, largura, altura, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    try:
        letras.desenhar(round(px), round(altura-py), str(conteudo), max(10,round(13*escala)),
                        cor, z=1-2*profundidade)
    finally:
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(modo_anterior)
        glViewport(*viewport_anterior)


def contorno(x, y, cor, tamanho=0.90):
    for deslocamento in (-tamanho / 2, tamanho / 2):
        bloco(x + deslocamento, y, 0.035, 0.035, tamanho, 0.025, cor)
        bloco(x, y + deslocamento, 0.035, tamanho, 0.035, 0.025, cor)




def mundo(posicao):
    linha, coluna = posicao
    return coluna - (jogo.COLUNAS - 1) / 2, (jogo.LINHAS - 1) / 2 - linha

def cenario():
    bloco(0, 0, -0.40, jogo.COLUNAS + 2.5, jogo.LINHAS + 2.5, 0.48,
          (0.43, 0.47, 0.48), "pedra")
    for x in (-5.0, 5.0):
        for y in (-3.1, 0, 3.1):
            glPushMatrix()
            glTranslatef(x, y, -0.03)
            glScalef(0.38, 0.53, 0.34)
            glRotatef(24, 1, 1, 0)
            material((0.35, 0.40, 0.43))
            glutSolidDodecahedron()
            glPopMatrix()
        for y in (-2.8, 2.8):
            bloco(x, y, 0.45, 0.16, 0.16, 1.2, (0.8, 0.73, 0.58), "madeira")
        bloco(x, 0, 1.0, 0.18, 5.8, 0.16, (0.8, 0.73, 0.58), "madeira")

def posto_3d(numero, visitado):
    cor = VERDE if visitado else OURO
    bloco(-0.30, -0.24, 0.35, 0.045, 0.045, 0.70, cor)
    bloco(-0.18, -0.24, 0.61, 0.25, 0.035, 0.18, cor)
    texto_3d(-0.36, -0.24, 0.85, str(numero), cor)

def projetar(x, y, z):
    px, py, _ = gluProject(x, y, z)
    return px / escala, (altura - py) / escala

def tabuleiro():
    alvos_casas.clear()
    centros_casas.clear()
    jogador = estado["jogadores"][estado["atual"]] if estado else None
    atuais = []
    if jogador and tela == "jogo":
        linha, coluna = jogador["posicao"]
        atuais = [(linha + jogo.DIRECOES[d][0], coluna + jogo.DIRECOES[d][1])
                  for d in jogo.movimentos_validos(estado)]
    for linha in range(jogo.LINHAS):
        for coluna in range(jogo.COLUNAS):
            pos = (linha, coluna)
            x, y = mundo(pos)
            casa = estado["tabuleiro"][linha][coluna] if estado else None
            dono = casa["descobridor"] if casa else None
            cor = (0.36, 0.43, 0.48) if dono is None else (0.64, 0.68, 0.66)
            if pos in atuais and not modo_sondagem:
                cor = tuple(0.52 + canal * 0.35 for canal in jogador["cor"])
            bloco(x, y, -0.07, 0.94, 0.94, 0.14, cor, "pedra")
            # A área lógica inclui os pequenos vãos entre os blocos: a leitura
            # não deve saltar para o peão quando o ponteiro cruza uma borda.
            alvos_casas[pos] = [projetar(x + dx, y + dy, 0.02)
                               for dx, dy in ((-.50, -.50), (.50, -.50), (.50, .50), (-.50, .50))]
            centros_casas[pos] = projetar(x, y, .10)
            if dono is not None:
                contorno(x, y, jogo.IDENTIDADES[dono][1])
                glPushMatrix()
                glTranslatef(x - .30, y + .30, .12)
                forma_avatar(dono, .35)
                glPopMatrix()
                glPushMatrix()
                glTranslatef(x, y, 0)
                if casa["tipo"] == "diamante":
                    diamante(casa["valor"])
                elif casa["tipo"] == "tunel":
                    tunel()
                elif casa["tipo"] == "esconderijo":
                    esconderijo()
                else:
                    pista()
                glPopMatrix()
            if jogador and pos in jogador["sondagens"] and dono is None:
                contorno(x, y, CIANO, .70)
            if estado and pos in jogo.POSTOS:
                glPushMatrix()
                glTranslatef(x, y, 0)
                posto_3d(jogo.POSTOS.index(pos) + 1, pos in jogador["postos_visitados"])
                glPopMatrix()
            if pos in atuais and tela == "jogo" and not modo_sondagem:
                # Borda elevada continua visível mesmo nas revisitas.
                contorno(x, y, jogador["cor"], .98)
    for coluna in range(jogo.COLUNAS):
        x, _ = mundo((0, coluna))
        texto_3d(x - .07, jogo.LINHAS / 2 + .18, .02, chr(65 + coluna), SUAVE)
    for linha in range(jogo.LINHAS):
        _, y = mundo((linha, 0))
        texto_3d(-jogo.COLUNAS / 2 - .27, y, .02, str(linha + 1), SUAVE)
    for participante in estado["jogadores"] if estado else []:
        indice = participante["id"]
        x, y = mundo(jogo.ENTRADAS[indice])
        bloco(x, y, -.10, .74, .74, .12, participante["cor"])
        texto_3d(x - .06, y, .02, str(indice + 1), TEXTO)
        if participante["invisivel"]:
            continue
        x, y = mundo(participante["posicao"])
        dx, dy = [(-.23, -.22), (.23, -.22), (.23, .19), (-.23, .19)][indice]
        if indice == estado["atual"] and tela == "jogo":
            # Marcador em losango e seta: identificação também por forma/número.
            contorno(x, y, participante["cor"], .78)
            glPushMatrix()
            glTranslatef(x + dx, y + dy, 1.24)
            glRotatef(180, 1, 0, 0)
            material(participante["cor"])
            glutSolidCone(.14, .30, 4, 1)
            glPopMatrix()
        glPushMatrix()
        glTranslatef(x + dx, y + dy, .36)
        forma_avatar(indice, .9)
        if participante["protegido"]:
            material(CIANO)
            glutWireSphere(.29, 12, 8)
        glPopMatrix()
        texto_3d(x + dx - .03, y + dy, .69, str(indice + 1), participante["cor"])

def vista_polar():
    glTranslatef(0, 0, -distancia)
    glRotatef(-incidencia, 1, 0, 0)
    glRotatef(azimute, 0, 0, 1)

def desenhar_cena():
    vw = max(1, int((largura_logica - 400) * escala))
    vh = max(1, int((altura_logica - 286) * escala))
    glViewport(int(16 * escala), int(170 * escala), vw, vh)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    aspecto = vw / vh
    campo = math.degrees(2 * math.atan(math.tan(math.radians(45) / 2) * max(1, 1.20 / aspecto)))
    gluPerspective(campo, aspecto, .5, 80)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    vista_polar()
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glLightfv(GL_LIGHT0, GL_POSITION, (-3., 1., 8., 1.))
    if estado and tela in ("jogo", "pausa"):
        jogador = estado["jogadores"][estado["atual"]]
        if not jogador["invisivel"]:
            x, y = mundo(jogador["posicao"])
            glEnable(GL_LIGHT1)
            glLightfv(GL_LIGHT1, GL_POSITION, (x, y, 3., 1.))
            glLightfv(GL_LIGHT1, GL_SPOT_DIRECTION, (0., 0., -1.))
            glLightfv(GL_LIGHT1, GL_DIFFUSE, (*jogador["cor"], 1.))
        else:
            glDisable(GL_LIGHT1)
    else:
        glDisable(GL_LIGHT1)
    cenario()
    tabuleiro()

def projecao_2d():
    glViewport(0, 0, largura, altura)
    glDisable(GL_DEPTH_TEST)
    glDisable(GL_LIGHTING)
    glDisable(GL_TEXTURE_2D)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glOrtho(0, largura_logica, altura_logica, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

def retangulo(x, y, w, h, cor):
    glColor3f(*cor)
    glBegin(GL_QUADS)
    for vx, vy in ((x,y), (x+w,y), (x+w,y+h), (x,y+h)):
        glVertex2f(vx, vy)
    glEnd()

def poligono(pontos, cor):
    glColor3f(*cor)
    glBegin(GL_POLYGON)
    for x, y in pontos:
        glVertex2f(x, y)
    glEnd()

def circulo(x, y, r, cor):
    poligono([(x + math.cos(a * math.pi / 16) * r, y + math.sin(a * math.pi / 16) * r)
              for a in range(32)], cor)

def linha_2d(pontos, cor, espessura=2):
    glColor3f(*cor)
    glLineWidth(espessura)
    glBegin(GL_LINE_STRIP)
    for x, y in pontos:
        glVertex2f(x, y)
    glEnd()
    glLineWidth(1)

def fonte(tamanho):
    return max(9, round(tamanho*escala))

def medida(conteudo, tamanho=16):
    return letras.medir(str(conteudo), fonte(tamanho)) / escala

def texto(x, y, conteudo, cor=TEXTO, tamanho=16):
    # Alinha a textura à tela para não borrar glifos pequenos ao redimensionar.
    dx, dy = origem_painel
    x = round((x+dx)*escala)/escala-dx
    y = round((y+dy)*escala)/escala-dy
    letras.desenhar(x, y, str(conteudo), fonte(tamanho), cor, escala=escala)

def centralizado(x, y, conteudo, cor=TEXTO, tamanho=16):
    texto(x - medida(conteudo, tamanho) / 2, y, conteudo, cor, tamanho)

def paragrafo(x, y, conteudo, limite, cor=SUAVE, tamanho=16, entrelinha=24):
    linha = ""
    for palavra in conteudo.split():
        tentativa = (linha + " " + palavra).strip()
        if linha and medida(tentativa, tamanho) > limite:
            texto(x, y, linha, cor, tamanho)
            y += entrelinha
            linha = palavra
        else:
            linha = tentativa
    if linha:
        texto(x, y, linha, cor, tamanho)
    return y + entrelinha

def icone(tipo, x, y, s=24, cor=TEXTO):
    """Símbolos geométricos próprios, independentes de fontes Unicode."""
    if tipo == "diamante":
        poligono([(x,y-s*.6),(x+s*.48,y),(x,y+s*.6),(x-s*.48,y)], cor)
        linha_2d([(x-s*.32,y),(x+s*.32,y)], FUNDO)
    elif tipo == "perigo":
        poligono([(x,y-s*.60),(x+s*.60,y+s*.48),(x-s*.60,y+s*.48)], cor)
        retangulo(x-s*.065,y-s*.23,s*.13,s*.36,FUNDO)
        circulo(x,y+s*.29,s*.075,FUNDO)
    elif tipo == "escudo":
        poligono([(x-s*.48,y-s*.5),(x+s*.48,y-s*.5),(x+s*.4,y+s*.12),
                  (x,y+s*.60),(x-s*.4,y+s*.12)], cor)
        linha_2d([(x-s*.23,y),(x-s*.03,y+s*.20),(x+s*.25,y-s*.19)], FUNDO, 3)
    elif tipo == "radar":
        circulo(x,y,s*.56,cor)
        circulo(x,y,s*.43,FUNDO)
        circulo(x,y,s*.31,cor)
        circulo(x,y,s*.21,FUNDO)
        linha_2d([(x,y),(x+s*.39,y-s*.39)],cor,3)
        circulo(x-s*.18,y+s*.11,s*.065,TEXTO)
    elif tipo == "bandeira":
        retangulo(x-s*.4,y-s*.57,s*.08,s*1.15,cor)
        poligono([(x-s*.32,y-s*.55),(x+s*.50,y-s*.55),(x+s*.27,y-s*.22),
                  (x+s*.50,y+s*.08),(x-s*.32,y+s*.08)],cor)
    elif tipo == "energia":
        poligono([(x+s*.12,y-s*.62),(x-s*.43,y+s*.06),(x-s*.04,y+s*.06),
                  (x-s*.14,y+s*.62),(x+s*.43,y-s*.12),(x+s*.04,y-s*.12)],cor)
    elif tipo == "ok":
        linha_2d([(x-s*.43,y),(x-s*.08,y+s*.33),(x+s*.46,y-s*.35)],cor,4)
    elif tipo == "olho":
        linha_2d([(x-s*.55,y),(x,y-s*.3),(x+s*.55,y),(x,y+s*.3),(x-s*.55,y)],cor,2)
        linha_2d([(x-s*.5,y+s*.48),(x+s*.5,y-s*.48)],cor,3)
    elif tipo in ("cima","baixo","esquerda","direita","play"):
        angulo = {"cima":-90,"baixo":90,"esquerda":180,"direita":0,"play":0}[tipo]
        a = math.radians(angulo)
        pts = [(.48,0),(-.27,-.40),(-.27,.40)]
        poligono([(x+(px*math.cos(a)-py*math.sin(a))*s,
                   y+(px*math.sin(a)+py*math.cos(a))*s) for px,py in pts],cor)
    elif tipo == "tunel":
        retangulo(x-s*.50,y-s*.48,s,s,cor)
        retangulo(x-s*.27,y-s*.23,s*.54,s*.75,FUNDO)
    elif tipo == "esconderijo":
        retangulo(x-s*.5,y-s*.35,s,s*.75,cor)
        retangulo(x-s*.18,y-s*.03,s*.36,s*.43,FUNDO)
    elif tipo == "pista":
        icone("bandeira",x,y,s,cor)
    elif tipo == "cruz":
        for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)):
            retangulo(x+dx*s*.4-s*.12,y+dy*s*.4-s*.12,s*.24,s*.24,cor)
        retangulo(x-s*.12,y-s*.12,s*.24,s*.24,CIANO)
    else:
        centralizado(x,y+s*.25,"?",cor,max(16,s))

def avatar_2d(indice, x, y, s=32, cor=None):
    cor = cor or jogo.IDENTIDADES[indice][1]
    if indice == 0:
        circulo(x,y,s*.48,cor)
    elif indice == 1:
        retangulo(x-s*.45,y-s*.45,s*.9,s*.9,cor)
    elif indice == 2:
        poligono([(x,y-s*.55),(x+s*.52,y+s*.43),(x-s*.52,y+s*.43)],cor)
    else:
        poligono([(x,y-s*.57),(x+s*.49,y),(x,y+s*.57),(x-s*.49,y)],cor)
    centralizado(x,y+s*.16,str(indice+1),FUNDO,max(16,s*.46))

def botao(x, y, w, h, rotulo, acao, destaque=False, simbolo=None, ativo=True, cor=None):
    dx,dy = origem_painel
    sobre = x+dx <= ponteiro[0] <= x+dx+w and y+dy <= ponteiro[1] <= y+dy+h
    base = cor or (OURO if destaque else BORDA)
    if not ativo:
        base = cor if cor and destaque else tuple(v*.48 for v in BORDA)
    elif sobre:
        base = tuple(min(1,v*1.20+.04) for v in base)
    retangulo(x,y,w,h,base)
    tinta = FUNDO if destaque else TEXTO
    if not ativo:
        tinta = FUNDO if cor and destaque else SUAVE
    if simbolo:
        icone(simbolo,x+27,y+h/2,24,tinta)
        texto(x+50,y+h/2+6,rotulo,tinta,17)
    else:
        centralizado(x+w/2,y+h/2+6,rotulo,tinta,18)
    if ativo:
        botoes.append((x+dx,y+dy,w,h,acao))

def painel_centralizado(desenhar):
    global origem_painel
    origem_painel = ((largura_logica-1440)/2,(altura_logica-900)/2)
    glPushMatrix()
    glTranslatef(*origem_painel,0)
    try:
        desenhar()
    finally:
        glPopMatrix()
        origem_painel = (0,0)

def escurecer():
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(.01,.02,.03,.87)
    glBegin(GL_QUADS)
    for x,y in ((0,0),(largura_logica,0),(largura_logica,altura_logica),(0,altura_logica)):
        glVertex2f(x,y)
    glEnd()
    glDisable(GL_BLEND)



def cabecalho():
    retangulo(0,0,largura_logica,106,PAINEL)
    if estado:
        jogador = estado["jogadores"][estado["atual"]]
        cor = jogador["cor"]
        retangulo(0,0,largura_logica,6,cor)
        avatar_2d(jogador["id"],57,55,58)
        texto(104,35,"SUA VEZ",SUAVE,13)
        texto(104,69,f"JOGADOR {jogador['id']+1}  /  {jogador['nome'].upper()}",cor,26)
        inicio = min(560,largura_logica-850)
        for i,p in enumerate(estado["jogadores"]):
            px = inicio + i*78
            if p["id"] == estado["atual"]:
                retangulo(px-29,24,58,65,BORDA)
                icone("cima",px,98,14,p["cor"])
            avatar_2d(p["id"],px,55,34)
        tx = largura_logica-382
        texto(tx,35,f"{estado['turnos']:02d} / {jogo.TOTAL_TURNOS}",OURO,18)
        texto(tx,59,"MOVIMENTOS",SUAVE,11)
        retangulo(tx,74,100,4,BORDA)
        retangulo(tx,74,100*estado["turnos"]/jogo.TOTAL_TURNOS,4,OURO)
        botao(largura_logica-254,27,116,50,"Pausa","pausa")
        botao(largura_logica-126,27,102,50,"?","instrucoes")
    else:
        icone("diamante",53,52,47,CIANO)
        texto(95,44,"MINA DE CRISTAL",TEXTO,26)
        texto(96,72,"Explore. Descubra pistas. Escolha seu caminho.",SUAVE,15)

def placar():
    x = largura_logica-366
    retangulo(x,122,342,322,PAINEL)
    icone("diamante",x+25,148,20,OURO)
    texto(x+47,154,"PLACAR",OURO,16)
    for indice,p in enumerate(jogo.ranking(estado)):
        y = 170 + indice*65
        atual = p["id"] == estado["atual"]
        retangulo(x+10,y,322,59,BORDA if atual else FUNDO)
        if atual:
            retangulo(x+10,y,5,59,p["cor"])
            icone("play",x+309,y+18,14,p["cor"])
        avatar_2d(p["id"],x+36,y+26,28)
        texto(x+60,y+23,p["nome"],p["cor"],17)
        pontos = str(p["pontos"])
        texto(x+288-medida(pontos,20),y+25,pontos,TEXTO,20)
        texto(x+60,y+45,f"{p['jogadas']}/{jogo.TOTAL_TURNOS//len(estado['jogadores'])}",SUAVE,12)
        for n in range(3):
            icone("energia",x+122+n*17,y+42,12,OURO if n<p["cargas"] else BORDA)
        if p["protegido"]:
            icone("escudo",x+190,y+41,17,CIANO)
        if p["invisivel"]:
            icone("olho",x+215,y+41,17,SUAVE)
        elif p["tunel_pendente"]:
            icone("tunel",x+211,y+41,17,PERIGO)
        for n in range(min(2,len(p["postos_visitados"]))):
            icone("bandeira",x+250+n*18,y+42,13,VERDE)

def painel_objetivo():
    x,y = largura_logica-366,456
    p = estado["jogadores"][estado["atual"]]
    retangulo(x,y,342,110,PAINEL)
    icone("bandeira",x+26,y+27,25,OURO)
    texto(x+49,y+24,"VISITE 2 POSTOS",OURO,16)
    texto(x+49,y+44,"Caminhe até as bandeiras",SUAVE,12)
    for i,pos in enumerate(jogo.POSTOS):
        bx = x+29+i*51
        visitado = pos in p["postos_visitados"]
        icone("bandeira",bx,y+76,24,VERDE if visitado else SUAVE)
        centralizado(bx+17,y+88,str(i+1),VERDE if visitado else TEXTO,12)
        if visitado:
            icone("ok",bx,y+76,15,FUNDO)
    if p["objetivo_concluido"]:
        icone("ok",x+257,y+74,28,VERDE)
        texto(x+280,y+83,"+8",VERDE,22)
    else:
        texto(x+242,y+70,f"{min(2,len(p['postos_visitados']))}/2",TEXTO,20)
        texto(x+243,y+94,"+8",OURO,20)

def selecionar_casa(posicao):
    global selecionada
    if posicao is not None and jogo.dentro(*posicao):
        selecionada = posicao

def consulta_pista():
    """O ponteiro tem prioridade; fora do tabuleiro, consulta a casa do peão."""
    if not estado:
        return None, None
    pos = casa_no_mouse(*ponteiro)
    if pos is None:
        atual = estado["jogadores"][estado["atual"]]["posicao"]
        pos = atual if jogo.dentro(*atual) else None
    return pos, jogo.pista_disponivel(estado, pos) if pos is not None else None

def marca_sondagem(posicao, dados=None):
    """O ícone identifica leituras que o jogador pode consultar novamente."""
    if posicao not in centros_casas:
        return
    x, y = centros_casas[posicao]
    if 32 < x < largura_logica-400 and 136 < y < altura_logica-188:
        circulo(x+14,y-14,8,FUNDO)
        icone("radar",x+14,y-14,13,CIANO)

def pista_flutuante():
    """Leitura contextual sobre a casa; não recebe cliques nem interrompe o jogo."""
    if tela != "jogo":
        return
    pos, dados = consulta_pista()
    if pos not in centros_casas:
        return
    cx,cy = centros_casas[pos]
    minimo_x,maximo_x = 24,largura_logica-392
    minimo_y,maximo_y = 154,altura_logica-178
    if not (minimo_x <= cx <= maximo_x and 116 <= cy <= maximo_y):
        return
    w,h = 234,104 if dados is None else 90
    x = max(minimo_x,min(maximo_x-w,cx-w/2))
    y = cy-h-25
    if y < minimo_y:
        y = cy+27
    y = min(y,maximo_y-h)
    cor = CIANO if dados is not None else SUAVE
    ponta_x = max(x+12,min(x+w-12,cx))
    ponta_y = y+h if y+h <= cy else y
    linha_2d([(cx,cy),(ponta_x,ponta_y)],cor,2)
    circulo(cx,cy,3,cor)
    retangulo(x,y,w,h,FUNDO)
    retangulo(x,y,w,3,cor)
    icone("cruz",x+18,y+19,18,cor)
    titulo = f"{jogo.nome_casa(pos)}  /  VIZINHOS"
    texto(x+35,y+24,titulo,cor,15)
    icone("perigo",x+25,y+50,23,PERIGO if dados is not None else SUAVE)
    texto(x+45,y+59,str(dados["armadilhas"]) if dados is not None else "?",TEXTO,23)
    icone("diamante",x+133,y+50,23,CIANO if dados is not None else SUAVE)
    texto(x+153,y+59,str(dados["quilates"]) if dados is not None else "?",TEXTO,23)
    texto(x+13,y+79,"armadilhas",SUAVE,12)
    texto(x+119,y+79,"quilates",SUAVE,12)
    if dados is None:
        texto(x+13,y+96,"Explore ou use o radar [Q]",SUAVE,12)

def marcadores_mapa():
    if tela != "jogo":
        return
    p = estado["jogadores"][estado["atual"]]
    if modo_sondagem:
        texto(30,134,"RADAR",CIANO,18)
        texto(124,134,"Clique em uma casa oculta",TEXTO,16)
    else:
        texto(30,134,"CLIQUE NAS SETAS PARA ANDAR",p["cor"],15)
    pos_pista, dados = consulta_pista()
    if pos_pista in alvos_casas:
        pontos = alvos_casas[pos_pista]
        linha_2d(pontos+[pontos[0]],CIANO if modo_sondagem else TEXTO,2)
    # Linhas unem a origem da leitura às casas que entram no cálculo.
    if pos_pista in centros_casas and dados is not None:
        centro = centros_casas[pos_pista]
        for dl,dc in jogo.DIRECOES.values():
            pos = (pos_pista[0]+dl,pos_pista[1]+dc)
            if pos in alvos_casas:
                pontos = alvos_casas[pos]
                linha_2d(pontos+[pontos[0]],CIANO,2.5)
                linha_2d([centro,centros_casas[pos]],(.12,.42,.50),1.5)
    # Leituras do radar permanecem no mapa apenas para seu autor.
    for pos in sorted(p["sondagens"]):
        linha,coluna = pos
        if estado["tabuleiro"][linha][coluna]["descobridor"] is None:
            marca_sondagem(pos)
    # Bandeiras em tela continuam reconhecíveis ao afastar a câmera.
    for i,pos in enumerate(jogo.POSTOS):
        if pos in centros_casas:
            x,y = centros_casas[pos]
            cor = VERDE if pos in p["postos_visitados"] else OURO
            if pos in p["sondagens"] and estado["tabuleiro"][pos[0]][pos[1]]["descobridor"] is None:
                # Separa a bandeira do pequeno ícone de radar.
                icone("bandeira",x-25,y-17,15,cor)
                texto(x-29,y-28,str(i+1),cor,11)
            else:
                circulo(x-10,y-14,15,FUNDO)
                icone("bandeira",x-10,y-14,21,cor)
                if pos in p["postos_visitados"]:
                    icone("ok",x-8,y-12,14,VERDE)
                texto(x+6,y-15,str(i+1),cor,13)
    for d in jogo.movimentos_validos(estado):
        dl,dc = jogo.DIRECOES[d]
        pos = (p["posicao"][0]+dl,p["posicao"][1]+dc)
        centro = centros_casas.get(pos)
        if centro and not modo_sondagem:
            x,y = centro
            # Triângulo aponta para o destino em qualquer orientação da câmera.
            # Ângulo de tela deriva da projeção dos próprios centros.
            anterior = centros_casas.get(p["posicao"])
            if anterior is None:
                # Entradas estão fora do cache; direção aproximada pelo eixo da tela.
                a = math.radians(90 if dl>0 else -90)
            else:
                a = math.atan2(y-anterior[1],x-anterior[0])
            circulo(x,y,16,FUNDO)
            pts = [(10,0),(-6,-8),(-6,8)]
            poligono([(x+px*math.cos(a)-py*math.sin(a),
                       y+px*math.sin(a)+py*math.cos(a)) for px,py in pts],p["cor"])
    pista_flutuante()

def barra_acoes():
    p = estado["jogadores"][estado["atual"]]
    x,y = 24,altura_logica-151
    w = largura_logica-420
    retangulo(x,y,w,128,PAINEL)
    icone("energia",x+28,y+28,25,OURO)
    texto(x+51,y+33,"ENERGIA",SUAVE,12)
    for n in range(3):
        retangulo(x+18+n*30,y+50,22,34,OURO if n<p["cargas"] else BORDA)
        if n<p["cargas"]:
            icone("energia",x+29+n*30,y+67,16,FUNDO)
    botao(x+125,y+20,186,61,"Sondar [Q]","sondar",modo_sondagem,"radar",
          p["cargas"]>0 or modo_sondagem,CIANO if modo_sondagem else None)
    botao(x+324,y+20,186,61,"Escudo [E]","proteger",p["protegido"],"escudo",
          p["cargas"]>0 and not p["protegido"],CIANO if p["protegido"] else None)
    if p["protegido"]:
        icone("escudo",x+490,y+103,19,CIANO)
        texto(x+322,y+108,"Proteção ativa",CIANO,13)
    else:
        texto(x+129,y+107,"Cada uso gasta 1 carga.",SUAVE,13)
    resumo_jogada(x+552,y+14)
    # Setas na cruz oferecem alternativa visual ao teclado.
    bx = x+w-135
    by = y+40
    validos = jogo.movimentos_validos(estado)
    for d,dx,dy in (("cima",0,-1),("baixo",0,1),("esquerda",-1,0),("direita",1,0)):
        px,py = bx+dx*37,by+dy*32
        disponivel = d in validos and not modo_sondagem
        botao(px,py,34,30,"","mover_"+d,False,None,disponivel)
        icone(d,px+17,py+15,21,p["cor"] if disponivel else SUAVE)
    texto(bx-39,y+117,"Q: CANCELAR" if modo_sondagem else "SETAS: MOVER",SUAVE,11)
    # Aviso curto não compete com os controles; detalhes ficam na ajuda.
    if estado["mensagem"] and tela=="jogo":
        aviso = estado["mensagem"]
        if len(aviso)>105:
            aviso = aviso[:102]+"..."
        texto(29,altura_logica-5,aviso,SUAVE,12)

def interface_jogo():
    cabecalho()
    placar()
    painel_objetivo()
    marcadores_mapa()
    barra_acoes()

def menu():
    cabecalho()
    x = largura_logica-602
    retangulo(x,139,578,altura_logica-164,PAINEL)
    icone("bandeira",x+43,184,34,OURO)
    texto(x+78,188,"UMA MINA. MUITAS ESCOLHAS.",OURO,18)
    texto(x+30,239,"Escolha os exploradores",TEXTO,26)
    for i,n in enumerate((2,3,4)):
        botao(x+30+i*174,269,160,61,f"{n} jogadores",f"jogadores_{n}",n==quantidade)
    for i in range(quantidade):
        cx = x+64+(i%2)*264
        cy = 377+(i//2)*63
        avatar_2d(i,cx,cy,42)
        texto(cx+35,cy+5,jogo.IDENTIDADES[i][0],jogo.IDENTIDADES[i][1],18)
    texto(x+30,506,"8 x 9 CASAS",CIANO,20)
    texto(x+288,506,f"{72//quantidade} MOVIMENTOS CADA",OURO,17)
    for i,(tipo,titulo,sub) in enumerate((
            ("radar","LEIA AS PISTAS","Risco e riqueza dos vizinhos"),
            ("escudo","ESCOLHA SEU EQUIPAMENTO","3 cargas para radar ou escudo"),
            ("bandeira","TRACE UMA ROTA","Visite 2 postos e ganhe +8"))):
        yy = 549+i*62
        icone(tipo,x+47,yy+4,30,(CIANO,VERDE,OURO)[i])
        texto(x+79,yy,titulo,TEXTO,15)
        texto(x+79,yy+22,sub,SUAVE,13)
    botao(x+30,751,518,57,"Entrar na mina [Enter]","iniciar",True,"play")
    botao(x+30,821,330,46,"Como jogar [H]","instrucoes")
    botao(x+374,821,174,46,"Sair [Esc]","sair")
    texto(35,altura_logica-81,"CLIQUE. EXPLORE. PLANEJE.",OURO,19)
    texto(35,altura_logica-48,"Os tesouros ficam ocultos até a descoberta.",SUAVE,14)

def resumo_jogada(x, y):
    """Retorno da última ação integrado à barra, sem bloquear o próximo jogador."""
    evento = estado.get("ultimo_evento")
    if not evento:
        return
    anterior = estado["jogadores"][evento["jogador"]]
    tipo = evento["tipo"]
    texto(x,y+5,"ÚLTIMA JOGADA",SUAVE,11)
    avatar_2d(anterior["id"],x+13,y+31,25)
    icone(tipo if tipo!="revisita" else "ok",x+49,y+31,24,
          PERIGO if tipo in ("tunel","esconderijo") else CIANO)
    delta = evento["pontos"]
    texto(x+72,y+37,f"{delta:+d}",VERDE if delta>=0 else PERIGO,20)
    if evento["objetivo"]:
        icone("bandeira",x+139,y+31,23,OURO)
        texto(x+158,y+37,"+8",OURO,17)
    if evento["bloqueado"]:
        icone("escudo",x+219,y+31,26,CIANO)
    if tipo=="esconderijo":
        for i,rival in enumerate(p for p in estado["jogadores"] if p["id"]!=anterior["id"]):
            px = x+13+i*76
            avatar_2d(rival["id"],px,y+77,23)
            if rival["id"] in evento["protegidos"]:
                icone("escudo",px+29,y+77,21,CIANO)
            else:
                texto(px+18,y+83,"-5",PERIGO,16)
    elif tipo=="tunel":
        icone("tunel",x+13,y+77,24,PERIGO)
        icone("direita",x+44,y+77,20,SUAVE)
        texto(x+65,y+83,"-10 ao sair",PERIGO,16)
    elif evento["posto"]:
        icone("bandeira",x+13,y+77,22,OURO)
        icone("ok",x+44,y+77,21,VERDE)


def pausa():
    retangulo(445,195,550,520,PAINEL)
    texto(483,251,"EXPEDIÇÃO PAUSADA",OURO,26)
    for y,rotulo,acao in ((294,"Continuar [P / Esc]","continuar"),
                           (371,"Reiniciar partida [R]","reiniciar"),
                           (448,"Como jogar [H]","instrucoes"),
                           (525,"Voltar ao menu [M]","menu"),
                           (602,"Sair do jogo","sair")):
        botao(483,y,474,57,rotulo,acao,acao=="continuar")

def instrucoes():
    retangulo(170,92,1100,724,PAINEL)
    texto(209,139,"GUIA VISUAL",OURO,26)
    exemplos = (
        ("play","1. SUA VEZ","Seu avatar fica destacado no alto. Clique nas setas do mapa para andar."),
        ("radar","2. PISTAS","Passe o mouse numa casa: a leitura flutua sobre ela e conta seus vizinhos."),
        ("perigo","3. RISCO","O triângulo conta armadilhas; o diamante soma os quilates ao redor."),
        ("energia","4. EQUIPAMENTOS","3 cargas no total. Q: sondar uma casa oculta. E: escudo contra uma perda."),
        ("bandeira","5. OBJETIVO","Visite 2 bandeiras diferentes: +8 pontos. Cada jogador pode completar."),
        ("diamante","6. TESOUROS","Diamante: +1 a +10. Placa: +3. Túnel: -10 ao sair. Esconderijo: rivais -5."),
    )
    for i,(tipo,titulo,descricao) in enumerate(exemplos):
        yy = 192+i*75
        icone(tipo,239,yy+12,35,(CIANO,CIANO,PERIGO,OURO,OURO,CIANO)[i])
        texto(278,yy,titulo,TEXTO,17)
        texto(278,yy+28,descricao,SUAVE,15)
    texto(209,681,"Setas: mover  |  W/A/S/D ou arraste: câmera  |  Z/X ou roda: zoom  |  Espaço: restaurar",SUAVE,14)
    texto(209,710,"Escudos bloqueiam uma perda própria. Pistas incluem casas já reveladas. São 72 movimentos ao todo.",SUAVE,14)
    botao(209,747,1022,46,"Voltar [Esc / H]","voltar",True)

def resultado():
    retangulo(345,128,750,640,PAINEL)
    ganhadores = jogo.vencedores(estado)
    cor = ganhadores[0]["cor"] if len(ganhadores)==1 else OURO
    retangulo(345,128,750,8,cor)
    texto(385,180,"EXPEDIÇÃO CONCLUÍDA",OURO,23)
    for i,p in enumerate(ganhadores):
        avatar_2d(p["id"],425+i*72,240,60)
    texto(385,307,"Vitória compartilhada!" if len(ganhadores)>1 else f"Vitória de {ganhadores[0]['nome']}!",TEXTO,26)
    for i,p in enumerate(jogo.ranking(estado)):
        y = 340+i*65
        retangulo(385,y,670,57,FUNDO)
        avatar_2d(p["id"],413,y+28,33)
        texto(445,y+34,p["nome"],p["cor"],18)
        texto(656,y+34,f"{p['pontos']} quilates",TEXTO,18)
        if p["objetivo_concluido"]:
            icone("bandeira",965,y+29,25,OURO)
            texto(988,y+34,"+8",OURO,17)
    exploradas = sum(c["descobridor"] is not None for row in estado["tabuleiro"] for c in row)
    texto(385,636,f"{exploradas} de 72 casas exploradas  /  72 movimentos",SUAVE,15)
    botao(385,684,324,55,"Jogar de novo [R]","reiniciar",True)
    botao(725,684,330,55,"Menu [M / Esc]","menu")

def display():
    botoes.clear()
    glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
    desenhar_cena()
    projecao_2d()
    if tela=="menu":
        menu()
    else:
        if estado:
            interface_jogo()
        if tela in ("pausa","instrucoes","resultado"):
            escurecer()
            botoes.clear()
            painel_centralizado({"pausa":pausa,
                                 "instrucoes":instrucoes,"resultado":resultado}[tela])
    glutSwapBuffers()


def reshape(width, height):
    global largura, altura, escala, largura_logica, altura_logica
    largura,altura = max(1,width),max(1,height)
    escala = min(largura/1440,altura/900)
    largura_logica,altura_logica = largura/escala,altura/escala
    glutPostRedisplay()

origem_pausa = "jogo"

def executar(acao):
    global tela, origem_instrucoes, origem_pausa, quantidade, estado
    global arrastando, modo_sondagem, selecionada, mouse_inicio
    arrastando = False
    mouse_inicio = None
    if acao.startswith("jogadores_") and tela=="menu":
        quantidade = int(acao[-1])
    elif acao=="iniciar" and tela=="menu":
        iniciar_partida()
    elif acao=="reiniciar" and estado:
        estado = jogo.reiniciar(estado)
        tela,modo_sondagem,selecionada = "jogo",False,None
        restaurar_camera()
    elif acao=="menu":
        tela,estado,modo_sondagem,selecionada = "menu",None,False,None
        restaurar_camera()
    elif acao=="pausa" and tela=="jogo":
        origem_pausa,tela = tela,"pausa"
        modo_sondagem = False
    elif acao=="continuar" and tela=="pausa":
        tela = origem_pausa
    elif acao=="resultado" and estado:
        tela,modo_sondagem = "resultado",False
    elif acao=="instrucoes":
        origem_instrucoes,tela = tela,"instrucoes"
        modo_sondagem = False
    elif acao=="voltar" and tela=="instrucoes":
        tela = origem_instrucoes
    elif acao=="sondar" and tela=="jogo":
        if modo_sondagem:
            modo_sondagem = False
        elif estado["jogadores"][estado["atual"]]["cargas"]>0:
            modo_sondagem = True
    elif acao=="proteger" and tela=="jogo":
        jogo.usar_equipamento(estado,"proteger")
    elif acao.startswith("mover_") and tela=="jogo" and not modo_sondagem:
        mover_jogador(acao[6:])
    elif acao=="sair":
        glutLeaveMainLoop()
        return
    glutPostRedisplay()

def mover_jogador(direcao):
    global tela,modo_sondagem,selecionada,arrastando
    if tela!="jogo":
        return False
    if jogo.mover(estado,direcao):
        modo_sondagem,selecionada,arrastando = False,None,False
        tela = "resultado" if estado["finalizado"] else "jogo"
        pos = estado["jogadores"][estado["atual"]]["posicao"]
        selecionada = pos if jogo.dentro(*pos) else None
        glutPostRedisplay()
        return True
    glutPostRedisplay()
    return False

def clicar_casa(posicao):
    global modo_sondagem
    if tela!="jogo" or not jogo.dentro(*posicao):
        return
    selecionar_casa(posicao)
    if modo_sondagem:
        if jogo.usar_equipamento(estado,"sondar",posicao):
            modo_sondagem = False
    else:
        p = estado["jogadores"][estado["atual"]]
        deslocamento = (posicao[0]-p["posicao"][0],posicao[1]-p["posicao"][1])
        direcao = next((d for d,delta in jogo.DIRECOES.items() if delta==deslocamento),None)
        if direcao:
            mover_jogador(direcao)
    glutPostRedisplay()

def keyboard(key,x,y):
    global modo_sondagem
    key = key.lower()
    if tela=="instrucoes":
        if key in (b"\x1b",b"h"):
            executar("voltar")
        return
    if tela=="menu":
        if key in (b"2",b"3",b"4"):
            executar("jogadores_"+key.decode())
        elif key in (b"\r",b"\n"):
            executar("iniciar")
        elif key==b"h":
            executar("instrucoes")
        elif key==b"\x1b":
            executar("sair")
        return
    if key==b"m" or (key==b"\x1b" and tela=="resultado"):
        executar("menu")
    elif key==b"r":
        executar("reiniciar")
    elif key==b"h" and tela in ("jogo","pausa"):
        executar("instrucoes")
    elif key==b"\x1b" and modo_sondagem:
        modo_sondagem = False
        glutPostRedisplay()
    elif key in (b"p",b"\x1b") and tela in ("jogo","pausa"):
        executar("continuar" if tela=="pausa" else "pausa")
    elif tela=="jogo":
        if key==b"q":
            executar("sondar")
        elif key==b"e":
            executar("proteger")
        elif key==b"a":
            ajustar_camera(giro=-6)
        elif key==b"d":
            ajustar_camera(giro=6)
        elif key==b"w":
            ajustar_camera(elevacao=-5)
        elif key==b"s":
            ajustar_camera(elevacao=5)
        elif key==b"z":
            ajustar_camera(zoom=-.5)
        elif key==b"x":
            ajustar_camera(zoom=.5)
        elif key==b" ":
            restaurar_camera()
        glutPostRedisplay()

def keySpecial(key,x,y):
    if tela!="jogo" or modo_sondagem:
        return
    direcao = {GLUT_KEY_UP:"cima",GLUT_KEY_DOWN:"baixo",
               GLUT_KEY_LEFT:"esquerda",GLUT_KEY_RIGHT:"direita"}.get(key)
    if direcao:
        mover_jogador(direcao)

def coordenadas_mouse(x,y):
    return x/escala,y/escala

def ponto_no_poligono(u,v,vertices):
    sinais = []
    for i,(x1,y1) in enumerate(vertices):
        x2,y2 = vertices[(i+1)%len(vertices)]
        sinais.append((x2-x1)*(v-y1)-(y2-y1)*(u-x1))
    return all(s>=0 for s in sinais) or all(s<=0 for s in sinais)

def casa_no_mouse(u,v):
    if not (16<=u<=largura_logica-384 and 116<=v<=altura_logica-170):
        return None
    return next((pos for pos,pts in alvos_casas.items()
                 if ponto_no_poligono(u,v,pts)),None)

def mouse(button,state,x,y):
    global arrastando,mouse_anterior,mouse_inicio,ponteiro
    u,v = coordenadas_mouse(x,y)
    ponteiro = (u,v)
    if button==GLUT_LEFT_BUTTON:
        if state==GLUT_DOWN:
            mouse_inicio = None
            for bx,by,w,h,acao in botoes:
                if bx<=u<=bx+w and by<=v<=by+h:
                    executar(acao)
                    return
            if tela=="jogo" and 16<=u<=largura_logica-384 and 116<=v<=altura_logica-170:
                mouse_inicio = (x,y)
                mouse_anterior = (x,y)
                arrastando = False
        elif state==GLUT_UP:
            inicio,foi_arraste = mouse_inicio,arrastando
            arrastando,mouse_inicio = False,None
            if inicio is not None and not foi_arraste:
                pos = casa_no_mouse(u,v)
                if pos is not None:
                    clicar_casa(pos)
    elif state==GLUT_DOWN and button in (3,4) and tela=="jogo":
        ajustar_camera(zoom=-.5 if button==3 else .5)
    glutPostRedisplay()

def motion(x,y):
    global mouse_anterior,arrastando,ponteiro
    ponteiro = coordenadas_mouse(x,y)
    if mouse_inicio is not None and tela=="jogo":
        if math.hypot(x-mouse_inicio[0],y-mouse_inicio[1])>5:
            arrastando = True
        if arrastando:
            ajustar_camera(giro=(x-mouse_anterior[0])*.4,
                           elevacao=(y-mouse_anterior[1])*.4)
            mouse_anterior = (x,y)
            glutPostRedisplay()

def passive_motion(x,y):
    global ponteiro
    ponteiro = coordenadas_mouse(x,y)
    if tela=="jogo":
        pos = casa_no_mouse(*ponteiro)
        if pos is not None:
            selecionar_casa(pos)
    glutPostRedisplay()

def entrada_mouse(situacao):
    global ponteiro, selecionada
    if situacao == GLUT_LEFT:
        ponteiro, selecionada = (-1,-1),None
        glutPostRedisplay()

def init():
    global amostras_msaa
    amostras_msaa = int(glGetIntegerv(GL_SAMPLES)) if glGetIntegerv(GL_SAMPLE_BUFFERS) else 0
    if amostras_msaa:
        glEnable(GL_MULTISAMPLE)
    glClearColor(*FUNDO,1)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_NORMALIZE)
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK,GL_AMBIENT_AND_DIFFUSE)
    glEnable(GL_LIGHT0)
    glLightModelfv(GL_LIGHT_MODEL_AMBIENT,(.30,.33,.38,1.))
    glLightfv(GL_LIGHT0,GL_AMBIENT,(.15,.15,.14,1.))
    glLightfv(GL_LIGHT0,GL_DIFFUSE,(.82,.85,.88,1.))
    glLightfv(GL_LIGHT0,GL_SPECULAR,(.9,.95,1.,1.))
    glLightfv(GL_LIGHT1,GL_AMBIENT,(0.,0.,0.,1.))
    glLightfv(GL_LIGHT1,GL_SPECULAR,(.5,.5,.5,1.))
    glLightf(GL_LIGHT1,GL_SPOT_CUTOFF,38.)
    glLightf(GL_LIGHT1,GL_SPOT_EXPONENT,12.)
    glLightf(GL_LIGHT1,GL_CONSTANT_ATTENUATION,1.)
    glLightf(GL_LIGHT1,GL_LINEAR_ATTENUATION,.035)
    glShadeModel(GL_SMOOTH)
    for tipo in ("pedra","madeira"):
        texturas[tipo] = criar_textura(tipo)

def configurar_display():
    modo = GLUT_RGBA|GLUT_DOUBLE|GLUT_DEPTH
    for amostras in (4,2):
        glutSetOption(GLUT_MULTISAMPLE,amostras)
        glutInitDisplayMode(modo|GLUT_MULTISAMPLE)
        if glutGet(GLUT_DISPLAY_MODE_POSSIBLE):
            return
    glutInitDisplayMode(modo)

def main():
    glutInit(sys.argv)
    configurar_display()
    glutInitWindowSize(largura,altura)
    glutCreateWindow(b"Mina de Cristal")
    glutSetOption(GLUT_ACTION_ON_WINDOW_CLOSE,GLUT_ACTION_GLUTMAINLOOP_RETURNS)
    init()
    print(f"Antialiasing: MSAA {amostras_msaa}x" if amostras_msaa else "Antialiasing: MSAA indisponível.")
    glutDisplayFunc(display)
    glutReshapeFunc(reshape)
    glutKeyboardFunc(keyboard)
    glutSpecialFunc(keySpecial)
    glutMouseFunc(mouse)
    glutMotionFunc(motion)
    glutPassiveMotionFunc(passive_motion)
    glutEntryFunc(entrada_mouse)
    glutIgnoreKeyRepeat(1)
    glutMainLoop()

if __name__=="__main__":
    main()
