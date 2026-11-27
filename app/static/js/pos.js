(function () {
  const CLP = new Intl.NumberFormat("es-CL");

  function formatMoney(value) {
    return `$${CLP.format(Math.round(value || 0))}`;
  }

  function escapeHtml(str) {
    return String(str || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  document.addEventListener("DOMContentLoaded", () => {
    const searchInput = document.getElementById("pos-search");
    const productsGrid = document.getElementById("pos-productos");
    const categoryTabsEl = document.getElementById("category-tabs");

    const cartItemsEl = document.getElementById("cart-items");
    const cartCountEl = document.getElementById("cart-count");
    const cartTotalEl = document.getElementById("cart-total");
    const ticketDateEl = document.getElementById("ticket-date");
    const payMethodsEl = document.getElementById("pay-methods");
    const efectivoBox = document.getElementById("efectivo-box");
    const fiadoBox = document.getElementById("fiado-box");
    const fiadoClienteSelect = document.getElementById("fiado-cliente");
    const fiadoCupoInfo = document.getElementById("fiado-cupo-info");
    const montoRecibidoInput = document.getElementById("monto-recibido");
    const vueltoValorEl = document.getElementById("vuelto-valor");
    const btnCobrar = document.getElementById("btn-cobrar");
    const btnUltimoTicket = document.getElementById("btn-ultimo-ticket");
    const btnUltimoTicketLabel = document.getElementById("btn-ultimo-ticket-label");
    const btnLimpiar = document.getElementById("btn-limpiar-carrito");

    const tabMeson = document.getElementById("tab-meson");
    const tabHistorial = document.getElementById("tab-historial");
    const panelMeson = document.getElementById("panel-meson");
    const panelHistorial = document.getElementById("panel-historial");
    const historialTbody = document.getElementById("historial-tbody");

    const cajaStatusText = document.getElementById("caja-status-text");
    const btnAbrirCaja = document.getElementById("btn-abrir-caja-banner");
    const modalCaja = document.getElementById("modal-abrir-caja");
    const formCaja = document.getElementById("form-abrir-caja");
    const fondoInicialInput = document.getElementById("fondo-inicial");

    const modalAnular = document.getElementById("modal-anular-venta");
    const anularMensaje = document.getElementById("anular-mensaje");
    const btnConfirmarAnular = document.getElementById("confirmar-anular");

    const modalCantidad = document.getElementById("modal-cantidad");
    const formCantidad = document.getElementById("form-cantidad");
    const cantProdNombre = document.getElementById("cant-prod-nombre");
    const cantProdMeta = document.getElementById("cant-prod-meta");
    const cantLabel = document.getElementById("cant-label");
    const cantInput = document.getElementById("cant-input");
    const cantPresets = document.getElementById("cant-presets");
    const cantSubtotal = document.getElementById("cant-subtotal");

    const modalAtajos = document.getElementById("modal-atajos");
    const btnAtajos = document.getElementById("btn-atajos");
    const btnFullscreen = document.getElementById("btn-fullscreen");
    const btnFullscreenLabel = document.getElementById("btn-fullscreen-label");
    const autoPrintToggle = document.getElementById("auto-print-toggle");
    const printFrame = document.getElementById("print-frame");
    const modalTicket = document.getElementById("modal-ticket");
    const ticketPreviewFrame = document.getElementById("ticket-preview-frame");
    const btnImprimirModalTicket = document.getElementById("btn-imprimir-modal-ticket");

    const AUTO_PRINT_KEY = "sb_auto_print";
    if (autoPrintToggle) {
      const savedAuto = localStorage.getItem(AUTO_PRINT_KEY);
      autoPrintToggle.checked = savedAuto === null ? true : savedAuto === "1";
      autoPrintToggle.addEventListener("change", () => {
        localStorage.setItem(AUTO_PRINT_KEY, autoPrintToggle.checked ? "1" : "0");
      });
    }

    let productos = [];
    let clientesFiado = [];
    let carrito = [];
    let categoriaActiva = "TODOS";
    let metodoPago = "EFECTIVO";
    let cajaAbierta = null;
    let ventaAAnular = null;
    let ultimoTicketId = null;
    let productoSeleccionado = null;
    let enviandoVenta = false;

    function imprimirTicketDirecto(ventaId) {
      if (!printFrame) return;
      printFrame.onload = () => {
        try {
          printFrame.contentWindow.focus();
          printFrame.contentWindow.print();
        } catch (_err) {
          window.StockBarrio.showToast("No se pudo abrir impresion automatica", "warn");
        }
      };
      printFrame.src = `/pos/ticket/${ventaId}?embed=1`;
    }

    function previsualizarTicket(ventaId) {
      if (!modalTicket || !ticketPreviewFrame) return;
      ticketPreviewFrame.src = `/pos/ticket/${ventaId}?embed=1`;
      modalTicket.classList.add("open");
    }

    function cerrarModalTicket() {
      if (!modalTicket) return;
      modalTicket.classList.remove("open");
      searchInput.focus();
    }

    function actualizarRelojTicket() {
      if (!ticketDateEl) return;
      const ahora = new Date();
      const fecha = ahora.toLocaleDateString("es-CL");
      const hora = ahora.toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" });
      ticketDateEl.textContent = `${fecha} · ${hora}`;
    }

    function actualizarEstadoCaja(caja) {
      cajaAbierta = caja;
      if (btnAbrirCaja) {
        btnAbrirCaja.style.display = caja ? "none" : "block";
      }
      if (cajaStatusText) {
        const partes = cajaStatusText.textContent.split("·");
        const nombreUsuario = partes.length > 1 ? partes[1].trim() : "";
        const etiquetaCaja = caja ? `Caja #${caja.id}` : "Caja sin abrir";
        cajaStatusText.textContent = nombreUsuario ? `${etiquetaCaja} · ${nombreUsuario}` : etiquetaCaja;
      }
      actualizarBotonCobrar();
    }

    function calcularTotal() {
      return carrito.reduce(
        (acc, item) => acc + Math.round(item.cantidad * item.precio_venta),
        0
      );
    }

    function actualizarVuelto() {
      const total = calcularTotal();
      if (metodoPago !== "EFECTIVO") {
        vueltoValorEl.textContent = "$0";
        return;
      }
      const recibido = Number(montoRecibidoInput.value || 0);
      const vuelto = recibido >= total && total > 0 ? recibido - total : 0;
      vueltoValorEl.textContent = formatMoney(vuelto);
    }

    function actualizarInfoFiado() {
      if (!fiadoCupoInfo || !fiadoClienteSelect) return;
      const clienteId = Number(fiadoClienteSelect.value || 0);
      const cliente = clientesFiado.find((c) => c.id === clienteId);
      const total = calcularTotal();

      if (!cliente) {
        fiadoCupoInfo.classList.remove("error");
        fiadoCupoInfo.textContent = clientesFiado.length
          ? "Selecciona un vecino para validar su cupo disponible."
          : "No hay clientes activos registrados en Fiados.";
        return;
      }

      if (total > cliente.cupo_disponible) {
        fiadoCupoInfo.classList.add("error");
        fiadoCupoInfo.textContent = `Excede cupo disponible (${formatMoney(cliente.cupo_disponible)}). Deuda actual: ${formatMoney(cliente.deuda_actual)}.`;
      } else {
        fiadoCupoInfo.classList.remove("error");
        fiadoCupoInfo.textContent = `Disponible: ${formatMoney(cliente.cupo_disponible)} · Deuda: ${formatMoney(cliente.deuda_actual)} / ${formatMoney(cliente.limite_credito)}`;
      }
    }

    function renderClientesFiado() {
      if (!fiadoClienteSelect) return;
      const prev = fiadoClienteSelect.value;
      fiadoClienteSelect.innerHTML = '<option value="">Seleccionar cliente...</option>';
      clientesFiado.forEach((c) => {
        const opt = document.createElement("option");
        opt.value = String(c.id);
        opt.textContent = `${c.nombre} (disp. ${formatMoney(c.cupo_disponible)})`;
        fiadoClienteSelect.appendChild(opt);
      });
      if (prev && clientesFiado.some((c) => String(c.id) === prev)) {
        fiadoClienteSelect.value = prev;
      }
      actualizarInfoFiado();
    }

    function actualizarBotonCobrar() {
      actualizarInfoFiado();
      const total = calcularTotal();
      const hayItems = carrito.length > 0 && total > 0;
      let fiadoInvalido = false;
      if (metodoPago === "FIADO") {
        const cliId = Number(fiadoClienteSelect ? fiadoClienteSelect.value : 0);
        const cli = clientesFiado.find((c) => c.id === cliId);
        fiadoInvalido = !cli || total > cli.cupo_disponible;
      }
      btnCobrar.disabled = !cajaAbierta || !hayItems || enviandoVenta || fiadoInvalido;
    }

    function renderCategorias() {
      const unicas = [];
      productos.forEach((p) => {
        const cat = p.categoria_nombre || "General";
        if (!unicas.includes(cat)) unicas.push(cat);
      });

      const botones = ['<button type="button" class="cat-tab' + (categoriaActiva === "TODOS" ? " active" : "") + '" data-cat="TODOS">Todos</button>'];
      unicas.forEach((cat) => {
        const active = categoriaActiva === cat ? " active" : "";
        botones.push(
          `<button type="button" class="cat-tab${active}" data-cat="${escapeHtml(cat)}">${escapeHtml(cat)}</button>`
        );
      });
      categoryTabsEl.innerHTML = botones.join("");
    }

    function badgeProducto(p) {
      if (p.estado_vencimiento === "VENCIDO") {
        return '<span class="tag-vencido">VENCIDO</span>';
      }
      if (p.estado_vencimiento === "POR_VENCER") {
        return '<span class="tag-por-vencer">POR VENCER</span>';
      }
      return "";
    }

    function filtrarProductos() {
      const q = (searchInput.value || "").trim().toLowerCase();
      return productos.filter((p) => {
        const cat = p.categoria_nombre || "General";
        if (categoriaActiva !== "TODOS" && cat !== categoriaActiva) return false;
        if (!q) return true;
        return (
          p.nombre.toLowerCase().includes(q) ||
          (p.codigo_barras && p.codigo_barras.toLowerCase().includes(q))
        );
      });
    }

    function renderProductos() {
      const lista = filtrarProductos();
      if (!lista.length) {
        productsGrid.innerHTML =
          '<div class="empty-box">No hay productos que coincidan con el filtro.</div>';
        return;
      }

      productsGrid.innerHTML = lista
        .map((p) => {
          const sinStock = p.stock_actual <= 0;
          const bloqueado = p.bloqueado_venta || sinStock;
          const unidadTxt = p.unidad === "KG" ? " (kg)" : "";
          const badge = badgeProducto(p);
          return `
            <button type="button" class="product-card ${bloqueado ? "blocked" : ""}" data-prod-id="${p.id}">
              <div class="product-head">
                <div class="product-title-row">
                  <span class="product-name">${escapeHtml(p.nombre)}${p.nombre.toLowerCase().includes("kg") ? "" : unidadTxt}</span>
                  ${badge}
                </div>
                <span class="product-stock">Stock: ${p.stock_actual}</span>
              </div>
              <div class="product-foot">
                <span class="product-price">${formatMoney(p.precio_venta)}</span>
              </div>
            </button>
          `;
        })
        .join("");
    }

    function disponibleParaAgregar(producto) {
      const enCarrito = carrito.find((i) => i.producto_id === producto.id);
      const cantCarrito = enCarrito ? enCarrito.cantidad : 0;
      return Math.round((producto.stock_actual - cantCarrito) * 1000) / 1000;
    }

    function actualizarSubtotalModal() {
      if (!productoSeleccionado) return;
      const cant = Number(cantInput.value || 0);
      const monto = cant > 0 ? Math.round(cant * productoSeleccionado.precio_venta) : 0;
      cantSubtotal.textContent = formatMoney(monto);
    }

    function abrirModalCantidad(producto) {
      if (!producto) return;
      if (producto.bloqueado_venta) {
        window.StockBarrio.showToast(`Producto vencido: ${producto.nombre}`, "error");
        return;
      }
      if (producto.stock_actual <= 0) {
        window.StockBarrio.showToast(`Sin stock disponible para ${producto.nombre}`, "warn");
        return;
      }
      const restante = disponibleParaAgregar(producto);
      if (restante <= 0) {
        window.StockBarrio.showToast(`Ya agregaste todo el stock de ${producto.nombre}`, "warn");
        return;
      }

      productoSeleccionado = producto;
      const esKg = producto.unidad === "KG";
      const step = esKg ? "0.1" : "1";
      const min = esKg ? "0.1" : "1";
      const inicial = Math.min(1, restante);

      cantProdNombre.textContent = producto.nombre;
      cantProdMeta.textContent = `${formatMoney(producto.precio_venta)} / ${producto.unidad} · Disponible: ${restante} ${producto.unidad}`;
      cantLabel.textContent = `Cantidad (${producto.unidad})`;

      cantInput.min = min;
      cantInput.step = step;
      cantInput.max = String(restante);
      cantInput.value = String(inicial);

      const opciones = esKg ? [0.25, 0.5, 1, 2] : [1, 2, 3, 5, 10];
      cantPresets.innerHTML = opciones
        .filter((val) => val <= restante)
        .map(
          (val) =>
            `<button type="button" class="qty-preset-btn" data-preset="${val}">${val} ${escapeHtml(producto.unidad)}</button>`
        )
        .join("");

      actualizarSubtotalModal();
      modalCantidad.classList.add("open");
      cantInput.focus();
      cantInput.select();
    }

    function cerrarModalCantidad() {
      productoSeleccionado = null;
      modalCantidad.classList.remove("open");
      searchInput.focus();
    }

    function confirmarCantidadModal(cantidadValor) {
      if (!productoSeleccionado) return;
      const cantidad = Math.round(Number(cantidadValor) * 1000) / 1000;
      if (!cantidad || cantidad <= 0) {
        window.StockBarrio.showToast("Ingresa una cantidad valida", "warn");
        cantInput.focus();
        return;
      }

      const restante = disponibleParaAgregar(productoSeleccionado);
      if (cantidad > restante) {
        window.StockBarrio.showToast(
          `Stock insuficiente (disponible: ${restante} ${productoSeleccionado.unidad})`,
          "warn"
        );
        cantInput.focus();
        cantInput.select();
        return;
      }

      const existente = carrito.find((i) => i.producto_id === productoSeleccionado.id);
      if (existente) {
        existente.cantidad = Math.round((existente.cantidad + cantidad) * 1000) / 1000;
      } else {
        carrito.push({
          producto_id: productoSeleccionado.id,
          nombre: productoSeleccionado.nombre,
          unidad: productoSeleccionado.unidad,
          precio_venta: productoSeleccionado.precio_venta,
          stock_actual: productoSeleccionado.stock_actual,
          cantidad,
        });
      }

      renderCarrito();
      searchInput.value = "";
      renderProductos();
      cerrarModalCantidad();
    }

    function renderCarrito() {
      const totalArticulos = carrito.reduce((acc, i) => acc + (i.unidad === "KG" ? 1 : i.cantidad), 0);
      cartCountEl.textContent = `Articulos (${Math.round(totalArticulos * 100) / 100})`;

      if (!carrito.length) {
        cartItemsEl.innerHTML =
          '<div class="ticket-empty">Escanea o selecciona productos para cobrar.</div>';
        cartTotalEl.textContent = "$0";
        actualizarVuelto();
        actualizarBotonCobrar();
        return;
      }

      cartItemsEl.innerHTML = carrito
        .map((item) => {
          const subtotal = Math.round(item.cantidad * item.precio_venta);
          const step = item.unidad === "KG" ? "0.1" : "1";
          return `
            <div class="ticket-row" data-item-id="${item.producto_id}">
              <div class="ticket-row-info">
                <div class="ticket-row-name">${escapeHtml(item.nombre)}</div>
                <div class="ticket-row-unit">${formatMoney(item.precio_venta)} c/u</div>
              </div>
              <div class="ticket-row-right">
                <div class="qty-ctrl">
                  <button type="button" class="qty-btn" data-qty-op="dec">-</button>
                  <input
                    type="number"
                    class="qty-input"
                    min="${step}"
                    step="${step}"
                    max="${item.stock_actual}"
                    value="${item.cantidad}"
                    data-qty-input
                  >
                  <button type="button" class="qty-btn" data-qty-op="inc">+</button>
                </div>
                <div class="ticket-row-sub">${formatMoney(subtotal)}</div>
              </div>
            </div>
          `;
        })
        .join("");

      cartTotalEl.textContent = formatMoney(calcularTotal());
      actualizarVuelto();
      actualizarBotonCobrar();
    }

    function setMetodoPago(metodo) {
      metodoPago = metodo;
      payMethodsEl.querySelectorAll(".pay-btn").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.method === metodo);
      });
      efectivoBox.style.display = metodo === "EFECTIVO" ? "grid" : "none";
      if (fiadoBox) {
        fiadoBox.style.display = metodo === "FIADO" ? "flex" : "none";
      }
      actualizarVuelto();
      actualizarBotonCobrar();
    }

    function cambiarTab(tab) {
      const esMeson = tab === "meson";
      tabMeson.classList.toggle("active", esMeson);
      tabHistorial.classList.toggle("active", !esMeson);
      panelMeson.style.display = esMeson ? "flex" : "none";
      panelHistorial.style.display = esMeson ? "none" : "flex";
      if (!esMeson) {
        cargarHistorial();
      }
    }

    async function cargarEstadoInicial() {
      try {
        const [caja, prods, clientes] = await Promise.all([
          window.StockBarrio.apiFetch("/api/v1/pos/caja-actual"),
          window.StockBarrio.apiFetch("/api/v1/pos/productos"),
          window.StockBarrio.apiFetch("/api/v1/fiados/clientes").catch(() => []),
        ]);
        actualizarEstadoCaja(caja);
        productos = prods;
        clientesFiado = clientes;
        renderCategorias();
        renderProductos();
        renderClientesFiado();
      } catch (err) {
        window.StockBarrio.showToast(err.message, "error");
      }
    }

    async function cargarHistorial() {
      try {
        const ventas = await window.StockBarrio.apiFetch("/api/v1/pos/ventas?solo_turno=true");
        if (!ventas.length) {
          historialTbody.innerHTML =
            '<tr><td colspan="8" style="text-align:center; color:var(--pos-muted); padding:24px;">Sin ventas registradas en este turno.</td></tr>';
          return;
        }
        historialTbody.innerHTML = ventas
          .map((v) => {
            const hora = new Date(v.creada_en).toLocaleTimeString("es-CL", {
              hour: "2-digit",
              minute: "2-digit",
            });
            const detalle = v.items
              .map((i) => `${i.cantidad}x ${i.producto_nombre}`)
              .join(", ");
            const anulada = v.estado === "ANULADA";
            const badgeEstado = anulada
              ? '<span class="badge-state badge-danger">Anulada</span>'
              : '<span class="badge-state badge-ok">Completada</span>';
            const accion = anulada
              ? `<button type="button" class="pos-btn-sec" data-ticket-id="${v.id}" style="padding:5px 9px; font-size:12px;">Ticket</button>`
              : `<div style="display:flex; gap:6px;">
                  <button type="button" class="pos-btn-sec" data-ticket-id="${v.id}" style="padding:5px 9px; font-size:12px;">Ticket</button>
                  <button type="button" class="pos-btn-danger" data-anular-id="${v.id}" data-anular-folio="${escapeHtml(v.folio)}" data-anular-total="${v.total}" style="padding:5px 10px; font-size:12px;">Anular</button>
                 </div>`;

            return `
              <tr>
                <td class="mono"><strong>${escapeHtml(v.folio)}</strong></td>
                <td class="mono" style="color:var(--pos-muted);">${hora}</td>
                <td>${escapeHtml(v.usuario_nombre)}</td>
                <td style="max-width:250px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${escapeHtml(detalle)}">${escapeHtml(detalle)}</td>
                <td><span class="badge-state badge-neutral">${escapeHtml(v.metodo_pago)}</span></td>
                <td class="mono"><strong>${formatMoney(v.total)}</strong></td>
                <td>${badgeEstado}</td>
                <td>${accion}</td>
              </tr>
            `;
          })
          .join("");
      } catch (err) {
        window.StockBarrio.showToast(err.message, "error");
      }
    }

    async function cobrarVenta() {
      if (enviandoVenta) return;
      if (!cajaAbierta) {
        window.StockBarrio.showToast("Debes abrir caja antes de cobrar", "warn");
        return;
      }
      if (!carrito.length) {
        window.StockBarrio.showToast("Agrega al menos un producto", "warn");
        return;
      }

      const total = calcularTotal();
      let montoRecibido = null;
      let clienteId = null;
      if (metodoPago === "EFECTIVO") {
        const valorRaw = montoRecibidoInput.value.trim();
        montoRecibido = valorRaw === "" ? total : Number(valorRaw);
        if (montoRecibido < total) {
          window.StockBarrio.showToast("El monto recibido es menor al total", "error");
          montoRecibidoInput.focus();
          return;
        }
      } else if (metodoPago === "FIADO") {
        clienteId = Number(fiadoClienteSelect ? fiadoClienteSelect.value : 0);
        if (!clienteId) {
          window.StockBarrio.showToast("Selecciona un cliente para vender fiado", "warn");
          if (fiadoClienteSelect) fiadoClienteSelect.focus();
          return;
        }
      }

      enviandoVenta = true;
      actualizarBotonCobrar();
      try {
        const venta = await window.StockBarrio.apiFetch("/api/v1/pos/ventas", {
          method: "POST",
          body: JSON.stringify({
            metodo_pago: metodoPago,
            monto_recibido: montoRecibido,
            cliente_id: clienteId,
            items: carrito.map((i) => ({
              producto_id: i.producto_id,
              cantidad: i.cantidad,
            })),
          }),
        });
        const msgVuelto =
          venta.metodo_pago === "EFECTIVO" && venta.vuelto > 0
            ? ` (Vuelto: ${formatMoney(venta.vuelto)})`
            : "";
        window.StockBarrio.showToast(`Venta ${venta.folio} registrada${msgVuelto}`, "ok");
        ultimoTicketId = venta.id;
        if (btnUltimoTicket && btnUltimoTicketLabel) {
          btnUltimoTicketLabel.textContent = `Ver ticket ${venta.folio}`;
          btnUltimoTicket.style.display = "inline-flex";
        }
        if (autoPrintToggle && autoPrintToggle.checked) {
          imprimirTicketDirecto(venta.id);
        }
        carrito = [];
        montoRecibidoInput.value = "";
        renderCarrito();
        await cargarEstadoInicial();
        searchInput.focus();
      } catch (err) {
        window.StockBarrio.showToast(err.message, "error");
      } finally {
        enviandoVenta = false;
        actualizarBotonCobrar();
      }
    }

    // Categorias
    categoryTabsEl.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-cat]");
      if (!btn) return;
      categoriaActiva = btn.dataset.cat;
      cambiarTab("meson");
      renderCategorias();
      renderProductos();
    });

    // Pantalla completa
    function aplicarEstadoFullscreen(activo) {
      document.body.classList.toggle("pos-fullscreen", activo);
      if (btnFullscreenLabel) {
        btnFullscreenLabel.textContent = activo ? "Salir pantalla" : "Pantalla completa";
      }
      const iconEl = btnFullscreen ? btnFullscreen.querySelector("svg, i") : null;
      if (iconEl) {
        iconEl.setAttribute("data-lucide", activo ? "minimize-2" : "maximize-2");
        if (window.lucide) window.lucide.createIcons();
      }
    }

    function sincronizarFullscreenUI() {
      aplicarEstadoFullscreen(Boolean(document.fullscreenElement));
    }

    if (btnFullscreen) {
      btnFullscreen.addEventListener("click", async () => {
        try {
          if (!document.fullscreenElement && !document.body.classList.contains("pos-fullscreen")) {
            await document.documentElement.requestFullscreen();
          } else if (document.fullscreenElement) {
            await document.exitFullscreen();
          } else {
            aplicarEstadoFullscreen(false);
          }
        } catch (_err) {
          const nuevoEstado = !document.body.classList.contains("pos-fullscreen");
          aplicarEstadoFullscreen(nuevoEstado);
          window.StockBarrio.showToast("Usa F11 para pantalla completa", "warn");
        }
      });
    }
    document.addEventListener("fullscreenchange", sincronizarFullscreenUI);

    // Buscador y lector USB
    searchInput.addEventListener("input", renderProductos);
    searchInput.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      const q = searchInput.value.trim().toLowerCase();
      if (!q) return;
      const exacto = productos.find(
        (p) => p.codigo_barras && p.codigo_barras.toLowerCase() === q
      );
      if (exacto) {
        abrirModalCantidad(exacto);
        return;
      }
      const filtrados = filtrarProductos();
      if (filtrados.length === 1) {
        abrirModalCantidad(filtrados[0]);
      }
    });

    productsGrid.addEventListener("click", (e) => {
      const card = e.target.closest("[data-prod-id]");
      if (!card) return;
      const prod = productos.find((p) => p.id === Number(card.dataset.prodId));
      abrirModalCantidad(prod);
    });

    // Modal cantidad
    cantInput.addEventListener("input", actualizarSubtotalModal);
    cantPresets.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-preset]");
      if (!btn) return;
      cantInput.value = btn.dataset.preset;
      actualizarSubtotalModal();
      confirmarCantidadModal(btn.dataset.preset);
    });
    formCantidad.addEventListener("submit", (e) => {
      e.preventDefault();
      confirmarCantidadModal(cantInput.value);
    });
    document.getElementById("cerrar-modal-cantidad").addEventListener("click", cerrarModalCantidad);
    document.getElementById("cancelar-modal-cantidad").addEventListener("click", cerrarModalCantidad);
    modalCantidad.addEventListener("click", (e) => {
      if (e.target === modalCantidad) cerrarModalCantidad();
    });

    // Carrito inline
    cartItemsEl.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-qty-op]");
      if (!btn) return;
      const row = btn.closest("[data-item-id]");
      const item = carrito.find((i) => i.producto_id === Number(row.dataset.itemId));
      if (!item) return;

      const paso = item.unidad === "KG" ? 0.5 : 1;
      if (btn.dataset.qtyOp === "inc") {
        const next = Math.round((item.cantidad + paso) * 1000) / 1000;
        if (next > item.stock_actual) {
          window.StockBarrio.showToast(`Stock maximo alcanzado (${item.stock_actual})`, "warn");
          return;
        }
        item.cantidad = next;
      } else {
        const next = Math.round((item.cantidad - paso) * 1000) / 1000;
        if (next <= 0) {
          carrito = carrito.filter((i) => i.producto_id !== item.producto_id);
        } else {
          item.cantidad = next;
        }
      }
      renderCarrito();
    });

    cartItemsEl.addEventListener("change", (e) => {
      const input = e.target.closest("[data-qty-input]");
      if (!input) return;
      const row = input.closest("[data-item-id]");
      const item = carrito.find((i) => i.producto_id === Number(row.dataset.itemId));
      if (!item) return;

      const val = Number(input.value);
      if (!val || val <= 0) {
        carrito = carrito.filter((i) => i.producto_id !== item.producto_id);
      } else if (val > item.stock_actual) {
        window.StockBarrio.showToast(`Stock insuficiente (max: ${item.stock_actual})`, "warn");
        item.cantidad = item.stock_actual;
      } else {
        item.cantidad = val;
      }
      renderCarrito();
    });

    payMethodsEl.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-method]");
      if (btn) setMetodoPago(btn.dataset.method);
    });

    if (fiadoClienteSelect) {
      fiadoClienteSelect.addEventListener("change", actualizarBotonCobrar);
    }

    montoRecibidoInput.addEventListener("input", actualizarVuelto);
    montoRecibidoInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        if (!btnCobrar.disabled) cobrarVenta();
      }
    });

    btnCobrar.addEventListener("click", cobrarVenta);
    if (btnUltimoTicket) {
      btnUltimoTicket.addEventListener("click", () => {
        if (ultimoTicketId) previsualizarTicket(ultimoTicketId);
      });
    }
    if (btnImprimirModalTicket) {
      btnImprimirModalTicket.addEventListener("click", () => {
        if (ticketPreviewFrame && ticketPreviewFrame.contentWindow) {
          ticketPreviewFrame.contentWindow.focus();
          ticketPreviewFrame.contentWindow.print();
        }
      });
    }
    document.getElementById("cerrar-modal-ticket").addEventListener("click", cerrarModalTicket);
    document.getElementById("cancelar-modal-ticket").addEventListener("click", cerrarModalTicket);
    modalTicket.addEventListener("click", (e) => {
      if (e.target === modalTicket) cerrarModalTicket();
    });
    btnLimpiar.addEventListener("click", () => {
      carrito = [];
      montoRecibidoInput.value = "";
      renderCarrito();
      searchInput.focus();
    });

    // Pestanas rail
    tabMeson.addEventListener("click", () => cambiarTab("meson"));
    tabHistorial.addEventListener("click", () => cambiarTab("historial"));
    document.getElementById("btn-volver-meson").addEventListener("click", () => cambiarTab("meson"));
    document.getElementById("btn-refrescar-historial").addEventListener("click", cargarHistorial);

    // Modal atajos
    function abrirModalAtajos() { modalAtajos.classList.add("open"); }
    function cerrarModalAtajos() {
      modalAtajos.classList.remove("open");
      searchInput.focus();
    }
    btnAtajos.addEventListener("click", abrirModalAtajos);
    document.getElementById("cerrar-modal-atajos").addEventListener("click", cerrarModalAtajos);
    document.getElementById("aceptar-modal-atajos").addEventListener("click", cerrarModalAtajos);
    modalAtajos.addEventListener("click", (e) => {
      if (e.target === modalAtajos) cerrarModalAtajos();
    });

    // Modal abrir caja
    function abrirModalCaja() {
      fondoInicialInput.value = "0";
      modalCaja.classList.add("open");
      fondoInicialInput.focus();
      fondoInicialInput.select();
    }
    function cerrarModalCaja() {
      modalCaja.classList.remove("open");
      searchInput.focus();
    }

    btnAbrirCaja.addEventListener("click", abrirModalCaja);
    document.getElementById("cerrar-modal-caja").addEventListener("click", cerrarModalCaja);
    document.getElementById("cancelar-modal-caja").addEventListener("click", cerrarModalCaja);
    modalCaja.addEventListener("click", (e) => { if (e.target === modalCaja) cerrarModalCaja(); });

    formCaja.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const caja = await window.StockBarrio.apiFetch("/api/v1/pos/caja/abrir", {
          method: "POST",
          body: JSON.stringify({ fondo_inicial: Number(fondoInicialInput.value || 0) }),
        });
        actualizarEstadoCaja(caja);
        cerrarModalCaja();
        window.StockBarrio.showToast("Caja abierta correctamente", "ok");
        searchInput.focus();
      } catch (err) {
        window.StockBarrio.showToast(err.message, "error");
      }
    });

    // Modal anular venta
    function cerrarModalAnular() {
      ventaAAnular = null;
      modalAnular.classList.remove("open");
    }

    historialTbody.addEventListener("click", (e) => {
      const ticketBtn = e.target.closest("[data-ticket-id]");
      if (ticketBtn) {
        previsualizarTicket(Number(ticketBtn.dataset.ticketId));
        return;
      }
      const btn = e.target.closest("[data-anular-id]");
      if (!btn) return;
      ventaAAnular = {
        id: Number(btn.dataset.anularId),
        folio: btn.dataset.anularFolio,
        total: Number(btn.dataset.anularTotal),
      };
      anularMensaje.textContent = `¿Confirmas anular la venta ${ventaAAnular.folio} por ${formatMoney(ventaAAnular.total)}? Se repondra el stock.`;
      modalAnular.classList.add("open");
    });

    document.getElementById("cerrar-modal-anular").addEventListener("click", cerrarModalAnular);
    document.getElementById("cancelar-modal-anular").addEventListener("click", cerrarModalAnular);
    modalAnular.addEventListener("click", (e) => { if (e.target === modalAnular) cerrarModalAnular(); });

    btnConfirmarAnular.addEventListener("click", async () => {
      if (!ventaAAnular) return;
      try {
        await window.StockBarrio.apiFetch(`/api/v1/pos/ventas/${ventaAAnular.id}/anular`, {
          method: "POST",
        });
        window.StockBarrio.showToast(`Venta ${ventaAAnular.folio} anulada`, "ok");
        cerrarModalAnular();
        await Promise.all([cargarHistorial(), cargarEstadoInicial()]);
      } catch (err) {
        window.StockBarrio.showToast(err.message, "error");
      }
    });

    // Atajos globales
    document.addEventListener("keydown", (e) => {
      if (e.key === "F1") {
        e.preventDefault();
        if (modalAtajos.classList.contains("open")) {
          cerrarModalAtajos();
        } else {
          abrirModalAtajos();
        }
        return;
      }

      if (e.key === "Escape") {
        if (modalTicket && modalTicket.classList.contains("open")) { cerrarModalTicket(); return; }
        if (modalCantidad.classList.contains("open")) { cerrarModalCantidad(); return; }
        if (modalAtajos.classList.contains("open")) { cerrarModalAtajos(); return; }
        if (modalCaja.classList.contains("open")) { cerrarModalCaja(); return; }
        if (modalAnular.classList.contains("open")) { cerrarModalAnular(); return; }
        if (searchInput.value) {
          searchInput.value = "";
          renderProductos();
          return;
        }
        if (carrito.length) {
          carrito = [];
          montoRecibidoInput.value = "";
          renderCarrito();
          searchInput.focus();
        }
        return;
      }

      const algunModalAbierto =
        (modalTicket && modalTicket.classList.contains("open")) ||
        modalCantidad.classList.contains("open") ||
        modalAtajos.classList.contains("open") ||
        modalCaja.classList.contains("open") ||
        modalAnular.classList.contains("open");
      if (algunModalAbierto) return;

      const tag = document.activeElement ? document.activeElement.tagName : "";
      const escribiendo = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";

      if (e.key === "F2" || (!escribiendo && e.key === "/")) {
        e.preventDefault();
        cambiarTab("meson");
        searchInput.focus();
        searchInput.select();
        return;
      }

      if (e.key === "F9" || (e.ctrlKey && e.key === "Enter")) {
        e.preventDefault();
        if (panelMeson.style.display !== "none" && !btnCobrar.disabled) {
          cobrarVenta();
        }
        return;
      }

      if (e.key === "F8" || (e.altKey && e.key.toLowerCase() === "e")) {
        e.preventDefault();
        if (panelMeson.style.display !== "none" && metodoPago === "EFECTIVO") {
          montoRecibidoInput.focus();
          montoRecibidoInput.select();
        }
        return;
      }

      if ((e.altKey && ["1", "2", "3", "4"].includes(e.key)) || (!escribiendo && ["1", "2", "3", "4"].includes(e.key))) {
        if (panelMeson.style.display !== "none") {
          e.preventDefault();
          if (e.key === "1") setMetodoPago("EFECTIVO");
          if (e.key === "2") setMetodoPago("DEBITO");
          if (e.key === "3") setMetodoPago("TRANSFERENCIA");
          if (e.key === "4") setMetodoPago("FIADO");
        }
      }
    });

    actualizarRelojTicket();
    setInterval(actualizarRelojTicket, 30000);
    cargarEstadoInicial();
    searchInput.focus();
  });
})();
