// Estado da Cesta / Carrinho
let cart = [
    { id: 1, name: "Coxinha de frango", price: 6.50, qty: 2 },
    { id: 2, name: "Café coado", price: 5.00, qty: 1 }
];

// Elementos da Tela
document.addEventListener("DOMContentLoaded", () => {
    initTimeSlots();
    initFilters();
    renderCart();
});

// Seleção de Horários de Retirada
function initTimeSlots() {
    const timeButtons = document.querySelectorAll(".time-btn");
    timeButtons.forEach(button => {
        button.addEventListener("click", () => {
            timeButtons.forEach(btn => btn.classList.remove("active"));
            button.classList.add("active");
        });
    });
}

// Filtros do Cardápio
function initFilters() {
    const filterButtons = document.querySelectorAll(".filter-btn");
    filterButtons.forEach(button => {
        button.addEventListener("click", () => {
            filterButtons.forEach(btn => btn.classList.remove("active"));
            button.classList.add("active");
            // Aqui você pode adicionar a lógica para filtrar os produtos da grade se quiser
        });
    });
}

// Atualizar e Renderizar a Cesta de Compras
function renderCart() {
    const cartItemsContainer = document.querySelector(".cart-items");
    const summaryLines = document.querySelector(".cart-summary");
    
    if (!cartItemsContainer) return;

    cartItemsContainer.innerHTML = "";
    let subtotal = 0;

    cart.forEach((item, index) => {
        subtotal += item.price * item.qty;

        const itemElement = document.createElement("div");
        itemElement.classList.add("cart-item");
        itemElement.innerHTML = `
            <span>${item.name}</span>
            <div class="qty-control">
                <button onclick="changeQty(${index}, -1)">-</button>
                <span>${item.qty}</span>
                <button onclick="changeQty(${index}, 1)">+</button>
            </div>
        `;
        cartItemsContainer.appendChild(itemElement);
    });

    // Atualiza os totais
    const totalHTML = `
        <div class="summary-line"><span>Subtotal</span> <span>R$ ${subtotal.toFixed(2).replace('.', ',')}</span></div>
        <div class="summary-line"><span>Retirada</span> <span class="free">Grátis</span></div>
        <div class="summary-line total"><span>Total</span> <span>R$ ${subtotal.toFixed(2).replace('.', ',')}</span></div>
    `;
    
    // Insere antes do botão de checkout
    const checkoutBtn = document.querySelector(".checkout-btn");
    let summaryContainer = document.querySelector(".cart-summary");
    if (summaryContainer) {
        summaryContainer.innerHTML = totalHTML;
    }
}

// Alterar Quantidade de Itens
function changeQty(index, delta) {
    cart[index].qty += delta;
    if (cart[index].qty <= 0) {
        cart.splice(index, 1); // Remove o item se zerar
    }
    renderCart();
}

// Ação do Botão de Confirmar Pedido
document.addEventListener("click", (e) => {
    if (e.target.classList.contains("checkout-btn")) {
        if (cart.length === 0) {
            alert("Sua cesta está vazia, irmão!");
            return;
        }
        alert("Pedido confirmado com sucesso! A Ruth já vai separar no balcão.");
        // Aqui você pode disparar a chamada fetch para o back-end em Python salvar o pedido!
    }
});