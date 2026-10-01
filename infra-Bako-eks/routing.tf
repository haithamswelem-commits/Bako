resource "aws_internet_gateway" "bako" {
  vpc_id = aws_vpc.bako.id

  tags = {
    Name = "bako-igw"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.bako.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.bako.id
  }

  tags = {
    Name = "bako-public-rt"
  }
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name = "bako-nat-eip"
  }
}

resource "aws_nat_gateway" "bako" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public_a.id

  depends_on = [aws_internet_gateway.bako]

  tags = {
    Name = "bako-nat"
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.bako.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.bako.id
  }

  tags = {
    Name = "bako-private-rt"
  }
}

resource "aws_route_table_association" "private_a" {
  subnet_id      = aws_subnet.private_a.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_b" {
  subnet_id      = aws_subnet.private_b.id
  route_table_id = aws_route_table.private.id
}