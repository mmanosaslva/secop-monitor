# 📋 Plan de Implementación - Continuación Proyecto SECOP

## 🎯 Resumen Ejecutivo

**Objetivo**: Adaptar el MVP existente para cumplir con los requisitos del cliente:
- Foco en región Caribe, **solo mínima cuantía** (≤ $70,036,200 COP = 40 SMLMV 2026)
- Productos: dotación, uniformes, elementos de protección personal (EPP)
- Certificaciones: mujer líder + equidad de género (ventaja competitiva)
- Stack 100% free
- Solo notificaciones por correo (sin WhatsApp)
- Capacidad cliente: 3,500 prensas/mes, facturación $35-47M COP/mes

**Stack Actual (100% Free)**:
| Componente | Tecnología | Tier |
|---|---|---|
| Lenguaje | Python 3.11 | - |
| HTTP Client | httpx | - |
| Base de datos | Neon PostgreSQL | Free (0.5 GB) |
| Email | Brevo API | Free (300 emails/día) |
| Cron | GitHub Actions | Free |
| API SECOP | datos.gov.co (dataset p6dx-8zbt) | Datos abiertos |

**Campos SECOP II relevantes**:
| Campo API | Descripción | Uso |
|---|---|---|
| `modalidad_de_contratacion` | Modalidad de contratación | Filtro mínima cuantía (normalizar texto) |
| `precio_base` | Precio proyectado (COP) | Filtro cuantía ≤ $70,036,200 |
| `departamento_entidad` | Departamento entidad | Filtro región Caribe |
| `nombre_del_procedimiento` | Nombre proceso | Filtro keywords + certificaciones |
| `descripci_n_del_procedimiento` | Descripción proceso | Filtro keywords + certificaciones |
| `codigo_principal_de_categoria` | Código UNSPSC | Filtro categoría producto |

---

## 🎯 Resumen de Decisiones Tomadas

| Decisión | Estado |
|---|---|
| ✅ Departamentos del Caribe | 7 departamentos configurados |
| ✅ Palabras clave | Dotación, uniformes, EPP + certificaciones |
| ✅ Solo Mínima Cuantía | Sin Selección Abreviada (cliente decide) |
| ✅ Tope cuantía | $70,036,200 COP (40 SMLMV 2026) |
| ✅ Normalización modalidad | SECOP inconsistente (tildes, mayúsculas) → normalizar texto |
| ✅ Cron job 4 ciclos | 00:45, 10:00, 13:30, 20:00 COT |
| ✅ Badges en email | Mujer Líder, Equidad de Género, PYME |
| ✅ Sección explicativa en email | Texto descriptivo de ventajas |
| ✅ Preferencia como ventaja | No requisito, sino puntos extras |

---

## 📁 Archivos a Modificar

### 1. `config/client_config.json` - Configuración del Cliente

**Cambios**:
- Agregar departamentos del Caribe (7 departamentos)
- Agregar palabras clave: dotación, EPP, protección personal
- Agregar palabras clave de certificaciones
- Solo modalidad: Mínima Cuantía (sin Selección Abreviada)
- Agregar max_cuantia: $70,036,200 COP (40 SMLMV 2026)

**Estructura final**:
```json
{
  "name": "Cliente Textil Caribe",
  "email": "meriyei.manfer@gmail.com",
  "phone_whatsapp": "+573001234567",
  "departments": [
    "Atlantico", "Bolivar", "Magdalena", "Cordoba", 
    "Sucre", "La Guajira", "Cesar"
  ],
  "keywords": [
    "uniforme", "uniformes", "ropa deportiva", "vestuario",
    "confeccion", "prendas", "textil", "sportswear",
    "camiseta", "pantalon", "chaqueta", "calzado",
    "dotacion", "dotación", "epp", "elementos de proteccion personal",
    "proteccion personal", "equipo de proteccion"
  ],
  "unspsc_codes": [
    "V1.53102700", "V1.53102710", "V1.53102715", "V1.53102720",
    "V1.53102900", "V1.53102901", "V1.53102902", "V1.53100000",
    "V1.53101500", "V1.53101600", "V1.53101800", "V1.53103000",
    "V1.53110000", "V1.53111600"
  ],
  "certification_keywords": [
    "equidad de genero", "equidad de género",
    "mujer lider", "mujer líder",
    "empresa de mujeres", "emprendimiento femenino",
    "genero", "género"
  ],
  "modalidad": "minima cuantia",
  "max_cuantia": 70036200
}
```

**Nota**: `modalidad` es string (no array) porque cliente solo participa en mínima cuantía. `max_cuantia` en COP.

---

### 2. `src/database/connection.py` - Esquema de Base de Datos

**Cambios**:
- Agregar campos a tabla `processes`: modalidad_seleccion, cuantia, favorece_mujer_lider, favorece_pyme, requiere_equidad_genero
- Agregar campos a tabla `client_config`: certification_keywords, modalidad, max_cuantia

**Migración SQL**:
```sql
-- Campos nuevos en processes
ALTER TABLE processes ADD COLUMN IF NOT EXISTS modalidad_seleccion TEXT;
ALTER TABLE processes ADD COLUMN IF NOT EXISTS cuantia NUMERIC;
ALTER TABLE processes ADD COLUMN IF NOT EXISTS favorece_mujer_lider BOOLEAN DEFAULT FALSE;
ALTER TABLE processes ADD COLUMN IF NOT EXISTS favorece_pyme BOOLEAN DEFAULT FALSE;
ALTER TABLE processes ADD COLUMN IF NOT EXISTS requiere_equidad_genero BOOLEAN DEFAULT FALSE;

-- Campos nuevos en client_config
ALTER TABLE client_config ADD COLUMN IF NOT EXISTS certification_keywords JSONB DEFAULT '[]';
ALTER TABLE client_config ADD COLUMN IF NOT EXISTS modalidad TEXT DEFAULT 'minima cuantia';
ALTER TABLE client_config ADD COLUMN IF NOT EXISTS max_cuantia NUMERIC DEFAULT 70036200;
```

---

### 3. `src/filters/engine.py` - Motor de Filtros

**Cambios**:
- Agregar filtro por modalidad (normalizado, sin tildes, lowercase)
- Agregar filtro por cuantía (precio_base ≤ max_cuantia)
- Agregar detección de certificaciones en nombre/descripción
- Agregar palabras clave de certificación como filtro adicional

**Nota SECOP**: Campo `modalidad_de_contratacion` viene inconsistente (tildes, mayúsculas). Normalizar con `unicodedata` antes de comparar.

**Nueva estructura**:
```python
import unicodedata

class FilterEngine:
    def __init__(self, config: Dict):
        self.departments = config.get("departments", [])
        self.keywords = [kw.upper() for kw in config.get("keywords", [])]
        self.unspsc_codes = config.get("unspsc_codes", [])
        self.certification_keywords = [kw.upper() for kw in config.get("certification_keywords", [])]
        self.modalidad = config.get("modalidad", "minima cuantia")  # string, no array
        self.max_cuantia = config.get("max_cuantia", 70036200)  # 40 SMLMV 2026

    def normalize_text(self, text: str) -> str:
        """Quita tildes, lowercase, espacios extra"""
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        return text.lower().strip()

    def matches(self, process: Dict) -> bool:
        # Filtro 1: Departamento
        if process.get("department") not in self.departments:
            return False

        # Filtro 2: Modalidad (normalizada)
        modality_raw = process.get("modality", "")
        modality_normalized = self.normalize_text(modality_raw)
        if self.modalidad not in modality_normalized:
            return False

        # Filtro 3: Cuantía (precio_base ≤ max_cuantia)
        precio_base = process.get("base_price", 0)
        if precio_base and precio_base > self.max_cuantia:
            return False

        # Filtro 4: Código UNSPSC
        if process.get("unspsc_code") in self.unspsc_codes:
            return True

        # Filtro 5: Palabras clave del producto
        name_upper = process.get("name", "").upper()
        desc_upper = process.get("description", "").upper()
        
        for kw in self.keywords:
            if kw in name_upper or kw in desc_upper:
                return True

        # Filtro 6: Palabras clave de certificación
        for kw in self.certification_keywords:
            if kw in name_upper or kw in desc_upper:
                return True

        return False

    def detect_certifications(self, process: Dict) -> Dict:
        """Detecta certificaciones mencionadas en el proceso"""
        name_upper = process.get("name", "").upper()
        desc_upper = process.get("description", "").upper()
        text = f"{name_upper} {desc_upper}"
        
        return {
            "favorece_mujer_lider": any(kw in text for kw in ["MUJER LIDER", "MUJER LÍDER", "EMPRESA DE MUJERES"]),
            "favorece_pyme": any(kw in text for kw in ["PYME", "PEQUEÑA EMPRESA", "MICROEMPRESA"]),
            "requiere_equidad_genero": any(kw in text for kw in ["EQUIDAD DE GENERO", "EQUIDAD DE GÉNERO", "GENERO", "GÉNERO"]),
        }
```

---

### 4. `src/notifications/email.py` - Email con Badges

**Cambios**:
- Agregar badges visuales (Mínima Cuantía, Mujer Líder, Equidad de Género, PYME)
- Agregar sección explicativa de ventaja competitiva
- Formato responsive para móvil
- Sin badge Selección Abreviada (cliente no participa)

**Nueva estructura del email**:
```
┌─────────────────────────────────────────────────────────────┐
│  Nueva Oportunidad SECOP II                                  │
├─────────────────────────────────────────────────────────────┤
│  🏷️ Mínima Cuantía  🏷️ Preferencia: Mujer Líder            │
├─────────────────────────────────────────────────────────────┤
│  Entidad          │ Ministerio de Salud                     │
│  Objeto           │ Dotación de uniformes y EPP para         │
│                   │ personal administrativo                  │
│  Ubicación        │ Barranquilla, Atlántico                  │
│  Valor base       │ $45,000,000 COP                         │
│  Fecha publicación│ 2026-09-01                              │
│  Fecha límite     │ 2026-09-15                              │
│  Tipo contrato    │ Servicios                               │
│  Modalidad        │ Mínima Cuantía                          │
│  ID Proceso       │ 2026-SECOP-001                          │
├─────────────────────────────────────────────────────────────┤
│  ✅ Ventaja competitiva                                     │
│  Este proceso valora empresas lideradas por mujeres y        │
│  equidad de género. Sus certificaciones le dan preferencia. │
├─────────────────────────────────────────────────────────────┤
│  [ Ver Proceso en SECOP II ]                                │
└─────────────────────────────────────────────────────────────┘
```

---

### 5. `.github/workflows/secop.yml` - Cron Job

**Cambios**:
- 4 ciclos diarios (no3)
- 00:45 COT: nocturno, captura publicaciones madrugada
- 10:00 COT: mañana, pre actualización SECOP
- 13:30 COT: post actualización SECOP (12:00-14:00)
- 20:00 COT: noche, segunda oportunidad

**Nuevo cron**:
```yaml
on:
  schedule:
    - cron: '45 5 * * *'   # 00:45 COT (05:45 UTC) - nocturno
    - cron: '0 15 * * *'   # 10:00 COT (15:00 UTC) - mañana
    - cron: '30 18 * * *'  # 1:30 PM COT (18:30 UTC) - post actualización
    - cron: '0 1 * * *'    # 8:00 PM COT (01:00 UTC) - noche
  workflow_dispatch:
```

---

### 6. `src/main.py` - Flujo Principal

**Cambios**:
- Integrar detección de certificaciones
- Pasar certificaciones al email
- Guardar certificaciones en BD

**Flujo actualizado**:
```python
def main():
    # ... código existente ...
    
    engine = FilterEngine(config)
    matched = engine.filter_batch(processes)
    
    # Detectar certificaciones para cada proceso
    for process in matched:
        certs = engine.detect_certifications(process)
        process["certifications"] = certs
        
        # Guardar en BD con certificaciones
        save_process(conn, process, h, certs)
    
    # Enviar emails con badges
    for process in matched:
        emailer.send(process, client_email, process.get("certifications", {}))
```

---

## 📊 Diagrama de Flujo

```
GitHub Actions (cron: 00:45, 10:00, 13:30, 20:00 COT)
         │
         ▼
src/main.py
         │
         ├──► src/config.py (carga client_config.json)
         │
         ├──► src/sources/secop.py
         │       │
         │       └──► datos.gov.co API
         │            (filtrado por departamento + estado)
         │
         ├──► src/filters/engine.py
         │       │
         │       ├── Filtro 1: Departamento (7 del Caribe)
         │       ├── Filtro 2: Modalidad (normalizada: "minima cuantia")
         │       ├── Filtro 3: Cuantía (precio_base ≤ $70,036,200)
         │       ├── Filtro 4: Código UNSPSC
         │       ├── Filtro 5: Palabras clave (dotación, uniformes, EPP)
         │       └── Filtro 6: Certificaciones (bonus)
         │
         ├──► src/database/models.py
         │       │
         │       ├── Guardar proceso con certificaciones
         │       └── Deduplicación por hash
         │
         └──► src/notifications/email.py
                 │
                 ├── Badge: Mínima Cuantía
                 ├── Badge: Preferencia: Mujer Líder
                 ├── Badge: Equidad de Género
                 ├── Badge: PYME Favorable
                 └── Sección: Ventaja competitiva
```

---

## 📅 Cronograma de Implementación

| Fase | Archivo | Descripción | Tiempo Est. |
|---|---|---|---|
| 1 | `config/client_config.json` | Actualizar configuración del cliente | 5 min |
| 2 | `src/database/connection.py` | Agregar campos a esquema | 10 min |
| 3 | `src/filters/engine.py` | Implementar filtros, normalización y certificaciones | 25 min |
| 4 | `src/notifications/email.py` | Agregar badges y sección explicativa | 25 min |
| 5 | `.github/workflows/secop.yml` | Actualizar cron a4 ciclos | 5 min |
| 6 | `src/main.py` | Integrar flujo completo | 15 min |
| 7 | Pruebas | Verificar funcionamiento | 20 min |
| **Total** | | | **~105 min** |

---

## ✅ Criterios de Aceptación

1. **Filtros**: El sistema filtra por departamentos del Caribe, modalidad mínima cuantía (normalizada), cuantía ≤ $70,036,200 COP, palabras clave de producto y certificaciones
2. **Certificaciones**: El sistema detecta "mujer líder", "equidad de género" y "PYME" en nombre/descripción del proceso
3. **Email**: Los emails incluyen badges visuales y sección explicativa de ventaja competitiva
4. **Cron job**: El sistema ejecuta a las 00:45, 10:00, 1:30 PM y 8:00 PM COT (4 ciclos)
5. **BD**: Los procesos se guardan con campos de certificaciones
6. **Free tier**: Todo funciona sin costo (GitHub Actions, Neon, Brevo)
7. **Normalización**: Filtro modalidad maneja tildes, mayúsculas, variaciones de SECOP

---

## 🔧 Comandos Útiles

```bash
# Ejecutar localmente
python -m src.main

# Ejecutar en modo stealth (sin enviar emails)
STEALTH_MODE=true python -m src.main

# Ejecutar pruebas
pytest tests/

# Ver logs
tail -f logs/secop.log
```

---

## 📝 Notas Adicionales

- **Mínima cuantía**: Modalidad para contratos ≤ 40 SMLMV ($70,036,200 COP en 2026). Proceso ágil, menos competencia. Cliente solo participa en esta modalidad.
- **Normalización SECOP**: Campo `modalidad_de_contratacion` viene inconsistente (tildes, mayúsculas). Usar `unicodedata.normalize('NFD')` para quitar tildes + lowercase antes de comparar.
- **Certificaciones**: La clienta indicó que sus certificaciones "les dan preferencia" (no son requisitos excluyentes). Se implementan como badges informativos.
- **Actualización SECOP**: Los datos se actualizan entre 12:00-14:00 COT. El cron job a las 1:30 PM captura esta actualización.
- **Capacidad cliente**: 3,500 prensas/mes, facturación $35-47M COP/mes. Encaja en contratos de mínima cuantía.
- **API SECOP**: Dataset `p6dx-8zbt` tiene57 campos. Usamos ~16 relevantes. Campo `precio_base` = cuantía del contrato.

---

**Última actualización**: 2026-09-07
**Autor**: Equipo de desarrollo
**Estado**: Pendiente de implementación
