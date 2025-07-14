# modules/scales.py

import streamlit as st
import json

from pathlib import Path

def render_scale_form(scale_path: str):
    """
    <docstrings>
    Função que carrega e renderiza uma escala psicométrica baseada em definição externa de itens e opções de resposta.
    
    Args:
        scale_path (str): Caminho para o arquivo JSON contendo a escala.
    
    Armazena:
        st.session_state["escalas_respondidas"]: dicionário com escalas preenchidas durante a sessão.
    
    Calls:
        open(): Função para leitura de arquivos | built-in.
        json.load(): Função para carregar dados JSON | built-in.
        st.form(): Componente de formulário do Streamlit | instanciado por st.
        st.selectbox(): Componente de escolha única | instanciado por st.
        st.warning(), st.success(): Componentes de feedback | instanciados por st.
        st.session_state.__setitem__(): Método do objeto SessionStateProxy | instanciado por st.session_state.
    """

    # --- Leitura do arquivo da escala ---
    with open(scale_path, "r", encoding="utf-8") as f:
        escala = json.load(f)

    nome = escala.get("nome", "Escala Sem Nome")
    itens = escala.get("itens", [])
    opcoes = escala.get("respostas", [])

    if not itens or not opcoes:
        st.error("Erro: Itens ou respostas não definidos no arquivo da escala.")
        return

    # --- Renderização do formulário ---
    with st.form(f"form_{nome}"):
        st.subheader(f"Escala: {nome}")
        respostas = {}

        for i, item in enumerate(itens):
            respostas[str(i)] = st.selectbox(
                f"{i+1}. {item}",
                # options=[""] + opcoes,  # "" representa "não respondido"
                options = opcoes,
                key=f"{nome}_{i}"
            )
        placeholder = st.empty()
        
        enviado = st.form_submit_button("Enviar escala", use_container_width=True)

    # --- Validação ---

    if enviado:
        if "" in respostas.values():
            st.warning("⚠️ Por favor, responda todos os itens antes de enviar.")
        else:
            if "escalas_respondidas" not in st.session_state:
                st.session_state["escalas_respondidas"] = {}
            
            st.session_state["escalas_respondidas"][nome] = respostas
            placeholder.success("✅ Escala enviada com sucesso!")


def render_scale_selector(scales_dir: str = "scales"):
    """
    <docstrings>
    Exibe um seletor de escalas psicométricas baseado nos arquivos .json em uma pasta.
    
    Args:
        scales_dir (str): Caminho para a pasta contendo os arquivos de escalas (.json).
    
    Calls:
        Path.glob(): Busca arquivos no diretório | instanciado por Path.
        json.load(): Carrega cada escala para obter o nome | built-in.
        st.selectbox(): Select box interativo | instanciado por st.
        render_scale_form(): Renderiza o formulário da escala selecionada | definida em modules/scales.py.
    """

    dir_path = Path(scales_dir)
    arquivos_json = list(dir_path.glob("*.json"))

    if not arquivos_json:
        st.warning("Nenhuma escala encontrada na pasta.")
        return

    # Carrega nomes legíveis das escalas
    lista_nomes = []
    mapa_nome_para_arquivo = {}

    for arquivo in arquivos_json:
        try:
            with open(arquivo, "r", encoding="utf-8") as f:
                dados = json.load(f)
                nome = dados.get("nome", arquivo.stem)
                lista_nomes.append(nome)
                mapa_nome_para_arquivo[nome] = arquivo
        except Exception as e:
            st.error(f"Erro ao ler {arquivo.name}: {e}")

    # Seletor
    escala_selecionada = st.selectbox("Selecione uma escala para responder:", lista_nomes)

    if escala_selecionada:
        render_scale_form(mapa_nome_para_arquivo[escala_selecionada])


def corretion(respostas_dict: dict, escala_json: dict, modo: str = "ordinal") -> dict:
    """
    <docstrings>
    Corrige o resultado de uma escala a partir das respostas e do JSON da escala,
    aplicando inversão de itens e somando os pontos por fator e no total.

    Args:
        respostas_dict (dict): Dicionário com índices em string e respostas em texto.
        escala_json (dict): Dicionário JSON da escala.
        modo (str): Modo de correção. Pode ser 'ordinal', 'ordinal_1based' ou 'binario'.

    Returns:
        dict: Dicionário com pontuação total e por fator.
    """

    respostas_str = escala_json.get("respostas", [])
    reversos = set(escala_json.get("itens_reversos", []))
    fatores = escala_json.get("fatores", {})

    resultado = {fator: 0 for fator in fatores}
    resultado["total"] = 0

    for idx_str, resposta in respostas_dict.items():
        idx = int(idx_str)

        if resposta not in respostas_str:
            continue

        # --- Modo ordinal (base 0 ou base 1) ---
        if modo == "ordinal":
            valor_bruto = respostas_str.index(resposta)
        elif modo == "ordinal_1based":
            valor_bruto = respostas_str.index(resposta) + 1
        elif modo == "binario":
            # Considera as duas respostas mais autísticas como 1, resto 0
            valor_bruto = int(resposta in respostas_str[-2:])
        else:
            raise ValueError(f"Modo de correção inválido: {modo}")

        # --- Aplica reverso ---
        if idx in reversos:
            if modo.startswith("ordinal"):
                max_valor = len(respostas_str) - 1 if modo == "ordinal" else len(respostas_str)
                valor_corrigido = max_valor - valor_bruto
            elif modo == "binario":
                valor_corrigido = 1 - valor_bruto
        else:
            valor_corrigido = valor_bruto

        # --- Soma ---
        for fator, indices in fatores.items():
            if idx in indices:
                resultado[fator] += valor_corrigido

        resultado["total"] += valor_corrigido

    return resultado


def render_results_with_reference(nome_escala: str, escala_json: dict, normas_opcoes: dict):
    """
    Renderiza os resultados com base na referência selecionada (ex: Egito et al.),
    aplicando automaticamente o modo de correção e a população disponível.

    Args:
        nome_escala (str): Nome da escala no session_state.
        escala_json (dict): JSON da definição da escala.
        normas_opcoes (dict): Mapa {nome_referencia: json_carregado}

    Exibe:
        Tabela com pontuação por fator e percentil estimado.
    """

    respostas = st.session_state.get("escalas_respondidas", {}).get(nome_escala)
    if not respostas:
        st.warning("📭 Nenhuma resposta encontrada para essa escala.")
        return

    # --- Seletor de referência (norma) ---
    referencia_nomes = [
        norma.get("reference_label", nome)
        for nome, norma in normas_opcoes.items()
    ]

    mapa_label_para_nome = {
        norma.get("reference_label", nome): nome
        for nome, norma in normas_opcoes.items()
    }

    ref_label_escolhida = st.selectbox("Escolha a referência normativa:", referencia_nomes)
    ref_nome_escolhido = mapa_label_para_nome[ref_label_escolhida]
    norma = normas_opcoes[ref_nome_escolhido]

    # --- Extrai a citação da referência ---
    citation = norma.get("reference_citation", {})
    st.info(citation)

    # --- Extrai modo e populações disponíveis ---
    modo = norma.get("modo_correcao", "ordinal")
    
    # --- Mapeamento manual dos nomes internos para rótulos legíveis ---
    normative_group_raw = norma.get("normative_data", {})

    normative_group_aliases = {
        "total_pid5" : "Amostra total (N = 1210); entre 15 e 73 anos",
        "clinico_pid5" : "Grupo clínico (N = 554); entre 15 e 63 anos",
        "comunitario_pid5" : "Grupo comunitário (N = 656); entre 15 e 73 anos",
        "bis11_malloy" : "Amostra única (N = 3,053); entre 18 e 84 anos.",
        "masculino": "Homens",
        "feminino": "Mulheres",
        "amostra1_diagnostico_sim": "Amostra 1 (N = 415); entre 18 e 86 anos com tratamento psiquiátrico",
        "amostra1_diagnostico_nao": "Amostra 1 (N = 415); entre 18 e 86 anos sem tratamento psiquiátrico",
        "amostra2_diagnostico_sim": "Amostra 2 (N = 1011); entre 18 e 67 anos com tratamento psiquiátrico",
        "amostra2_diagnostico_nao": "Amostra 2 (N = 1011); entre 18 e 67 anos sem tratamento psiquiátrico",
    }

    # Garante que só as chaves existentes serão mostradas
    options_display = [
        normative_group_aliases.get(k, k.replace("_", " ").title())
        for k in normative_group_raw.keys()
    ]

    # Mapeia de volta para chave interna
    label_to_key_map = {
        normative_group_aliases.get(k, k.replace("_", " ").title()): k
        for k in normative_group_raw.keys()
    }

    # Selectbox com nomes legíveis
    selected_display = st.selectbox("População normativa:", options_display)
    selected_group = label_to_key_map[selected_display]


    # --- Corrige os resultados com o modo indicado ---
    result = corretion(respostas, escala_json, modo=modo)

    # --- Apelidos para exibição amigável ---
    factor_tags = {
        "habilidades_sociais": "Habilidades Sociais",
        "comunicacao": "Comunicação",
        "imaginacao": "Imaginação",
        "atencao_a_detalhes": "Atenção a Detalhes",
        "troca_de_atencao": "Atenção Alternada",
        "total": "Total"
    }

    # --- Tabela ---
    linhas = []
    for fator, valor in result.items():
        fator_exibido = factor_tags.get(fator, fator.replace("_", " ").title())
        value = int(valor)

        linha = {
            "Fator": fator_exibido,
            "Pontuação": value
        }

        percentil = search_percentile(value, selected_group, norma, fator=fator)
        linha["Percentil"] = f"{percentil:.1f}" if percentil is not None else "—"

        linhas.append(linha)

    # --- Exibição ---
    st.subheader(f"🧮 Resultado – {escala_json.get('nome', nome_escala)}")
    st.caption(f"Correção baseada em: **{ref_label_escolhida}** (modo: `{modo}`)")

    st.table(linhas)



def search_percentile(pontuacao: int, normative_data: str, normas: dict, fator: str = "total") -> float | None:
    """
    Estima o percentil baseado em pontuação, normative_data e fator, suportando
    normas simples (com listas) e normas fatoriais (com dicionários por fator).

    Args:
        pontuacao (int): Escore a ser interpretado.
        normative_data (str): População normativa (ex: "masculino").
        normas (dict): JSON completo da norma.
        fator (str): Nome do fator a buscar (padrão: "total").

    Returns:
        float | None: Percentil estimado ou None se indisponível.
    """

    normative_data = normative_data.lower()
    grupo = normas.get("normative_data", {}).get(normative_data)
    if not grupo:
        return None

    pontos_raw = grupo.get("pontuacoes")
    percentis_raw = grupo.get("percentis")

    # --- Modo fator: dict com chaves por fator ---
    if isinstance(pontos_raw, dict) and isinstance(percentis_raw, dict):
        pontos = pontos_raw.get(fator)
        percentis = percentis_raw.get(fator)

    # --- Modo simples: listas aplicáveis só ao total ---
    elif isinstance(pontos_raw, list) and isinstance(percentis_raw, list) and fator == "total":
        pontos = pontos_raw
        percentis = percentis_raw

    else:
        return None  # incompatível ou fator não disponível

    # --- Validação e parsing ---
    if not pontos or not percentis or len(pontos) != len(percentis):
        return None

    try:
        pontos = list(map(float, pontos))
        percentis = list(map(float, percentis))
    except Exception:
        return None

    for p, perc in zip(pontos, percentis):
        if pontuacao <= p:
            return perc
    return 99.9
