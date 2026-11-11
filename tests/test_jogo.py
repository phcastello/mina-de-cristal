"""Testes das regras; executam com a biblioteca padrão, sem OpenGL."""

from collections import Counter
from copy import deepcopy
import random
import unittest

import jogo


def partida_preparada(quantidade=2):
    estado = jogo.novo_jogo(quantidade, 7)
    for linha in estado["tabuleiro"]:
        for casa in linha:
            casa.update(tipo="diamante", valor=2, descobridor=None)
    return estado


def definir(estado, linha, coluna, tipo, valor=0):
    estado["tabuleiro"][linha][coluna].update(tipo=tipo, valor=valor)


class TestTabuleiro(unittest.TestCase):
    def test_distribuicao_e_valores(self):
        for semente in range(100):
            with self.subTest(semente=semente):
                estado = jogo.novo_jogo(4, semente)
                casas = [c for linha in estado["tabuleiro"] for c in linha]
                self.assertEqual([len(linha) for linha in estado["tabuleiro"]], [9] * 8)
                self.assertEqual(Counter(c["tipo"] for c in casas),
                                 {"diamante": 61, "pista": 4, "tunel": 4, "esconderijo": 3})
                self.assertTrue(all(1 <= c["valor"] <= 10 for c in casas if c["tipo"] == "diamante"))
                self.assertTrue(all(c["descobridor"] is None for c in casas))
                self.assertEqual(len({id(c) for c in casas}), 72)

    def test_sorteio_reprodutivel_e_variavel(self):
        self.assertEqual(jogo.novo_jogo(2, 2), jogo.novo_jogo(2, 2))
        self.assertNotEqual(jogo.novo_jogo(2, 2)["tabuleiro"], jogo.novo_jogo(2, 3)["tabuleiro"])

    def test_quantidades_invalidas(self):
        for n in (0, 1, 5):
            with self.assertRaises(ValueError):
                jogo.novo_jogo(n)


class TestMovimento(unittest.TestCase):
    def test_entradas_e_alternancia(self):
        for quantidade in (2, 3, 4):
            estado = partida_preparada(quantidade)
            for indice in range(quantidade):
                self.assertEqual(estado["atual"], indice)
                direcao = "baixo" if indice < 2 else "cima"
                self.assertEqual(jogo.movimentos_validos(estado), [direcao])
                self.assertTrue(jogo.mover(estado, direcao))
                self.assertEqual(estado["jogadores"][indice]["posicao"],
                                 [(0, 0), (0, 8), (7, 8), (7, 0)][indice])
            self.assertEqual(estado["atual"], 0)
            self.assertEqual(estado["turnos"], quantidade)

    def test_invalidos_nao_alteram_estado_salvo_mensagem(self):
        estado = partida_preparada()
        for direcao in ("cima", "esquerda", "direita", "diagonal", ""):
            antes = deepcopy(estado)
            self.assertFalse(jogo.mover(estado, direcao))
            antes["mensagem"] = estado["mensagem"]
            self.assertEqual(antes, estado)

    def test_adjacencia_e_limites(self):
        estado = partida_preparada()
        jogador = estado["jogadores"][0]
        for linha in range(jogo.LINHAS):
            for coluna in range(jogo.COLUNAS):
                jogador["posicao"] = (linha, coluna)
                esperados = {d for d, (dl, dc) in jogo.DIRECOES.items()
                             if 0 <= linha + dl < jogo.LINHAS and 0 <= coluna + dc < jogo.COLUNAS}
                self.assertEqual(set(jogo.movimentos_validos(estado)), esperados)
                for direcao in jogo.DIRECOES:
                    copia = deepcopy(estado)
                    valido = jogo.mover(copia, direcao)
                    self.assertEqual(valido, direcao in esperados)
                    if valido:
                        destino = copia["jogadores"][0]["posicao"]
                        self.assertEqual(abs(destino[0] - linha) + abs(destino[1] - coluna), 1)

    def test_revisita_e_casa_ocupada(self):
        estado = partida_preparada()
        jogo.mover(estado, "baixo")
        estado["jogadores"][1]["posicao"] = (0, 1)
        self.assertTrue(jogo.mover(estado, "esquerda"))
        self.assertEqual(estado["jogadores"][0]["posicao"], estado["jogadores"][1]["posicao"])
        self.assertEqual([j["pontos"] for j in estado["jogadores"]], [2, 0])
        self.assertEqual(estado["tabuleiro"][0][0]["descobridor"], 0)
        jogo.mover(estado, "baixo")
        jogo.mover(estado, "direita")
        jogo.mover(estado, "cima")
        self.assertEqual(estado["jogadores"][0]["pontos"], 4)


class TestEfeitos(unittest.TestCase):
    def test_pista_e_diamante(self):
        estado = partida_preparada()
        definir(estado, 0, 0, "pista")
        definir(estado, 0, 8, "diamante", 10)
        jogo.mover(estado, "baixo")
        jogo.mover(estado, "baixo")
        self.assertEqual([j["pontos"] for j in estado["jogadores"]], [3, 10])

    def test_tunel_cobrado_somente_na_saida_valida(self):
        estado = partida_preparada()
        definir(estado, 0, 0, "tunel")
        jogo.mover(estado, "baixo")
        jogador = estado["jogadores"][0]
        self.assertEqual(jogador["pontos"], 0)
        self.assertTrue(jogador["tunel_pendente"])
        jogo.mover(estado, "baixo")
        self.assertFalse(jogo.mover(estado, "cima"))
        self.assertTrue(jogador["tunel_pendente"])
        self.assertTrue(jogo.mover(estado, "direita"))
        self.assertEqual(jogador["pontos"], -8)
        self.assertFalse(jogador["tunel_pendente"])
        jogo.mover(estado, "baixo")
        jogo.mover(estado, "esquerda")
        self.assertFalse(jogador["tunel_pendente"])
        jogo.mover(estado, "cima")
        jogo.mover(estado, "direita")
        self.assertEqual(jogador["pontos"], -8)

    def test_tunel_nao_cobrado_se_jogo_termina_antes_da_saida(self):
        estado = partida_preparada()
        definir(estado, 0, 0, "tunel")
        jogo.mover(estado, "baixo")
        # Os dois participantes revisitam apenas casas próximas após entrar.
        jogo.mover(estado, "baixo")
        while estado["turnos"] < 70:
            jogador = estado["jogadores"][estado["atual"]]
            jogo.mover(estado, "baixo" if jogador["posicao"][0] == 0 else "cima")
        # O túnel já explorado não cobra novamente; coloque um túnel novo na última rodada.
        definir(estado, 1, 0, "tunel")
        estado["tabuleiro"][1][0]["descobridor"] = None
        pontos = estado["jogadores"][0]["pontos"]
        jogo.mover(estado, "baixo")
        jogo.mover(estado, "baixo")
        self.assertTrue(estado["finalizado"])
        self.assertTrue(estado["jogadores"][0]["tunel_pendente"])
        self.assertEqual(estado["jogadores"][0]["pontos"], pontos)

    def test_esconderijo_oculta_ate_proximo_movimento_valido(self):
        for quantidade in (2, 3, 4):
            estado = partida_preparada(quantidade)
            definir(estado, 0, 0, "esconderijo")
            jogo.mover(estado, "baixo")
            jogador = estado["jogadores"][0]
            self.assertTrue(jogador["invisivel"])
            self.assertEqual([j["pontos"] for j in estado["jogadores"]], [0] + [-5] * (quantidade - 1))
            for indice in range(1, quantidade):
                jogo.mover(estado, "baixo" if indice < 2 else "cima")
            self.assertTrue(jogador["invisivel"])
            self.assertFalse(jogo.mover(estado, "cima"))
            self.assertTrue(jogador["invisivel"])
            jogo.mover(estado, "direita")
            self.assertFalse(jogador["invisivel"])

    def test_armadilhas_nao_repetem_para_adversario(self):
        for tipo in ("esconderijo", "tunel", "pista"):
            estado = partida_preparada()
            definir(estado, 0, 0, tipo)
            jogo.mover(estado, "baixo")
            estado["jogadores"][1]["posicao"] = (0, 1)
            pontos = [j["pontos"] for j in estado["jogadores"]]
            jogo.mover(estado, "esquerda")
            self.assertEqual([j["pontos"] for j in estado["jogadores"]], pontos)
            self.assertFalse(estado["jogadores"][1]["invisivel"])
            self.assertFalse(estado["jogadores"][1]["tunel_pendente"])
            self.assertEqual(estado["tabuleiro"][0][0]["descobridor"], 0)

    def test_saida_de_tunel_e_entrada_em_esconderijo(self):
        estado = partida_preparada()
        definir(estado, 0, 0, "tunel")
        definir(estado, 0, 1, "esconderijo")
        jogo.mover(estado, "baixo")
        jogo.mover(estado, "baixo")
        jogo.mover(estado, "direita")
        self.assertEqual([j["pontos"] for j in estado["jogadores"]], [-10, -3])
        self.assertTrue(estado["jogadores"][0]["invisivel"])


class TestPartida(unittest.TestCase):
    def test_partidas_completas(self):
        for quantidade in (2, 3, 4):
            for semente in range(50):
                estado = jogo.novo_jogo(quantidade, semente)
                gerador = random.Random(semente)
                for turno in range(jogo.TOTAL_TURNOS):
                    self.assertFalse(estado["finalizado"])
                    self.assertEqual(estado["atual"], turno % quantidade)
                    self.assertTrue(jogo.mover(estado, gerador.choice(jogo.movimentos_validos(estado))))
                self.assertTrue(estado["finalizado"])
                self.assertEqual(estado["turnos"], jogo.TOTAL_TURNOS)
                self.assertEqual([j["jogadas"] for j in estado["jogadores"]], [jogo.TOTAL_TURNOS // quantidade] * quantidade)
                self.assertEqual(jogo.movimentos_validos(estado), [])
                antes = deepcopy(estado)
                self.assertFalse(jogo.mover(estado, "baixo"))
                self.assertEqual(estado, antes)
                pontos = [j["pontos"] for j in jogo.ranking(estado)]
                self.assertEqual(pontos, sorted(pontos, reverse=True))

    def test_vitoria_ranking_e_empate_com_pontos_negativos(self):
        estado = partida_preparada(4)
        for j, pontos in zip(estado["jogadores"], (-7, -2, -2, -10)):
            j["pontos"] = pontos
        self.assertEqual([j["id"] for j in jogo.ranking(estado)], [1, 2, 0, 3])
        self.assertEqual([j["id"] for j in jogo.vencedores(estado)], [1, 2])
        estado["jogadores"][0]["pontos"] = 1
        self.assertEqual([j["id"] for j in jogo.vencedores(estado)], [0])

    def test_reinicio_limpa_todo_estado(self):
        for quantidade in (2, 3, 4):
            estado = partida_preparada(quantidade)
            definir(estado, 0, 0, "esconderijo")
            jogo.mover(estado, "baixo")
            estado["jogadores"][0].update(cargas=0, protegido=True,
                                         postos_visitados=set(jogo.POSTOS), objetivo_concluido=True,
                                         sondagens={(3, 3), (4, 4)})
            novo = jogo.reiniciar(estado, 9)
            self.assertEqual(novo, jogo.novo_jogo(quantidade, 9))
            self.assertIsNot(novo["tabuleiro"], estado["tabuleiro"])
            self.assertTrue(all(j["pontos"] == j["jogadas"] == 0 for j in novo["jogadores"]))
            self.assertTrue(all(not j["invisivel"] and not j["tunel_pendente"] for j in novo["jogadores"]))
            self.assertTrue(all(j["cargas"] == 3 and not j["protegido"] and not j["sondagens"]
                                and not j["postos_visitados"] and not j["objetivo_concluido"]
                                for j in novo["jogadores"]))
            self.assertIsNone(novo["ultimo_evento"])


class TestPistas(unittest.TestCase):
    def test_pista_conta_so_os_quatro_vizinhos_com_valores_fixos(self):
        estado = partida_preparada()
        definir(estado, 2, 3, "tunel")
        definir(estado, 3, 4, "esconderijo")
        definir(estado, 4, 3, "pista")
        definir(estado, 3, 2, "diamante", 9)
        definir(estado, 3, 3, "diamante", 10)  # Centro não participa.
        definir(estado, 2, 2, "tunel")  # Diagonal não participa.
        esperado = {"armadilhas": 2, "quilates": 9, "casas": 4}
        self.assertEqual(jogo.pistas_vizinhas(estado, (3, 3)), esperado)
        estado["tabuleiro"][3][2]["descobridor"] = 1
        self.assertEqual(jogo.pistas_vizinhas(estado, (3, 3)), esperado)
        self.assertEqual(jogo.pistas_vizinhas(estado, (0, 0)),
                         {"armadilhas": 0, "quilates": 4, "casas": 2})
        self.assertEqual(jogo.pistas_vizinhas(estado, (7, 8))["casas"], 2)
        self.assertEqual(jogo.pistas_vizinhas(estado, (0, 4))["casas"], 3)
        for invalida in (None, (-1, 0), (8, 0), (0, 9), (0,), "A1", (0.5, 1)):
            self.assertIsNone(jogo.pistas_vizinhas(estado, invalida))

    def test_pistas_ocultas_nao_vazam_e_descoberta_torna_pista_publica(self):
        estado = partida_preparada()
        self.assertIsNone(jogo.pista_disponivel(estado, (0, 0)))
        for entrada in jogo.ENTRADAS:
            self.assertIsNone(jogo.pista_disponivel(estado, entrada))
        jogo.mover(estado, "baixo")
        self.assertEqual(jogo.pista_disponivel(estado, (0, 0), 0),
                         jogo.pista_disponivel(estado, (0, 0), 1))
        self.assertIsNone(jogo.pista_disponivel(estado, (0, 1), 1))
        self.assertIsNone(jogo.pista_disponivel(estado, (0, 0), -1))

    def test_sondagem_privatiza_so_a_pista_sem_revelar_item_ou_gastar_turno(self):
        estado = partida_preparada()
        alvo = (3, 3)
        tabuleiro_antes = deepcopy(estado["tabuleiro"])
        self.assertTrue(jogo.usar_equipamento(estado, "sondar", alvo))
        self.assertEqual(estado["tabuleiro"], tabuleiro_antes)
        self.assertEqual(estado["turnos"], 0)
        self.assertEqual(estado["atual"], 0)
        self.assertEqual(estado["jogadores"][0]["posicao"], jogo.ENTRADAS[0])
        self.assertEqual(estado["jogadores"][0]["cargas"], 2)
        self.assertIsNotNone(jogo.pista_disponivel(estado, alvo))
        self.assertIsNone(jogo.pista_disponivel(estado, alvo, 1))
        jogo.mover(estado, "baixo")
        self.assertIsNone(jogo.pista_disponivel(estado, alvo))
        self.assertIsNotNone(jogo.pista_disponivel(estado, alvo, 0))


class TestEquipamentos(unittest.TestCase):
    def assertFalhaSemEfeito(self, estado, tipo, posicao=None):
        antes = deepcopy(estado)
        self.assertFalse(jogo.usar_equipamento(estado, tipo, posicao))
        antes["mensagem"] = estado["mensagem"]
        self.assertEqual(estado, antes)

    def test_alvos_invalidos_duplicados_e_finalizado_nao_consumem_cargas(self):
        estado = partida_preparada()
        self.assertFalhaSemEfeito(estado, "inexistente")
        for invalido in (None, (-1, 0), (8, 0), (0, 9), "A1", (0,), (0.5, 1)):
            self.assertFalhaSemEfeito(estado, "sondar", invalido)
        estado["tabuleiro"][1][1]["descobridor"] = 0
        self.assertFalhaSemEfeito(estado, "sondar", (1, 1))
        self.assertTrue(jogo.usar_equipamento(estado, "sondar", (2, 3)))
        self.assertFalhaSemEfeito(estado, "sondar", (2, 3))
        self.assertTrue(jogo.usar_equipamento(estado, "proteger"))
        self.assertFalhaSemEfeito(estado, "proteger")
        estado["finalizado"] = True
        self.assertFalhaSemEfeito(estado, "sondar", (3, 3))
        self.assertFalhaSemEfeito(estado, "proteger")

    def test_reserva_compartilhada_limitada_a_tres_usos(self):
        estado = partida_preparada()
        for tipo, alvo in (("sondar", (1, 1)), ("proteger", None), ("sondar", (4, 4))):
            self.assertTrue(jogo.usar_equipamento(estado, tipo, alvo))
        self.assertEqual(estado["jogadores"][0]["cargas"], 0)
        self.assertFalhaSemEfeito(estado, "sondar", (5, 5))
        self.assertEqual(estado["jogadores"][1]["cargas"], 3)
        self.assertEqual(estado["turnos"], 0)

    def test_escudo_bloqueia_tunel_na_saida_sem_ser_gasto_na_entrada_ou_invalido(self):
        estado = partida_preparada()
        definir(estado, 0, 0, "tunel")
        jogo.usar_equipamento(estado, "proteger")
        jogo.mover(estado, "baixo")
        jogador = estado["jogadores"][0]
        self.assertTrue(jogador["protegido"])
        jogo.mover(estado, "baixo")
        jogo.mover(estado, "cima")  # Inválido, preserva o escudo.
        self.assertTrue(jogador["protegido"])
        jogo.mover(estado, "direita")
        self.assertEqual(jogador["pontos"], 2)
        self.assertFalse(jogador["protegido"])
        self.assertFalse(jogador["tunel_pendente"])
        self.assertTrue(estado["ultimo_evento"]["bloqueado"])
        self.assertEqual(estado["ultimo_evento"]["pontos"], 2)

    def test_escudo_bloqueia_esconderijo_adversario_uma_unica_vez(self):
        estado = partida_preparada(3)
        definir(estado, 0, 0, "esconderijo")
        definir(estado, 0, 8, "esconderijo")
        estado["atual"] = 1
        jogo.usar_equipamento(estado, "proteger")
        estado["atual"] = 0
        jogo.mover(estado, "baixo")
        self.assertEqual([j["pontos"] for j in estado["jogadores"]], [0, 0, -5])
        self.assertEqual(estado["ultimo_evento"]["protegidos"], [1])
        self.assertFalse(estado["jogadores"][1]["protegido"])
        self.assertTrue(estado["jogadores"][0]["invisivel"])
        jogo.mover(estado, "baixo")
        self.assertEqual([j["pontos"] for j in estado["jogadores"]], [-5, 0, -10])

    def test_escudo_proprio_nao_impede_esconderijo_nem_gasta_com_diamante(self):
        estado = partida_preparada()
        jogo.usar_equipamento(estado, "proteger")
        jogo.mover(estado, "baixo")
        jogo.mover(estado, "baixo")
        definir(estado, 0, 1, "esconderijo")
        jogo.mover(estado, "direita")
        jogador = estado["jogadores"][0]
        self.assertTrue(jogador["protegido"])
        self.assertTrue(jogador["invisivel"])
        self.assertEqual(estado["jogadores"][1]["pontos"], -3)


class TestObjetivosEEventos(unittest.TestCase):
    def visitar(self, estado, jogador_id, posto):
        estado["atual"] = jogador_id
        estado["jogadores"][jogador_id]["posicao"] = (posto[0], posto[1] - 1)
        self.assertTrue(jogo.mover(estado, "direita"))

    def test_dois_postos_distintos_bonus_unico_por_jogador_inclusive_revisita(self):
        estado = partida_preparada()
        jogador = estado["jogadores"][0]
        primeiro, segundo, terceiro, _ = jogo.POSTOS
        self.visitar(estado, 0, primeiro)
        self.assertFalse(jogador["objetivo_concluido"])
        self.assertEqual(jogador["pontos"], 2)
        self.visitar(estado, 0, primeiro)
        self.assertEqual(jogador["postos_visitados"], {primeiro})
        self.assertFalse(estado["ultimo_evento"]["posto"])
        self.visitar(estado, 0, segundo)
        self.assertTrue(jogador["objetivo_concluido"])
        self.assertEqual(jogador["pontos"], 4 + jogo.BONUS_OBJETIVO)
        self.assertTrue(estado["ultimo_evento"]["objetivo"])
        self.assertEqual(estado["ultimo_evento"]["pontos"], 2 + jogo.BONUS_OBJETIVO)
        self.visitar(estado, 0, terceiro)
        self.assertEqual(jogador["pontos"], 6 + jogo.BONUS_OBJETIVO)
        self.assertFalse(estado["ultimo_evento"]["objetivo"])
        self.visitar(estado, 1, primeiro)
        self.visitar(estado, 1, segundo)
        self.assertTrue(estado["jogadores"][1]["objetivo_concluido"])
        self.assertEqual(estado["jogadores"][1]["pontos"], jogo.BONUS_OBJETIVO)
        self.assertEqual(estado["ultimo_evento"]["tipo"], "revisita")

    def test_posto_nao_revela_conteudo_nem_da_bonus_por_sondagem(self):
        estado = partida_preparada()
        for posto in jogo.POSTOS[:2]:
            self.assertTrue(jogo.usar_equipamento(estado, "sondar", posto))
            self.assertIsNone(estado["tabuleiro"][posto[0]][posto[1]]["descobridor"])
        jogador = estado["jogadores"][0]
        self.assertEqual(jogador["postos_visitados"], set())
        self.assertFalse(jogador["objetivo_concluido"])
        self.assertEqual(jogador["pontos"], 0)

    def test_evento_registra_delta_com_penalidade_e_nao_muda_em_movimento_invalido(self):
        estado = partida_preparada()
        definir(estado, 0, 0, "tunel")
        jogo.mover(estado, "baixo")
        jogo.mover(estado, "baixo")
        jogo.mover(estado, "direita")
        evento = deepcopy(estado["ultimo_evento"])
        self.assertEqual(evento["pontos"], -8)
        self.assertEqual(evento["jogador"], 0)
        self.assertEqual(evento["posicao"], (0, 1))
        self.assertEqual(evento["tipo"], "diamante")
        self.assertFalse(jogo.mover(estado, "cima"))
        self.assertEqual(estado["ultimo_evento"], evento)

    def test_ultimo_movimento_pode_concluir_objetivo_e_entra_no_ranking(self):
        estado = partida_preparada()
        jogador = estado["jogadores"][1]
        jogador["postos_visitados"].add(jogo.POSTOS[0])
        estado["turnos"] = jogo.TOTAL_TURNOS - 1
        self.visitar(estado, 1, jogo.POSTOS[1])
        self.assertTrue(estado["finalizado"])
        self.assertTrue(estado["ultimo_evento"]["objetivo"])
        self.assertEqual(jogo.vencedores(estado)[0]["id"], 1)
        self.assertEqual(jogador["pontos"], 2 + jogo.BONUS_OBJETIVO)


if __name__ == "__main__":
    unittest.main()
