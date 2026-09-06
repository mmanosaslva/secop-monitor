# 📋 Plan de Implementación - Continuación Proyecto SECOP

## 🎯 Resumen Ejecutivo

**Objetivo**: Adaptar el MVP existente para cumplir con los requisitos del cliente:
- Foco en región Caribe, mínima cuantía
- Productos: dotación, uniformes, elementos de protección personal (EPP)
- Certificaciones: mujer líder + equidad de género (ventaja competitiva)
- Stack 100% free
- Solo notificaciones por correo (sin WhatsApp)

**Stack Actual (100% Free)**:
| Componente | Tecnología | Tier |
|---|---|---|
| Lenguaje | Python 3.11 | - |
| HTTP Client | httpx | - |
| Base de datos | Neon PostgreSQL | Free (0.5 GB) |
| Email | Brevo API | Free (300 emails/día) |
| Cron | GitHub Actions | Free |
| API SECOP | datos.gov.co | Datos abiertos |

---

## 🎯 Resumen de Decisiones Tomadas

| Decisión | Estado |
|---|---|
| ✅ Departamentos del Caribe | 7 departamentos configurados |
| ✅ Palabras clave | Dotación, uniformes, EPP + certificaciones |
| ✅ Mínima cuantía + Selección Abreviada | Ambas modalidades incluidas |
| ✅ Cron job 2:30 PM | Alineado con actualización SECOP |
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
- Agregar modalidades: Mínima Cuantía, Selección Abreviada

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
  "modalidades": [
    "Mínima Cuantía", "Selección Abreviada"
  ]
}
```

---

### 2. `src/database/connection.py` - Esquema de Base de Datos

**Cambios**:
- Agregar campos a tabla `processes`: modalidad_seleccion, cuantia, favorece_mujer_lider, favorece_pyme, requiere_equidad_genero
- Agregar campos a tabla `client_config`: certification_keywords, modalidades

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
ALTER TABLE client_config ADD COLUMN IF NOT EXISTS modalidades JSONB DEFAULT '[]';
```

---

### 3. `src/filters/engine.py` - Motor de Filtros

**Cambios**:
- Agregar filtro por modalidad (Mínima Cuantía / Selección Abreviada)
- Agregar detección de certificaciones en nombre/descripción
- Agregar palabras clave de certificación como filtro adicional

**Nueva estructura**:
```python
class FilterEngine:
    def __init__(self, config: Dict):
        self.departments = config.get("departments", [])
        self.keywords = [kw.upper() for kw in config.get("keywords", [])]
        self.unspsc_codes = config.get("unspsc_codes", [])
        self.certification_keywords = [kw.upper() for kw in config.get("certification_keywords", [])]
        self.modalidades = config.get("modalidades", [])

    def matches(self, process: Dict) -> bool:
        # Filtro 1: Departamento
        if process.get("department") not in self.departments:
            return False

        # Filtro 2: Modalidad
        if self.modalidades and process.get("modality") not in self.modalidades:
            return False

        # Filtro 3: Código UNSPSC
        if process.get("unspsc_code") in self.unspsc_codes:
            return True

        # Filtro 4: Palabras clave del producto
        name_upper = process.get("name", "").upper()
        desc_upper = process.get("description", "").upper()
        
        for kw in self.keywords:
            if kw in name_upper or kw in desc_upper:
                return True

        # Filtro 5: Palabras clave de certificación
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
- Agregar badges visuales (Mínima Cuantía, Selección Abreviada, Mujer Líder, Equidad de Género, PYME)
- Agregar sección explicativa de ventaja competitiva
- Formato responsive para móvil

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
- Actualizar horarios para alinear con actualización SECOP (12:00-14:00 COT)
- Nuevo horario: 10:00 AM, 1:30 PM, 8:00 COT

**Nuevo cron**:
```yaml
on:
  schedule:
    - cron: '0 15 * * *'  # 10:00 COT (15:00 UTC)
    - cron: '30 18 * * *' # 1:30 PM COT (18:30 UTC)
    - cron: '0 1 * * *'   # 8:00 PM COT (01:00 UTC)
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
GitHub Actions (cron: 10AM, 1:30PM, 8PM COT)
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
         │       ├── Filtro 2: Modalidad (Mínima Cuantía / Selección Abreviada)
         │       ├── Filtro 3: Código UNSPSC
         │       ├── Filtro 4: Palabras clave (dotación, uniformes, EPP)
         │       └── Filtro 5: Certificaciones (bonus)
         │
         ├──► src/database/models.py
         │       │
         │       ├── Guardar proceso con certificaciones
         │       └── Deduplicación por hash
         │
         └──► src/notifications/email.py
                 │
                 ├── Badge: Mínima Cuantía
                 ├── Badge: Selección Abreviada
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
| 3 | `src/filters/engine.py` | Implementar filtros y certificaciones | 20 min |
| 4 | `src/notifications/email.py` | Agregar badges y sección explicativa | 25 min |
| 5 | `.github/workflows/secop.yml` | Actualizar cron job | 5 min |
| 6 | `src/main.py` | Integrar flujo completo | 15 min |
| 7 | Pruebas | Verificar funcionamiento | 20 min |
| **Total** | | | **~100 min** |

---

## ✅ Criterios de Aceptación

1. **Filtros**: El sistema filtra por departamentos del Caribe, modalidad (Mínima Cuantía / Selección Abreviada), palabras clave de producto y certificaciones
2. **Certificaciones**: El sistema detecta "mujer líder", "equidad de género" y "PYME" en nombre/descripción del proceso
3. **Email**: Los emails incluyen badges visuales y sección explicativa de ventaja competitiva
4. **Cron job**: El sistema ejecuta a las 10:00 AM, 1:30 PM y 8:00 PM COT
5. **BD**: Los procesos se guardan con campos de certificaciones
6. **Free tier**: Todo funciona sin costo (GitHub Actions, Neon, Brevo)

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

- **Mínima cuantía**: Modalidad para contratos ≤10% de la menor cuantía de la entidad. Proceso ágil (1 día), menos competencia.
- **Selección abreviada**: Modalidad para menor cuantía. Más competencia que mínima cuantía pero menos que licitación pública.
- **Certificaciones**: La clienta indicó que sus certificaciones "les dan preferencia" (no son requisitos excluyentes). Se implementan como badges informativos.
- **Actualización SECOP**: Los datos se actualizan entre 12:00-14:00 COT. El cron job a las 1:30 PM captura esta actualización.

---

**Última actualización**: 2026-09-06
**Autor**: Equipo de desarrollo
**Estado**: Pendiente de implementación
