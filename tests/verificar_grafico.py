"""Integração em contexto OpenGL real, com capturas PNG opcionais.

Execute da raiz: python tests/verificar_grafico.py --capturas <diretorio>
Requer sessão gráfica, GLU e FreeGLUT. Não adiciona dependências ao jogo.
"""

import argparse
from collections import Counter
from copy import deepcopy
import ctypes
from pathlib import Path
import struct
import sys
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jogo
import main as m


def capturar(destino, nome):
    if destino is None:
        return
    m.glFinish()
    m.glReadBuffer(m.GL_FRONT)
    m.glPixelStorei(m.GL_PACK_ALIGNMENT, 1)
    pixels = (ctypes.c_ubyte * (m.largura * m.altura * 3))()
    m.glReadPixels(0, 0, m.largura, m.altura, m.GL_RGB, m.GL_UNSIGNED_BYTE, pixels)
    dados, passo = bytes(pixels), m.largura * 3
    linhas = b"".join(b"\0" + dados[y * passo:(y + 1) * passo]
                      for y in reversed(range(m.altura)))

    def bloco(tipo, conteudo):
        return (struct.pack("!I", len(conteudo)) + tipo + conteudo
                + struct.pack("!I", zlib.crc32(tipo + conteudo)))

    imagem = b"\x89PNG\r\n\x1a\n"
    imagem += bloco(b"IHDR", struct.pack("!2I5B", m.largura, m.altura, 8, 2, 0, 0, 0))
    imagem += bloco(b"IDAT", zlib.compress(linhas)) + bloco(b"IEND", b"")
    (destino / (nome + ".png")).write_bytes(imagem)


def desenhar(destino=None, nome="cena"):
    m.display()
    assert m.glGetError() == m.GL_NO_ERROR, f"Erro OpenGL em {nome}"
    capturar(destino, nome)


def clicar(u, v):
    x, y = round(u * m.escala), round(v * m.escala)
    m.mouse(m.GLUT_LEFT_BUTTON, m.GLUT_DOWN, x, y)
    m.mouse(m.GLUT_LEFT_BUTTON, m.GLUT_UP, x, y)


def clicar_botao(acao):
    desenhar()
    alvos = [b for b in m.botoes if b[4] == acao]
    assert alvos, f"Botão ausente: {acao} na tela {m.tela}"
    x, y, w, h, _ = alvos[0]
    clicar(x + w / 2, y + h / 2)


def clicar_casa(posicao):
    desenhar()
    vertices = m.alvos_casas[posicao]
    clicar(sum(v[0] for v in vertices) / len(vertices),
           sum(v[1] for v in vertices) / len(vertices))


def passar_mouse_casa(posicao):
    desenhar()
    vertices = m.alvos_casas[posicao]
    u = sum(v[0] for v in vertices) / len(vertices)
    v = sum(v[1] for v in vertices) / len(vertices)
    m.passive_motion(round(u * m.escala), round(v * m.escala))


def iniciar(quantidade):
    m.executar("menu")
    m.keyboard(str(quantidade).encode(), 0, 0)
    criar = jogo.novo_jogo
    with patch.object(jogo, "novo_jogo", side_effect=lambda n: criar(n, 23)):
        m.keyboard(b"\r", 0, 0)
    assert m.tela == "jogo" and len(m.estado["jogadores"]) == quantidade


def verificar_ocultacao():
    with patch.object(m, "diamante", wraps=m.diamante) as d, \
         patch.object(m, "tunel", wraps=m.tunel) as t, \
         patch.object(m, "esconderijo", wraps=m.esconderijo) as e, \
         patch.object(m, "pista", wraps=m.pista) as p:
        # Isola a cena 3D: ícones de legenda no HUD não são conteúdos revelados.
        m.desenhar_cena()
        assert not any(f.called for f in (d, t, e, p)), "Item oculto foi desenhado"
        assert m.glGetError() == m.GL_NO_ERROR


def verificar_posicao_postos():
    """As bandeiras devem ocupar quatro casas distintas, não a origem da cena."""
    original = m.posto_3d
    vistos = []

    def conferir(numero, visitado):
        centro = m.projetar(0, 0, .10)
        esperado = m.centros_casas[jogo.POSTOS[numero - 1]]
        assert all(abs(a - b) < 1e-5 for a, b in zip(centro, esperado)), \
            f"Bandeira {numero} foi desenhada fora de seu posto"
        vistos.append(numero)
        return original(numero, visitado)

    with patch.object(m, "posto_3d", side_effect=conferir):
        m.desenhar_cena()
    assert vistos == [1, 2, 3, 4]


def verificar_texto_suave():
    # Cobertura parcial comprova AA próprio, inclusive para letras acentuadas.
    raster = m.letras.rasterizar("Âmbar: ação, proteção e túneis", 18)
    assert any(0 < a < 255 for a in raster.imagem.getchannel("A").tobytes())
    assert raster.topo < 0 and raster.avanco > 0
    m.glPushAttrib(m.GL_ALL_ATTRIB_BITS)
    try:
        m.projecao_2d()
        m.glDisable(m.GL_MULTISAMPLE)
        m.glClearColor(0, 0, 0, 1)
        m.glClear(m.GL_COLOR_BUFFER_BIT)
        estados = {s: bool(m.glIsEnabled(s)) for s in
                   (m.GL_BLEND, m.GL_TEXTURE_2D, m.GL_LIGHTING, m.GL_DEPTH_TEST)}
        escrita = bool(m.glGetBooleanv(m.GL_DEPTH_WRITEMASK))
        m.texto(20, 70, "Ág 2", (1, 1, 1), 28)
        assert estados == {s: bool(m.glIsEnabled(s)) for s in estados}
        assert escrita == bool(m.glGetBooleanv(m.GL_DEPTH_WRITEMASK))
        m.glFinish()
        m.glReadBuffer(m.GL_BACK)
        m.glPixelStorei(m.GL_PACK_ALIGNMENT, 1)
        w, h = round(200 * m.escala), round(110 * m.escala)
        pixels = (ctypes.c_ubyte * (w * h * 3))()
        m.glReadPixels(0, m.altura-h, w, h, m.GL_RGB, m.GL_UNSIGNED_BYTE, pixels)
        assert any(0 < c < 255 for c in bytes(pixels)[::3]), \
            "Texto sem cobertura suave quando MSAA está desligado"
        assert m.glGetError() == m.GL_NO_ERROR
    finally:
        m.glPopAttrib()


def verificar(destino):
    m.glutInit([])
    m.configurar_display()
    m.glutInitWindowSize(1280, 800)
    janela = m.glutCreateWindow(b"Procurando o Tesouro - verificacao")
    m.glutDisplayFunc(m.display)
    m.glutReshapeFunc(m.reshape)
    try:
        m.init()
        m.reshape(1280, 800)
        m.glutMainLoopEvent()
        print("OpenGL:", m.glGetString(m.GL_VERSION).decode())
        print("Renderizador:", m.glGetString(m.GL_RENDERER).decode())
        print("MSAA:", m.amostras_msaa, "amostras")
        assert all(m.glIsTexture(t) for t in m.texturas.values())
        if m.amostras_msaa:
            assert m.glIsEnabled(m.GL_MULTISAMPLE)
        verificar_texto_suave()
        desenhar(destino, "01-menu")
        clicar_botao("jogadores_4")
        assert m.quantidade == 4
        criar = jogo.novo_jogo
        with patch.object(jogo, "novo_jogo", side_effect=lambda n: criar(n, 23)):
            clicar_botao("iniciar")
        assert m.tela == "jogo"
        desenhar(destino, "02-partida-inicial")
        # Iniciar e realizar jogadas consecutivas não exige Enter nem confirmação.
        for indice in range(2):
            m.keySpecial(m.GLUT_KEY_DOWN, 0, 0)
            assert m.tela == "jogo", "Uma jogada abriu uma interrupção de turno"
            assert m.estado["turnos"] == indice + 1
            assert m.estado["atual"] == indice + 1
        assert [p["jogadas"] for p in m.estado["jogadores"]] == [1, 1, 0, 0]
        iniciar(4)
        verificar_ocultacao()
        verificar_posicao_postos()
        desenhar(destino, "03-mina-oculta")
        assert len(m.alvos_casas) == jogo.LINHAS * jogo.COLUNAS
        assert m.glIsEnabled(m.GL_LIGHT1), "Luz do jogador ativo não foi ativada"

        # Uma sondagem consultável apenas pelo autor, sem pontos nem descoberta.
        alvo = (3, 3)
        assert jogo.pista_disponivel(m.estado, alvo) is None
        clicar_botao("sondar")
        assert m.modo_sondagem
        antes = deepcopy(m.estado)
        m.keySpecial(m.GLUT_KEY_DOWN, 0, 0)
        assert m.estado == antes and m.modo_sondagem, "Seta andou durante seleção de sondagem"
        clicar_casa(alvo)
        assert alvo in m.estado["jogadores"][0]["sondagens"]
        assert m.estado["jogadores"][0]["cargas"] == 2
        assert m.estado["turnos"] == 0 and not m.modo_sondagem
        assert m.estado["tabuleiro"][3][3]["descobridor"] is None
        assert jogo.pista_disponivel(m.estado, alvo) is not None
        assert jogo.pista_disponivel(m.estado, alvo, 1) is None
        dados_radar = jogo.pistas_vizinhas(m.estado, alvo)
        assert m.consulta_pista() == (alvo, dados_radar)
        verificar_ocultacao()
        with patch.object(m, "pista_flutuante", wraps=m.pista_flutuante) as flutuante, \
             patch.object(m, "painel_pistas", create=True) as painel_antigo:
            desenhar(destino, "04-sondagem-sem-revelar")
            assert flutuante.called and not painel_antigo.called, \
                "A leitura deve aparecer junto da casa, sem painel lateral de pistas"
        # O tooltip acompanha a casa sob o ponteiro, inclusive se for desconhecida.
        passar_mouse_casa((3, 4))
        assert m.consulta_pista() == ((3, 4), None), \
            "Tooltip conservou uma leitura que pertence a outra casa"
        desenhar(destino, "04b-tooltip-casa-oculta")
        passar_mouse_casa(alvo)
        assert m.consulta_pista() == (alvo, dados_radar)
        clicar_botao("proteger")
        assert m.estado["jogadores"][0]["protegido"]
        assert m.estado["jogadores"][0]["cargas"] == 1
        assert m.estado["turnos"] == 0
        desenhar(destino, "05-escudo-ativo")

        # Efeitos passam pelos mesmos callbacks usados na partida.
        entradas = ((0, 0), (0, 8), (7, 8), (7, 0))
        for posicao, tipo in zip(entradas, ("diamante", "tunel", "esconderijo", "pista")):
            m.estado["tabuleiro"][posicao[0]][posicao[1]].update(
                tipo=tipo, valor=8, descobridor=None)
        m.keySpecial(m.GLUT_KEY_UP, 0, 0)
        assert m.estado["turnos"] == 0 and m.tela == "jogo"
        clicar_casa((0, 0))
        assert m.estado["turnos"] == 1 and m.tela == "jogo"
        assert m.estado["atual"] == 1
        passar_mouse_casa(alvo)
        assert m.consulta_pista()[1] is None, "Radar privado vazou para o próximo jogador"
        desenhar(destino, "06-turno-automatico")
        for indice in range(1, 4):
            assert jogo.pista_disponivel(m.estado, alvo) is None
            m.keySpecial(m.GLUT_KEY_DOWN if indice < 2 else m.GLUT_KEY_UP, 0, 0)
            assert m.tela == "jogo"
            assert m.estado["atual"] == (indice + 1) % 4
            if indice == 2:
                desenhar(destino, "06b-esconderijo")
        assert m.estado["turnos"] == 4
        assert m.estado["jogadores"][2]["invisivel"]
        assert m.estado["jogadores"][1]["tunel_pendente"]
        assert not m.estado["jogadores"][0]["protegido"], "Escudo não bloqueou esconderijo alheio"
        assert m.estado["jogadores"][0]["pontos"] == 8
        # Casas reveladas continuam consultáveis por hover, e sondagens próprias
        # podem ser consultadas novamente sem gastar uma segunda carga.
        passar_mouse_casa(alvo)
        assert m.consulta_pista() == (alvo, dados_radar)
        cargas_antes = m.estado["jogadores"][0]["cargas"]
        passar_mouse_casa((0, 0))
        assert m.consulta_pista() == ((0, 0), jogo.pistas_vizinhas(m.estado, (0, 0)))
        assert m.estado["jogadores"][0]["cargas"] == cargas_antes
        # Fora do tabuleiro, a leitura acompanha o peão que tem a vez.
        m.entrada_mouse(m.GLUT_LEFT)
        assert m.ponteiro == (-1, -1)
        assert m.consulta_pista() == ((0, 0), jogo.pistas_vizinhas(m.estado, (0, 0)))
        desenhar(destino, "07-pistas-e-descobertas")

        # O marcador permanente fica, somente o avatar invisível desaparece.
        with patch.object(m, "forma_avatar", wraps=m.forma_avatar) as avatar:
            m.desenhar_cena()
            invisivel = Counter(c.args[0] for c in avatar.call_args_list)
            avatar.reset_mock()
            m.estado["jogadores"][2]["invisivel"] = False
            m.desenhar_cena()
            visivel = Counter(c.args[0] for c in avatar.call_args_list)
            assert visivel[2] == invisivel[2] + 1
            m.estado["jogadores"][2]["invisivel"] = True

        m.keySpecial(m.GLUT_KEY_DOWN, 0, 0)
        assert m.estado["atual"] == 1
        posicao_atual = m.estado["jogadores"][1]["posicao"]
        assert m.consulta_pista() == (posicao_atual, jogo.pistas_vizinhas(m.estado, posicao_atual)), \
            "Tooltip fora do tabuleiro não acompanhou a troca de jogador"
        desenhar(destino, "07b-tooltip-peao-atual")

        # Pausa e ajuda preservam regras e reserva de equipamentos.
        m.keyboard(b"p", 0, 0)
        assert m.tela == "pausa"
        antes = deepcopy(m.estado)
        m.keySpecial(m.GLUT_KEY_DOWN, 0, 0)
        m.keyboard(b"e", 0, 0)
        m.keyboard(b"q", 0, 0)
        assert m.estado == antes
        desenhar(destino, "08-pausa")
        m.keyboard(b"h", 0, 0)
        assert m.tela == "instrucoes"
        m.keySpecial(m.GLUT_KEY_DOWN, 0, 0)
        assert m.estado == antes
        desenhar(destino, "09-ajuda-visual")
        m.keyboard(b"\x1b", 0, 0)
        assert m.tela == "pausa"
        m.keyboard(b"p", 0, 0)
        assert m.tela == "jogo"

        camera = (m.distancia, m.azimute, m.incidencia)
        for tecla in (b"w", b"a", b"z"):
            m.keyboard(tecla, 0, 0)
        assert (m.distancia, m.azimute, m.incidencia) != camera
        m.keyboard(b" ", 0, 0)
        assert (m.distancia, m.azimute, m.incidencia) == camera
        desenhar()
        vertices = m.alvos_casas[(3, 3)]
        x = round(sum(v[0] for v in vertices) / len(vertices) * m.escala)
        y = round(sum(v[1] for v in vertices) / len(vertices) * m.escala)
        antes = deepcopy(m.estado)
        m.mouse(m.GLUT_LEFT_BUTTON, m.GLUT_DOWN, x, y)
        m.motion(x + 35, y + 20)
        m.mouse(m.GLUT_LEFT_BUTTON, m.GLUT_UP, x + 35, y + 20)
        m.mouse(3, m.GLUT_DOWN, x, y)
        assert (m.distancia, m.azimute, m.incidencia) != camera
        assert m.estado == antes, "Arraste foi interpretado como movimento"
        m.ajustar_camera(zoom=-100, elevacao=-100)
        assert m.distancia == 9 and m.incidencia == 15
        desenhar(destino, "10-camera-proxima")
        m.ajustar_camera(zoom=100, elevacao=100)
        assert m.distancia == 27 and m.incidencia == 75
        desenhar(destino, "11-camera-afastada")
        m.restaurar_camera()

        # Objetivo por visita, sem depender do item sorteado e sem repetir prêmio.
        m.estado = jogo.novo_jogo(4, 23)
        m.tela = "jogo"
        jogador = m.estado["jogadores"][0]
        for posto in jogo.POSTOS[:2]:
            jogador["posicao"] = (posto[0], posto[1] - 1)
            m.estado["atual"] = 0
            m.estado["tabuleiro"][posto[0]][posto[1]].update(
                tipo="diamante", valor=2, descobridor=1)
            m.keySpecial(m.GLUT_KEY_RIGHT, 0, 0)
            assert m.tela == "jogo"
        assert jogador["objetivo_concluido"] and jogador["pontos"] == jogo.BONUS_OBJETIVO
        m.estado["atual"] = 0
        passar_mouse_casa(jogo.POSTOS[1])
        desenhar(destino, "12-objetivo-concluido")

        for w, h in ((960, 640), (1280, 800), (1600, 900), (1024, 768), (720, 900)):
            m.glutReshapeWindow(w, h)
            m.glutMainLoopEvent()
            m.reshape(w, h)
            desenhar(destino, f"13-janela-{w}x{h}")
            assert tuple(m.glGetIntegerv(m.GL_VIEWPORT)) == (0, 0, w, h)
            assert abs(m.largura_logica / m.altura_logica - w / h) < 1e-9
            with patch.object(m, "gluPerspective", wraps=m.gluPerspective) as perspectiva:
                m.desenhar_cena()
                _, _, vw, vh = m.glGetIntegerv(m.GL_VIEWPORT)
                assert abs(perspectiva.call_args.args[1] - vw / vh) < 1e-9
            m.keyboard(b"p", 0, 0)
            assert m.tela == "pausa"
            clicar_botao("continuar")
            assert m.tela == "jogo", "Botão deslocado após redimensionamento"
            iniciar(2)
            clicar_casa((0, 0))
            assert m.estado["turnos"] == 1 and m.tela == "jogo", "Picking deslocado após resize"
        m.glutReshapeWindow(1280, 800)
        m.glutMainLoopEvent()
        m.reshape(1280, 800)

        teclas = {"cima": m.GLUT_KEY_UP, "baixo": m.GLUT_KEY_DOWN,
                  "esquerda": m.GLUT_KEY_LEFT, "direita": m.GLUT_KEY_RIGHT}
        for n in (2, 3, 4):
            iniciar(n)
            for turno in range(jogo.TOTAL_TURNOS):
                assert m.tela == "jogo"
                m.keySpecial(teclas[jogo.movimentos_validos(m.estado)[0]], 0, 0)
                desenhar()
            assert m.tela == "resultado"
            assert [j["jogadas"] for j in m.estado["jogadores"]] == [72 // n] * n
            desenhar(destino, f"14-resultado-{n}-jogadores")
            m.keyboard(b"r", 0, 0)
            assert m.tela == "jogo" and m.estado["turnos"] == 0
            assert all(c["descobridor"] is None for linha in m.estado["tabuleiro"] for c in linha)
            assert all(j["cargas"] == 3 and not j["sondagens"] and not j["postos_visitados"]
                       and not j["protegido"] for j in m.estado["jogadores"])
        for jogador in m.estado["jogadores"]:
            jogador["pontos"] = -5
        m.estado["turnos"] = jogo.TOTAL_TURNOS
        m.estado["finalizado"] = True
        m.executar("resultado")
        desenhar(destino, "15-empate")
        m.keyboard(b"\x1b", 0, 0)
        assert m.tela == "menu" and m.estado is None
        m.keyboard(b"h", 0, 0)
        desenhar()
        m.keyboard(b"h", 0, 0)
        assert m.tela == "menu"
        print("OK: 8x9, ocultacao, pistas privadas, equipamentos, postos, turnos automaticos,")
        print("camera, picking e menus apos resize, reinicio e partidas de 72 turnos para 2/3/4.")
        if destino:
            print("Capturas:", destino)
    finally:
        m.glutDestroyWindow(janela)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capturas", type=Path, help="Diretório opcional para PNGs")
    args = parser.parse_args()
    if args.capturas:
        args.capturas.mkdir(parents=True, exist_ok=True)
    verificar(args.capturas)
