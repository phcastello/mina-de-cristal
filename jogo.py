"""Estado e regras de Procurando o Tesouro, sem dependência do OpenGL."""

import random

LINHAS = 8
COLUNAS = 9
TOTAL_TURNOS = LINHAS * COLUNAS
CARGAS_INICIAIS = 3
BONUS_OBJETIVO = 8
POSTOS = ((2, 2), (2, 6), (5, 2), (5, 6))
DIRECOES = {"cima": (-1, 0), "baixo": (1, 0), "esquerda": (0, -1), "direita": (0, 1)}
ENTRADAS = [(-1, 0), (-1, COLUNAS - 1), (LINHAS, COLUNAS - 1), (LINHAS, 0)]
IDENTIDADES = [
    ("Rubi", (0.92, 0.32, 0.32), "esfera"),
    ("Safira", (0.30, 0.65, 1.0), "cubo"),
    ("Âmbar", (1.0, 0.73, 0.24), "cone"),
    ("Jade", (0.35, 0.85, 0.62), "octaedro"),
]


def criar_tabuleiro(gerador):
    """Cada casa recebe exatamente um conteúdo, inicialmente oculto."""
    itens = [{"tipo": "diamante", "valor": gerador.randint(1, 10)} for _ in range(61)]
    for tipo, quantidade in (("pista", 4), ("tunel", 4), ("esconderijo", 3)):
        itens += [{"tipo": tipo, "valor": 0} for _ in range(quantidade)]
    gerador.shuffle(itens)
    for item in itens:
        item["descobridor"] = None
    return [itens[i:i + COLUNAS] for i in range(0, TOTAL_TURNOS, COLUNAS)]


def novo_jogo(quantidade=2, semente=None):
    """A semente é opcional e permite reproduzir partidas nos testes."""
    if quantidade not in (2, 3, 4):
        raise ValueError("Escolha 2, 3 ou 4 jogadores.")
    jogadores = []
    for indice in range(quantidade):
        nome, cor, forma = IDENTIDADES[indice]
        jogadores.append({
            "id": indice, "nome": nome, "cor": cor, "forma": forma,
            "posicao": ENTRADAS[indice], "pontos": 0, "jogadas": 0,
            "invisivel": False, "tunel_pendente": False,
            "cargas": CARGAS_INICIAIS, "protegido": False,
            "postos_visitados": set(), "objetivo_concluido": False, "sondagens": set(),
        })
    return {
        "tabuleiro": criar_tabuleiro(random.Random(semente)),
        "jogadores": jogadores, "atual": 0, "turnos": 0, "finalizado": False,
        "ultimo_evento": None,
        "mensagem": "Rubi começa na entrada A1. Pressione a seta para baixo para entrar na mina.",
    }


def dentro(linha, coluna):
    return 0 <= linha < LINHAS and 0 <= coluna < COLUNAS


def _posicao_interna(posicao):
    """Valida alvos de ferramentas antes de consultar a matriz."""
    if (not isinstance(posicao, (tuple, list)) or len(posicao) != 2
            or not all(isinstance(coordenada, int) for coordenada in posicao)):
        return None
    return tuple(posicao) if dentro(*posicao) else None


def pistas_vizinhas(estado, posicao):
    """Leitura fixa dos quatro vizinhos, sem incluir a casa consultada.

    Inclui conteúdos já descobertos para que pistas de casas diferentes possam
    ser cruzadas. Esta função interna de cálculo não verifica acesso à pista;
    a interface deve consultar pista_disponivel.
    """
    posicao = _posicao_interna(posicao)
    if posicao is None:
        return None
    linha, coluna = posicao
    vizinhos = [estado["tabuleiro"][linha + dl][coluna + dc]
                for dl, dc in DIRECOES.values() if dentro(linha + dl, coluna + dc)]
    return {
        "armadilhas": sum(c["tipo"] in ("tunel", "esconderijo") for c in vizinhos),
        "quilates": sum(c["valor"] for c in vizinhos if c["tipo"] == "diamante"),
        "casas": len(vizinhos),
    }


def pista_disponivel(estado, posicao, jogador_id=None):
    """Retorna somente pistas públicas ou sondadas pelo jogador consultado."""
    posicao = _posicao_interna(posicao)
    if posicao is None:
        return None
    jogador_id = estado["atual"] if jogador_id is None else jogador_id
    if not isinstance(jogador_id, int) or not 0 <= jogador_id < len(estado["jogadores"]):
        return None
    linha, coluna = posicao
    if (estado["tabuleiro"][linha][coluna]["descobridor"] is not None
            or posicao in estado["jogadores"][jogador_id]["sondagens"]):
        return pistas_vizinhas(estado, posicao)
    return None


def usar_equipamento(estado, tipo, posicao=None):
    """Sonda e escudo dividem uma reserva finita; nenhuma ação gasta turno."""
    if estado["finalizado"]:
        return False
    jogador = estado["jogadores"][estado["atual"]]
    if jogador["cargas"] <= 0:
        estado["mensagem"] = "Sem cargas de equipamento."
        return False
    if tipo == "sondar":
        posicao = _posicao_interna(posicao)
        if posicao is None:
            estado["mensagem"] = "Escolha uma casa oculta dentro da mina para sondar."
            return False
        linha, coluna = posicao
        if (estado["tabuleiro"][linha][coluna]["descobridor"] is not None
                or posicao in jogador["sondagens"]):
            estado["mensagem"] = "A pista dessa casa já está disponível. Nenhuma carga foi gasta."
            return False
        jogador["sondagens"].add(posicao)
        estado["mensagem"] = f"Sondagem em {nome_casa(posicao)}: pista dos vizinhos disponível."
    elif tipo == "proteger":
        if jogador["protegido"]:
            estado["mensagem"] = "Escudo já ativo. Nenhuma carga foi gasta."
            return False
        jogador["protegido"] = True
        estado["mensagem"] = "Escudo ativo: bloqueia a próxima perda de quilates."
    else:
        estado["mensagem"] = "Equipamento desconhecido."
        return False
    jogador["cargas"] -= 1
    return True


def _perder_quilates(jogador, valor):
    """True indica que um escudo foi consumido no lugar dos pontos."""
    if jogador["protegido"]:
        jogador["protegido"] = False
        return True
    jogador["pontos"] -= valor
    return False


def nome_casa(posicao):
    linha, coluna = posicao
    return f"{chr(65 + coluna)}{linha + 1}"


def movimentos_validos(estado):
    if estado["finalizado"]:
        return []
    linha, coluna = estado["jogadores"][estado["atual"]]["posicao"]
    return [nome for nome, (dl, dc) in DIRECOES.items() if dentro(linha + dl, coluna + dc)]


def descobrir(estado, jogador, casa, evento=None):
    """Efeitos são aplicados somente ao primeiro descobridor."""
    if casa["descobridor"] is not None:
        return "casa já explorada; nenhum novo efeito."
    casa["descobridor"] = jogador["id"]
    tipo = casa["tipo"]
    if tipo == "diamante":
        jogador["pontos"] += casa["valor"]
        return f"diamante de {casa['valor']} quilates!"
    if tipo == "pista":
        jogador["pontos"] += 3
        return "Prossiga! +3 quilates."
    if tipo == "tunel":
        jogador["tunel_pendente"] = True
        return "túnel sem saída: perderá 10 quilates ao sair."
    jogador["invisivel"] = True
    for adversario in estado["jogadores"]:
        if adversario["id"] != jogador["id"]:
            if _perder_quilates(adversario, 5) and evento is not None:
                evento["protegidos"].append(adversario["id"])
    return "esconderijo secreto! Rivais sem escudo perdem 5 quilates; avatar oculto até seu próximo movimento."


def mover(estado, direcao):
    """Retorna True se consumiu um turno; movimentos inválidos só mudam a mensagem."""
    if estado["finalizado"]:
        return False
    if direcao not in movimentos_validos(estado):
        estado["mensagem"] = "Movimento inválido. Use uma casa adjacente dentro da mina; o turno continua seu."
        return False
    jogador = estado["jogadores"][estado["atual"]]
    pontos_antes = jogador["pontos"]
    evento = {"jogador": jogador["id"], "pontos": 0, "objetivo": False,
              "bloqueado": False, "protegidos": [], "posto": False}
    dl, dc = DIRECOES[direcao]
    linha, coluna = jogador["posicao"]
    jogador["posicao"] = (linha + dl, coluna + dc)
    # A saída só ocorre depois de validar o destino, inclusive na última jogada.
    penalidade = ""
    if jogador["tunel_pendente"]:
        evento["bloqueado"] = _perder_quilates(jogador, 10)
        jogador["tunel_pendente"] = False
        penalidade = "Escudo bloqueou o túnel. " if evento["bloqueado"] else "Saiu do túnel: -10 quilates. "
    jogador["invisivel"] = False
    casa = estado["tabuleiro"][linha + dl][coluna + dc]
    evento["tipo"] = casa["tipo"] if casa["descobridor"] is None else "revisita"
    evento["posicao"] = jogador["posicao"]
    efeito = descobrir(estado, jogador, casa, evento)
    if jogador["posicao"] in POSTOS:
        evento["posto"] = jogador["posicao"] not in jogador["postos_visitados"]
        jogador["postos_visitados"].add(jogador["posicao"])
        if len(jogador["postos_visitados"]) >= 2 and not jogador["objetivo_concluido"]:
            jogador["pontos"] += BONUS_OBJETIVO
            jogador["objetivo_concluido"] = True
            evento["objetivo"] = True
            efeito += f" Dois postos visitados: +{BONUS_OBJETIVO} quilates!"
    evento["pontos"] = jogador["pontos"] - pontos_antes
    estado["ultimo_evento"] = evento
    estado["mensagem"] = f"{jogador['nome']} em {nome_casa(jogador['posicao'])}: {penalidade}{efeito}"
    jogador["jogadas"] += 1
    estado["turnos"] += 1
    estado["finalizado"] = estado["turnos"] == TOTAL_TURNOS
    if not estado["finalizado"]:
        estado["atual"] = (estado["atual"] + 1) % len(estado["jogadores"])
    return True


def ranking(estado):
    """A ordem de entrada apenas estabiliza a exibição dos empates."""
    return sorted(estado["jogadores"], key=lambda jogador: (-jogador["pontos"], jogador["id"]))


def vencedores(estado):
    ordem = ranking(estado)
    return [jogador for jogador in ordem if jogador["pontos"] == ordem[0]["pontos"]]


def reiniciar(estado, semente=None):
    return novo_jogo(len(estado["jogadores"]), semente)
