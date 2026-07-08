# Módulo: iam — ESQUELETO
#
# 6-C2 NO crea recursos IAM: los roles reales cuelgan de los servicios ECS,
# que están explícitamente diferidos. Se deja la estructura lista para 6-C3.
#
# TODO 6-C3:
#   - aws_iam_role.ecs_task_execution
#       + attach AmazonECSTaskExecutionRolePolicy (pull ECR + escribir logs)
#   - aws_iam_role.ecs_task
#       + política mínima de la app (S3 media, Secrets Manager, etc.)
#   - separar permisos por marca si la API se separa (api.<dominio-nora>)
#
# Sin recursos por ahora. Las variables quedan declaradas para no romper la
# llamada desde environments/staging.
