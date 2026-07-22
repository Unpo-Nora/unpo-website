"""
Comandos de mantenimiento ejecutables fuera del proceso web (Etapa 1D).

Se ejecutan como procesos/cron separados, NUNCA como tareas de fondo dentro de FastAPI
(Render puede reiniciar o escalar el servicio web y duplicar el trabajo). Ver
`whatsapp_maintenance` para el reprocesador y la purga.
"""
