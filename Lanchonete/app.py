from flask import Flask, jsonify, render_template, request

app = Flask(_name_, template_folder=".", static_folder=".")


@app.route("/")
def home():
    # Renderiza o seu index.html na raiz do projeto
    return render_template("index.html")


@app.route("/api/pedido", methods=["POST"])
def receber_pedido():
    # Recebe os dados do carrinho enviados pelo JavaScript do front-end
    dados_pedido = request.get_json()

    print("Novo pedido recebido na Lanchonete Dona Ruth:", dados_pedido)

    # Aqui você pode salvar no banco de dados, gerar comandas ou logar no terminal
    resposta = {
        "status": "sucesso",
        "mensagem": (
            "Pedido registrado com sucesso no back-end Python da Dona Ruth!"
        ),
        "pedido": dados_pedido,
    }

    return jsonify(resposta)


if _name_ == "_main_":
    print("Servidor da Lanchonete Dona Ruth rodando...")
    app.run(debug=True, port=5000)