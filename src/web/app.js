/**
 * SECOP Monitor - Frontend
 */

// ==========================================================================
// 0. Sesion y permisos
// ==========================================================================
// Espejo del mapa de permisos del backend (src/web_server.py). El render usa
// esto para no mostrar lo prohibido; la decision que vale es siempre la del
// servidor, que rechaza la peticion si el rol no autoriza.
let sesion = null; // { usuario: {...}, permisos: [...] }

/** Unico lugar donde se resuelve un permiso en el frontend. */
function puede(accion) {
    return Boolean(sesion && sesion.permisos.includes(accion));
}

function esAdmin() {
    return Boolean(sesion && sesion.usuario.rol === 'admin');
}

document.addEventListener('DOMContentLoaded', () => {
    initAcceso();
    restaurarSesion();
});

/** Al cargar: si ya hay sesion en el navegador, entra directo. */
async function restaurarSesion() {
    try {
        const resp = await fetch('/api/auth/me');
        if (resp.ok) {
            sesion = await resp.json();
            entrarALaApp();
            return;
        }
    } catch (err) {
        console.warn('No se pudo consultar la sesion:', err);
    }
    mostrarAcceso();
}

function mostrarAcceso() {
    document.getElementById('login-screen').hidden = false;
    document.getElementById('app-shell').hidden = true;
}

function initAcceso() {
    const btnLogin = document.getElementById('btn-login');
    const btnLogout = document.getElementById('btn-logout');

    if (btnLogin) {
        btnLogin.addEventListener('click', iniciarSesion);
    }
    if (btnLogout) {
        btnLogout.addEventListener('click', cerrarSesion);
    }
}

async function iniciarSesion() {
    const btnLogin = document.getElementById('btn-login');
    const error = document.getElementById('login-error');
    const seleccion = document.querySelector('input[name="rol-acceso"]:checked');

    error.hidden = true;
    btnLogin.disabled = true;
    btnLogin.textContent = 'Entrando...';

    try {
        const resp = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rol: seleccion ? seleccion.value : 'usuario' })
        });
        const data = await resp.json();

        if (!resp.ok) {
            error.textContent = data.error || 'No se pudo iniciar la sesion.';
            error.hidden = false;
            return;
        }

        sesion = data;
        entrarALaApp();
    } catch (err) {
        error.textContent = 'No hay conexion con el servidor. Levanta src/web_server.py e intenta de nuevo.';
        error.hidden = false;
    } finally {
        btnLogin.disabled = false;
        btnLogin.textContent = 'Entrar al monitor';
    }
}

async function cerrarSesion() {
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
    } catch (err) {
        console.warn('Fallo al cerrar sesion en el servidor:', err);
    }
    sesion = null;
    window.location.reload();
}

/** Arranca la aplicacion con los modulos que el rol autoriza. */
function entrarALaApp() {
    document.getElementById('login-screen').hidden = true;
    document.getElementById('app-shell').hidden = false;

    pintarIdentidad();
    aplicarModoSoloLectura();
    renderizarNavegacion();

    initModal();
    cargarMetricas();
    if (puede('ver_monitoreo')) initLiveSECOP();
    if (puede('editar_configuracion')) initConfigEditor();
    if (puede('ver_notificaciones')) initNotificaciones();
    if (puede('editar_metricas')) initManualSync();
    if (puede('gestionar_usuarios')) initGestionUsuarios();
}

/**
 * Saca del DOM los controles de escritura cuando el rol no los autoriza.
 * No basta con ocultarlos: un control oculto sigue siendo pulsable desde el
 * inspector. Aqui se elimina, y ademas el backend rechaza la peticion.
 */
function aplicarModoSoloLectura() {
    if (puede('editar_metricas')) return;

    const sync = document.getElementById('btn-run-manual-sync');
    if (sync) sync.remove();

    const panel = document.getElementById('tab-dashboard');
    if (panel) {
        panel.classList.add('is-readonly');
        const banner = panel.querySelector('.section-banner .banner-text');
        if (banner) {
            const aviso = document.createElement('span');
            aviso.className = 'chip-solo-lectura';
            aviso.textContent = 'Solo lectura';
            banner.appendChild(aviso);
        }
    }
}

function pintarIdentidad() {
    if (!sesion) return;
    const nombre = document.getElementById('session-user-name');
    const chip = document.getElementById('session-user-role');
    if (nombre) nombre.textContent = sesion.usuario.nombre;
    if (chip) {
        chip.textContent = esAdmin() ? 'Administrador' : 'Usuario';
        chip.classList.toggle('is-admin', esAdmin());
    }
}

// ==========================================================================
// 1. Navegacion condicionada por rol
// ==========================================================================
// Cada modulo declara el permiso que exige. El nav se construye desde aqui:
// lo que el rol no autoriza no se pinta y su seccion se saca del DOM, para que
// no quede accesible desempolvando una clase CSS desde el inspector.
const MODULOS = [
    { id: 'dashboard', etiqueta: 'Panel de Métricas', icono: '📊', permiso: 'ver_metricas' },
    { id: 'architecture', etiqueta: '¿Cómo Funciona por Dentro?', icono: '🧠', permiso: 'ver_arquitectura' },
    { id: 'secop-live', etiqueta: 'Monitoreo en Vivo (SECOP II)', icono: '🌐', permiso: 'ver_monitoreo' },
    { id: 'config', etiqueta: 'Configuración del Cliente', icono: '⚙️', permiso: 'editar_configuracion' },
    { id: 'users', etiqueta: 'Gestión de Usuarios', icono: '👥', permiso: 'gestionar_usuarios' }
];

function modulosAutorizados() {
    return MODULOS.filter(m => puede(m.permiso));
}

function renderizarNavegacion() {
    const contenedor = document.getElementById('tabs-container');
    const autorizados = modulosAutorizados();

    // Saca del DOM las secciones que el rol no puede ver.
    MODULOS.forEach(m => {
        if (!puede(m.permiso)) {
            const seccion = document.getElementById(`tab-${m.id}`);
            if (seccion) seccion.remove();
        }
    });

    contenedor.innerHTML = autorizados.map(m => `
        <button class="nav-tab" data-tab="${m.id}">
            <span class="tab-icon">${m.icono}</span> ${escapeHtml(m.etiqueta)}
        </button>
    `).join('');

    contenedor.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => abrirModulo(tab.getAttribute('data-tab')));
    });

    const volver = document.getElementById('btn-volver-inicio');
    if (volver) {
        volver.addEventListener('click', () => {
            const primero = modulosAutorizados()[0];
            if (primero) abrirModulo(primero.id);
        });
    }

    if (autorizados.length > 0) {
        abrirModulo(autorizados[0].id);
    }
}

/** Unica puerta de entrada a un modulo: comprueba el permiso antes de mostrarlo. */
function abrirModulo(id) {
    const modulo = MODULOS.find(m => m.id === id);

    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));

    if (!modulo || !puede(modulo.permiso)) {
        mostrarAccesoDenegado(modulo ? modulo.etiqueta : id);
        return;
    }

    const seccion = document.getElementById(`tab-${id}`);
    if (seccion) seccion.classList.add('active');

    const tab = document.querySelector(`.nav-tab[data-tab="${id}"]`);
    if (tab) tab.classList.add('active');
}

/** Vista de acceso denegado. Tambien la usan los 403 que devuelve el backend. */
function mostrarAccesoDenegado(queModulo) {
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    const denegado = document.getElementById('tab-denegado');
    if (!denegado) return;

    const detalle = document.getElementById('denegado-detalle');
    if (detalle && queModulo) {
        detalle.textContent = `El módulo "${queModulo}" solo está disponible para administradores. `
            + 'Tu sesión es de rol usuario.';
    }
    denegado.classList.add('active');
}

// Global active client config state
let clientConfig = {
    name: "Cliente Textil Caribe",
    email: "cliente@email.com",
    departments: ["Atlantico", "Bolivar", "Magdalena", "Cordoba", "Sucre", "La Guajira", "Cesar"],
    keywords: ["uniforme", "ropa deportiva", "vestuario", "calzado", "dotacion", "textil"],
    unspsc_codes: ["V1.53102700", "V1.53102710"],
    certification_keywords: ["mujer lider", "equidad de genero", "pyme"],
    modalidad_keywords: ["minima cuantia"]
};

let fetchedProcesses = [];

// Text Normalizer (replicates FilterEngine logic in JS)
function normalizeText(text) {
    if (!text) return '';
    return text.normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .trim();
}

// FilterEngine Match Evaluator
function evaluateProcessMatch(process, config) {
    const depts = config.departments.map(d => normalizeText(d));
    const kws = config.keywords.map(k => normalizeText(k));
    const certKws = config.certification_keywords.map(k => normalizeText(k));
    const modKws = config.modalidad_keywords.map(k => normalizeText(k));

    const deptNorm = normalizeText(process.department);
    const modNorm = normalizeText(process.modality);
    const nameNorm = normalizeText(process.name);
    const descNorm = normalizeText(process.description);

    const matchesDept = depts.includes(deptNorm);
    const matchesModality = modKws.some(kw => modNorm.includes(kw));

    let matchedKeyword = null;
    let matchedUnspsc = null;

    if (config.unspsc_codes.includes(process.unspsc_code)) {
        matchedUnspsc = process.unspsc_code;
    }

    for (let kw of kws) {
        if (nameNorm.includes(kw) || descNorm.includes(kw)) {
            matchedKeyword = kw;
            break;
        }
    }

    if (!matchedKeyword && !matchedUnspsc) {
        for (let kw of certKws) {
            if (nameNorm.includes(kw) || descNorm.includes(kw)) {
                matchedKeyword = `cert:${kw}`;
                break;
            }
        }
    }

    const isMatch = matchesDept && matchesModality && (matchedKeyword !== null || matchedUnspsc !== null);

    // Certification detection
    const fullText = `${nameNorm} ${descNorm}`;
    const certs = {
        favorece_mujer_lider: ['mujer lider', 'empresa de mujeres'].some(k => fullText.includes(k)),
        favorece_pyme: ['pyme', 'pequeña empresa', 'microempresa'].some(k => fullText.includes(k)),
        requiere_equidad_genero: ['equidad de genero', 'genero'].some(k => fullText.includes(k))
    };

    return {
        isMatch,
        matchesDept,
        matchesModality,
        matchedKeyword,
        matchedUnspsc,
        certifications: certs
    };
}

// ==========================================================================
// 2. Live SECOP II Explorador
// ==========================================================================
function initLiveSECOP() {
    const btnRefresh = document.getElementById('btn-refresh-live');
    const searchInput = document.getElementById('live-search-input');
    const deptSelect = document.getElementById('filter-dept-select');
    const matchSelect = document.getElementById('filter-match-only');

    btnRefresh.addEventListener('click', loadLiveSecopData);
    searchInput.addEventListener('input', renderTable);
    deptSelect.addEventListener('change', renderTable);
    matchSelect.addEventListener('change', renderTable);

    loadLiveSecopData();
}

async function loadLiveSecopData() {
    const tableBody = document.getElementById('secop-table-body');
    tableBody.innerHTML = `<tr><td colspan="7" class="tabla-aviso">⏳ Consultando procesos en SECOP II...</td></tr>`;

    try {
        // Solo a traves del backend. Antes habia un fallback que consultaba
        // datos.gov.co directamente desde el navegador cuando la API fallaba:
        // eso convertia un 403 del servidor en datos igualmente servidos, es
        // decir, saltaba el control de permisos. El 403 ahora se respeta.
        const resp = await fetch('/api/secop/live');

        if (resp.status === 403 || resp.status === 401) {
            mostrarAccesoDenegado('Monitoreo en Vivo (SECOP II)');
            return;
        }
        if (!resp.ok) {
            tableBody.innerHTML = `<tr><td colspan="7" class="tabla-aviso">
                No se pudo consultar SECOP II. Reintenta con "Consultar API SECOP II".</td></tr>`;
            return;
        }

        const data = await resp.json();

        // Process data through filter engine logic
        fetchedProcesses = data.map(p => {
            const evalRes = evaluateProcessMatch(p, clientConfig);
            return {
                ...p,
                is_matched: evalRes.isMatch,
                certifications: evalRes.certifications,
                evalDetails: evalRes
            };
        });

        updateKpis();
        renderTable();

    } catch (err) {
        console.error('Error fetching SECOP data:', err);
        // Display sample data on error
        fetchedProcesses = generateMockProcesses();
        updateKpis();
        renderTable();
    }
}

function updateKpis() {
    const total = fetchedProcesses.length;
    const matched = fetchedProcesses.filter(p => p.is_matched).length;
    const advantages = fetchedProcesses.filter(p => Object.values(p.certifications).some(v => v)).length;

    pintarKpis({
        analizados: total,
        coincidencias: matched,
        notificados: matched,
        con_ventaja: advantages
    });
}

function pintarKpis(m) {
    const asignar = (id, valor) => {
        const el = document.getElementById(id);
        if (el) el.textContent = Number(valor).toLocaleString('es-CO');
    };
    asignar('kpi-analyzed', m.analizados);
    asignar('kpi-matched', m.coincidencias);
    asignar('kpi-notified', m.notificados);
    asignar('kpi-advantages', m.con_ventaja);
}

/**
 * Carga los KPIs agregados del panel.
 * El rol usuario no puede pedir la lista de procesos (/api/secop/live exige
 * ver_monitoreo), pero si los conteos: para eso existe /api/metrics.
 */
async function cargarMetricas() {
    const panel = document.getElementById('tab-dashboard');
    if (!panel) return;

    try {
        const resp = await fetch('/api/metrics');
        if (!resp.ok) {
            marcarMetricasNoDisponibles();
            return;
        }
        pintarKpis(await resp.json());
    } catch (err) {
        marcarMetricasNoDisponibles();
    }
}

function marcarMetricasNoDisponibles() {
    ['kpi-analyzed', 'kpi-matched', 'kpi-notified', 'kpi-advantages'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '—';
    });
}

function renderTable() {
    const tableBody = document.getElementById('secop-table-body');
    const query = normalizeText(document.getElementById('live-search-input').value);
    const deptFilter = document.getElementById('filter-dept-select').value;
    const matchOnlyFilter = document.getElementById('filter-match-only').value;

    const filtered = fetchedProcesses.filter(p => {
        const matchesQuery = !query || 
            normalizeText(p.name).includes(query) || 
            normalizeText(p.entity_name).includes(query) || 
            normalizeText(p.id).includes(query);

        const matchesDept = !deptFilter || p.department === deptFilter;
        const matchesMatchOnly = matchOnlyFilter !== 'matched_only' || p.is_matched;

        return matchesQuery && matchesDept && matchesMatchOnly;
    });

    if (filtered.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="7" class="tabla-aviso">No se encontraron procesos con los filtros aplicados.</td></tr>`;
        return;
    }

    tableBody.innerHTML = filtered.map(p => {
        const priceFormatted = p.base_price ? `$${Number(p.base_price).toLocaleString('es-CO')} COP` : 'No definido';
        
        let badgesHtml = `<span class="badge-status badge-minima">${p.modality}</span>`;
        if (p.certifications.favorece_mujer_lider) {
            badgesHtml += `<span class="badge-status" style="background:#FCE7F3;color:#BE185D;">👩‍💼 Mujer Líder</span>`;
        }
        if (p.certifications.favorece_pyme) {
            badgesHtml += `<span class="badge-status" style="background:#D1FAE5;color:#065F46;">🌿 PYME</span>`;
        }
        if (p.certifications.requiere_equidad_genero) {
            badgesHtml += `<span class="badge-status" style="background:#EDE9FE;color:#6B21A8;">⚖️ Equidad</span>`;
        }

        const matchTag = p.is_matched 
            ? `<span style="color:#059669;font-weight:700;">🟢 Coincide</span>` 
            : `<span style="color:#94A3B8;">⚪ No Coincide</span>`;

        return `
            <tr>
                <td class="proc-id">${p.id}</td>
                <td>
                    <div class="entity-name">${escapeHtml(p.entity_name)}</div>
                    <div class="location-tag">📍 ${escapeHtml(p.city)}, ${escapeHtml(p.department)}</div>
                </td>
                <td style="max-width:320px;">
                    <div style="font-weight:600;color:#00324D;">${escapeHtml(p.name)}</div>
                    <div style="font-size:11px;color:#64748B;margin-top:2px;">${matchTag}</div>
                </td>
                <td class="price-text">${priceFormatted}</td>
                <td>${escapeHtml(p.modality)}</td>
                <td>${badgesHtml}</td>
                <td>
                    <button class="btn-view-detail" data-id="${p.id}">Ver Detalle</button>
                </td>
            </tr>
        `;
    }).join('');

    // Attach click listeners to view detail buttons
    document.querySelectorAll('.btn-view-detail').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const procId = e.target.getAttribute('data-id');
            const proc = fetchedProcesses.find(p => p.id === procId);
            if (proc) openModal(proc);
        });
    });
}

// ==========================================================================
// 4. Config Editor
// ==========================================================================
function initConfigEditor() {
    const btnSave = document.getElementById('btn-save-config');
    if (btnSave) {
        btnSave.addEventListener('click', () => {
            clientConfig.name = document.getElementById('cfg-name').value;
            clientConfig.email = document.getElementById('cfg-email').value;
            clientConfig.departments = document.getElementById('cfg-departments').value.split(',').map(s => s.trim());
            clientConfig.keywords = document.getElementById('cfg-keywords').value.split(',').map(s => s.trim());
            clientConfig.unspsc_codes = document.getElementById('cfg-unspsc').value.split(',').map(s => s.trim());
            clientConfig.certification_keywords = document.getElementById('cfg-certifications').value.split(',').map(s => s.trim());

            // Update UI displays
            document.getElementById('dash-client-name').textContent = clientConfig.name;
            document.getElementById('dash-client-email').textContent = clientConfig.email;
            
            document.getElementById('dash-client-depts').innerHTML = clientConfig.departments.map(d => `<span class="tag-dept">${d}</span>`).join('');
            document.getElementById('dash-client-keywords').innerHTML = clientConfig.keywords.map(k => `<span class="tag-kw">${k}</span>`).join('');

            alert('✅ Configuración del cliente actualizada correctamente.');
            loadLiveSecopData();
        });
    }
}

// ==========================================================================
// 5. Notificaciones: desplegable del encabezado
// ==========================================================================
// Dejo de ser un modulo del nav. Es una campana con badge de conteo y un panel
// flotante, disponible para los dos roles.
let notificaciones = [];

function initNotificaciones() {
    const boton = document.getElementById('btn-campana');
    const panel = document.getElementById('panel-notificaciones');
    const marcarTodas = document.getElementById('btn-marcar-todas');
    if (!boton || !panel) return;

    boton.addEventListener('click', (e) => {
        e.stopPropagation();
        const abierto = !panel.hidden;
        panel.hidden = abierto;
        boton.setAttribute('aria-expanded', String(!abierto));
        if (!abierto) cargarNotificaciones();
    });

    // Cierre al hacer clic fuera
    document.addEventListener('click', (e) => {
        if (!panel.hidden && !panel.contains(e.target) && e.target !== boton) {
            panel.hidden = true;
            boton.setAttribute('aria-expanded', 'false');
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !panel.hidden) {
            panel.hidden = true;
            boton.setAttribute('aria-expanded', 'false');
        }
    });

    if (marcarTodas) {
        marcarTodas.addEventListener('click', () => marcarNotificacion(null));
    }

    cargarNotificaciones();
}

async function cargarNotificaciones() {
    try {
        const resp = await fetch('/api/notifications');
        if (!resp.ok) {
            pintarNotificaciones([], 'No se pudieron cargar las notificaciones.');
            return;
        }
        const data = await resp.json();
        notificaciones = data.notificaciones || [];
        pintarNotificaciones(notificaciones);
        actualizarBadge(data.sin_leer || 0);
    } catch (err) {
        pintarNotificaciones([], 'Sin conexión con el servidor.');
    }
}

function actualizarBadge(sinLeer) {
    const badge = document.getElementById('campana-badge');
    if (!badge) return;
    badge.textContent = sinLeer > 9 ? '9+' : String(sinLeer);
    badge.hidden = sinLeer === 0;
}

function pintarNotificaciones(lista, mensajeError) {
    const contenedor = document.getElementById('panel-lista');
    const nota = document.getElementById('panel-nota');
    if (!contenedor) return;

    if (mensajeError) {
        contenedor.innerHTML = `<div class="panel-vacio">${escapeHtml(mensajeError)}</div>`;
        if (nota) nota.textContent = '';
        return;
    }

    if (lista.length === 0) {
        contenedor.innerHTML = `<div class="panel-vacio">
            <span class="panel-vacio-icono">📭</span>
            <strong>Sin notificaciones</strong>
            <span>Cuando el motor encuentre una oportunidad que coincida, aparecerá aquí.</span>
        </div>`;
        if (nota) nota.textContent = '';
        return;
    }

    contenedor.innerHTML = lista.map(n => `
        <button class="notif-item ${n.leida ? 'leida' : 'sin-leer'}" data-id="${escapeHtml(n.id)}" type="button">
            <span class="notif-punto" aria-hidden="true"></span>
            <span class="notif-cuerpo">
                <span class="notif-titulo">${escapeHtml(n.titulo)}</span>
                <span class="notif-meta">${escapeHtml(n.entidad)} · ${formatearPesos(n.valor_base)}</span>
                <span class="notif-fecha">${formatearFecha(n.fecha)}</span>
            </span>
        </button>
    `).join('');

    contenedor.querySelectorAll('.notif-item').forEach(item => {
        item.addEventListener('click', () => {
            const id = item.getAttribute('data-id');
            marcarNotificacion(id);
            const notif = notificaciones.find(n => n.id === id);
            if (notif) abrirDetalleNotificacion(notif);
        });
    });

    if (nota) {
        const sinLeer = lista.filter(n => !n.leida).length;
        nota.textContent = sinLeer > 0
            ? `${sinLeer} sin leer de ${lista.length}`
            : `${lista.length} notificaciones, todas leídas`;
    }
}

async function marcarNotificacion(id) {
    try {
        const resp = await fetch('/api/notifications/read', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(id ? { id } : {})
        });
        if (resp.ok) cargarNotificaciones();
    } catch (err) {
        console.warn('No se pudo marcar la notificacion:', err);
    }
}

/** Abre el correo tal como lo recibe el cliente, reutilizando el generador. */
function abrirDetalleNotificacion(notif) {
    const modal = document.getElementById('process-modal');
    const contenido = document.getElementById('modal-content');
    const titulo = document.getElementById('modal-title');
    if (!modal || !contenido) return;

    if (titulo) titulo.textContent = 'Notificación enviada al cliente';
    contenido.innerHTML = construirCorreoHtml(notif);
    modal.classList.add('active');

    const panel = document.getElementById('panel-notificaciones');
    if (panel) panel.hidden = true;
}

/**
 * Generador del correo transaccional. Viene de initEmailPreview(), que era un
 * modulo entero del nav; ahora es el detalle de una notificacion concreta.
 */
function construirCorreoHtml(notif) {
    return `
        <div class="correo-mockup">
            <div class="correo-cabecera">
                <strong class="correo-marca">SECOP Monitor</strong>
                <h3 class="correo-asunto">Nueva oportunidad detectada para ${escapeHtml(clientConfig.name)}</h3>
            </div>

            <div class="correo-badges">
                <span class="badge-status badge-minima">${escapeHtml(notif.modalidad || 'Mínima cuantía')}</span>
            </div>

            <table class="sena-data-table correo-tabla">
                <tr><td><strong>Entidad</strong></td><td>${escapeHtml(notif.entidad)}</td></tr>
                <tr><td><strong>Objeto</strong></td><td>${escapeHtml(notif.titulo)}</td></tr>
                <tr><td><strong>Ubicación</strong></td><td>${escapeHtml(notif.ubicacion)}</td></tr>
                <tr><td><strong>Valor base</strong></td><td class="price-text">${formatearPesos(notif.valor_base)}</td></tr>
                <tr><td><strong>Modalidad</strong></td><td>${escapeHtml(notif.modalidad)}</td></tr>
            </table>

            <div class="correo-ventaja">
                <strong>Ventaja competitiva para tu empresa</strong>
                <p>Este proceso valora empresas lideradas por mujeres y certificación PYME.
                   Tus acreditaciones te dan preferencia en la adjudicación.</p>
            </div>

            <div class="correo-cta">
                <a href="https://www.datos.gov.co" target="_blank" rel="noopener" class="btn-sena-action">
                    Ver proceso en SECOP II
                </a>
            </div>
        </div>
    `;
}

function formatearPesos(valor) {
    if (!valor) return 'No definido';
    return `$${Number(valor).toLocaleString('es-CO')} COP`;
}

function formatearFecha(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d)) return '';
    return d.toLocaleString('es-CO', {
        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
    });
}

// ==========================================================================
// 5b. Gestion y control de usuarios (solo admin)
// ==========================================================================
let usuariosCargados = [];

function initGestionUsuarios() {
    const nuevo = document.getElementById('btn-nuevo-usuario');
    const cerrar = document.getElementById('btn-close-user-modal');
    const guardar = document.getElementById('btn-guardar-usuario');
    const modal = document.getElementById('user-modal');

    if (nuevo) nuevo.addEventListener('click', () => abrirFormularioUsuario(null));
    if (cerrar) cerrar.addEventListener('click', cerrarFormularioUsuario);
    if (guardar) guardar.addEventListener('click', guardarUsuario);
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) cerrarFormularioUsuario();
        });
    }

    cargarUsuarios();
}

async function cargarUsuarios() {
    const cuerpo = document.getElementById('users-table-body');
    if (!cuerpo) return;
    cuerpo.innerHTML = '<tr><td colspan="7" class="tabla-aviso">Cargando usuarios...</td></tr>';

    try {
        const resp = await fetch('/api/users');
        if (resp.status === 403 || resp.status === 401) {
            mostrarAccesoDenegado('Gestión de Usuarios');
            return;
        }
        if (!resp.ok) {
            cuerpo.innerHTML = '<tr><td colspan="7" class="tabla-aviso">No se pudieron cargar los usuarios.</td></tr>';
            return;
        }
        const data = await resp.json();
        usuariosCargados = data.usuarios || [];
        pintarResumenUsuarios(data.resumen || {});
        pintarTablaUsuarios(usuariosCargados);
    } catch (err) {
        cuerpo.innerHTML = '<tr><td colspan="7" class="tabla-aviso">Sin conexión con el servidor.</td></tr>';
    }
}

function pintarResumenUsuarios(r) {
    const asignar = (id, valor) => {
        const el = document.getElementById(id);
        if (el) el.textContent = valor;
    };
    asignar('um-total', r.total ?? '—');
    asignar('um-activos', r.activos ?? '—');
    asignar('um-accesos', r.accesos ?? '—');
    asignar('um-acciones', r.acciones ?? '—');
    asignar('um-desglose', `${r.administradores ?? 0} administradores · ${r.inactivos ?? 0} inactivos`);
}

function pintarTablaUsuarios(lista) {
    const cuerpo = document.getElementById('users-table-body');
    if (!cuerpo) return;

    if (lista.length === 0) {
        cuerpo.innerHTML = '<tr><td colspan="7" class="tabla-aviso">Todavía no hay usuarios registrados.</td></tr>';
        return;
    }

    cuerpo.innerHTML = lista.map(u => {
        const activo = u.estado === 'activo';
        return `
        <tr>
            <td>
                <div class="celda-usuario">
                    <span class="avatar-usuario">${escapeHtml(iniciales(u.nombre))}</span>
                    <span class="entity-name">${escapeHtml(u.nombre)}</span>
                </div>
            </td>
            <td>${escapeHtml(u.correo)}</td>
            <td><span class="chip-rol ${u.rol === 'admin' ? 'es-admin' : ''}">${u.rol === 'admin' ? 'Administrador' : 'Usuario'}</span></td>
            <td><span class="chip-estado ${activo ? 'es-activo' : 'es-inactivo'}">${activo ? 'Activo' : 'Inactivo'}</span></td>
            <td class="celda-tenue">${u.ultimo_acceso ? formatearFecha(u.ultimo_acceso) : 'Nunca'}</td>
            <td class="celda-tenue">${u.accesos} accesos · ${u.acciones} acciones</td>
            <td>
                <div class="acciones-fila">
                    <button class="btn-view-detail" data-accion="editar" data-id="${escapeHtml(u.id)}">Editar</button>
                    <button class="btn-fila-secundario" data-accion="estado" data-id="${escapeHtml(u.id)}">${activo ? 'Desactivar' : 'Activar'}</button>
                    <button class="btn-fila-peligro" data-accion="eliminar" data-id="${escapeHtml(u.id)}">Eliminar</button>
                </div>
            </td>
        </tr>`;
    }).join('');

    cuerpo.querySelectorAll('button[data-accion]').forEach(btn => {
        btn.addEventListener('click', () => {
            const id = btn.getAttribute('data-id');
            const accion = btn.getAttribute('data-accion');
            const usuario = usuariosCargados.find(u => u.id === id);
            if (!usuario) return;

            if (accion === 'editar') abrirFormularioUsuario(usuario);
            else if (accion === 'estado') alternarEstadoUsuario(usuario);
            else if (accion === 'eliminar') eliminarUsuario(usuario);
        });
    });
}

function iniciales(nombre) {
    return (nombre || '?')
        .split(' ')
        .filter(Boolean)
        .slice(0, 2)
        .map(p => p[0].toUpperCase())
        .join('');
}

function abrirFormularioUsuario(usuario) {
    const modal = document.getElementById('user-modal');
    const titulo = document.getElementById('user-modal-title');
    const error = document.getElementById('uf-error');
    if (!modal) return;

    document.getElementById('uf-id').value = usuario ? usuario.id : '';
    document.getElementById('uf-nombre').value = usuario ? usuario.nombre : '';
    document.getElementById('uf-correo').value = usuario ? usuario.correo : '';
    document.getElementById('uf-rol').value = usuario ? usuario.rol : 'usuario';
    document.getElementById('uf-estado').value = usuario ? usuario.estado : 'activo';

    if (titulo) titulo.textContent = usuario ? 'Editar usuario' : 'Crear usuario';
    if (error) error.hidden = true;
    modal.classList.add('active');
}

function cerrarFormularioUsuario() {
    const modal = document.getElementById('user-modal');
    if (modal) modal.classList.remove('active');
}

function mostrarErrorUsuario(mensaje) {
    const error = document.getElementById('uf-error');
    if (!error) return;
    error.textContent = mensaje;
    error.hidden = false;
}

async function guardarUsuario() {
    const id = document.getElementById('uf-id').value;
    const datos = {
        nombre: document.getElementById('uf-nombre').value.trim(),
        correo: document.getElementById('uf-correo').value.trim(),
        rol: document.getElementById('uf-rol').value,
        estado: document.getElementById('uf-estado').value
    };

    const resultado = await peticionUsuarios(
        id ? `/api/users/${id}` : '/api/users',
        id ? 'PUT' : 'POST',
        datos
    );
    if (resultado.ok) {
        cerrarFormularioUsuario();
        cargarUsuarios();
    } else {
        mostrarErrorUsuario(resultado.mensaje);
    }
}

async function alternarEstadoUsuario(usuario) {
    const nuevoEstado = usuario.estado === 'activo' ? 'inactivo' : 'activo';
    const resultado = await peticionUsuarios(
        `/api/users/${usuario.id}`, 'PUT', { estado: nuevoEstado });
    if (resultado.ok) cargarUsuarios();
    else alert(resultado.mensaje);
}

async function eliminarUsuario(usuario) {
    if (!confirm(`¿Eliminar a ${usuario.nombre}? Esta acción no se puede deshacer.`)) return;
    const resultado = await peticionUsuarios(`/api/users/${usuario.id}`, 'DELETE');
    if (resultado.ok) cargarUsuarios();
    else alert(resultado.mensaje);
}

/** Envoltura comun: traduce la respuesta del backend a {ok, mensaje}. */
async function peticionUsuarios(ruta, metodo, cuerpo) {
    try {
        const opciones = { method: metodo, headers: { 'Content-Type': 'application/json' } };
        if (cuerpo) opciones.body = JSON.stringify(cuerpo);

        const resp = await fetch(ruta, opciones);
        if (resp.status === 403 || resp.status === 401) {
            const datos = await resp.json().catch(() => ({}));
            // Un 403 por falta de permiso saca al usuario del modulo; los 409
            // son salvaguardas de negocio y se muestran en el formulario.
            if (datos.codigo === 'sin_permiso' || datos.codigo === 'sin_sesion') {
                mostrarAccesoDenegado('Gestión de Usuarios');
                return { ok: false, mensaje: datos.error || 'Sin permiso' };
            }
            return { ok: false, mensaje: datos.error || 'Sin permiso' };
        }
        if (!resp.ok) {
            const datos = await resp.json().catch(() => ({}));
            return { ok: false, mensaje: datos.error || 'No se pudo completar la operación.' };
        }
        return { ok: true };
    } catch (err) {
        return { ok: false, mensaje: 'Sin conexión con el servidor.' };
    }
}

// ==========================================================================
// 6. Modal Controller
// ==========================================================================
function initModal() {
    const modal = document.getElementById('process-modal');
    const btnClose = document.getElementById('btn-close-modal');

    if (btnClose) {
        btnClose.addEventListener('click', () => {
            modal.classList.remove('active');
        });
    }

    window.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });
}

function openModal(process) {
    const modal = document.getElementById('process-modal');
    const content = document.getElementById('modal-content');

    content.innerHTML = `
        <h4 style="color:#00324D;font-size:16px;margin-bottom:10px;">${escapeHtml(process.name)}</h4>
        <div style="font-size:12px;color:#64748B;margin-bottom:16px;">ID: ${escapeHtml(process.id)} | Entidad: ${escapeHtml(process.entity_name)}</div>
        
        <table class="sena-data-table" style="margin-bottom:16px;">
            <tr><td><strong>Departamento:</strong></td><td>${escapeHtml(process.department)}</td></tr>
            <tr><td><strong>Ciudad:</strong></td><td>${escapeHtml(process.city)}</td></tr>
            <tr><td><strong>Valor Estimado:</strong></td><td class="price-text">$${Number(process.base_price).toLocaleString('es-CO')} COP</td></tr>
            <tr><td><strong>Modalidad:</strong></td><td>${escapeHtml(process.modality)}</td></tr>
            <tr><td><strong>Código UNSPSC:</strong></td><td>${escapeHtml(process.unspsc_code)}</td></tr>
        </table>

        <div style="margin-top:16px;text-align:right;">
            <a href="${process.url || 'https://www.datos.gov.co'}" target="_blank" class="btn-sena-action">
                🌐 Abrir en SECOP II
            </a>
        </div>
    `;

    modal.classList.add('active');
}

function initManualSync() {
    const btnSync = document.getElementById('btn-run-manual-sync');
    if (!btnSync) return;

    btnSync.addEventListener('click', async () => {
        const original = '<span>🔄</span> Ejecutar Sincronización Manual';
        btnSync.disabled = true;
        btnSync.innerHTML = '⏳ Sincronizando SECOP...';

        try {
            const resp = await fetch('/api/sync', { method: 'POST' });

            if (resp.status === 403 || resp.status === 401) {
                mostrarAccesoDenegado('Sincronización manual');
                return;
            }
            if (!resp.ok) {
                btnSync.innerHTML = '⚠️ No se pudo sincronizar';
            } else {
                const data = await resp.json();
                btnSync.innerHTML = `<span>✅</span> ${data.procesos} procesos sincronizados`;
                cargarMetricas();
                if (puede('ver_monitoreo')) loadLiveSecopData();
            }
        } catch (err) {
            btnSync.innerHTML = '⚠️ Sin conexión con el servidor';
        } finally {
            setTimeout(() => {
                btnSync.disabled = false;
                btnSync.innerHTML = original;
            }, 2500);
        }
    });
}

// Helpers
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function generateMockProcesses() {
    return [
        {
            id: "CO1.REQ.5891024",
            entity_name: "SERVICIO NACIONAL DE APRENDIZAJE SENA",
            department: "Atlantico",
            city: "Barranquilla",
            name: "Suministro de vestuario deportivo y dotación textil para instructores",
            description: "Adquisición de camisetas, sudaderas y uniformes institucionales. Incluye criterio de mujer lider y pyme.",
            modality: "Mínima cuantía",
            base_price: 32000000,
            unspsc_code: "V1.53102700",
            is_matched: true,
            certifications: { favorece_mujer_lider: true, favorece_pyme: true, requiere_equidad_genero: false },
            url: "https://www.datos.gov.co"
        },
        {
            id: "CO1.REQ.5891115",
            entity_name: "ALCALDIA MUNICIPAL DE SOLEDAD",
            department: "Atlantico",
            city: "Soledad",
            name: "Dotación de calzado y prendas de protección laboral para el personal operativo",
            description: "Compra de botas de seguridad y calzado de trabajo.",
            modality: "Mínima cuantía",
            base_price: 28500000,
            unspsc_code: "V1.53102710",
            is_matched: true,
            certifications: { favorece_mujer_lider: false, favorece_pyme: true, requiere_equidad_genero: true },
            url: "https://www.datos.gov.co"
        },
        {
            id: "CO1.REQ.5892010",
            entity_name: "GOBERNACION DEL BOLIVAR",
            department: "Bolivar",
            city: "Cartagena",
            name: "Adquisición de uniforme escolar e insumos textiles para programa social",
            description: "Dotaciones de vestuario para comunidades vulnerables.",
            modality: "Mínima cuantía",
            base_price: 45000000,
            unspsc_code: "V1.53102700",
            is_matched: true,
            certifications: { favorece_mujer_lider: true, favorece_pyme: false, requiere_equidad_genero: true },
            url: "https://www.datos.gov.co"
        }
    ];
}
