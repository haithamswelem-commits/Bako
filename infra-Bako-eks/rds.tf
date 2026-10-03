resource "aws_db_subnet_group" "bako" {
  name       = "bako-db-subnet-group"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]

  tags = {
    Name = "bako-db-subnet-group"
  }
}

resource "aws_security_group" "rds" {
  name        = "bako-rds-sg"
  description = "Allow Postgres access from the EKS cluster only"
  vpc_id      = aws_vpc.bako.id

  ingress {
    description     = "Postgres from EKS nodes"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_eks_cluster.bako.vpc_config[0].cluster_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "bako-rds-sg"
  }
}

resource "aws_db_instance" "bako" {
  identifier     = "bako-db"
  engine         = "postgres"
  engine_version = "16.15"
  instance_class = "db.t4g.micro"

  allocated_storage = 20
  storage_type      = "gp3"

  db_name                      = "bako"
  username                     = "bako_admin"
  manage_master_user_password  = true

  db_subnet_group_name   = aws_db_subnet_group.bako.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  publicly_accessible = false
  multi_az            = false
  skip_final_snapshot = true

  tags = {
    Name = "bako-db"
  }
}

output "rds_endpoint" {
  value = aws_db_instance.bako.address
}

output "rds_master_user_secret_arn" {
  value = aws_db_instance.bako.master_user_secret[0].secret_arn
}

output "rds_secret_arn" {
  value = aws_db_instance.bako.master_user_secret[0].secret_arn
}