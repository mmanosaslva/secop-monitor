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
    const formulario = document.getElementById('login-form');
    const btnLogout = document.getElementById('btn-logout');
    const btnVer = document.getElementById('btn-ver-contrasena');

    if (formulario) formulario.addEventListener('submit', iniciarSesion);
    if (btnLogout) btnLogout.addEventListener('click', cerrarSesion);

    document.querySelectorAll('.btn-ver-contrasena[data-campo]').forEach(boton => {
        boton.addEventListener('click', () => {
            const campo = document.getElementById(boton.dataset.campo);
            const oculta = campo.type === 'password';
            campo.type = oculta ? 'text' : 'password';
            boton.setAttribute('aria-label', oculta ? 'Ocultar contraseña' : 'Mostrar contraseña');
            campo.focus();
        });
    });

    if (btnVer) {
        btnVer.addEventListener('click', () => {
            const campo = document.getElementById('login-contrasena');
            const oculta = campo.type === 'password';
            campo.type = oculta ? 'text' : 'password';
            btnVer.setAttribute('aria-label', oculta ? 'Ocultar contraseña' : 'Mostrar contraseña');
            campo.focus();
        });
    }
}

async function iniciarSesion(evento) {
    if (evento) evento.preventDefault();

    const btnLogin = document.getElementById('btn-login');
    const error = document.getElementById('login-error');
    const correo = document.getElementById('login-correo').value.trim();
    const contrasena = document.getElementById('login-contrasena').value;

    error.hidden = true;

    if (!correo || !contrasena) {
        error.textContent = 'Indica tu correo y tu contraseña.';
        error.hidden = false;
        return;
    }

    btnLogin.disabled = true;
    btnLogin.textContent = 'Comprobando...';

    try {
        const resp = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ correo, contrasena })
        });
        const data = await resp.json();

        if (!resp.ok) {
            error.textContent = data.error || 'No se pudo iniciar la sesión.';
            error.hidden = false;
            document.getElementById('login-contrasena').value = '';
            return;
        }

        sesion = data;
        entrarALaApp();
    } catch (err) {
        error.textContent = 'No hay conexión con el servidor. Levanta src/web_server.py e intenta de nuevo.';
        error.hidden = false;
    } finally {
        btnLogin.disabled = false;
        btnLogin.textContent = 'Entrar al monitor';
    }
}

// ----------------------------------------------------------------------
// Cambio de la propia contrasena
// ----------------------------------------------------------------------
function initCambioClave() {
    const abrir = document.getElementById('btn-clave');
    const cerrar = document.getElementById('btn-close-clave-modal');
    const guardar = document.getElementById('btn-guardar-clave');
    const cancelar = document.getElementById('btn-cancelar-clave');
    const modal = document.getElementById('clave-modal');

    if (abrir) abrir.addEventListener('click', abrirCambioClave);
    if (cerrar) cerrar.addEventListener('click', cerrarCambioClave);
    if (cancelar) cancelar.addEventListener('click', cerrarCambioClave);
    if (guardar) guardar.addEventListener('click', guardarClave);
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) cerrarCambioClave();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('active')) cerrarCambioClave();
        });
    }
}

function abrirCambioClave() {
    const modal = document.getElementById('clave-modal');
    if (!modal) return;
    ['cf-actual', 'cf-nueva'].forEach(id => {
        const campo = document.getElementById(id);
        campo.value = '';
        campo.type = 'password';
    });
    document.getElementById('cf-error').hidden = true;
    document.getElementById('cf-exito').hidden = true;
    modal.classList.add('active');
    document.getElementById('cf-actual').focus();
}

function cerrarCambioClave() {
    const modal = document.getElementById('clave-modal');
    if (modal) modal.classList.remove('active');
}

async function guardarClave() {
    const error = document.getElementById('cf-error');
    const exito = document.getElementById('cf-exito');
    const actual = document.getElementById('cf-actual').value;
    const nueva = document.getElementById('cf-nueva').value;

    error.hidden = true;
    exito.hidden = true;

    try {
        const resp = await fetch('/api/auth/password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ actual, nueva })
        });
        const data = await resp.json();

        if (!resp.ok) {
            error.textContent = data.error || 'No se pudo cambiar la contraseña.';
            error.hidden = false;
            return;
        }
        exito.hidden = false;
        document.getElementById('cf-actual').value = '';
        document.getElementById('cf-nueva').value = '';
    } catch (err) {
        error.textContent = 'Sin conexión con el servidor.';
        error.hidden = false;
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
    renderizarNavegacion();

    initModal();
    initCambioClave();
    cargarConfiguracion();
    cargarMetricas();
    if (puede('ver_actividad')) initActividad();
    if (puede('ver_notificaciones')) initNotificaciones();
    if (puede('gestionar_usuarios')) initGestionUsuarios();
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
    { id: 'dashboard', etiqueta: 'Panel de Métricas', permiso: 'ver_metricas' },
    { id: 'architecture', etiqueta: '¿Cómo Funciona por Dentro?', permiso: 'ver_arquitectura' },
    { id: 'actividad', etiqueta: 'Actividad del Monitor', permiso: 'ver_actividad' },
    { id: 'config', etiqueta: 'Configuración del Cliente', permiso: 'ver_configuracion' },
    { id: 'users', etiqueta: 'Gestión de Usuarios', permiso: 'gestionar_usuarios' }
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
        <button class="nav-tab" data-tab="${m.id}">${escapeHtml(m.etiqueta)}</button>
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

// ==========================================================================
// 2. Datos del monitor (solo lectura)
// ==========================================================================
// Todo sale de lo que registro el cron en la base de datos y de GitHub
// Actions. La interfaz no lanza ejecuciones ni cambia filtros.

const ESTADOS_CICLO = {
    completado: 'Completado',
    en_curso: 'En curso',
    en_cola: 'En cola en GitHub',
    esperando: 'Esperando a GitHub',
    programado: 'Programado',
    fallido: 'Falló',
    interrumpido: 'Sin terminar',
    omitido: 'No se ejecutó',
    desconocido: 'Sin datos'
};

const ESTADOS_CORREO = {
    enviado: 'Enviado',
    entregado: 'Entregado',
    abierto: 'Abierto por el cliente',
    diferido: 'Entrega diferida',
    rebotado: 'Rebotó',
    bloqueado: 'Bloqueado',
    spam: 'Marcado como spam',
    fallido: 'No se pudo enviar'
};

const CORREOS_CON_PROBLEMA = ['rebotado', 'bloqueado', 'spam', 'fallido'];

const ORIGENES = { programado: 'Programado', manual: 'Manual', local: 'Local (pruebas)' };

// Colombia no tiene horario de verano: UTC-5 todo el año.
const OFFSET_COT_MS = -5 * 60 * 60 * 1000;

function fechaCot(iso) {
    return new Date(new Date(iso).getTime() + OFFSET_COT_MS);
}

/** "15:55" en hora de Colombia. */
function horaCot(iso) {
    if (!iso) return '';
    const d = fechaCot(iso);
    return `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`;
}

/** "2026-09-29" en hora de Colombia. */
function diaCot(iso) {
    return fechaCot(iso).toISOString().slice(0, 10);
}

/** Minutos desde la medianoche de Colombia, para ubicar en el eje del dia. */
function minutoDelDia(iso) {
    const d = fechaCot(iso);
    return d.getUTCHours() * 60 + d.getUTCMinutes();
}

function nombreDia(fecha) {
    const [a, m, d] = fecha.split('-').map(Number);
    return new Date(Date.UTC(a, m - 1, d, 12)).toLocaleDateString('es-CO', {
        weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC'
    });
}

function duracionTexto(minutos) {
    if (minutos < 60) return `${minutos} min`;
    const h = Math.floor(minutos / 60);
    const m = minutos % 60;
    return m ? `${h} h ${m} min` : `${h} h`;
}

function numero(valor) {
    return valor === null || valor === undefined ? '—' : Number(valor).toLocaleString('es-CO');
}

// --------------------------------------------------------------------------
// Configuracion del cliente: la leen el panel y la pestaña de configuracion
// --------------------------------------------------------------------------
let clientConfig = { name: '' };

async function cargarConfiguracion() {
    try {
        const resp = await fetch('/api/config');
        if (!resp.ok) return;
        clientConfig = await resp.json();
    } catch (err) {
        return;
    }
    const texto = (id, valor) => {
        const el = document.getElementById(id);
        if (el) el.textContent = valor || '—';
    };
    const chips = (id, lista, clase) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.innerHTML = (lista || []).length
            ? lista.map(v => `<span class="${clase}">${escapeHtml(v)}</span>`).join('')
            : '<span class="config-vacio">Ninguno</span>';
    };

    texto('dash-client-name', clientConfig.name);
    texto('dash-client-email', clientConfig.email);
    texto('dash-client-depts-label', `Departamentos (${(clientConfig.departments || []).length})`);
    chips('dash-client-depts', clientConfig.departments, 'tag-dept');
    chips('dash-client-keywords', clientConfig.keywords, 'tag-kw');

    texto('cfg-name', clientConfig.name);
    texto('cfg-email', clientConfig.email);
    chips('cfg-departments', clientConfig.departments, 'tag-dept');
    chips('cfg-modalidad', clientConfig.modalidad_keywords, 'tag-kw');
    chips('cfg-keywords', clientConfig.keywords, 'tag-kw');
    chips('cfg-unspsc', clientConfig.unspsc_codes, 'tag-kw');
    chips('cfg-certifications', clientConfig.certification_keywords, 'tag-kw');
}

// --------------------------------------------------------------------------
// Panel de metricas
// --------------------------------------------------------------------------
async function cargarMetricas() {
    if (!document.getElementById('tab-dashboard')) return;
    try {
        const resp = await fetch('/api/metrics');
        if (!resp.ok) {
            marcarMetricasNoDisponibles(await mensajeDeError(resp));
            return;
        }
        pintarKpis(await resp.json());
    } catch (err) {
        marcarMetricasNoDisponibles('Sin conexión con el servidor.');
    }
}

function pintarKpis(m) {
    const asignar = (id, valor) => {
        const el = document.getElementById(id);
        if (el) el.textContent = numero(valor);
    };
    asignar('kpi-analyzed', m.analizados);
    asignar('kpi-matched', m.coincidencias);
    asignar('kpi-new', m.nuevas);
    asignar('kpi-notified', m.notificados);

    const sub = (id, texto) => {
        const el = document.getElementById(id);
        if (el) el.textContent = texto;
    };
    sub('kpi-analyzed-sub', m.ultimo_ciclo
        ? `En el ciclo de las ${horaCot(m.ultimo_ciclo)} (${nombreDia(diaCot(m.ultimo_ciclo))})`
        : 'Aún no hay ciclos registrados');
    sub('kpi-new-sub', m.con_ventaja
        ? `Últimos 7 días · ${numero(m.con_ventaja)} con ventaja competitiva`
        : 'Últimos 7 días');
    sub('kpi-notified-sub', m.correos_con_problema
        ? `Últimos 7 días · ${numero(m.correos_con_problema)} con problemas de entrega`
        : 'Últimos 7 días');

    const act = document.getElementById('dash-actualizado');
    if (act) act.textContent = `Actualizado a las ${horaCot(m.actualizado)}`;
}

function marcarMetricasNoDisponibles(mensaje) {
    ['kpi-analyzed', 'kpi-matched', 'kpi-new', 'kpi-notified'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '—';
    });
    const act = document.getElementById('dash-actualizado');
    if (act) act.textContent = mensaje;
}

async function mensajeDeError(resp) {
    try {
        const data = await resp.json();
        if (data.codigo === 'sin_base_de_datos') {
            return 'Sin acceso a la base de datos del monitor.';
        }
        return data.error || 'No se pudo cargar.';
    } catch (err) {
        return 'No se pudo cargar.';
    }
}

// --------------------------------------------------------------------------
// Actividad del monitor
// --------------------------------------------------------------------------
let actividad = null;          // ultima respuesta de /api/actividad
let ejecucionSeleccionada = null;
const INTERVALO_ACTUALIZACION_MS = 30000;

function initActividad() {
    const ir = document.getElementById('btn-ir-actividad');
    if (ir) ir.addEventListener('click', () => abrirModulo('actividad'));

    cargarActividad();

    // Se actualiza sola mientras la pestaña esta a la vista. Con 4 ciclos al
    // dia no hace falta una conexion abierta: basta con volver a preguntar.
    setInterval(() => {
        if (document.visibilityState !== 'visible') return;
        cargarActividad();
        const panel = document.getElementById('tab-dashboard');
        if (panel && panel.classList.contains('active')) cargarMetricas();
    }, INTERVALO_ACTUALIZACION_MS);
}

async function cargarActividad() {
    try {
        const resp = await fetch('/api/actividad');
        if (resp.status === 401 || resp.status === 403) {
            mostrarAccesoDenegado('Actividad del Monitor');
            return;
        }
        if (!resp.ok) {
            pintarActividadNoDisponible(await mensajeDeError(resp));
            return;
        }
        actividad = await resp.json();
    } catch (err) {
        pintarActividadNoDisponible('Sin conexión con el servidor.');
        return;
    }

    pintarResumenCiclos(actividad.hoy);
    pintarAviso(actividad);
    pintarDia(actividad);
    pintarHistorial(actividad);
    pintarTodas(actividad.ejecuciones);

    const act = document.getElementById('act-actualizado');
    if (act) act.textContent = `Actualizado a las ${horaCot(actividad.ahora)}`;

    // La primera vez se abre la ultima ejecucion; despues se respeta lo que
    // haya elegido la persona y solo se refresca.
    const id = ejecucionSeleccionada ? ejecucionSeleccionada.id
        : (actividad.ultima ? actividad.ultima.id : null);
    if (id) {
        cargarEjecucion(id, ejecucionSeleccionada ? ejecucionSeleccionada.contexto
            : contextoDeEjecucion(id));
    } else {
        pintarSinEjecucion();
    }
}

function pintarActividadNoDisponible(mensaje) {
    const aviso = document.getElementById('act-aviso');
    if (aviso) {
        aviso.textContent = mensaje;
        aviso.className = 'aviso-actividad es-error';
        aviso.hidden = false;
    }
    const resumen = document.getElementById('dash-ciclos');
    if (resumen) resumen.innerHTML = `<li class="ciclos-resumen-aviso">${escapeHtml(mensaje)}</li>`;
}

function pintarAviso(datos) {
    const aviso = document.getElementById('act-aviso');
    if (!aviso) return;
    let texto = '';
    let clase = 'aviso-actividad';
    if (!datos.workflow_activo) {
        texto = 'El cron está pausado en GitHub: no correrán nuevos ciclos hasta que se reactive.';
        if (datos.estado_workflow === 'disabled_inactivity') {
            texto += ' GitHub lo desactivó tras 60 días sin actividad en el repositorio.';
        }
        clase += ' es-error';
    } else if (!datos.github_disponible && esAdmin()) {
        texto = 'No se pudo consultar GitHub. Se muestra lo que registró la base de datos; '
            + 'las ejecuciones en cola y los fallos previos a la base no aparecerán.';
    }
    aviso.textContent = texto;
    aviso.className = clase;
    aviso.hidden = !texto;
}

/** Texto de cuando corrio un ciclo, o de por que aun no. */
function metaDeCiclo(r) {
    const e = r.ejecucion;
    if (r.estado === 'programado') return `Programado para las ${r.etiqueta}`;
    if (r.estado === 'esperando') return 'GitHub suele retrasarlo varias horas';
    if (r.estado === 'omitido') return 'GitHub no lo corrió en las 8 h siguientes';
    if (!e || !e.inicio) return '';
    const retraso = r.retraso_min >= 5 ? ` · ${duracionTexto(r.retraso_min)} después` : '';
    return `Corrió a las ${horaCot(e.inicio)}${retraso}`;
}

function conteoDeCiclo(e) {
    if (!e || e.analizados === null || e.analizados === undefined) return '';
    const correos = e.enviados ? ` · ${numero(e.enviados)} correos` : '';
    return `${numero(e.analizados)} analizados · ${numero(e.coincidencias)} coinciden${correos}`;
}

function pintarResumenCiclos(hoy) {
    const lista = document.getElementById('dash-ciclos');
    if (!lista) return;
    lista.innerHTML = hoy.map(r => `
        <li class="ciclo-resumen estado-${r.estado}">
            <span class="ciclo-resumen-hora">${r.etiqueta}</span>
            <span class="ciclo-resumen-cuerpo">
                <span class="insignia-estado">${ESTADOS_CICLO[r.estado] || r.estado}</span>
                <span class="ciclo-resumen-meta">${escapeHtml([metaDeCiclo(r), conteoDeCiclo(r.ejecucion)].filter(Boolean).join(' · '))}</span>
            </span>
        </li>
    `).join('');
}

function pintarDia(datos) {
    const eje = document.getElementById('act-eje');
    const lista = document.getElementById('act-ciclos');
    const siguiente = document.getElementById('act-siguiente');
    if (!eje || !lista) return;

    if (siguiente && datos.siguiente) {
        const faltan = Math.max(0, Math.round((new Date(datos.siguiente) - new Date(datos.ahora)) / 60000));
        siguiente.textContent = `Siguiente ciclo: ${horaCot(datos.siguiente)}, en ${duracionTexto(faltan)}`;
    }

    // Eje de 24 h: marca hueca en la hora programada, punto en la hora real
    // y, entre ambos, el tramo que GitHub tardo en correrlo.
    const hoy = diaCot(datos.ahora);
    const pct = min => `${(min / 1440 * 100).toFixed(3)}%`;
    let marcas = '';
    [0, 6, 12, 18, 24].forEach(h => {
        const extremo = h === 0 ? ' es-inicio' : h === 24 ? ' es-fin' : '';
        marcas += `<span class="eje-hora${extremo}" style="left:${pct(h * 60)}">${String(h).padStart(2, '0')}:00</span>`;
    });
    datos.hoy.forEach(r => {
        const inicio = minutoDelDia(r.programado);
        marcas += `<span class="eje-programado estado-${r.estado}" style="left:${pct(inicio)}"></span>`;
        const e = r.ejecucion;
        if (e && e.inicio) {
            const real = diaCot(e.inicio) === hoy ? minutoDelDia(e.inicio) : 1440;
            if (real > inicio) {
                marcas += `<span class="eje-retraso" style="left:${pct(inicio)};width:${pct(real - inicio)}"></span>`;
            }
            marcas += `<span class="eje-real estado-${r.estado}" style="left:${pct(real)}"></span>`;
        }
    });
    marcas += `<span class="eje-ahora" style="left:${pct(minutoDelDia(datos.ahora))}"></span>`;
    eje.innerHTML = `<span class="eje-linea"></span>${marcas}`;

    lista.innerHTML = datos.hoy.map(r => {
        const e = r.ejecucion;
        const elegible = e && e.id;
        const etiqueta = `
            <span class="ciclo-hora">${r.etiqueta}</span>
            <span class="insignia-estado">${ESTADOS_CICLO[r.estado] || r.estado}</span>
            <span class="ciclo-meta">${escapeHtml(metaDeCiclo(r))}</span>
            <span class="ciclo-conteo">${escapeHtml(conteoDeCiclo(e))}</span>`;
        return `<li class="ciclo estado-${r.estado}">${elegible
            ? `<button type="button" class="ciclo-boton" data-id="${e.id}" data-contexto="Ciclo de las ${r.etiqueta} · hoy">${etiqueta}</button>`
            : `<div class="ciclo-boton es-inerte">${etiqueta}</div>`}</li>`;
    }).join('');

    lista.querySelectorAll('.ciclo-boton[data-id]').forEach(b => {
        b.addEventListener('click', () => cargarEjecucion(Number(b.dataset.id), b.dataset.contexto));
    });
    marcarSeleccion();
}

function pintarHistorial(datos) {
    const tabla = document.getElementById('act-historial');
    if (!tabla) return;
    const ranuras = [...datos.hoy, ...datos.historial];
    const dias = [...new Set(ranuras.map(r => r.fecha))].sort().reverse();
    const etiquetas = datos.hoy.map(r => r.etiqueta);

    const celda = r => {
        if (!r) return '<td></td>';
        const e = r.ejecucion;
        const texto = e && e.inicio ? horaCot(e.inicio) : (ESTADOS_CICLO[r.estado] || r.estado);
        const titulo = `${ESTADOS_CICLO[r.estado] || r.estado}. ${metaDeCiclo(r)}. ${conteoDeCiclo(e)}`;
        const contenido = `<span class="punto-estado" aria-hidden="true"></span><span>${escapeHtml(texto)}</span>`;
        return e && e.id
            ? `<td class="estado-${r.estado}"><button type="button" class="celda-ciclo" data-id="${e.id}"
                   data-contexto="Ciclo de las ${r.etiqueta} · ${nombreDia(r.fecha)}" title="${escapeHtml(titulo)}"
                   aria-label="${r.etiqueta}, ${nombreDia(r.fecha)}: ${escapeHtml(titulo)}">${contenido}</button></td>`
            : `<td class="estado-${r.estado}"><span class="celda-ciclo es-inerte" title="${escapeHtml(titulo)}">${contenido}</span></td>`;
    };

    tabla.innerHTML = `
        <thead><tr><th scope="col">Día</th>${etiquetas.map(t => `<th scope="col">${t}</th>`).join('')}</tr></thead>
        <tbody>${dias.map(dia => `
            <tr>
                <th scope="row">${dia === diaCot(datos.ahora) ? 'Hoy' : nombreDia(dia)}</th>
                ${etiquetas.map(t => celda(ranuras.find(r => r.fecha === dia && r.etiqueta === t))).join('')}
            </tr>`).join('')}
        </tbody>`;

    tabla.querySelectorAll('.celda-ciclo[data-id]').forEach(b => {
        b.addEventListener('click', () => {
            cargarEjecucion(Number(b.dataset.id), b.dataset.contexto);
            document.getElementById('act-ejecucion').scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    });
    marcarSeleccion();
}

function pintarTodas(ejecuciones) {
    const bloque = document.getElementById('act-todas');
    const cuerpo = document.getElementById('act-todas-cuerpo');
    if (!bloque || !cuerpo) return;
    if (!ejecuciones) {
        bloque.hidden = true;
        return;
    }
    bloque.hidden = false;
    cuerpo.innerHTML = ejecuciones.map(e => `
        <tr class="estado-${e.estado}">
            <td>${e.inicio ? `${nombreDia(diaCot(e.inicio))}, ${horaCot(e.inicio)}` : '—'}</td>
            <td>${ORIGENES[e.origen] || e.origen}</td>
            <td><span class="insignia-estado">${ESTADOS_CICLO[e.estado] || e.estado}</span></td>
            <td>${numero(e.analizados)}</td>
            <td>${numero(e.coincidencias)}</td>
            <td>${numero(e.enviados)}${e.fallidos ? ` · ${numero(e.fallidos)} fallidos` : ''}</td>
            <td>${e.github_url ? `<a href="${escapeHtml(e.github_url)}" target="_blank" rel="noopener">Ver log</a>` : '—'}</td>
        </tr>
    `).join('');
}

function contextoDeEjecucion(id) {
    if (!actividad) return '';
    const r = [...actividad.hoy, ...actividad.historial].find(x => x.ejecucion && x.ejecucion.id === id);
    if (!r) return 'Última ejecución';
    const dia = r.fecha === diaCot(actividad.ahora) ? 'hoy' : nombreDia(r.fecha);
    return `Ciclo de las ${r.etiqueta} · ${dia}`;
}

function marcarSeleccion() {
    const id = ejecucionSeleccionada ? String(ejecucionSeleccionada.id) : null;
    document.querySelectorAll('#tab-actividad [data-id]').forEach(b => {
        b.setAttribute('aria-pressed', String(b.dataset.id === id));
    });
}

function pintarSinEjecucion() {
    const destino = document.getElementById('act-ejecucion');
    if (!destino) return;
    destino.innerHTML = `
        <div class="ejecucion-vacia">
            <strong>Aún no hay ejecuciones registradas</strong>
            <span>Cuando el cron complete su primer ciclo, aquí verás qué analizó y qué correos envió.</span>
        </div>`;
}

async function cargarEjecucion(id, contexto) {
    const destino = document.getElementById('act-ejecucion');
    if (!destino) return;
    const cambio = !ejecucionSeleccionada || ejecucionSeleccionada.id !== id;
    ejecucionSeleccionada = { id, contexto };
    marcarSeleccion();
    if (cambio) destino.classList.add('is-cargando');

    try {
        const resp = await fetch(`/api/actividad/ejecucion/${id}`);
        if (!resp.ok) {
            destino.innerHTML = `<p class="ejecucion-error">${escapeHtml(await mensajeDeError(resp))}</p>`;
            return;
        }
        pintarEjecucion(await resp.json(), contexto);
    } catch (err) {
        destino.innerHTML = '<p class="ejecucion-error">Sin conexión con el servidor.</p>';
    } finally {
        destino.classList.remove('is-cargando');
    }
}

function pintarEjecucion(datos, contexto) {
    const destino = document.getElementById('act-ejecucion');
    const e = datos.ejecucion;

    const meta = [];
    if (e.inicio) meta.push(`Corrió el ${nombreDia(diaCot(e.inicio))} a las ${horaCot(e.inicio)}`);
    if (e.duracion_s !== undefined) meta.push(`duró ${e.duracion_s < 60 ? `${e.duracion_s} s` : duracionTexto(Math.round(e.duracion_s / 60))}`);

    const tecnico = [];
    if (e.origen) tecnico.push(ORIGENES[e.origen] || e.origen);
    if (e.destinatario) tecnico.push(`Correos a ${e.destinatario}`);
    if (e.silencioso) tecnico.push('Modo silencioso: esta ejecución no envía correos');
    const log = e.github_url
        ? `<a class="enlace-accion" href="${escapeHtml(e.github_url)}" target="_blank" rel="noopener">Ver log en GitHub</a>`
        : '';

    const dato = (valor, etiqueta) => `
        <div class="dato">
            <span class="dato-valor">${numero(valor)}</span>
            <span class="dato-etiqueta">${etiqueta}</span>
        </div>`;

    const error = e.error
        ? `<p class="ejecucion-error">${escapeHtml(e.error)}</p>`
        : (e.estado === 'fallido' || e.estado === 'interrumpido')
            ? '<p class="ejecucion-error">La ejecución no terminó bien. El detalle está en el log de GitHub.</p>'
            : '';

    destino.innerHTML = `
        <div class="ejecucion-cabecera">
            <div>
                <h3>${escapeHtml(contexto || 'Ejecución')}</h3>
                <p class="ejecucion-meta">
                    <span class="insignia-estado estado-${e.estado}">${ESTADOS_CICLO[e.estado] || e.estado}</span>
                    ${escapeHtml(meta.join(' · '))}
                </p>
                ${tecnico.length ? `<p class="ejecucion-tecnico">${escapeHtml(tecnico.join(' · '))}</p>` : ''}
            </div>
            ${log}
        </div>
        ${error}
        <div class="datos-fila">
            ${dato(e.analizados, 'procesos analizados')}
            ${dato(e.coincidencias, 'coinciden con tus filtros')}
            ${dato(e.nuevos, 'nuevos (no avisados antes)')}
            ${dato(e.enviados, e.fallidos ? `correos enviados · ${numero(e.fallidos)} fallidos` : 'correos enviados')}
        </div>
        ${pintarDescartes(e)}
        ${pintarCoincidencias(datos)}
    `;
    destino.querySelectorAll('.coincidencia-abrir').forEach(b => {
        b.addEventListener('click', () => {
            const p = datos.coincidencias.find(c => c.id === b.dataset.id);
            if (p) openModal(p);
        });
    });
}

function pintarDescartes(e) {
    const descartes = e.descartes;
    if (!descartes || !e.analizados) return '';
    const filas = Object.entries(descartes).sort((a, b) => b[1] - a[1]);
    if (!filas.length) return '';
    return `
        <div class="descartes">
            <h4>Por qué se descartaron los demás</h4>
            <ul>${filas.map(([motivo, n]) => `
                <li>
                    <span class="descarte-barra" style="--parte:${(n / e.analizados * 100).toFixed(1)}%"></span>
                    <span class="descarte-texto"><strong>${numero(n)}</strong> ${escapeHtml(motivo)}</span>
                </li>`).join('')}
            </ul>
        </div>`;
}

function pintarCoincidencias(datos) {
    const lista = datos.coincidencias;
    const nota = datos.detalle_completo ? '' : `
        <p class="coincidencias-nota">Esta ejecución es anterior al registro detallado: se conocen sus
            totales y los procesos nuevos que detectó, pero no el resto de sus coincidencias.</p>`;
    if (!lista.length) {
        return `<div class="coincidencias">${nota}
            <p class="coincidencias-vacio">${datos.detalle_completo
                ? 'Ningún proceso coincidió con tus filtros en este ciclo.'
                : 'Esta ejecución no detectó procesos nuevos.'}</p></div>`;
    }
    return `
        <div class="coincidencias">
            <h4>Procesos que coincidieron</h4>
            ${nota}
            <ul>${lista.map(c => {
                const correo = c.delivery_status || (c.email_status === 'failed' ? 'fallido' : null);
                const estadoCorreo = correo
                    ? `<span class="correo-estado ${CORREOS_CON_PROBLEMA.includes(correo) ? 'es-problema' : ''}">${ESTADOS_CORREO[correo] || correo}</span>`
                    : `<span class="correo-estado es-neutro">${c.is_new ? 'Sin correo' : 'Ya avisado antes'}</span>`;
                return `
                <li class="coincidencia">
                    <button type="button" class="coincidencia-abrir" data-id="${escapeHtml(c.id)}">
                        <span class="coincidencia-nombre">${escapeHtml(c.name)}</span>
                        <span class="coincidencia-meta">${escapeHtml([c.entity_name, [c.city, c.department].filter(Boolean).join(', ')].filter(Boolean).join(' · '))}</span>
                    </button>
                    <span class="coincidencia-valor">${formatearPesos(c.base_price)}</span>
                    <span class="coincidencia-lado">
                        ${c.is_new ? '<span class="insignia-nuevo">Nuevo</span>' : ''}
                        ${estadoCorreo}
                        ${c.match_reason ? `<span class="coincidencia-motivo">${escapeHtml(c.match_reason)}</span>` : ''}
                    </span>
                </li>`;
            }).join('')}
            </ul>
        </div>`;
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

    // El cron corre 4 veces al dia; el badge se revisa cada minuto.
    setInterval(() => {
        if (document.visibilityState === 'visible') cargarNotificaciones();
    }, 60000);

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

const TIPOS_NOTIFICACION = {
    oportunidad: 'Oportunidad nueva',
    ciclo_fallido: 'Ciclo con fallo',
    ciclo_omitido: 'Ciclo no ejecutado',
    correo_problema: 'Correo no entregado'
};

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
            <span class="panel-vacio-icono"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg></span>
            <strong>Sin novedades en los últimos 14 días</strong>
            <span>Cuando el cron encuentre una oportunidad que coincida, aparecerá aquí.</span>
        </div>`;
        if (nota) nota.textContent = '';
        return;
    }

    contenedor.innerHTML = lista.map(n => {
        const alerta = n.tipo !== 'oportunidad';
        let meta;
        if (alerta) {
            meta = n.detalle || '';
        } else {
            const correo = n.correo ? ` · Correo: ${ESTADOS_CORREO[n.correo] || n.correo}` : '';
            meta = `${n.entidad || ''} · ${formatearPesos(n.valor_base)}${correo}`;
        }
        return `
        <button class="notif-item ${n.leida ? 'leida' : 'sin-leer'} ${alerta ? 'es-alerta' : ''}"
                data-id="${escapeHtml(n.id)}" type="button">
            <span class="notif-punto" aria-hidden="true"></span>
            <span class="notif-cuerpo">
                <span class="notif-tipo">${TIPOS_NOTIFICACION[n.tipo] || ''}</span>
                <span class="notif-titulo">${escapeHtml(n.titulo)}</span>
                <span class="notif-meta">${escapeHtml(meta)}</span>
                <span class="notif-fecha">${formatearFecha(n.fecha)}</span>
            </span>
        </button>`;
    }).join('');

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

/** Una oportunidad abre su proceso; una alerta lleva a la actividad del cron. */
function abrirDetalleNotificacion(notif) {
    const panel = document.getElementById('panel-notificaciones');
    if (panel) panel.hidden = true;
    const boton = document.getElementById('btn-campana');
    if (boton) boton.setAttribute('aria-expanded', 'false');

    if (notif.tipo === 'oportunidad') {
        const [city, department] = (notif.ubicacion || '').split(', ');
        openModal({
            id: notif.proceso_id,
            name: notif.titulo,
            entity_name: notif.entidad,
            city, department,
            base_price: notif.valor_base,
            modality: notif.modalidad,
            url: notif.url,
            delivery_status: notif.correo
        });
        return;
    }
    if (puede('ver_actividad')) abrirModulo('actividad');
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

    const cancelar = document.getElementById('btn-cancelar-usuario');
    const rol = document.getElementById('uf-rol');
    const estado = document.getElementById('uf-estado');

    if (nuevo) nuevo.addEventListener('click', () => abrirFormularioUsuario(null));
    if (cerrar) cerrar.addEventListener('click', cerrarFormularioUsuario);
    if (cancelar) cancelar.addEventListener('click', cerrarFormularioUsuario);
    if (guardar) guardar.addEventListener('click', guardarUsuario);
    if (rol) rol.addEventListener('change', actualizarAyudasUsuario);
    if (estado) estado.addEventListener('change', actualizarAyudasUsuario);
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) cerrarFormularioUsuario();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('active')) cerrarFormularioUsuario();
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
    document.getElementById('uf-contrasena').value = '';

    const ayudaClave = document.getElementById('uf-contrasena-ayuda');
    if (ayudaClave) {
        ayudaClave.textContent = usuario
            ? 'Déjala vacía para conservar la contraseña actual.'
            : 'Mínimo 8 caracteres. El usuario la necesitará para entrar.';
    }

    if (titulo) titulo.textContent = usuario ? 'Editar usuario' : 'Crear usuario';
    const sub = document.getElementById('user-modal-sub');
    if (sub) {
        sub.textContent = usuario
            ? `Cambia los datos de acceso de ${usuario.nombre}.`
            : 'Entrará con este correo y la contraseña que definas.';
    }
    const guardar = document.getElementById('btn-guardar-usuario');
    if (guardar) guardar.textContent = usuario ? 'Guardar cambios' : 'Crear usuario';

    const campoClave = document.getElementById('uf-contrasena');
    campoClave.type = 'password';
    campoClave.placeholder = usuario ? 'Sin cambios' : '';
    campoClave.required = !usuario;

    actualizarAyudasUsuario();
    if (error) error.hidden = true;
    modal.classList.add('active');
    document.getElementById('uf-nombre').focus();
}

/** Explica, bajo cada selector, qué implica la opción elegida. */
function actualizarAyudasUsuario() {
    const rol = document.getElementById('uf-rol').value;
    const estado = document.getElementById('uf-estado').value;
    const ayudaRol = document.getElementById('uf-rol-ayuda');
    const ayudaEstado = document.getElementById('uf-estado-ayuda');
    if (ayudaRol) {
        ayudaRol.textContent = rol === 'admin'
            ? 'Además monitorea SECOP II, edita la configuración y gestiona usuarios.'
            : 'Consulta métricas, arquitectura y notificaciones.';
    }
    if (ayudaEstado) {
        ayudaEstado.textContent = estado === 'activo'
            ? 'Puede iniciar sesión.'
            : 'No podrá iniciar sesión hasta que lo actives.';
    }
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

    // Al crear es obligatoria; al editar, vacia significa "no la cambies".
    const contrasena = document.getElementById('uf-contrasena').value;
    if (contrasena) datos.contrasena = contrasena;

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
    const titulo = document.getElementById('modal-title');
    if (titulo) titulo.textContent = 'Proceso en SECOP II';

    const correo = process.delivery_status
        || (process.email_status === 'failed' ? 'fallido' : null);
    const fila = (etiqueta, valor) => valor
        ? `<tr><td><strong>${etiqueta}</strong></td><td>${valor}</td></tr>` : '';

    content.innerHTML = `
        <h4 class="modal-proceso-titulo">${escapeHtml(process.name)}</h4>
        <p class="modal-proceso-meta">${escapeHtml(process.id)} · ${escapeHtml(process.entity_name)}</p>
        <table class="tabla-datos modal-proceso-tabla">
            ${fila('Departamento', escapeHtml(process.department))}
            ${fila('Ciudad', escapeHtml(process.city))}
            ${fila('Valor base', `<span class="price-text">${formatearPesos(process.base_price)}</span>`)}
            ${fila('Modalidad', escapeHtml(process.modality))}
            ${fila('Por qué coincidió', escapeHtml(process.match_reason))}
            ${fila('Correo al cliente', correo ? escapeHtml(ESTADOS_CORREO[correo] || correo) : '')}
        </table>
        ${process.url && /^https?:\/\//.test(process.url) ? `
        <div class="modal-proceso-acciones">
            <a href="${escapeHtml(process.url)}" target="_blank" rel="noopener" class="btn-secundario">Abrir en SECOP II</a>
        </div>` : ''}
    `;

    modal.classList.add('active');
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
