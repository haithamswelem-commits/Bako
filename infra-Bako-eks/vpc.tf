resource "aws_vpc" "bako" {
  cidr_block = "10.0.0.0/16"

  tags = {
    Name = "bako-vpc"
  }
}

resource "aws_subnet" "public_a" {
  vpc_id            = aws_vpc.bako.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "eu-north-1a"

  tags = {
    Name = "bako-public-a"
  }
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.bako.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "eu-north-1a"

  tags = {
    Name = "bako-private-a"
  }
}

resource "aws_subnet" "public_b" {
  vpc_id            = aws_vpc.bako.id
  cidr_block        = "10.0.3.0/24"
  availability_zone = "eu-north-1b"

  tags = {
    Name = "bako-public-b"
  }
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.bako.id
  cidr_block        = "10.0.4.0/24"
  availability_zone = "eu-north-1b"

  tags = {
    Name = "bako-private-b"
  }
}