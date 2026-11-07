# Conventions for every file in infra/ (main.tf, outputs.tf, ...):
#   - Resource names are "${var.name_prefix}-<role>" (e.g. "${var.name_prefix}-env"). The
#     resource group is the exception: it already exists (var.resource_group_name, data source).
#     The ACR name allows alphanumerics only: replace(var.name_prefix, "-", "") + "acr".
#   - Every resource that supports tags sets `tags = var.tags`.
#   - Secrets are never inputs: they are generated (random_password, alphanumeric only)
#     and stored in Key Vault. Terraform state therefore contains them; protect the state.
#   - No hard-coded IDs (subscription, tenant, ...); take them from variables or from the
#     az CLI login (azuread provider, data.azurerm_client_config).
#   - Variable names mirror the app's env vars (app/core/config.py, .env.example).
#
# Interface contract between files (resource addresses other files may rely on):
#   identity.tf  random_password.postgres_admin, random_password.jwt_secret_seed
#                (result = the secret; replaces the removed variables
#                postgres_admin_password / jwt_secret_seed),
#                azurerm_key_vault.main (RBAC auth; secrets for both generated values;
#                applying identity = Key Vault Secrets Officer),
#                azuread_application.github, azuread_service_principal.github,
#                azuread_application_federated_identity_credential.github
#                (subject "repo:${var.github_repository}:ref:refs/heads/master"),
#                AcrPush on azurerm_container_registry.main,
#                Contributor on azurerm_container_app.api only.

variable "subscription_id" {
  description = "Azure subscription ID to deploy into."
  type        = string
}

variable "github_repository" {
  description = "GitHub repository (owner/name) allowed to deploy via OIDC federation from its master branch."
  type        = string
  default     = "pivoteer556/EquitySplitter"

  validation {
    condition     = can(regex("^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$", var.github_repository))
    error_message = "github_repository must look like owner/name."
  }
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

variable "resource_group_name" {
  description = "Name of the EXISTING resource group to deploy into (not created by Terraform)."
  type        = string
  default     = "Equity-Splitter-Dev"
}

variable "location" {
  description = "Azure region for all resources."
  type        = string
  default     = "eastus2" # eastus is restricted for Postgres Flexible Server on this subscription
}

variable "postgres_location" {
  description = "Region for the PostgreSQL server only; null means use var.location. Set it when the server size is not offered to this subscription in var.location."
  type        = string
  default     = null
}

variable "postgres_server_name" {
  description = "Name of the PostgreSQL server; null means \"<name_prefix>-pg\". Set it to work around a stuck leftover server holding the default name."
  type        = string
  default     = null
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

variable "postgres_database_name" {
  description = "Name of the application database."
  type        = string
  default     = "equity_splitter"
}

# --- Container App ---

# --- App settings (env vars read by app/core/config.py) ---

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
