# Infra AWS — Terraform (UNPO / NORA)

Estructura base de Terraform para el despliegue en AWS. Corresponde a la etapa
**6-C2** del plan de separación/infra.

> ⚠️ **Estado: esqueleto. NADA fue aplicado.**
> No se ejecutó `terraform init`, `plan` ni `apply`. No existen recursos en AWS
> creados por este código. Es solo estructura + definiciones para revisión.

## Alcance de 6-C2 (lo que hay acá)

Se prioriza lo que **no depende del dominio NORA definitivo** (decisión congelada
en la matriz 6-C1-B):

- Convención de estructura, naming y tags.
- `modules/network` — VPC, subnets públicas/privadas, IGW, NAT, route tables.
- `modules/security` — security groups base (ALB / app / db).
- `modules/ecr` — repositorios de imágenes (backend / frontend).
- `modules/iam` — **esqueleto** (roles ECS se completan en 6-C3).
- `modules/observability` — **esqueleto** (log groups / alarmas en 6-C3).
- `environments/staging` — entorno que cablea los módulos.

## Fuera de alcance (diferido a 6-C3 o más adelante)

Route 53, ACM, ALB/listeners, ECS services/tasks reales, RDS productiva, S3 +
CloudFront de media, dominios NORA (`<dominio-nora>`, `crm.<dominio-nora>`,
`api.<dominio-nora>`), backend remoto de state, integración Meta/WhatsApp,
GitHub Actions y cualquier secreto real.

## Convención de naming

Prefijo común: `${project}-${environment}` (ej.: `unpo-nora-staging`).
Cada recurso agrega su sufijo funcional: `-vpc`, `-alb-sg`, `-backend`, etc.

## Tags

Todos los recursos heredan `default_tags` del provider + un `tags` explícito por
módulo. Base mínima: `Project`, `Environment`, `ManagedBy = terraform`,
`Scope = 6-C2-bootstrap`. Se puede extender con `extra_tags`.

## Estado (state)

Por ahora **state local**. El backend remoto (S3 + DynamoDB lock) queda
**comentado** en `environments/staging/main.tf` y se define en 6-C3.
No configurar el backend con valores reales todavía.

## Uso (cuando se autorice — NO ahora)

```bash
cd infra/terraform/environments/staging
cp terraform.tfvars.example terraform.tfvars   # editar; NO commitear el real
# terraform init    # ⛔ requiere aviso/autorización previa
# terraform plan    # ⛔ requiere aviso/autorización previa
# terraform apply   # ⛔ no autorizado en 6-C2
```

## Roadmap 6-C3 (próxima etapa)

- Backend remoto de state (S3 + DynamoDB).
- ALB + listeners + target groups (host-based routing UNPO).
- ECS cluster + services (backend/frontend) + task/exec roles (módulo `iam`).
- Log groups + alarmas (módulo `observability`).
- ECR: se reutiliza lo definido acá.
- Rama NORA (Route 53 / ACM / hosts) queda gated por el registro del dominio NORA.
