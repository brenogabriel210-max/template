import os
import uuid
from datetime import datetime, date, timedelta
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(_file_))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads", "sobras")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(_name_, static_folder=BASE_DIR, static_url_path="")
app.config["SECRET_KEY"] = "stockflow-pro-secret-2026"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'estoque_fluxo.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

CORS(app, supports_credentials=True)
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)


# --- Modelos ---
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="funcionario")  # "gestor" ou "funcionario"

    def set_password(self, senha):
        self.password_hash = generate_password_hash(senha)

    def check_password(self, senha):
        return check_password_hash(self.password_hash, senha)


class ConfiguracaoExpediente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    horario_fechamento = db.Column(db.String(5), nullable=False, default="20:00")
    gestor_plantao = db.Column(db.String(100), nullable=False, default="gestor")
    capacidade_total_estoque = db.Column(db.Integer, nullable=False, default=500)
    ultimo_fechamento_data = db.Column(db.String(10), nullable=True)


class EspacoEstoque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo_posicao = db.Column(db.String(40), unique=True, nullable=False)
    capacidade = db.Column(db.Integer, nullable=False, default=50)
    ocupado = db.Column(db.Integer, nullable=False, default=0)
    status_fisico = db.Column(db.String(30), nullable=False, default="livre")  # "livre", "ocupado", "divergencia_nao_lancado"
    recebimento_ref = db.Column(db.String(60), nullable=True)
    ultimo_conferente = db.Column(db.String(100), nullable=True)
    ultima_conferencia_em = db.Column(db.String(30), nullable=True)

    @property
    def espaco_livre(self):
        return max(0, self.capacidade - self.ocupado)


class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo_barras = db.Column(db.String(100), unique=True, nullable=False)
    nome = db.Column(db.String(160), nullable=False)
    categoria = db.Column(db.String(100), nullable=False)
    preco = db.Column(db.Float, nullable=False, default=0.0)
    quantidade_estoque = db.Column(db.Integer, nullable=False, default=0)
    quantidade_venda = db.Column(db.Integer, nullable=False, default=0)
    quantidade_esperada_recebimento = db.Column(db.Integer, nullable=False, default=10)
    minimo = db.Column(db.Integer, nullable=False, default=5)
    posicao_codigo = db.Column(db.String(40), nullable=True)
    ultimo_conferente = db.Column(db.String(100), nullable=True)


class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_ref = db.Column(db.String(10), nullable=False)
    criado_em = db.Column(db.String(25), nullable=False)
    tipo = db.Column(db.String(40), nullable=False)  # "recebimento", "venda", "conferencia_vazio", "falta", "sobra", "checage_preco", "alteracao_preco"
    detalhe = db.Column(db.String(255), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=0)
    valor_unitario = db.Column(db.Float, nullable=False, default=0.0)
    responsavel = db.Column(db.String(100), nullable=False)
    gestor_notificado = db.Column(db.String(100), nullable=True)
    foto_url = db.Column(db.String(255), nullable=True)
    resolvido = db.Column(db.Boolean, default=False)


class BalancoDiario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_balanco = db.Column(db.String(10), unique=True, nullable=False)
    total_recebido = db.Column(db.Integer, nullable=False, default=0)
    total_area_venda = db.Column(db.Integer, nullable=False, default=0)
    total_faltas = db.Column(db.Integer, nullable=False, default=0)
    total_sobras = db.Column(db.Integer, nullable=False, default=0)
    valor_estoque_fechamento = db.Column(db.Float, nullable=False, default=0.0)
    espaco_livre_fechamento = db.Column(db.Integer, nullable=False, default=0)
    fechado_por = db.Column(db.String(100), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


def agora_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def hoje_str():
    return date.today().isoformat()


def registrar_mov(tipo, detalhe, quantidade=0, valor_unitario=0.0, responsavel=None, gestor_notificado=None, foto_url=None):
    cfg = ConfiguracaoExpediente.query.first()
    resp = responsavel or (current_user.username if current_user.is_authenticated else "sistema")
    mov = Movimentacao(
        data_ref=hoje_str(),
        criado_em=agora_str(),
        tipo=tipo,
        detalhe=detalhe,
        quantidade=quantidade,
        valor_unitario=valor_unitario,
        responsavel=resp,
        gestor_notificado=gestor_notificado or (cfg.gestor_plantao if cfg else "gestor"),
        foto_url=foto_url,
        resolvido=False
    )
    db.session.add(mov)
    return mov


def seed_inicial():
    if not Usuario.query.filter_by(username="gestor").first():
        g = Usuario(username="gestor", role="gestor")
        g.set_password("gestor123")
        db.session.add(g)

    if not Usuario.query.filter_by(username="funcionario").first():
        f = Usuario(username="funcionario", role="funcionario")
        f.set_password("func123")
        db.session.add(f)

    if not ConfiguracaoExpediente.query.first():
        db.session.add(ConfiguracaoExpediente(
            horario_fechamento="20:00",
            gestor_plantao="gestor",
            capacidade_total_estoque=400
        ))

    if EspacoEstoque.query.count() == 0:
        espacos = [
            EspacoEstoque(codigo_posicao="A-01", capacidade=80, ocupado=45, status_fisico="ocupado", recebimento_ref="REC-104", ultimo_conferente="gestor", ultima_conferencia_em="2026-11-21 18:10"),
            EspacoEstoque(codigo_posicao="A-02", capacidade=80, ocupado=0, status_fisico="livre", recebimento_ref="REC-105", ultimo_conferente="funcionario", ultima_conferencia_em="2026-11-22 08:30"),
            EspacoEstoque(codigo_posicao="B-01", capacidade=100, ocupado=0, status_fisico="livre", recebimento_ref="REC-106", ultimo_conferente="gestor", ultima_conferencia_em="2026-11-21 19:00"),
            EspacoEstoque(codigo_posicao="B-02", capacidade=100, ocupado=62, status_fisico="ocupado", recebimento_ref="REC-107", ultimo_conferente="funcionario", ultima_conferencia_em="2026-11-22 09:15"),
            EspacoEstoque(codigo_posicao="C-01", capacidade=60, ocupado=0, status_fisico="livre", recebimento_ref="REC-108", ultimo_conferente="gestor", ultima_conferencia_em="2026-11-20 17:40"),
        ]
        db.session.add_all(espacos)

    if Produto.query.count() == 0:
        produtos = [
            Produto(codigo_barras="7891000100011", nome="Camiseta Básica Preta", categoria="Vestuário", preco=49.90, quantidade_estoque=45, quantidade_venda=18, quantidade_esperada_recebimento=20, minimo=12, posicao_codigo="A-01", ultimo_conferente="gestor"),
            Produto(codigo_barras="7891000100028", nome="Tênis Esportivo Runner", categoria="Calçados", preco=229.90, quantidade_estoque=22, quantidade_venda=9, quantidade_esperada_recebimento=12, minimo=10, posicao_codigo="B-02", ultimo_conferente="funcionario"),
            Produto(codigo_barras="7891000100035", nome="Mochila Urbana 25L", categoria="Acessórios", preco=159.00, quantidade_estoque=40, quantidade_venda=14, quantidade_esperada_recebimento=15, minimo=8, posicao_codigo="A-01", ultimo_conferente="gestor"),
        ]
        db.session.add_all(produtos)

    ontem = (date.today() - timedelta(days=1)).isoformat()
    if not BalancoDiario.query.filter_by(data_balanco=ontem).first():
        db.session.add(BalancoDiario(
            data_balanco=ontem,
            total_recebido=34,
            total_area_venda=21,
            total_faltas=2,
            total_sobras=1,
            valor_estoque_fechamento=14850.00,
            espaco_livre_fechamento=215,
            fechado_por="gestor"
        ))

    db.session.commit()


with app.app_context():
    db.create_all()
    seed_inicial()


def verificar_fechamento_automatico():
    cfg = ConfiguracaoExpediente.query.first()
    if not cfg:
        return
    agora_hm = datetime.now().strftime("%H:%M")
    hoje = hoje_str()
    if agora_hm >= cfg.horario_fechamento and cfg.ultimo_fechamento_data != hoje:
        consolidar_balanco(hoje, automatico=True)


def consolidar_balanco(data_ref, automatico=False):
    cfg = ConfiguracaoExpediente.query.first()
    produtos = Produto.query.all()
    espacos = EspacoEstoque.query.all()
    movs_dia = Movimentacao.query.filter_by(data_ref=data_ref).all()

    total_recebido = sum(m.quantidade for m in movs_dia if m.tipo == "recebimento")
    total_venda = sum(m.quantidade for m in movs_dia if m.tipo == "venda")
    total_faltas = sum(m.quantidade for m in movs_dia if m.tipo == "falta")
    total_sobras = sum(m.quantidade for m in movs_dia if m.tipo == "sobra")
    valor_estoque = sum(p.quantidade_estoque * p.preco for p in produtos)
    espaco_livre = sum(e.espaco_livre for e in espacos)

    balanco = BalancoDiario.query.filter_by(data_balanco=data_ref).first()
    quem = "sistema_auto" if automatico else (current_user.username if current_user.is_authenticated else "gestor")

    if not balanco:
        balanco = BalancoDiario(data_balanco=data_ref)
        db.session.add(balanco)

    balanco.total_recebido = total_recebido
    balanco.total_area_venda = total_venda
    balanco.total_faltas = total_faltas
    balanco.total_sobras = total_sobras
    balanco.valor_estoque_fechamento = round(valor_estoque, 2)
    balanco.espaco_livre_fechamento = espaco_livre
    balanco.fechado_por = quem

    cfg.ultimo_fechamento_data = data_ref
    db.session.commit()
    return balanco


def calcular_previsao_compra():
    ontem = (date.today() - timedelta(days=1)).isoformat()
    balanco_ontem = BalancoDiario.query.filter_by(data_balanco=ontem).first()
    if not balanco_ontem:
        balanco_ontem = BalancoDiario.query.order_by(BalancoDiario.id.desc()).first()

    produtos = Produto.query.all()
    espacos = EspacoEstoque.query.all()
    espaco_livre_atual = sum(e.espaco_livre for e in espacos)

    base_venda_ontem = balanco_ontem.total_area_venda if balanco_ontem else 10
    base_faltas_ontem = balanco_ontem.total_faltas if balanco_ontem else 0

    sugestoes = []
    total_unidades_sugeridas = 0
    valor_estimado_compra = 0.0

    for p in produtos:
        demanda_diaria = max(p.minimo, int(round(base_venda_ontem / max(1, len(produtos))))) + base_faltas_ontem
        alvo_cobertura = p.minimo + demanda_diaria
        sugerido = max(0, alvo_cobertura - p.quantidade_estoque)
        if sugerido > espaco_livre_atual:
            sugerido = espaco_livre_atual
        espaco_livre_atual = max(0, espaco_livre_atual - sugerido)

        total_unidades_sugeridas += sugerido
        valor_estimado_compra += sugerido * p.preco
        sugestoes.append({
            "produto_id": p.id,
            "codigo_barras": p.codigo_barras,
            "nome": p.nome,
            "estoque_atual": p.quantidade_estoque,
            "minimo": p.minimo,
            "sugerido_comprar": sugerido,
            "custo_estimado": round(sugerido * p.preco, 2)
        })

    return {
        "data_base_balanco": balanco_ontem.data_balanco if balanco_ontem else "N/A",
        "venda_dia_anterior": balanco_ontem.total_area_venda if balanco_ontem else 0,
        "faltas_dia_anterior": balanco_ontem.total_faltas if balanco_ontem else 0,
        "espaco_livre_atual": sum(e.espaco_livre for e in espacos),
        "total_unidades_sugeridas": total_unidades_sugeridas,
        "valor_estimado_compra": round(valor_estimado_compra, 2),
        "itens": sugestoes
    }


# --- Rotas de Páginas e Arquivos Estáticos ---
@app.route("/")
def raiz():
    return send_from_directory(BASE_DIR, "login.html")


@app.route("/<path:filename>")
def arquivos_estaticos(filename):
    return send_from_directory(BASE_DIR, filename)


@app.route("/uploads/sobras/<path:filename>")
@login_required
def servir_foto_sobra(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# --- Autenticação ---
@app.route("/api/login", methods=["POST"])
def login():
    dados = request.get_json() or {}
    username = (dados.get("username") or "").strip()
    password = dados.get("password") or ""
    perfil_solicitado = dados.get("perfil_solicitado")

    usuario = Usuario.query.filter_by(username=username).first()
    if not usuario or not usuario.check_password(password):
        return jsonify({"erro": "Usuário ou senha inválidos."}), 401

    if perfil_solicitado and usuario.role != perfil_solicitado:
        return jsonify({"erro": f"Esta conta é do perfil '{usuario.role}'. Selecione a aba correspondente."}), 403

    login_user(usuario)
    return jsonify({
        "mensagem": "Login realizado com sucesso.",
        "username": usuario.username,
        "role": usuario.role
    }), 200


@app.route("/api/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({"mensagem": "Sessão encerrada."}), 200


@app.route("/api/check-auth", methods=["GET"])
def check_auth():
    if current_user.is_authenticated:
        verificar_fechamento_automatico()
        return jsonify({
            "autenticado": True,
            "username": current_user.username,
            "role": current_user.role
        }), 200
    return jsonify({"autenticado": False}), 401


# --- Dashboard do Gestor ---
@app.route("/api/gestor/dashboard", methods=["GET"])
@login_required
def dashboard_gestor():
    if current_user.role != "gestor":
        return jsonify({"erro": "Acesso restrito a gestores."}), 403

    verificar_fechamento_automatico()
    cfg = ConfiguracaoExpediente.query.first()
    produtos = Produto.query.all()
    espacos = EspacoEstoque.query.all()
    movs_hoje = Movimentacao.query.filter_by(data_ref=hoje_str()).all()

    total_estoque = sum(p.quantidade_estoque for p in produtos)
    total_venda = sum(p.quantidade_venda for p in produtos)
    valor_estoque = sum(p.quantidade_estoque * p.preco for p in produtos)
    valor_venda = sum(p.quantidade_venda * p.preco for p in produtos)

    capacidade_total = sum(e.capacidade for e in espacos) or cfg.capacidade_total_estoque
    espaco_livre = sum(e.espaco_livre for e in espacos)
    espaco_ocupado = sum(e.ocupado for e in espacos)

    total_fluxo = max(1, total_estoque + total_venda)
    pct_estoque = round((total_estoque / total_fluxo) * 100, 1)
    pct_venda = round((total_venda / total_fluxo) * 100, 1)

    alertas = [
        {
            "id": m.id,
            "tipo": m.tipo,
            "detalhe": m.detalhe,
            "quantidade": m.quantidade,
            "responsavel": m.responsavel,
            "gestor_notificado": m.gestor_notificado,
            "criado_em": m.criado_em,
            "foto_url": m.foto_url
        }
        for m in Movimentacao.query.filter(Movimentacao.tipo.in_(["falta", "sobra", "checage_preco", "conferencia_vazio"])).order_by(Movimentacao.id.desc()).limit(25).all()
        if m.tipo in ["falta", "sobra"] or "Irregular" in m.detalhe or "Divergência" in m.detalhe
    ]

    return jsonify({
        "configuracao": {
            "horario_fechamento": cfg.horario_fechamento,
            "gestor_plantao": cfg.gestor_plantao,
            "ultimo_fechamento_data": cfg.ultimo_fechamento_data
        },
        "kpis": {
            "total_estoque": total_estoque,
            "total_venda": total_venda,
            "valor_estoque": round(valor_estoque, 2),
            "valor_venda": round(valor_venda, 2),
            "pct_estoque": pct_estoque,
            "pct_venda": pct_venda,
            "capacidade_total": capacidade_total,
            "espaco_ocupado": espaco_ocupado,
            "espaco_livre": espaco_livre,
            "total_alertas": len(alertas)
        },
        "comparativo": {
            "labels": [p.nome for p in produtos],
            "entrada_estoque": [p.quantidade_estoque for p in produtos],
            "area_venda": [p.quantidade_venda for p in produtos]
        },
        "produtos": [
            {
                "id": p.id,
                "codigo_barras": p.codigo_barras,
                "nome": p.nome,
                "categoria": p.categoria,
                "preco": p.preco,
                "quantidade_estoque": p.quantidade_estoque,
                "quantidade_venda": p.quantidade_venda,
                "minimo": p.minimo,
                "posicao_codigo": p.posicao_codigo,
                "ultimo_conferente": p.ultimo_conferente or "N/A"
            }
            for p in produtos
        ],
        "alertas": alertas,
        "previsao_compra": calcular_previsao_compra(),
        "movimentacoes_hoje": [
            {
                "id": m.id,
                "tipo": m.tipo,
                "detalhe": m.detalhe,
                "quantidade": m.quantidade,
                "responsavel": m.responsavel,
                "criado_em": m.criado_em,
                "foto_url": m.foto_url
            }
            for m in reversed(movs_hoje)
        ]
    }), 200


@app.route("/api/gestor/configuracao", methods=["POST"])
@login_required
def atualizar_configuracao():
    if current_user.role != "gestor":
        return jsonify({"erro": "Acesso restrito a gestores."}), 403

    dados = request.get_json() or {}
    cfg = ConfiguracaoExpediente.query.first()
    if dados.get("horario_fechamento"):
        cfg.horario_fechamento = dados["horario_fechamento"].strip()
    if dados.get("gestor_plantao"):
        cfg.gestor_plantao = dados["gestor_plantao"].strip()
    db.session.commit()
    return jsonify({"mensagem": "Configurações salvas.", "horario_fechamento": cfg.horario_fechamento}), 200


@app.route("/api/gestor/fechar-dia", methods=["POST"])
@login_required
def fechar_dia_manual():
    if current_user.role != "gestor":
        return jsonify({"erro": "Acesso restrito a gestores."}), 403

    balanco = consolidar_balanco(hoje_str(), automatico=False)
    return jsonify({
        "mensagem": f"Balanço de {balanco.data_balanco} consolidado.",
        "previsao_compra": calcular_previsao_compra()
    }), 200


@app.route("/api/gestor/alterar-preco", methods=["POST"])
@login_required
def alterar_preco():
    if current_user.role != "gestor":
        return jsonify({"erro": "Acesso restrito a gestores."}), 403

    dados = request.get_json() or {}
    produto_id = dados.get("produto_id")
    novo_preco = float(dados.get("novo_preco", 0))

    if novo_preco <= 0:
        return jsonify({"erro": "Informe um valor válido maior que zero."}), 400

    produto = Produto.query.get(produto_id)
    if not produto:
        return jsonify({"erro": "Produto não encontrado."}), 404

    preco_antigo = produto.preco
    produto.preco = round(novo_preco, 2)
    registrar_mov(
        tipo="alteracao_preco",
        detalhe=f"Preço de '{produto.nome}' alterado de R$ {preco_antigo:.2f} para R$ {produto.preco:.2f}",
        quantidade=1,
        valor_unitario=produto.preco
    )
    db.session.commit()
    return jsonify({"mensagem": "Preço atualizado com sucesso