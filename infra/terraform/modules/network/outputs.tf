output "vpc_id" {
  description = "ID de la VPC."
  value       = aws_vpc.this.id
}

output "vpc_cidr" {
  description = "CIDR de la VPC."
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  description = "IDs de las subnets públicas."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs de las subnets privadas."
  value       = aws_subnet.private[*].id
}

output "nat_gateway_ids" {
  description = "IDs de las NAT gateways (vacío si NAT deshabilitada)."
  value       = aws_nat_gateway.this[*].id
}

output "public_route_table_id" {
  description = "ID de la route table pública."
  value       = aws_route_table.public.id
}

output "private_route_table_ids" {
  description = "IDs de las route tables privadas."
  value       = aws_route_table.private[*].id
}
