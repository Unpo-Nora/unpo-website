# UNPO & NORA Digital Ecosystem

Este proyecto es un sistema integral para la gestión de leads, CRM y portal administrativo para las marcas UNPO (B2B) y NORA (B2C).

## 🚀 Requisitos Previos

Para ejecutar este sistema en cualquier computadora, el gerente o usuario solo necesita tener instalado:

1.  **Docker Desktop**: Es la herramienta que contiene todo el entorno (Base de datos, Servidor y Web).
    - Descarga: [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)
2.  **Git** (Opcional, si se descarga el código desde un repositorio).

## 🛠️ Cómo Iniciar el Proyecto

1.  **Descargar el código**: Descomprimir el archivo ZIP o clonar el repositorio.
2.  **Abrir una terminal**: Situarse en la carpeta raíz del proyecto (`UNPO_NORA_System`).
3.  **Ejecutar el comando**:
    ```bash
    docker-compose up -d --build
    ```
    *Este comando descargará las imágenes, configurará la base de datos y encenderá los servidores automáticamente.*

## 🌐 Accesos Locales

Una vez que los contenedores "Healthy", podrás acceder a:

- **Ecosistema Web (Público)**: [http://localhost:3000](http://localhost:3000)
- **Panel Administrativo / CRM**: [http://localhost:3000/admin/login](http://localhost:3000/admin/login)
- **Documentación de la API**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Gestor de Base de Datos (Adminer)**: [http://localhost:8081](http://localhost:8081)

## 🔑 Credenciales de Acceso (Staff)

Las credenciales de staff **no se versionan en este repositorio**. Solicitarlas al administrador del sistema por un canal seguro (nunca por commit, chat público ni documentación).

> Nota de seguridad: versiones anteriores de este archivo contenían contraseñas reales. Esas credenciales deben considerarse comprometidas y rotarse.

## 📦 Estructura del Proyecto

- `/frontend`: Aplicación web interactiva (Next.js).
- `/backend`: Servidor de lógica y API (FastAPI).
- `docker-compose.yml`: Archivo de orquestación mágica.
- `.env`: Variables de configuración (Base de datos, Meta API).
