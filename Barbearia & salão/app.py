import sqlite3
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(_name_)
app.secret_key = 'chave_super_secreta_do_salao_2026'
DB_NAME = 'database.db'

# =====================================================================
# GAVETA 1: CONFIGURAÇÃO DE WHATSAPP (EXEMPLO COM EVOLUTION API / Z-API)
# =====================================================================
WHATSAPP_API_URL = "https://sua-api-whatsapp.com/message/sendText/instancia"
WHATSAPP_API_KEY = "SUA_CHAVE_API_AQUI"

def enviar_whatsapp(telefone, mensagem):
    """Envia mensagem via API de WhatsApp e registra no console para testes."""
    # Limpa caracteres não numéricos e garante o DDI 55 (Brasil)
    numero_limpo = ''.join(filter(str.isdigit, telefone))
    if not numero_limpo.startswith('55'):
        numero_limpo = '55' + numero_limpo

    print(f"\n[WHATSAPP DISPARADO] Para: {numero_limpo} | Msg: {mensagem}\n")

    # Descomente o bloco abaixo quando conectar sua API real (Evolution API, Z-API, etc.)
    """
    headers = {"apikey": WHATSAPP_API_KEY, "Content-Type": "application/json"}
    payload = {
        "number": numero_limpo,
        "text": mensagem
    }
    try:
        requests.post(WHATSAPP_API_URL, json=payload, headers=headers, timeout=5)
    except Exception as e:
        print(f"Erro ao enviar WhatsApp: {e}")
    """

# =====================================================================
# GAVETA 2: BANCO DE DADOS (SQLITE)
# =====================================================================
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Tabela de Usuários (Clientes e Profissionais)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            tipo TEXT DEFAULT 'cliente' -- 'cliente' ou 'admin'
        )
    ''')

    # Tabela de Profissionais (Barbeiros e Cabeleireiras)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profissionais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            especialidade TEXT NOT NULL, -- 'Barbeiro' ou 'Cabeleireira'
            descricao TEXT NOT NULL,
            tempo_medio_min INTEGER NOT NULL, -- Tempo médio por cliente em minutos
            foto_url TEXT
        )
    ''')

    # Tabela de Fila em Tempo Real
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fila (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            profissional_id INTEGER NOT NULL,
            servico TEXT NOT NULL,
            status TEXT DEFAULT 'aguardando', -- 'aguardando', 'atendendo', 'concluido', 'cancelado'
            notificado_15min INTEGER DEFAULT 0, -- 0 = Não avisado, 1 = Já avisado
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id),
            FOREIGN KEY(profissional_id) REFERENCES profissionais(id)
        )
    ''')

    # Popula profissionais iniciais se a tabela estiver vazia
    cursor.execute('SELECT COUNT(*) FROM profissionais')
    if cursor.fetchone()[0] == 0:
        profissionais_iniciais = [
            ("Lucas Silva", "Barbeiro", "Especialista em degradê navalhado, barba terapia e visagismo masculino.", 30, "https://images.unsplash.com/photo-1585747860715-2ba37e788b70?w=400"),
            ("Rafael Costa", "Barbeiro", "Cortes clássicos, tesoura, pigmentação e acabamento impecável.", 25, "https://images.unsplash.com/photo-1503951914875-452162b0f3f1?w=400"),
            ("Camila Souza", "Cabeleireira", "Cortes femininos, escova modelada, hidratação profunda e colorimetria.", 45, "https://images.unsplash.com/photo-1560066984-138dadb4c035?w=400"),
            ("Juliana Mendes", "Cabeleireira", "Mechas, progressiva sem formol, penteados e tratamentos capilares.", 50, "https://images.unsplash.com/photo-1522337660859-02fbefca4702?w=400")
        ]
        cursor.executemany('''
            INSERT INTO profissionais (nome, especialidade, descricao, tempo_medio_min, foto_url)
            VALUES (?, ?, ?, ?, ?)
        ''', profissionais_iniciais)

    conn.commit()
    conn.close()

# =====================================================================
# GAVETA 3: MOTOR DE TEMPO E GATILHO DE 15 MINUTOS
# =====================================================================
def verificar_e_notificar_fila(profissional_id):
    """Recalcula o tempo da fila de um profissional e avisa quem está a <= 15 min."""
    conn = get_db()
    cursor = conn.cursor()

    prof = cursor.execute('SELECT * FROM profissionais WHERE id = ?', (profissional_id,)).fetchone()
    if not prof:
        return

    tempo_medio = prof['tempo_medio_min']

    # Verifica se há alguém na cadeira sendo atendido agora (conta metade do tempo médio como restante)
    em_atendimento = cursor.execute('''
        SELECT id FROM fila WHERE profissional_id = ? AND status = 'atendendo'
    ''', (profissional_id,)).fetchone()

    tempo_acumulado = (tempo_medio // 2) if em_atendimento else 0

    # Pega todos que estão aguardando por ordem de chegada
    aguardando = cursor.execute('''
        SELECT f.id, f.notificado_15min, u.nome, u.telefone
        FROM fila f
        JOIN usuarios u ON f.usuario_id = u.id
        WHERE f.profissional_id = ? AND f.status = 'aguardando'
        ORDER BY f.id ASC
    ''', (profissional_id,)).fetchall()

    for index, item in enumerate(aguardando):
        pessoas_na_frente = index + (1 if em_atendimento else 0)
        tempo_estimado = tempo_acumulado

        # Se o tempo estimado for <= 15 minutos e ele ainda não recebeu o aviso:
        if tempo_estimado <= 15 and item['notificado_15min'] == 0:
            msg = (
                f"Olá {item['nome']}! ✂️ Sua vez com {prof['nome']} está chegando!\n"
                f"Faltam aproximadamente {tempo_estimado} minutos ({pessoas_na_frente} pessoa(s) na sua frente).\n"
                f"Já pode ir se aproximando do salão!"
            )
            enviar_whatsapp(item['telefone'], msg)
            cursor.execute('UPDATE fila SET notificado_15min = 1 WHERE id = ?', (item['id'],))

        tempo_acumulado += tempo_medio

    conn.commit()
    conn.close()

# =====================================================================
# GAVETA 4: ROTAS DA API (LOGIN, CADASTRO E FILA)
# =====================================================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/cadastro', methods=['POST'])
def cadastro():
    dados = request.json
    nome = dados.get('nome')
    telefone = dados.get('telefone')
    senha = dados.get('senha')

    if not nome or not telefone or not senha:
        return jsonify({'erro': 'Preencha todos os campos.'}), 400

    conn = get_db()
    try:
        hash_senha = generate_password_hash(senha)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO usuarios (nome, telefone, senha) VALUES (?, ?, ?)',
                       (nome, telefone, hash_senha))
        conn.commit()
        user_id = cursor.lastrowid
        session['user_id'] = user_id
        session['user_nome'] = nome

        enviar_whatsapp(telefone, f"Bem-vindo(a) ao nosso Salão & Barbearia, {nome}! Seu cadastro foi realizado com sucesso.")
        return jsonify({'mensagem': 'Cadastro realizado!', 'usuario': {'id': user_id, 'nome': nome}})
    except sqlite3.IntegrityError:
        return jsonify({'erro': 'Este número de WhatsApp já está cadastrado.'}), 400
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    dados = request.json
    telefone = dados.get('telefone')
    senha = dados.get('senha')

    conn = get_db()
    user = conn.execute('SELECT * FROM usuarios WHERE telefone = ?', (telefone,)).fetchone()
    conn.close()

    if user and check_password_hash(user['senha'], senha):
        session['user_id'] = user['id']
        session['user_nome'] = user['nome']
        return jsonify({'mensagem': 'Login efetuado!', 'usuario': {'id': user['id'], 'nome': user['nome']}})
    return jsonify({'erro': 'Telefone ou senha incorretos.'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'mensagem': 'Desconectado'})

@app.route('/api/status_geral', methods=['GET'])
def status_geral():
    """Retorna profissionais, tamanho da fila de cada um e status do cliente logado."""
    conn = get_db()
    profs = conn.execute('SELECT * FROM profissionais').fetchall()

    lista_profs = []
    for p in profs:
        qtd_aguardando = conn.execute('''
            SELECT COUNT(*) FROM fila WHERE profissional_id = ? AND status IN ('aguardando', 'atendendo')
        ''', (p['id'],)).fetchone()[0]

        lista_profs.append({
            'id': p['id'],
            'nome': p['nome'],
            'especialidade': p['especialidade'],
            'descricao': p['descricao'],
            'tempo_medio_min': p['tempo_medio_min'],
            'foto_url': p['foto_url'],
            'na_fila': qtd_aguardando,
            'tempo_espera_total': qtd_aguardando * p['tempo_medio_min']
        })

    meu_ticket = None
    user_id = session.get('user_id')

    if user_id:
        ticket = conn.execute('''
            SELECT f.*, p.nome as prof_nome, p.especialidade, p.tempo_medio_min
            FROM fila f
            JOIN profissionais p ON f.profissional_id = p.id
            WHERE f.usuario_id = ? AND f.status IN ('aguardando', 'atendendo')
            ORDER BY f.id DESC LIMIT 1
        ''', (user_id,)).fetchone()

        if ticket:
            # Conta quantos estão estritamente na frente dele
            na_frente = conn.execute('''
                SELECT COUNT(*) FROM fila
                WHERE profissional_id = ? AND status IN ('aguardando', 'atendendo') AND id < ?
            ''', (ticket['profissional_id'], ticket['id'])).fetchone()[0]

            tempo_estimado = na_frente * ticket['tempo_medio_min']
            meu_ticket = {
                'id': ticket['id'],
                'profissional_id': ticket['profissional_id'],
                'prof_nome': ticket['prof_nome'],
                'especialidade': ticket['especialidade'],
                'servico': ticket['servico'],
                'status': ticket['status'],
                'pessoas_na_frente': na_frente,
                'tempo_estimado': tempo_estimado
            }

    # Lista completa da fila ativa (para o Painel do Profissional)
    fila_ativa = conn.execute('''
        SELECT f.id, f.status, f.servico, u.nome as cliente_nome, u.telefone, p.nome as prof_nome, p.id as prof_id
        FROM fila f
        JOIN usuarios u ON f.usuario_id = u.id
        JOIN profissionais p ON f.profissional_id = p.id
        WHERE f.status IN ('aguardando', 'atendendo')
        ORDER BY f.id ASC
    ''').fetchall()

    conn.close()
    return jsonify({
        'usuario_logado': {'id': user_id, 'nome': session.get('user_nome')} if user_id else None,
        'profissionais': lista_profs,
        'meu_ticket': meu_ticket,
        'fila_ativa': [dict(row) for row in fila_ativa]
    })

@app.route('/api/entrar_fila', methods=['POST'])
def entrar_fila():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'erro': 'Faça login para entrar na fila.'}), 401

    dados = request.json
    prof_id = dados.get('profissional_id')
    servico = dados.get('servico', 'Corte Padrão')

    conn = get_db()
    # Impede entrar em duas filas ao mesmo tempo
    ativo = conn.execute('''
        SELECT id FROM fila WHERE usuario_id = ? AND status IN ('aguardando', 'atendendo')
    ''', (user_id,)).fetchone()

    if ativo:
        conn.close()
        return jsonify({'erro': 'Você já está em uma fila ativa!'}), 400

    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO fila (usuario_id, profissional_id, servico) VALUES (?, ?, ?)
    ''', (user_id, prof_id, servico))
    conn.commit()

    user = conn.execute('SELECT nome, telefone FROM usuarios WHERE id = ?', (user_id,)).fetchone()
    prof = conn.execute('SELECT nome FROM profissionais WHERE id = ?', (prof_id,)).fetchone()
    conn.close()

    enviar_whatsapp(
        user['telefone'],
        f"✅ Confirmado, {user['nome']}! Você entrou na fila com {prof['nome']} ({servico}). Acompanhe pelo site em tempo real!"
    )

    # Já verifica se ele entrou com <= 15 minutos de espera
    verificar_e_notificar_fila(prof_id)
    return jsonify({'mensagem': 'Você entrou na fila!'})

@app.route('/api/sair_fila', methods=['POST'])
def sair_fila():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'erro': 'Não autorizado'}), 401

    conn = get_db()
    ticket = conn.execute('''
        SELECT id, profissional_id FROM fila WHERE usuario_id = ? AND status IN ('aguardando', 'atendendo')
    ''', (user_id,)).fetchone()

    if ticket:
        conn.execute('UPDATE fila SET status = "cancelado" WHERE id = ?', (ticket['id'],))
        conn.commit()
        prof_id = ticket['profissional_id']
        conn.close()
        verificar_e_notificar_fila(prof_id)
        return jsonify({'mensagem': 'Você saiu da fila.'})

    conn.close()
    return jsonify({'erro': 'Nenhum agendamento ativo encontrado.'}), 404

@app.route('/api/profissional/acao', methods=['POST'])
def acao_profissional():
    """Permite ao barbeiro/cabeleireira chamar o próximo ou finalizar atendimento."""
    dados = request.json
    ticket_id = dados.get('ticket_id')
    nova_acao = dados.get('acao') # 'atendendo' ou 'concluido'

    conn = get_db()
    ticket = conn.execute('SELECT profissional_id FROM fila WHERE id = ?', (ticket_id,)).fetchone()
    if not ticket:
        conn.close()
        return jsonify({'erro': 'Ticket não encontrado'}), 404

    conn.execute('UPDATE fila SET status = ? WHERE id = ?', (nova_acao, ticket_id))
    conn.commit()
    prof_id = ticket['profissional_id']
    conn.close()

    # Sempre que a fila anda, recalcula e dispara WhatsApp para quem chegou nos 15 min!
    verificar_e_notificar_fila(prof_id)
    return jsonify({'mensagem': f'Status atualizado para {nova_acao}'})

if _name_ == '_main_':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)