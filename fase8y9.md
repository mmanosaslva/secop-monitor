# Fase 8-9: Verificación y Producción

## Fase 8: Verificar GitHub Actions (stealth mode)

**Objetivo:** Confirmar que el cron ejecuta 4x/dia y registra en BD.

### Pasos

1. Ejecutar workflow manual
   ```bash
   gh workflow run secop.yml
   ```

2. Verificar ejecución
   ```bash
   gh run list --limit 5
   ```

3. Verificar Neon DB
   ```bash
   python -c "
   from src.database.connection import get_connection
   from src.config import DATABASE_URL
   conn = get_connection(DATABASE_URL)
   cursor = conn.cursor()
   cursor.execute('SELECT * FROM job_runs ORDER BY started_at DESC LIMIT 5')
   for row in cursor.fetchall(): print(row)
   conn.close()
   "
   ```

4. Confirmar `notifications_sent = 0` (stealth mode)
5. Verificar logs muestran procesos encontrados

### Criterio éxito
- 1+ jobs con `status='success'`
- `processes_found > 0`
- `notifications_sent = 0`

---

## Fase 9: Producción

**Objetivo:** Emails llegan a cliente real, formato correcto.

### Decisiones pendientes

| Pregunta | Opciones |
|----------|----------|
| Dominio email | Propio ($10/año) vs sin dominio (spam 30-40%) |
| Email remitente | Profesional vs `whoami_jay@proton.me` |

### Pasos

1. Decidir dominio email
2. Configurar sender en Brevo
3. Actualizar GitHub Secrets
   ```bash
   gh secret set SENDER_EMAIL --body "notificaciones@tudominio.com"
   gh secret set ADMIN_EMAIL --body "meriyei.manfer@gmail.com"
   gh secret set STEALTH_MODE --body "false"
   ```
4. Ejecutar workflow manual
5. Verificar email llega a inbox
6. Cliente confirma formato

### Criterio éxito
- Email con badges y ventaja competitiva llega a `meriyei.manfer@gmail.com`
- Sin errores en logs
- Cliente aprueba formato

---

## Notas técnicas

- `.env` está en `.gitignore` ✅
- GitHub Actions secrets ya configurados ✅
- 46/46 tests pasando ✅
- Cron UTC correcto: 00:45, 10:00, 13:30, 20:00 COT ✅
