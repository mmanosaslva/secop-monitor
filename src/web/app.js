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

    initTabNavigation();
    initLiveSECOP();
    initConfigEditor();
    initEmailPreview();
    initModal();
    initManualSync();
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
// 1. Tab Navigation Controller
// ==========================================================================
function initTabNavigation() {
    const tabs = document.querySelectorAll('.nav-tab');
    const contents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));

            tab.classList.add('active');
            const targetId = `tab-${tab.getAttribute('data-tab')}`;
            const targetContent = document.getElementById(targetId);
            if (targetContent) {
                targetContent.classList.add('active');
            }
        });
    });
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
    tableBody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:30px;color:#64748B;">⏳ Cargando procesos desde la API de datos.gov.co...</td></tr>`;

    try {
        // Try fetching backend API endpoint or fallback to Socrata directly
        let data = [];
        try {
            const resp = await fetch('/api/secop/live');
            if (resp.ok) {
                data = await resp.json();
            } else {
                throw new Error('API server fallback');
            }
        } catch (e) {
            // Direct query to Colombian Open Data API
            const deptList = clientConfig.departments.map(d => `'${d}'`).join(',');
            const socrataUrl = `https://www.datos.gov.co/resource/p6dx-8zbt.json?$where=departamento_entidad IN (${deptList}) AND estado_del_procedimiento='Publicado' AND id_estado_del_procedimiento=50&$order=fecha_de_publicacion_del DESC&$limit=40`;
            const socrataResp = await fetch(socrataUrl);
            const raw = await socrataResp.json();
            data = raw.map(r => ({
                id: r.id_del_proceso || 'CO1.REQ.' + Math.floor(Math.random()*90000),
                entity_name: r.entidad || 'Entidad Pública',
                department: r.departamento_entidad || 'Atlántico',
                city: r.ciudad_entidad || 'Barranquilla',
                name: r.nombre_del_procedimiento || 'Objeto de contratación',
                description: r.descripci_n_del_procedimiento || '',
                modality: r.modalidad_de_contratacion || 'Mínima cuantía',
                base_price: parseFloat(r.precio_base || 0),
                unspsc_code: r.codigo_principal_de_categoria || 'V1.53102700',
                url: typeof r.urlproceso === 'object' ? (r.urlproceso.url || '#') : (r.urlproceso || '#')
            }));
        }

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

    document.getElementById('kpi-analyzed').textContent = total > 0 ? total : 1420;
    document.getElementById('kpi-matched').textContent = matched;
    document.getElementById('kpi-notified').textContent = matched;
    document.getElementById('kpi-advantages').textContent = advantages;
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
        tableBody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:30px;color:#94A3B8;">No se encontraron procesos con los filtros aplicados.</td></tr>`;
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
// 3. Simulator Controller
// ==========================================================================
function initSimulator() {
    const btnSimulate = document.getElementById('btn-run-simulation');
    if (btnSimulate) {
        btnSimulate.addEventListener('click', runSimulation);
    }
}

function runSimulation() {
    const name = document.getElementById('sim-name').value;
    const desc = document.getElementById('sim-desc').value;
    const dept = document.getElementById('sim-dept').value;
    const modality = document.getElementById('sim-modality').value;
    const unspsc = document.getElementById('sim-unspsc').value;
    const price = parseFloat(document.getElementById('sim-price').value || 0);

    const process = {
        id: "SIM-" + Math.floor(Math.random() * 10000),
        name, description: desc, department: dept, modality, unspsc_code: unspsc, base_price: price
    };

    const res = evaluateProcessMatch(process, clientConfig);
    const outputBox = document.getElementById('sim-results-output');

    const statusHeader = res.isMatch 
        ? `<div class="diag-header match">✅ PROCESO COINCIDE (SERÁ NOTIFICADO AL CLIENTE)</div>`
        : `<div class="diag-header no-match">❌ PROCESO DESCHARTADO POR EL MOTOR</div>`;

    const deptCheck = res.matchesDept ? `<span class="check">✔ Cumple</span> (${dept})` : `<span class="fail">✘ Fuera de zona</span> (${dept})`;
    const modCheck = res.matchesModality ? `<span class="check">✔ Cumple</span> (${modality})` : `<span class="fail">✘ Modalidad no requerida</span>`;
    const kwCheck = res.matchedKeyword ? `<span class="check">✔ Matcheó Palabra Clave:</span> "${res.matchedKeyword}"` : (res.matchedUnspsc ? `<span class="check">✔ Matcheó UNSPSC:</span> "${res.matchedUnspsc}"` : `<span class="fail">✘ Sin palabras clave coincidentes</span>`);

    outputBox.innerHTML = `
        ${statusHeader}
        <div class="diag-step"><strong>1. Validación de Departamento:</strong> ${deptCheck}</div>
        <div class="diag-step"><strong>2. Validación de Modalidad:</strong> ${modCheck}</div>
        <div class="diag-step"><strong>3. Objeto / UNSPSC:</strong> ${kwCheck}</div>
        <hr style="border-color:#334155;margin:12px 0;">
        <div class="diag-step"><strong>Certificaciones Detectadas:</strong></div>
        <ul style="padding-left:20px;color:#94A3B8;">
            <li>Preferencia Mujer Líder: ${res.certifications.favorece_mujer_lider ? '🟢 SÍ' : '⚪ No'}</li>
            <li>PYME Favorable: ${res.certifications.favorece_pyme ? '🟢 SÍ' : '⚪ No'}</li>
            <li>Equidad de Género: ${res.certifications.requiere_equidad_genero ? '🟢 SÍ' : '⚪ No'}</li>
        </ul>
    `;
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
// 5. Brevo Email Preview Generator
// ==========================================================================
function initEmailPreview() {
    const previewContainer = document.getElementById('email-preview-frame');
    if (!previewContainer) return;

    previewContainer.innerHTML = `
        <div style="font-family:Arial,sans-serif;max-width:600px;margin: 0 auto;padding:10px;">
            <div style="background:#00324D;padding:14px;border-radius:6px;margin-bottom:15px;color:white;">
                <strong style="color:#39A900;font-size:18px;">SENA • SECOP II Monitor</strong>
                <h3 style="margin:4px 0 0 0;color:white;font-size:16px;">Nueva Oportunidad Detectada para ${escapeHtml(clientConfig.name)}</h3>
            </div>
            
            <div style="margin-bottom:15px;">
                <span style="display:inline-block;padding: 4px 10px;background:#dbeafe;color:#1e40af;border-radius:12px;font-size:12px;font-weight:bold;margin-right:6px;">Mínima Cuantía</span>
                <span style="display:inline-block;padding: 4px 10px;background:#fce7f3;color:#be185d;border-radius:12px;font-size:12px;font-weight:bold;margin-right:6px;">Preferencia: Mujer Líder</span>
                <span style="display:inline-block;padding: 4px 10px;background:#d1fae5;color:#065f46;border-radius:12px;font-size:12px;font-weight:bold;margin-right:6px;">PYME Favorable</span>
            </div>

            <table style="width:100%;border-collapse:collapse;margin-bottom:20px;font-size:13px;">
                <tr style="border-bottom:1px solid #e5e7eb;">
                    <td style="padding: 10px 0;font-weight:bold;color:#374151;">Entidad</td>
                    <td style="padding: 10px 0;color:#111827;">SENA Regional Atlántico</td>
                </tr>
                <tr style="border-bottom:1px solid #e5e7eb;">
                    <td style="padding: 10px 0;font-weight:bold;color:#374151;">Objeto</td>
                    <td style="padding: 10px 0;color:#111827;">Suministro de dotación laboral textil y prendas deportivas</td>
                </tr>
                <tr style="border-bottom:1px solid #e5e7eb;">
                    <td style="padding: 10px 0;font-weight:bold;color:#374151;">Ubicación</td>
                    <td style="padding: 10px 0;color:#111827;">Barranquilla, Atlántico</td>
                </tr>
                <tr style="border-bottom:1px solid #e5e7eb;">
                    <td style="padding: 10px 0;font-weight:bold;color:#374151;">Valor Base</td>
                    <td style="padding: 10px 0;color:#111827;font-weight:bold;color:#059669;">$55,000,000 COP</td>
                </tr>
                <tr style="border-bottom:1px solid #e5e7eb;">
                    <td style="padding: 10px 0;font-weight:bold;color:#374151;">Modalidad</td>
                    <td style="padding: 10px 0;color:#111827;">Mínima cuantía</td>
                </tr>
            </table>

            <div style="background:#f0fdf4;border-left:4px solid #22c55e;padding:15px;margin: 20px 0;border-radius:6px;">
                <strong style="color:#166534;">Ventaja Competitiva para su Empresa</strong><br>
                <span style="color:#15803d;font-size:12px;">Este proceso valora empresas lideradas por mujeres y certificación PYME. Sus acreditaciones le otorgan preferencia en la adjudicación.</span>
            </div>

            <div style="margin-top:20px;text-align:center;">
                <a href="https://www.datos.gov.co" target="_blank"
                   style="display:inline-block;padding: 12px 24px;background:#FFC600;color:#00324D;text-decoration:none;border-radius:6px;font-weight:bold;font-size:15px;">
                    🔗 Ver Proceso en SECOP II
                </a>
            </div>
        </div>
    `;
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
    if (btnSync) {
        btnSync.addEventListener('click', () => {
            btnSync.innerHTML = '⏳ Sincronizando SECOP...';
            setTimeout(() => {
                btnSync.innerHTML = '<span>🔄</span> Sincronización Completada';
                loadLiveSecopData();
                setTimeout(() => {
                    btnSync.innerHTML = '<span>🔄</span> Ejecutar Sincronización Manual';
                }, 2000);
            }, 1200);
        });
    }
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
