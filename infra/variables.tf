# Conventions for every file in infra/ (main.tf, outputs.tf, ...):
#   - Resource names are "${var.name_prefix}-<role>" (e.g. "${var.name_prefix}-rg").
#     The ACR name allows alphanumerics only: replace(var.name_prefix, "-", "") + "acr".
#   - Every resource that supports tags sets `tags = var.tags`.
#   - No secrets in defaults: secret variables are `sensitive` and have no default.
#   - No hard-coded IDs (subscription, tenant, ...); take them from variables.
#   - Variable names mirror the app's env vars (app/core/config.py, .env.example).

variable "subscription_id" {
  description = "Azure subscription ID to deploy into."
  type        = string
}

variable "name_prefix" {
  description = "Prefix for all resource names. Lowercase letters, digits and hyphens."
  type        = string
  default     = "equitysplitter"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,30}$", var.name_prefix))
    error_message = "name_prefix must be 3-30 characters of lowercase letters, digits or hyphens."
  }
}

variable "location" {
  description = "Azure region for all resources."
  type        = string
  default     = "eastus2" # eastus is restricted for Postgres Flexible Server on this subscription
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default = {
    app = "equitysplitter"
  }
}

# --- PostgreSQL Flexible Server ---

variable "postgres_admin_login" {
  description = "PostgreSQL administrator login."
  type        = string
  default     = "pgadmin"
}

variable "postgres_admin_password" {
  description = "PostgreSQL administrator password. Also used in the app's DATABASE_URL."
  type        = string
  sensitive   = true
}

variable "postgres_database_name" {
  description = "Name of the application database."
  type        = string
  default     = "equity_splitter"
}

# --- Container App ---

variable "image_tag" {
  description = "Tag of the app image in the ACR repository. Placeholder 'latest' until the first image is pushed."
  type        = string
  default     = "latest"
}

variable "container_port" {
  description = "Port uvicorn listens on in the container (scripts/entrypoint.sh)."
  type        = number
  default     = 8000
}

# --- App settings (env vars read by app/core/config.py) ---

variable "jwt_secret_seed" {
  description = "JWT_SECRET_SEED. Stored as a Container App secret."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.jwt_secret_seed) >= 32
    error_message = "jwt_secret_seed must be at least 32 characters."
  }
}

variable "jwt_exp_minutes" {
  description = "JWT_EXP_MINUTES (app default 10)."
  type        = number
  default     = 10
}

variable "jwt_rotation_days" {
  description = "JWT_ROTATION_DAYS (app default 30)."
  type        = number
  default     = 30
}

variable "trusted_proxy_hops" {
  description = "TRUSTED_PROXY_HOPS. 1 because Container Apps ingress is one proxy hop in front of the app."
  type        = number
  default     = 1
}
