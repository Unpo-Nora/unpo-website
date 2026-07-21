"""
Capa de servicios de dominio.

Lógica de negocio reutilizable que no pertenece ni a los routers (transporte HTTP)
ni a `app/crud.py` (helpers de acceso a datos del dominio comercial histórico).
Se introduce con el módulo WhatsApp Cloud API (Etapa 1C) para mantener el router
delgado y poder testear la lógica sin levantar HTTP.
"""
