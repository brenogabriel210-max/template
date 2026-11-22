<script>
    let modoCadastro = false;
    let filtroAtual = 'Todos';
    let profissionaisCache = [];
    let profSelecionadoId = null;
    let usuarioLogado = null;

    function abrirModal(id) { document.getElementById(id).style.display = 'flex'; }
    function fecharModal(id) { document.getElementById(id).style.display = 'none'; }

    function alternarModoAuth() {
        modoCadastro = !modoCadastro;
        document.getElementById('auth-title').innerText = modoCadastro ? 'Criar Cadastro' : 'Entrar na Conta';
        document.getElementById('grupo-nome').style.display = modoCadastro ? 'block' : 'none';
        document.getElementById('btn-toggle-auth').innerText = modoCadastro ? 'Já tem conta? Faça Login' : 'Não tem conta? Cadastre-se';
    }

    async function enviarAuth() {
        const nome = document.getElementById('auth-nome').value;
        const telefone = document.getElementById('auth-telefone').value;
        const senha = document.getElementById('auth-senha').value;

        const endpoint = modoCadastro ? '/api/cadastro' : '/api/login';
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nome, telefone, senha })
        });
        const data = await res.json();

        if (res.ok) {
            fecharModal('modal-auth');
            atualizarSistema();
        } else {
            alert(data.erro);
        }
    }

    async function logout() {
        await fetch('/api/logout', { method: 'POST' });
        atualizarSistema();
    }

    function filtrarProfissao(tipo, btn) {
        filtroAtual = tipo;
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderizarProfissionais();
    }

    function renderizarProfissionais() {
        const container = document.getElementById('lista-profissionais');
        container.innerHTML = '';

        const filtrados = filtroAtual === 'Todos'
            ? profissionaisCache
            : profissionaisCache.filter(p => p.especialidade === filtroAtual);

        filtrados.forEach(p => {
            container.innerHTML += `
                <div class="card-prof">
                    <img src="${p.foto_url}" alt="${p.nome}">
                    <div class="card-body">
                        <span class="tag-profissao">${p.especialidade}</span>
                        <h3>${p.nome}</h3>
                        <p>${p.descricao}</p>
                        <div class="fila-info">
                            <span>Na fila: <strong>${p.na_fila} pessoa(s)</strong></span>
                            <span>Espera: <strong>~${p.tempo_espera_total} min</strong></span>
                        </div>
                        <button class="btn btn-gold" style="width: 100%;" onclick="prepararEntradaFila(${p.id}, '${p.nome}')">
                            Entrar na Fila
                        </button>
                    </div>
                </div>
            `;
        });
    }

    function prepararEntradaFila(profId, profNome) {
        if (!usuarioLogado) {
            abrirModal('modal-auth');
            return;
        }
        profSelecionadoId = profId;
        document.getElementById('modal-prof-selecionado').innerText = Profissional: ${profNome};
        abrirModal('modal-servico');
    }

    async function confirmarEntradaFila() {
        const servico = document.getElementById('select-servico').value;
        const res = await fetch('/api/entrar_fila', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ profissional_id: profSelecionadoId, servico })
        });
        const data = await res.json();
        fecharModal('modal-servico');

        if (res.ok) {
            atualizarSistema();
        } else {
            alert(data.erro);
        }
    }

    async function sairDaFila() {
        if (!confirm('Tem certeza que deseja sair da fila?')) return;
        await fetch('/api/sair_fila', { method: 'POST' });
        atualizarSistema();
    }

    async function acaoAdmin(ticketId, acao) {
        await fetch('/api/profissional/acao', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticket_id: ticketId, acao })
        });
        atualizarSistema();
    }

    async function atualizarSistema() {
        const res = await fetch('/api/status_geral');
        const data = await res.json();

        // 1. Atualiza Header de Usuário
        usuarioLogado = data.usuario_logado;
        const authArea = document.getElementById('auth-area');
        if (usuarioLogado) {
            authArea.innerHTML = `
                <span style="margin-right: 12px; font-size: 0.9rem;">Olá, <strong>${usuarioLogado.nome}</strong></span>
                <button class="btn btn-outline" onclick="logout()">Sair</button>
            `;
        } else {
            authArea.innerHTML = <button class="btn btn-gold" onclick="abrirModal('modal-auth')">Entrar / Cadastrar</button>;
        }

        // 2. Atualiza Lista de Profissionais
        profissionaisCache = data.profissionais;
        renderizarProfissionais();

        // 3. Atualiza Ticket ao Vivo do Cliente
        const ticketBox = document.getElementById('meu-ticket-box');
        if (data.meu_ticket) {
            ticketBox.style.display = 'block';
            document.getElementById('ticket-prof-nome').innerText = ${data.meu_ticket.prof_nome} (${data.meu_ticket.especialidade});
            document.getElementById('ticket-servico').innerText = Serviço: ${data.meu_ticket.servico} | Status: ${data.meu_ticket.status.toUpperCase()};
            document.getElementById('ticket-frente').innerText = data.meu_ticket.pessoas_na_frente;
            document.getElementById('ticket-tempo').innerText = data.meu_ticket.status === 'atendendo'
                ? 'SUA VEZ!'
                : ${data.meu_ticket.tempo_estimado} min;
        } else {
            ticketBox.style.display = 'none';
        }

        // 4. Atualiza Painel do Profissional
        const adminList = document.getElementById('lista-fila-admin');
        if (data.fila_ativa.length === 0) {
            adminList.innerHTML = '<p style="color: var(--text-muted); font-size: 0.9rem;">Nenhum cliente na fila no momento.</p>';
        } else {
            adminList.innerHTML = data.fila_ativa.map(item => `
                <div class="fila-item-admin">
                    <div>
                        <strong>${item.cliente_nome}</strong> (${item.telefone}) — <span style="color: var(--gold);">${item.servico}</span><br>
                        <small style="color: var(--text-muted);">Profissional: ${item.prof_nome} | Status: <strong>${item.status.toUpperCase()}</strong></small>
                    </div>
                    <div style="display: flex; gap: 8px;">
                        ${item.status === 'aguardando' ? <button class="btn btn-gold" onclick="acaoAdmin(${item.id}, 'atendendo')">Chamar Cadeira</button> : ''}
                        <button class="btn btn-success" onclick="acaoAdmin(${item.id}, 'concluido')">Finalizar Corte</button>
                    </div>
                </div>
            `).join('');
        }
    }

    // Atualiza automaticamente em tempo real a cada 5 segundos
    atualizarSistema();
    setInterval(atualizarSistema, 5000);
</script>