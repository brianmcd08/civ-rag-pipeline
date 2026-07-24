terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "terraform"
    }
  }
}

variable "aws_region" {
  description = "Region for all resources. Bedrock model access was granted here."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name prefix on every resource, so they group together in the console."
  type        = string
  default     = "civ-rag"
}

variable "bedrock_model_id" {
  description = "Inference profile ID handed to ChatBedrockConverse at runtime."
  type        = string
  default     = "global.anthropic.claude-sonnet-4-6"
}

variable "database_url" {
  description = "Neon pooled connection string for the LangGraph checkpointer."
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "Embeddings stay on OpenAI regardless of LLM_PROVIDER."
  type        = string
  sensitive   = true
}

variable "pinecone_api_key" {
  type      = string
  sensitive = true
}

variable "pinecone_index_name_v2" {
  type    = string
  default = "civ6-bbg-v2"
}