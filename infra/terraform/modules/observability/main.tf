# Módulo: observability — ESQUELETO
#
# 6-C2 NO crea recursos: log groups, métricas y alarmas van atados a los
# servicios ECS y al ALB, que están diferidos. Estructura lista para 6-C3.
#
# TODO 6-C3:
#   - aws_cloudwatch_log_group por servicio (retención configurable)
#   - alarmas ALB 5xx / target health
#   - alarmas CPU / memoria de los servicios ECS
#   - dashboard base
#
# Sin recursos por ahora. Variables declaradas para no romper la llamada
# desde environments/staging.
