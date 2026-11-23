const API_URL = "http://127.0.0.1:5000/api";

let sessao = null;
let produtosCache = [];
let scannerAtivo = null;

// Estados do fluxo do funcionário
let recConfere = null;        // "sim" | "nao"
let recDivergencia = null;    // "faltando" | "sobrando"
let vendaStatusPreco = null;  // "correto" | "irregular"
let vendaDirecaoPreco = null; // "mais_barato" | "mais_caro"

// Instâncias dos gráficos do Gestor
let graficoLinear = null;
let graficoRosca = null;

function mostrarToast(msg) {
    const el = document.getElementById("toastFeedback");
    el.textContent = msg;
    el.classList.remove("hidden");
    clearTimeout(mostrarToast._t);
    mostrarToast._t = setTimeout(() => el.classList.add("hidden"), 3800);
}

function formatarMoeda(v) {
    return Number(v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

async function iniciarApp() {
    try {
        const res = await fetch(${API_URL}/check-auth, { credentials: "include" });
        if (!res.ok) {
            window.location.href = "login.html";
            return;
        }
        sessao = await res.json();
        if (!sessao.autenticado) {
            window.location.href = "login.html";
            return;
        }

        document.getElementById("badgeUsuario").textContent = ${sessao.username} (${sessao.role.toUpperCase()});

        if (sessao.role === "gestor") {
            document.getElementById("subtituloPerfil").textContent = "Visão Gerencial e Previsão";
            document.getElementById("ambienteGestor").classList.remove("hidden");
            document.getElementById("ambienteFuncionario").classList.add("hidden");
            await carregarPainelGestor();
        } else {
            document.getElementById("subtituloPerfil").textContent = "Operação de Loja / Depósito";
            document.getElementById("ambienteFuncionario").classList.remove("hidden");
            document.getElementById("ambienteGestor").classList.add("hidden");
            await carregarAmbienteFuncionario();
        }
    } catch (e) {
        window.location.href = "login.html";
    }
}

document.getElementById("btnLogout").addEventListener("click", async () => {
    await pararScanner();
    await fetch(${API_URL}/logout, { method: "POST", credentials: "include" });
    window.location.href = "login.html";
});

// =========================================================================
// VISÃO DO GESTOR
// =========================================================================
async function carregarPainelGestor() {
    const res = await fetch(${API_URL}/gestor/dashboard, { credentials: "include" });
    if (!res.ok) return;
    const dados = await res.json();

    const { kpis, configuracao, comparativo, produtos, alertas, previsao_compra } = dados;

    document.getElementById("gKpiEstoque").textContent = ${kpis.total_estoque} un.;
    document.getElementById("gPctEstoque").textContent = ${kpis.pct_estoque}% do fluxo;
    document.getElementById("gKpiVenda").textContent = ${kpis.total_venda} un.;
    document.getElementById("gPctVenda").textContent = ${kpis.pct_venda}% do fluxo;
    document.getElementById("gValorEstoque").textContent = formatarMoeda(kpis.valor_estoque);
    document.getElementById("gValorVenda").textContent = Área de venda: ${formatarMoeda(kpis.valor_venda)};
    document.getElementById("gEspacoLivre").textContent = ${kpis.espaco_livre} un.;
    document.getElementById("gEspacoDetalhe").textContent = Ocupado: ${kpis.espaco_ocupado} / Total: ${kpis.capacidade_total};

    document.getElementById("inputHorarioFechamento").value = configuracao.horario_fechamento;
    document.getElementById("inputGestorPlantao").value = configuracao.gestor_plantao;

    renderizarGraficosGestor(comparativo, kpis);
    renderizarPrevisaoCompra(previsao_compra);
    renderizarAlertas(alertas);
    renderizarTabelaGestor(produtos);
}

function renderizarGraficosGestor(comparativo, kpis) {
    const ctxLin = document.getElementById("graficoComparativoLinear").getContext("2d");
    if (graficoLinear) graficoLinear.destroy();
    graficoLinear = new Chart(ctxLin, {
        type: "line",
        data: {
            labels: comparativo.labels,
            datasets: [
                {
                    label: "Estoque",
                    data: comparativo.entrada_estoque,
                    borderColor: "#6366f1",
                    backgroundColor: "rgba(99, 102, 241, 0.14)",
                    fill: true,
                    tension: 0.3
                },
                {
                    label: "Área de Venda",
                    data: comparativo.area_venda,
                    borderColor: "#10b981",
                    backgroundColor: "rgba(16, 185, 129, 0.12)",
                    fill: true,
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: "#cbd5e1" } } },
            scales: {
                y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } },
                x: { ticks: { color: "#94a3b8" }, grid: { display: false } }
            }
        }
    });

    const ctxRos = document.getElementById("graficoFluxoRosca").getContext("2d");
    if (graficoRosca) graficoRosca.destroy();
    graficoRosca = new Chart(ctxRos, {
        type: "doughnut",
        data: {
            labels: ["Estoque", "Área de Venda", "Espaço Livre"],
            datasets: [{
                data: [kpis.total_estoque, kpis.total_venda, kpis.espaco_livre],
                backgroundColor: ["#6366f1", "#10b981", "#f59e0b"],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom", labels: { color: "#cbd5e1" } } }
        }
    });
}

function renderizarPrevisaoCompra(prev) {
    const box = document.getElementById("resumoPrevisao");
    const linhas = prev.itens.map(item => `
        <div class="previsao-item">
            <span><strong>${item.nome}</strong> (Atual: ${item.estoque_atual})</span>
            <span>Comprar: <strong class="text-indigo">${item.sugerido_comprar} un.</strong> (${formatarMoeda(item.custo_estimado)})</span>
        </div>
    `).join("");

    box.innerHTML = `
        <p style="margin-bottom:8px;">
            Baseado no balanço de <strong>${prev.data_base_balanco}</strong>
            (Venda: ${prev.venda_dia_anterior} un. | Faltas: ${prev.faltas_dia_anterior} un.) —
            Custo estimado: <strong class="text-emerald">${formatarMoeda(prev.valor_estimado_compra)}</strong>
        </p>
        ${linhas}
    `;
}

function renderizarAlertas(alertas) {
    document.getElementById("contadorAlertas").textContent = alertas.length;
    const lista = document.getElementById("listaAlertas");
    if (!alertas.length) {
        lista.innerHTML = <p class="muted">Nenhuma ocorrência crítica no momento.</p>;
        return;
    }

    lista.innerHTML = alertas.map(a => `
        <div class="alerta-item ${a.tipo === "sobra" ? "sobra" : ""}">
            <div><strong>${a.detalhe}</strong></div>
            ${a.foto_url ? <div style="margin-top:6px;"><a href="${a.foto_url}" target="_blank" style="color:#818cf8;font-size:12px;">Ver foto anexada</a></div> : ""}
            <div class="alerta-meta">Por: ${a.responsavel} • Gestor: ${a.gestor_notificado || "gestor"} • ${a.criado_em}</div>
        </div>
    `).join("");
}

function renderizarTabelaGestor(produtos) {
    const tbody = document.getElementById("tabelaGestorProdutos");
    tbody.innerHTML = produtos.map(p => `
        <tr>
            <td><code>${p.codigo_barras}</code></td>
            <td><strong>${p.nome}</strong></td>
            <td>${p.posicao_codigo || "—"}</td>
            <td>${p.quantidade_estoque}</td>
            <td>${p.quantidade_venda}</td>
            <td>${p.ultimo_conferente}</td>
            <td><strong>${formatarMoeda(p.preco)}</strong></td>
            <td>
                <form class="preco-edit-form" onsubmit="salvarNovoPreco(event, ${p.id})">
                    <input type="number" step="0.01" min="0.01" value="${p.preco.toFixed(2)}" required>
                    <button type="submit" class="btn btn-sm btn-secondary">Atualizar</button>
                </form>
            </td>
        </tr>
    `).join("");
}

async function salvarNovoPreco(event, produtoId) {
    event.preventDefault();
    const novoPreco = event.target.querySelector("input").value;
    const res = await fetch(${API_URL}/gestor/alterar-preco, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ produto_id: produtoId, novo_preco: Number(novoPreco) })
    });
    const data = await res.json();
    mostrarToast(data.mensagem || data.erro);
    carregarPainelGestor();
}

document.getElementById("formConfigExpediente").addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await fetch(${API_URL}/gestor/configuracao, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
            horario_fechamento: document.getElementById("inputHorarioFechamento").value,
            gestor_plantao: document.getElementById("inputGestorPlantao").value.trim()
        })
    });
    const data = await res.json();
    mostrarToast(data.mensagem || data.erro);
    carregarPainelGestor();
});

document.getElementById("btnFecharDiaAgora").addEventListener("click", async () => {
    const res = await fetch(${API_URL}/gestor/fechar-dia, {
        method: "POST",
        credentials: "include"
    });
    const data = await res.json();
    mostrarToast(data.mensagem || data.erro);
    carregarPainelGestor();
});

// =========================================================================
// VISÃO DO FUNCIONÁRIO (MODOS GUIADOS + CÂMERA + ÁRVORE DE DECISÃO)
// =========================================================================
async function carregarAmbienteFuncionario() {
    const [resProd, resEsp] = await Promise.all([
        fetch(${API_URL}/produtos, { credentials: "include" }),
        fetch(${API_URL}/espacos, { credentials: "include" })
    ]);
    produtosCache = await resProd.json();
    const espacos = await resEsp.json();

    const livreTotal = espacos.reduce((acc, e) => acc + e.espaco_livre, 0);
    document.getElementById("fEspacoLivre").textContent = ${livreTotal} un.;

    const espacoComRef = espacos.find(e => e.recebimento_ref && e.recebimento_ref !== "N/A");
    document.getElementById("fUltimoRecebimento").textContent = espacoComRef ? espacoComRef.recebimento_ref : "Sem registro";

    const ultimoConf = produtosCache.find(p => p.ultimo_conferente && p.ultimo_conferente !== "N/A");
    document.getElementById("fUltimoConferente").textContent = ultimoConf ? ultimoConf.ultimo_conferente : "—";

    renderizarEspacosVazios(espacos);
}

// Alternar modos do funcionário
document.querySelectorAll(".modo-tab").forEach(tab => {
    tab.addEventListener("click", async () => {
        await pararScanner();
        document.querySelectorAll(".modo-tab").forEach(t => t.classList.remove("active"));
        tab.classList.add("active");

        const modo = tab.dataset.modo;
        document.getElementById("modoVazio").classList.toggle("hidden", modo !== "vazio");
        document.getElementById("modoRecebimento").classList.toggle("hidden", modo !== "recebimento");
        document.getElementById("modoVenda").classList.toggle("hidden", modo !== "venda");
    });
});

// --- Modo 1: Espaços Vazios ---
function renderizarEspacosVazios(espacos) {
    const container = document.getElementById("listaEspacosVazios");
    const livres = espacos.filter(e => e.espaco_livre > 0 || e.status_fisico !== "ocupado");

    container.innerHTML = livres.map(e => `
        <div class="espaco-card ${e.status_fisico === "divergencia_nao_lancado" ? "divergencia" : ""}">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <strong>Posição ${e.codigo_posicao}</strong>
                <span class="text-emerald">Livre: ${e.espaco_livre} un.</span>
            </div>
            <small class="muted">Recebimento: ${e.recebimento_ref} • Últ. conferente: ${e.ultimo_conferente}</small>
            <div class="choice-row" style="margin-top:4px;">
                <button type="button" class="btn btn-sm btn-success" onclick="confirmarEspaco(${e.id}, 'vazio_confirmado')">
                    Está Vazio
                </button>
                <button type="button" class="btn btn-sm btn-secondary" onclick="confirmarEspaco(${e.id}, 'tem_item_nao_lancado')">
                    Tem Item Não Lançado
                </button>
            </div>
        </div>
    `).join("");
}

async function confirmarEspaco(espacoId, confirmacao) {
    let observacao = "";
    if (confirmacao === "tem_item_nao_lancado") {
        observacao = prompt("Qual item ou quantidade você encontrou sem lançamento?") || "";
    }
    const res = await fetch('${API_URL}/espacos/','${espacoId}/conferir', {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ confirmacao, observacao })
    });
    const data = await res.json();
    mostrarToast(data.mensagem || data.erro);
    await carregarAmbienteFuncionario();
}

// --- Leitor de Câmera (Código de Barras / QR Code) ---
async function pararScanner() {
    if (scannerAtivo) {
        try { await scannerAtivo.stop(); } catch (_) {}
        scannerAtivo = null;
    }
    document.getElementById("scannerRecebimentoArea").classList.add("hidden");
    document.getElementById("scannerRecebimentoArea").innerHTML = "";
    document.getElementById("scannerVendaArea").classList.add("hidden");
    document.getElementById("scannerVendaArea").innerHTML = "";
}

async function abrirLeitorCamera(containerId, aoLer) {
    await pararScanner();
    const box = document.getElementById(containerId);
    box.classList.remove("hidden");
    const leitor = new Html5Qrcode(containerId);
    scannerAtivo = leitor;

    try {
        await leitor.start(
            { facingMode: "environment" },
            { fps: 10, qrbox: { width: 240, height: 110 } },
            async (codigoLido) => {
                aoLer(codigoLido);
                await pararScanner();
            },
            () => {}
        );
    } catch (err) {
        mostrarToast("Não foi possível acessar a câmera.");
        await pararScanner();
    }
}

document.getElementById("btnCameraRecebimento").addEventListener("click", () => {
    abrirLeitorCamera("scannerRecebimentoArea", (codigo) => {
        const input = document.getElementById("recCodigo");
        input.value = codigo;
        input.dispatchEvent(new Event("input"));
    });
});

document.getElementById("btnCameraVenda").addEventListener("click", () => {
    abrirLeitorCamera("scannerVendaArea", (codigo) => {
        const input = document.getElementById("vendaCodigo");
        input.value = codigo;
        input.dispatchEvent(new Event("input"));
    });
});

// --- Modo 2: Recebimento com Árvore de Decisão ---
document.getElementById("recCodigo").addEventListener("input", (e) => {
    const cod = e.target.value.trim();
    const prod = produtosCache.find(p => p.codigo_barras === cod);
    const painel = document.getElementById("painelEsperadoRecebimento");

    if (prod) {
        painel.classList.remove("hidden");
        document.getElementById("recNomeProduto").textContent = prod.nome;
        document.getElementById("recQtdEsperada").textContent = prod.quantidade_esperada_recebimento;
        document.getElementById("recUltimoConferente").textContent = prod.ultimo_conferente || "—";
        document.getElementById("recQuantidade").value = prod.quantidade_esperada_recebimento;
    } else {
        painel.classList.add("hidden");
    }
});

document.getElementById("btnConfereSim").addEventListener("click", () => {
    recConfere = "sim";
    recDivergencia = null;
    document.getElementById("btnConfereSim").classList.add("selected");
    document.getElementById("btnConfereNao").classList.remove("selected");
    document.getElementById("blocoNaoConfere").classList.add("hidden");
    document.getElementById("blocoSobrando").classList.add("hidden");
});

document.getElementById("btnConfereNao").addEventListener("click", () => {
    recConfere = "nao";
    document.getElementById("btnConfereNao").classList.add("selected");
    document.getElementById("btnConfereSim").classList.remove("selected");
    document.getElementById("blocoNaoConfere").classList.remove("hidden");
});

document.getElementById("btnDivFaltando").addEventListener("click", () => {
    recDivergencia = "faltando";
    document.getElementById("btnDivFaltando").classList.add("selected");
    document.getElementById("btnDivSobrando").classList.remove("selected");
    document.getElementById("blocoSobrando").classList.add("hidden");
});

document.getElementById("btnDivSobrando").addEventListener("click", () => {
    recDivergencia = "sobrando";
    document.getElementById("btnDivSobrando").classList.add("selected");
    document.getElementById("btnDivFaltando").classList.remove("selected");
    document.getElementById("blocoSobrando").classList.remove("hidden");
});

document.getElementById("formRecebimento").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!recConfere) {
        mostrarToast("Selecione se a quantidade confere (Sim ou Não).");
        return;
    }
    if (recConfere === "nao" && !recDivergencia) {
        mostrarToast("Escolha se está Faltando ou Sobrando.");
        return;
    }

    const fotoInput = document.getElementById("fotoSobra");
    if (recDivergencia === "sobrando" && (!fotoInput.files || !fotoInput.files[0])) {
        mostrarToast("Anexe a foto para registrar sobra.");
        return;
    }

    const formData = new FormData();
    formData.append("codigo_barras", document.getElementById("recCodigo").value.trim());
    formData.append("confere", recConfere);
    if (recDivergencia) formData.append("tipo_divergencia", recDivergencia);
    formData.append("quantidade", document.getElementById("recQuantidade").value);
    formData.append("nome_produto", document.getElementById("nomeManualSobra").value.trim());
    formData.append("categoria_produto", document.getElementById("categoriaManualSobra").value.trim() || "Geral");
    formData.append("preco_produto", document.getElementById("precoManualSobra").value || "0");
    formData.append("posicao_codigo", document.getElementById("posicaoManualSobra").value.trim() || "A-02");

    if (fotoInput.files && fotoInput.files[0]) {
        formData.append("foto_sobra", fotoInput.files[0]);
    }

    const res = await fetch(`${API_URL}/recebimento/registrar`, {
        method: "POST",
        credentials: "include",
        body: formData
    });
    const data = await res.json();
    mostrarToast(data.mensagem || data.erro);

    if (res.ok) {
        e.target.reset();
        recConfere = null;
        recDivergencia = null;
        document.querySelectorAll("#formRecebimento .choice-btn").forEach(b => b.classList.remove("selected"));
        document.getElementById("blocoNaoConfere").classList.add("hidden");
        document.getElementById("blocoSobrando").classList.add("hidden");
        document.getElementById("painelEsperadoRecebimento").classList.add("hidden");
        await carregarAmbienteFuncionario();
    }
});

// --- Modo 3: Bipagem para Área de Venda com Checagem de Preço ---
document.getElementById("vendaCodigo").addEventListener("input", (e) => {
    const cod = e.target.value.trim();
    const prod = produtosCache.find(p => p.codigo_barras === cod);
    const painel = document.getElementById("painelVendaProduto");

    if (!painel) return;

    if (prod) {
        painel.classList.remove("hidden");
        document.getElementById("vendaNomeProduto").textContent = prod.nome;
        document.getElementById("vendaPrecoAtual").textContent = formatarMoeda(prod.preco);
        document.getElementById("vendaQtdEstoque").textContent = prod.quantidade_venda;
    } else {
        painel.classList.add("hidden");
    }
});

function selecionarStatusVenda(status) {
    vendaStatusPreco = status;
    vendaDirecaoPreco = null;

    document.querySelectorAll(".venda-preco-status").forEach(btn => btn.classList.remove("selected"));
    document.querySelector(`[data-venda-status="${status}"]`)?.classList.add("selected");

    const blocoDirecao = document.getElementById("blocoDirecaoPreco");
    if (blocoDirecao) blocoDirecao.classList.toggle("hidden", status === "correto");
}

function selecionarDirecaoPreco(direcao) {
    vendaDirecaoPreco = direcao;
    document.querySelectorAll(".venda-preco-direcao").forEach(btn => btn.classList.remove("selected"));
    document.querySelector(`[data-venda-direcao="${direcao}"]`)?.classList.add("selected");
}

document.querySelectorAll(".venda-preco-status").forEach(btn => {
    btn.addEventListener("click", () => selecionarStatusVenda(btn.dataset.vendaStatus));
});

document.querySelectorAll(".venda-preco-direcao").forEach(btn => {
    btn.addEventListener("click", () => selecionarDirecaoPreco(btn.dataset.vendaDirecao));
});

document.getElementById("formVenda").addEventListener("submit", async (e) => {
    e.preventEventDefault();

    if (!vendaStatusPreco) {
        mostrarToast("Selecione se o preço está correto ou irregular.");
        return;
    }

    if (vendaStatusPreco === "irregular" && !vendaDirecaoPreco) {
        mostrarToast("Informe se o preço está mais barato ou mais caro.");
        return;
    }

    const formData = new FormData();
    formData.append("codigo_barras", document.getElementById("vendaCodigo").value.trim());
    formData.append("status_preco", vendaStatusPreco);
    if (vendaDirecaoPreco) formData.append("direcao_preco", vendaDirecaoPreco);

    const res = await fetch(`${API_URL}/venda/registrar`, {
        method: "POST",
        credentials: "include",
        body: formData
    });
    const data = await res.json();
    mostrarToast(data.mensagem || data.erro);

    if (res.ok) {
        e.target.reset();
        vendaStatusPreco = null;
        vendaDirecaoPreco = null;
        document.querySelectorAll(".venda-preco-status, .venda-preco-direcao").forEach(btn => btn.classList.remove("selected"));
        document.getElementById("blocoDirecaoPreco")?.classList.add("hidden");
        document.getElementById("painelVendaProduto")?.classList.add("hidden");
        await carregarAmbienteFuncionario();
    }
});

iniciarApp();